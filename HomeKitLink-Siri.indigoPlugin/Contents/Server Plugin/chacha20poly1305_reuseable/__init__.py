__version__ = "0.4.2"

# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import os
import typing
from functools import partial
from typing import Optional, Union

from cryptography import exceptions
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

openssl_failure = partial(backend.openssl_assert, False)
lib = backend._lib
ffi = backend._ffi

EVP_CIPHER_CTX_ctrl = lib.EVP_CIPHER_CTX_ctrl
EVP_CTRL_AEAD_SET_TAG = lib.EVP_CTRL_AEAD_SET_TAG
EVP_CTRL_AEAD_SET_IVLEN = lib.EVP_CTRL_AEAD_SET_IVLEN
EVP_CipherInit_ex = lib.EVP_CipherInit_ex
EVP_CIPHER_CTX_new = lib.EVP_CIPHER_CTX_new
EVP_CIPHER_CTX_free = lib.EVP_CIPHER_CTX_free
EVP_get_cipherbyname = lib.EVP_get_cipherbyname
EVP_CIPHER_CTX_set_key_length = lib.EVP_CIPHER_CTX_set_key_length
EVP_CipherUpdate = lib.EVP_CipherUpdate
EVP_CipherFinal_ex = lib.EVP_CipherFinal_ex
EVP_CTRL_AEAD_GET_TAG = lib.EVP_CTRL_AEAD_GET_TAG

ffi_from_buffer = ffi.from_buffer
ffi_gc = ffi.gc
ffi_new = ffi.new
ffi_buffer = ffi.buffer

NULL = ffi.NULL

_ENCRYPT = 1
_DECRYPT = 0

_bytes = bytes
_int = int


def _check_params(
    nonce_len: _int,
    nonce: Union[_bytes, bytearray],
    data: _bytes,
    associated_data: _bytes,
) -> None:
    if not isinstance(nonce, (bytes, bytearray)):
        raise TypeError("Nonce must be bytes or bytearray")
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if not isinstance(associated_data, bytes):
        raise TypeError("associated_data must be bytes")
    if len(nonce) != nonce_len:
        raise ValueError("Nonce must be 12 bytes")


MAX_SIZE = 2**32
KEY_LEN = 32
NONCE_LEN = 12
NONCE_LEN_UINT = NONCE_LEN
TAG_LENGTH = 16
CIPHER_NAME = b"chacha20-poly1305"


class ChaCha20Poly1305Reusable(ChaCha20Poly1305):
    """A reuseable version of ChaCha20Poly1305.

    This is modified version of ChaCha20Poly1305 that does not recreate
    the underlying ctx each time. It is not thread-safe and should not
    only be called in the thread it was created.

    The primary use case for this code is HAP streams.
    """

    def __init__(self, key: Union[_bytes, bytearray]) -> None:
        if not backend.aead_cipher_supported(self):
            raise exceptions.UnsupportedAlgorithm(
                "ChaCha20Poly1305Reusable is not supported by this version of OpenSSL",
                exceptions._Reasons.UNSUPPORTED_CIPHER,
            )

        if not isinstance(key, (bytes, bytearray)):
            raise TypeError("key must be bytes or bytearay")

        if len(key) != KEY_LEN:
            raise ValueError("ChaCha20Poly1305Reusable key must be 32 bytes.")

        self._key = key
        self._decrypt_ctx: Optional[object] = None
        self._encrypt_ctx: Optional[object] = None

    @classmethod
    def generate_key(cls) -> _bytes:
        return os.urandom(KEY_LEN)

    def encrypt(
        self,
        nonce: Union[_bytes, bytearray],
        data: _bytes,
        associated_data: typing.Optional[bytes],
    ) -> bytes:
        encrypt_ctx = self._encrypt_ctx
        if not encrypt_ctx:
            encrypt_ctx = _aead_setup_with_fixed_nonce_len(
                CIPHER_NAME,
                self._key,
                NONCE_LEN,
                _ENCRYPT,
            )
            self._encrypt_ctx = encrypt_ctx

        if associated_data is None:
            associated_data = b""

        if len(data) > MAX_SIZE or len(associated_data) > MAX_SIZE:
            # This is OverflowError to match what cffi would raise
            raise OverflowError("Data or associated data too long. Max 2**32 bytes")

        _check_params(NONCE_LEN_UINT, nonce, data, associated_data)
        return _encrypt_with_fixed_nonce_len(
            encrypt_ctx,
            nonce,
            data,
            associated_data,
            TAG_LENGTH,
        )

    def decrypt(
        self,
        nonce: Union[_bytes, bytearray],
        data: _bytes,
        associated_data: typing.Optional[_bytes],
    ) -> bytes:
        decrypt_ctx = self._decrypt_ctx
        if not decrypt_ctx:
            decrypt_ctx = _aead_setup_with_fixed_nonce_len(
                CIPHER_NAME,
                self._key,
                NONCE_LEN,
                _DECRYPT,
            )
            self._decrypt_ctx = decrypt_ctx

        if associated_data is None:
            associated_data = b""

        _check_params(NONCE_LEN_UINT, nonce, data, associated_data)
        return _decrypt_with_fixed_nonce_len(
            decrypt_ctx,
            nonce,
            data,
            associated_data,
            TAG_LENGTH,
        )


