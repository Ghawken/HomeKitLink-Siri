"""SRTP encryption for AES_CM_128_HMAC_SHA1_80."""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_UINT32_BE = struct.Struct("!I")
_UINT16_BE = struct.Struct("!H")
_UINT16_UINT32_BE = struct.Struct("!HI")
_MIN_RTP_HEADER_SIZE = 12
_SEQ_ROLLOVER_THRESHOLD = 0x8000
_AUTH_TAG_LENGTH = 10


def _derive_srtp_key(
    master_key: bytes, master_salt: bytes, label: int, length: int
) -> bytes:
    """Derive an SRTP session key per RFC 3711 Section 4.3.1."""
    key_id = label << 48
    salt_int = int.from_bytes(master_salt, "big")
    x = key_id ^ salt_int
    iv = x.to_bytes(14, "big") + b"\x00\x00"

    cipher = Cipher(algorithms.AES(master_key), modes.CTR(iv))
    encryptor = cipher.encryptor()
    return (encryptor.update(b"\x00" * length) + encryptor.finalize())[:length]


class SRTPContext:
    """SRTP encryption context for AES_CM_128_HMAC_SHA1_80."""

    def __init__(self, master_key_b64: str) -> None:
        """Initialize from a base64-encoded master key (16 key + 14 salt)."""
        key_material = base64.b64decode(master_key_b64)
        if len(key_material) < 30:
            msg = (
                f"SRTP key material must be at least 30 bytes, got {len(key_material)}"
            )
            raise ValueError(msg)
        master_key = key_material[:16]
        master_salt = key_material[16:30]

        self._session_key = _derive_srtp_key(master_key, master_salt, 0, 16)
        self._session_auth_key = _derive_srtp_key(master_key, master_salt, 1, 20)
        self._session_salt = _derive_srtp_key(master_key, master_salt, 2, 14)
        self._roc: int = 0
        self._last_seq: int = 0

        # SRTCP keys (RFC 3711 Section 4.3.2, labels 3-5)
        self._rtcp_key = _derive_srtp_key(master_key, master_salt, 3, 16)
        self._rtcp_auth_key = _derive_srtp_key(master_key, master_salt, 4, 20)
        self._rtcp_salt = _derive_srtp_key(master_key, master_salt, 5, 14)
        self._rtcp_index: int = 0

    def encrypt(self, rtp_packet: bytes) -> bytes:
        """Encrypt an RTP packet to produce an SRTP packet."""
        header_len = _MIN_RTP_HEADER_SIZE
        cc = rtp_packet[0] & 0x0F
        header_len += cc * 4
        if (rtp_packet[0] >> 4) & 1:  # Extension bit
            ext_length = _UINT16_BE.unpack_from(rtp_packet, header_len + 2)[0]
            header_len += 4 + ext_length * 4

        header = rtp_packet[:header_len]
        payload = rtp_packet[header_len:]

        ssrc = _UINT32_BE.unpack_from(rtp_packet, 8)[0]
        seq = _UINT16_BE.unpack_from(rtp_packet, 2)[0]

        if seq < self._last_seq and (self._last_seq - seq) > _SEQ_ROLLOVER_THRESHOLD:
            self._roc += 1
        self._last_seq = seq

        packet_index = (self._roc << 16) | seq

        iv = bytearray(16)
        _UINT32_BE.pack_into(iv, 4, ssrc)
        _UINT16_UINT32_BE.pack_into(
            iv, 8, packet_index >> 32, packet_index & 0xFFFFFFFF
        )
        for i in range(14):
            iv[i] ^= self._session_salt[i]

        cipher = Cipher(algorithms.AES(self._session_key), modes.CTR(bytes(iv)))
        encryptor = cipher.encryptor()
        encrypted_payload = encryptor.update(payload) + encryptor.finalize()

        srtp_packet = header + encrypted_payload
        auth_data = srtp_packet + _UINT32_BE.pack(self._roc)
        auth_tag = hmac.new(self._session_auth_key, auth_data, hashlib.sha1).digest()[
            :_AUTH_TAG_LENGTH
        ]

        return srtp_packet + auth_tag

    def encrypt_rtcp(self, rtcp_packet: bytes) -> bytes:
        """Encrypt an RTCP (compound) packet to produce an SRTCP packet (RFC 3711 Section 3.4)."""
        index = self._rtcp_index
        self._rtcp_index = (self._rtcp_index + 1) & 0x7FFFFFFF

        ssrc = _UINT32_BE.unpack_from(rtcp_packet, 4)[0]
        iv = bytearray(16)
        _UINT32_BE.pack_into(iv, 4, ssrc)
        _UINT32_BE.pack_into(iv, 10, index)
        for i in range(14):
            iv[i] ^= self._rtcp_salt[i]

        cipher = Cipher(algorithms.AES(self._rtcp_key), modes.CTR(bytes(iv)))
        encryptor = cipher.encryptor()
        encrypted = rtcp_packet[:8] + encryptor.update(rtcp_packet[8:]) + encryptor.finalize()

        srtcp_packet = encrypted + _UINT32_BE.pack(0x80000000 | index)  # E flag + SRTCP index
        auth_tag = hmac.new(self._rtcp_auth_key, srtcp_packet, hashlib.sha1).digest()[:_AUTH_TAG_LENGTH]
        return srtcp_packet + auth_tag


