__version__ = "0.0.4"

# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import os
import typing
from typing import Union

from cryptography import exceptions
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

_ENCRYPT = 1
_DECRYPT = 0


class ChaCha20Poly1305Reusable(ChaCha20Poly1305):
    """A reuseable version of ChaCha20Poly1305.

    This is modified version of ChaCha20Poly1305 that does not recreate
    the underlying ctx each time. It is not thread-safe and should not
    only be called in the thread it was created.

    The primary use case for this code is HAP streams.
    """

    _MAX_SIZE = 2**32
    _KEY_LEN = 32
    _NONCE_LEN = 12
    _TAG_LENGTH = 16

    def __init__(self, key: Union[bytes, bytearray]) -> None:
        if not backend.aead_cipher_supported(self):
            raise exceptions.UnsupportedAlgorithm(
                "ChaCha20Poly1305Reusable is not supported by this version of OpenSSL",
                exceptions._Reasons.UNSUPPORTED_CIPHER,
            )

        if not isinstance(key, (bytes, bytearray)):
            raise TypeError("key must be bytes or bytearay")

        if len(key) != self._KEY_LEN:
            raise ValueError("ChaCha20Poly1305Reusable key must be 32 bytes.")

        self._cipher_name = b"chacha20-poly1305"
        self._key = key
        self._decrypt_ctx = None
        self._encrypt_ctx = None

    @classmethod
    def generate_key(cls) -> bytes:
        return os.urandom(ChaCha20Poly1305Reusable._KEY_LEN)

    def encrypt(
        self,
        nonce: Union[bytes, bytearray],
        data: bytes,
        associated_data: typing.Optional[bytes],
    ) -> bytes:
        if not self._encrypt_ctx:
            self._encrypt_ctx = _aead_setup_with_fixed_nonce_len(
                self._cipher_name,
                self._key,
                self._NONCE_LEN,
                _ENCRYPT,
            )

        if associated_data is None:
            associated_data = b""

        if len(data) > self._MAX_SIZE or len(associated_data) > self._MAX_SIZE:
            # This is OverflowError to match what cffi would raise
            raise OverflowError("Data or associated data too long. Max 2**32 bytes")

        self._check_params(nonce, data, associated_data)
        return _encrypt_with_fixed_nonce_len(
            self._encrypt_ctx,
            nonce,
            data,
            associated_data,
            self._TAG_LENGTH,
        )

    def decrypt(
        self,
        nonce: Union[bytes, bytearray],
        data: bytes,
        associated_data: typing.Optional[bytes],
    ) -> bytes:
        if not self._decrypt_ctx:
            self._decrypt_ctx = _aead_setup_with_fixed_nonce_len(
                self._cipher_name,
                self._key,
                self._NONCE_LEN,
                _DECRYPT,
            )

        if associated_data is None:
            associated_data = b""

        self._check_params(nonce, data, associated_data)
        return _decrypt_with_fixed_nonce_len(
            self._decrypt_ctx,
            nonce,
            data,
            associated_data,
            self._TAG_LENGTH,
        )

    def _check_params(
        self,
        nonce: Union[bytes, bytearray],
        data: bytes,
        associated_data: bytes,
    ) -> None:
        if not isinstance(nonce, (bytes, bytearray)):
            raise TypeError("Nonce must be bytes or bytearray")
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        if not isinstance(associated_data, bytes):
            raise TypeError("associated_data must be bytes")
        if len(nonce) != self._NONCE_LEN:
            raise ValueError("Nonce must be 12 bytes")


def _create_ctx():  # type: ignore[no-untyped-def]
    ctx = backend._lib.EVP_CIPHER_CTX_new()
    ctx = backend._ffi.gc(ctx, backend._lib.EVP_CIPHER_CTX_free)
    return ctx


def _set_cipher(ctx, cipher_name, operation):  # type: ignore[no-untyped-def]
    evp_cipher = backend._lib.EVP_get_cipherbyname(cipher_name)
    backend.openssl_assert(evp_cipher != backend._ffi.NULL)
    res = backend._lib.EVP_CipherInit_ex(
        ctx,
        evp_cipher,
        backend._ffi.NULL,
        backend._ffi.NULL,
        backend._ffi.NULL,
        int(operation == _ENCRYPT),
    )
    backend.openssl_assert(res != 0)


def _set_key_len(ctx, key_len):  # type: ignore[no-untyped-def]
    res = backend._lib.EVP_CIPHER_CTX_set_key_length(ctx, key_len)
    backend.openssl_assert(res != 0)