def _set_nonce(ctx: object, nonce: Union[_bytes, bytearray], operation: _int) -> None:
    nonce_ptr = ffi_from_buffer(nonce)
    res = EVP_CipherInit_ex(
        ctx,
        NULL,
        NULL,
        NULL,
        nonce_ptr,
        int(operation == _ENCRYPT),
    )
    openssl_assert(res != 0)


def _aead_setup_with_fixed_nonce_len(
    cipher_name: _bytes, key: Union[_bytes, bytearray], nonce_len: _int, operation: _int
) -> object:
    # create the ctx
    ctx = EVP_CIPHER_CTX_new()
    ctx = ffi_gc(ctx, EVP_CIPHER_CTX_free)
    # set the cipher
    evp_cipher = EVP_get_cipherbyname(cipher_name)
    openssl_assert(evp_cipher != NULL)
    res = EVP_CipherInit_ex(
        ctx,
        evp_cipher,
        NULL,
        NULL,
        NULL,
        int(operation == _ENCRYPT),
    )
    openssl_assert(res != 0)
    # Set the key length
    res = EVP_CIPHER_CTX_set_key_length(ctx, len(key))
    openssl_assert(res != 0)
    # Set the key
    res = EVP_CipherInit_ex(
        ctx,
        NULL,
        NULL,
        ffi_from_buffer(key),
        NULL,
        int(operation == _ENCRYPT),
    )
    openssl_assert(res != 0)
    # set nonce length
    res = EVP_CIPHER_CTX_ctrl(
        ctx,
        EVP_CTRL_AEAD_SET_IVLEN,
        nonce_len,
        NULL,
    )
    openssl_assert(res != 0)
    return ctx


def _process_aad(ctx: object, associated_data: _bytes) -> None:
    outlen = ffi_new("int *")
    res = EVP_CipherUpdate(ctx, NULL, outlen, associated_data, len(associated_data))
    openssl_assert(res != 0)


def _process_data(ctx: object, data: _bytes) -> _bytes:
    outlen = ffi_new("int *")
    data_len = len(data)
    buf = ffi_new("unsigned char[]", data_len)
    res = EVP_CipherUpdate(ctx, buf, outlen, data, data_len)
    openssl_assert(res != 0)
    return ffi_buffer(buf, outlen[0])[:]


def _encrypt_with_fixed_nonce_len(
    ctx: object,
    nonce: Union[_bytes, bytearray],
    data: _bytes,
    associated_data: _bytes,
    tag_length: _int,
) -> bytes:
    _set_nonce(ctx, nonce, _ENCRYPT)
    return _encrypt_data(ctx, data, associated_data, tag_length)


def _encrypt_data(
    ctx: object, data: _bytes, associated_data: _bytes, tag_length: _int
) -> bytes:
    _process_aad(ctx, associated_data)
    processed_data = _process_data(ctx, data)
    outlen = ffi_new("int *")
    res = EVP_CipherFinal_ex(ctx, NULL, outlen)
    openssl_assert(res != 0)
    openssl_assert(outlen[0] == 0)
    tag_buf = ffi_new("unsigned char[]", tag_length)
    res = EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_GET_TAG, tag_length, tag_buf)
    openssl_assert(res != 0)
    tag = ffi_buffer(tag_buf)[:]
    return processed_data + tag


def _decrypt_with_fixed_nonce_len(
    ctx: object,
    nonce: Union[_bytes, bytearray],
    data: _bytes,
    associated_data: _bytes,
    tag_length: _int,
) -> bytes:
    if len(data) < tag_length:
        raise InvalidTag
    negative_tag_length = -tag_length
    tag = data[negative_tag_length:]
    data = data[:negative_tag_length]
    _set_nonce(ctx, nonce, _DECRYPT)
    # set the decrypted tag
    res = EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_TAG, tag_length, tag)
    openssl_assert(res != 0)
    return _decrypt_data(ctx, data, associated_data)


def _decrypt_data(ctx: object, data: _bytes, associated_data: _bytes) -> _bytes:
    _process_aad(ctx, associated_data)
    processed_data = _process_data(ctx, data)
    outlen = ffi_new("int *")
    res = EVP_CipherFinal_ex(ctx, NULL, outlen)
    if res == 0:
        backend._consume_errors()
        raise InvalidTag

    return processed_data


def openssl_assert(ok: bool) -> None:
    """Raise an exception if OpenSSL returns an error."""
    if not ok:
        openssl_failure()