class SRTPDecryptContext:
    """SRTP decryption for AES_CM_128_HMAC_SHA1_80 (HomeKit two-way audio, from PR #42).

    HomeKit uses the same master key/salt for both directions of a session (pyhap answers
    Setup Endpoints with the controller's own key), so the Home app's microphone packets
    decrypt with the session's audio key, under their own SSRC.
    """

    def __init__(self, master_key_b64: str) -> None:
        key_material = base64.b64decode(master_key_b64)
        if len(key_material) < 30:
            raise ValueError("SRTP key material must be at least 30 bytes")
        master_key = key_material[:16]
        master_salt = key_material[16:30]
        self._session_key = _derive_srtp_key(master_key, master_salt, 0, 16)
        self._session_auth_key = _derive_srtp_key(master_key, master_salt, 1, 20)
        self._session_salt = _derive_srtp_key(master_key, master_salt, 2, 14)
        self._roc: int = 0
        self._last_seq: int | None = None

    def decrypt(self, srtp_packet: bytes) -> bytes | None:
        """Return the plain RTP packet, or None if too short or authentication fails."""
        if len(srtp_packet) < _MIN_RTP_HEADER_SIZE + _AUTH_TAG_LENGTH:
            return None
        header_len = _MIN_RTP_HEADER_SIZE + (srtp_packet[0] & 0x0F) * 4
        if (srtp_packet[0] >> 4) & 1:
            if len(srtp_packet) < header_len + 4:
                return None
            ext_length = _UINT16_BE.unpack_from(srtp_packet, header_len + 2)[0]
            header_len += 4 + ext_length * 4
        body = srtp_packet[:-_AUTH_TAG_LENGTH]
        tag = srtp_packet[-_AUTH_TAG_LENGTH:]
        if len(body) < header_len:
            return None

        seq = _UINT16_BE.unpack_from(srtp_packet, 2)[0]
        ssrc = _UINT32_BE.unpack_from(srtp_packet, 8)[0]
        # Estimate the rollover counter (RFC 3711 3.3.1, simplified)
        roc = self._roc
        if self._last_seq is not None:
            if seq < self._last_seq and (self._last_seq - seq) > _SEQ_ROLLOVER_THRESHOLD:
                roc = self._roc + 1
            elif seq > self._last_seq and (seq - self._last_seq) > _SEQ_ROLLOVER_THRESHOLD and self._roc > 0:
                roc = self._roc - 1

        expected = hmac.new(self._session_auth_key, body + _UINT32_BE.pack(roc), hashlib.sha1).digest()[:_AUTH_TAG_LENGTH]
        if not hmac.compare_digest(expected, tag):
            return None
        if roc >= self._roc and (self._last_seq is None or roc > self._roc or seq > self._last_seq):
            self._roc = roc
            self._last_seq = seq

        packet_index = (roc << 16) | seq
        iv = bytearray(16)
        _UINT32_BE.pack_into(iv, 4, ssrc)
        _UINT16_UINT32_BE.pack_into(iv, 8, packet_index >> 32, packet_index & 0xFFFFFFFF)
        for i in range(14):
            iv[i] ^= self._session_salt[i]
        decryptor = Cipher(algorithms.AES(self._session_key), modes.CTR(bytes(iv))).decryptor()
        payload = decryptor.update(body[header_len:]) + decryptor.finalize()
        return body[:header_len] + payload
