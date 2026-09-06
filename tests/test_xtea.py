"""XTEA cipher tests.

No known (plaintext, ciphertext) pair from real hardware exists in this
project's research (see cipher/xtea.py docstring) — these tests check internal
self-consistency (round-tripping) and the documented key/address-tweak
behavior, not correctness against a real BLHeli32 ESC.
"""

import os

import pytest

from blheli32proxy.cipher import xtea


def test_decrypt_encrypt_round_trip_zero_plaintext():
    plaintext = bytes(xtea.PLAINTEXT_SIZE)
    discarded = bytes(64)
    ciphertext = xtea.encrypt_setup_block(plaintext, discarded_low_words=discarded)
    assert len(ciphertext) == xtea.SETUP_BLOCK_SIZE
    recovered = xtea.decrypt_setup_block(ciphertext)
    assert recovered == plaintext


def test_decrypt_encrypt_round_trip_random_plaintext():
    plaintext = os.urandom(xtea.PLAINTEXT_SIZE)
    discarded = os.urandom(64)
    ciphertext = xtea.encrypt_setup_block(plaintext, discarded_low_words=discarded)
    recovered = xtea.decrypt_setup_block(ciphertext)
    assert recovered == plaintext


def test_round_trip_with_test_firmware_key():
    plaintext = os.urandom(xtea.PLAINTEXT_SIZE)
    ciphertext = xtea.encrypt_setup_block(plaintext, key=xtea.TEST_FIRMWARE_KEY)
    recovered = xtea.decrypt_setup_block(ciphertext, key=xtea.TEST_FIRMWARE_KEY)
    assert recovered == plaintext


def test_round_trip_with_alternate_address_tweak():
    plaintext = os.urandom(xtea.PLAINTEXT_SIZE)
    ciphertext = xtea.encrypt_setup_block(plaintext, address=0xF800)
    recovered = xtea.decrypt_setup_block(ciphertext, address=0xF800)
    assert recovered == plaintext


def test_wrong_key_does_not_decrypt_correctly():
    plaintext = os.urandom(xtea.PLAINTEXT_SIZE)
    ciphertext = xtea.encrypt_setup_block(plaintext, key=xtea.PRODUCTION_KEY)
    wrong = xtea.decrypt_setup_block(ciphertext, key=xtea.TEST_FIRMWARE_KEY)
    assert wrong != plaintext


def test_wrong_address_tweak_does_not_decrypt_correctly():
    plaintext = os.urandom(xtea.PLAINTEXT_SIZE)
    ciphertext = xtea.encrypt_setup_block(plaintext, address=0x7C00)
    wrong = xtea.decrypt_setup_block(ciphertext, address=0xF800)
    assert wrong != plaintext


def test_decrypt_rejects_wrong_length():
    with pytest.raises(ValueError):
        xtea.decrypt_setup_block(b"\x00" * 100)


def test_encrypt_rejects_wrong_length():
    with pytest.raises(ValueError):
        xtea.encrypt_setup_block(b"\x00" * 10)


def test_encrypt_rejects_wrong_discarded_length():
    with pytest.raises(ValueError):
        xtea.encrypt_setup_block(bytes(xtea.PLAINTEXT_SIZE), discarded_low_words=b"\x00")


def test_different_discarded_bytes_change_ciphertext_but_not_recovered_plaintext():
    plaintext = os.urandom(xtea.PLAINTEXT_SIZE)
    c1 = xtea.encrypt_setup_block(plaintext, discarded_low_words=bytes(64))
    c2 = xtea.encrypt_setup_block(plaintext, discarded_low_words=os.urandom(64))
    assert c1 != c2  # supports the "discarded bytes act as a nonce" theory
    assert xtea.decrypt_setup_block(c1) == xtea.decrypt_setup_block(c2) == plaintext