def _set_key(ctx, key, operation):  # type: ignore[no-untyped-def]
    key_ptr = backend._ffi.from_buffer(key)
    res = backend._lib.EVP_CipherInit_ex(
        ctx,
        backend._ffi.NULL,
        backend._ffi.NULL,
        key_ptr,
        backend._ffi.NULL,
        int(operation == _ENCRYPT),
    )
    backend.openssl_assert(res != 0)


def _set_decrypt_tag(ctx, tag):  # type: ignore[no-untyped-def]
    res = backend._lib.EVP_CIPHER_CTX_ctrl(
        ctx, backend._lib.EVP_CTRL_AEAD_SET_TAG, len(tag), tag
    )
    backend.openssl_assert(res != 0)


def _set_nonce_len(ctx, nonce_len):  # type: ignore[no-untyped-def]
    res = backend._lib.EVP_CIPHER_CTX_ctrl(
        ctx,
        backend._lib.EVP_CTRL_AEAD_SET_IVLEN,
        nonce_len,
        backend._ffi.NULL,
    )
    backend.openssl_assert(res != 0)


def _set_nonce(ctx, nonce, operation):  # type: ignore[no-untyped-def]
    nonce_ptr = backend._ffi.from_buffer(nonce)
    res = backend._lib.EVP_CipherInit_ex(
        ctx,
        backend._ffi.NULL,
        backend._ffi.NULL,
        backend._ffi.NULL,
        nonce_ptr,
        int(operation == _ENCRYPT),
    )
    backend.openssl_assert(res != 0)


def _aead_setup_with_fixed_nonce_len(cipher_name, key, nonce_len, operation):  # type: ignore[no-untyped-def]
    ctx = _create_ctx()
    _set_cipher(ctx, cipher_name, operation)
    _set_key_len(ctx, len(key))
    _set_key(ctx, key, operation)
    _set_nonce_len(ctx, nonce_len)
    return ctx


def _process_aad(ctx, associated_data):  # type: ignore[no-untyped-def]
    outlen = backend._ffi.new("int *")
    res = backend._lib.EVP_CipherUpdate(
        ctx, backend._ffi.NULL, outlen, associated_data, len(associated_data)
    )
    backend.openssl_assert(res != 0)


def _process_data(ctx, data):  # type: ignore[no-untyped-def]
    outlen = backend._ffi.new("int *")
    buf = backend._ffi.new("unsigned char[]", len(data))
    res = backend._lib.EVP_CipherUpdate(ctx, buf, outlen, data, len(data))
    backend.openssl_assert(res != 0)
    return backend._ffi.buffer(buf, outlen[0])[:]


def _encrypt_with_fixed_nonce_len(ctx, nonce, data, associated_data, tag_length):  # type: ignore[no-untyped-def]
    _set_nonce(ctx, nonce, _ENCRYPT)
    return _encrypt_data(ctx, data, associated_data, tag_length)


def _encrypt_data(ctx, data, associated_data, tag_length):  # type: ignore[no-untyped-def]
    _process_aad(ctx, associated_data)
    processed_data = _process_data(ctx, data)
    outlen = backend._ffi.new("int *")
    res = backend._lib.EVP_CipherFinal_ex(ctx, backend._ffi.NULL, outlen)
    backend.openssl_assert(res != 0)
    backend.openssl_assert(outlen[0] == 0)
    tag_buf = backend._ffi.new("unsigned char[]", tag_length)
    res = backend._lib.EVP_CIPHER_CTX_ctrl(
        ctx, backend._lib.EVP_CTRL_AEAD_GET_TAG, tag_length, tag_buf
    )
    backend.openssl_assert(res != 0)
    tag = backend._ffi.buffer(tag_buf)[:]

    return processed_data + tag


def _tag_from_data(data, tag_length):  # type: ignore[no-untyped-def]
    if len(data) < tag_length:
        raise InvalidTag
    return data[-tag_length:]


def _decrypt_with_fixed_nonce_len(ctx, nonce, data, associated_data, tag_length):  # type: ignore[no-untyped-def]
    tag = _tag_from_data(data, tag_length)
    data = data[:-tag_length]
    _set_nonce(ctx, nonce, _DECRYPT)
    _set_decrypt_tag(ctx, tag)
    return _decrypt_data(ctx, data, associated_data)


def _decrypt_data(ctx, data, associated_data):  # type: ignore[no-untyped-def]
    _process_aad(ctx, associated_data)
    processed_data = _process_data(ctx, data)
    outlen = backend._ffi.new("int *")
    res = backend._lib.EVP_CipherFinal_ex(ctx, backend._ffi.NULL, outlen)
    if res == 0:
        backend._consume_errors()
        raise InvalidTag

    return processed_data
