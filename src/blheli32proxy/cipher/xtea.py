"""XTEA cipher for the BLHeli32 256-byte Setup/config block.

Ported directly from the working reference decrypt script in
research/notes/BLHeliSuite32-Reverse2.en.md — a hand reverse-engineered algorithm,
not a textbook XTEA implementation, so the exact operation order (including the
asymmetric key-index bit-extraction between the two halves of each round) is
preserved deliberately rather than "cleaned up" into a standard form that might
silently behave differently.

IMPORTANT — NOT VERIFIED AGAINST LIVE HARDWARE: this project's research never
captured a (known plaintext, known ciphertext) pair encrypted with the same key,
so this implementation is only self-consistency-tested (encrypt/decrypt round
trips), not validated against a real BLHeli32 ESC. See PLAN.md §5 phase 1 —
verify this against a real captured Setup block before trusting it for anything
beyond experimentation.

Only relevant to reading/writing post-flash *configuration* — flashing a firmware
image needs none of this (see protocol/client.py's module docstring, and PLAN.md
§3.3: "FLASH data encrypted: False").
"""

from __future__ import annotations

DELTA = 0x9E3779B9
ROUNDS = 32
MASK32 = 0xFFFFFFFF

# Two known 128-bit keys, each as 4 32-bit words, from BLHeliSuite32-Reverse2.en.md
# and BLHeliSuite32-Reverse4.en.md.
PRODUCTION_KEY = (0x318234B4, 0x29A1FA54, 0x9E81C901, 0x81FBC617)
TEST_FIRMWARE_KEY = (0x315534B4, 0x20A5F454, 0x1E88C901, 0x71F1C617)

SETUP_BLOCK_SIZE = 256
PLAINTEXT_SIZE = 192  # 32 blocks x 6 kept bytes/block
BLOCK_SIZE = 8
KEPT_BYTES_PER_BLOCK = 6
DISCARDED_BYTES_PER_BLOCK = 2


def _key_words(key: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Reorder (K0, K1, K2, K3) into the indexing the reference disassembly uses:
    index 0 -> K3, 1 -> K2, 2 -> K1, 3 -> K0 (see module docstring)."""
    k0, k1, k2, k3 = key
    return (k3, k2, k1, k0)


def _decrypt_block(v0: int, v1: int, key: tuple[int, int, int, int], tweak: int) -> tuple[int, int]:
    words = _key_words(key)
    total_sum = (DELTA * ROUNDS) & MASK32
    for _ in range(ROUNDS):
        mx0 = (((v0 << 4) ^ (v0 >> 5)) + v0) & MASK32
        idx0 = (total_sum >> 11) & 0x3
        mx0 = (mx0 ^ ((words[idx0] + total_sum + tweak) & MASK32)) & MASK32
        v1 = (v1 - mx0) & MASK32
        total_sum = (total_sum - DELTA) & MASK32

        mx1 = (((v1 << 4) ^ (v1 >> 5)) + v1) & MASK32
        idx1 = total_sum & 0x3
        mx1 = (mx1 ^ ((words[idx1] + total_sum + tweak) & MASK32)) & MASK32
        v0 = (v0 - mx1) & MASK32
    return v0, v1


def _encrypt_block(v0: int, v1: int, key: tuple[int, int, int, int], tweak: int) -> tuple[int, int]:
    """Inverse of _decrypt_block.

    One decrypt round (given sum_old, sum_new = sum_old - DELTA) is:
        v1 = v1 - mx0(v0, sum_old)      # uses the round's *input* v0
        v0 = v0 - mx1(v1_new, sum_new)  # uses the just-updated v1

    So inverting round-by-round in reverse round order requires, per round:
        v0_in = v0_out + mx1(v1_out, sum_new)   # v1 not yet touched this step
        v1_in = v1_out + mx0(v0_in, sum_old)    # uses v0_in just recovered
    """
    words = _key_words(key)
    sums_old = []
    total_sum = (DELTA * ROUNDS) & MASK32
    for _ in range(ROUNDS):
        sums_old.append(total_sum)
        total_sum = (total_sum - DELTA) & MASK32
    for sum_old in reversed(sums_old):
        sum_new = (sum_old - DELTA) & MASK32

        idx1 = sum_new & 0x3
        mx1 = (((v1 << 4) ^ (v1 >> 5)) + v1) & MASK32
        mx1 = (mx1 ^ ((words[idx1] + sum_new + tweak) & MASK32)) & MASK32
        v0 = (v0 + mx1) & MASK32

        idx0 = (sum_old >> 11) & 0x3
        mx0 = (((v0 << 4) ^ (v0 >> 5)) + v0) & MASK32
        mx0 = (mx0 ^ ((words[idx0] + sum_old + tweak) & MASK32)) & MASK32
        v1 = (v1 + mx0) & MASK32
    return v0, v1


def decrypt_setup_block(
    ciphertext: bytes,
    key: tuple[int, int, int, int] = PRODUCTION_KEY,
    address: int = 0x7C00,
) -> bytes:
    """Decrypt a 256-byte encrypted Setup block into 192 bytes of plaintext.

    `address` is the flash address the block was read from (0x7C00 or 0xF800 per
    the research — this project observed it acts as part of the key schedule,
    not just a memory offset). It advances by 8 for each 8-byte block processed,
    matching the reference script.
    """
    if len(ciphertext) != SETUP_BLOCK_SIZE:
        raise ValueError(f"ciphertext must be {SETUP_BLOCK_SIZE} bytes, got {len(ciphertext)}")
    plaintext = bytearray()
    tweak = address
    for offset in range(0, SETUP_BLOCK_SIZE, BLOCK_SIZE):
        v0 = int.from_bytes(ciphertext[offset : offset + 4], "little")
        v1 = int.from_bytes(ciphertext[offset + 4 : offset + 8], "little")
        v0, v1 = _decrypt_block(v0, v1, key, tweak)
        # Keep v0's high 16 bits (2 bytes) + all of v1 (4 bytes); discard v0's low 16 bits.
        plaintext += ((v0 >> 16) & 0xFFFF).to_bytes(2, "little")
        plaintext += v1.to_bytes(4, "little")
        tweak = (tweak + BLOCK_SIZE) & 0xFFFF
    return bytes(plaintext)


def encrypt_setup_block(
    plaintext: bytes,
    key: tuple[int, int, int, int] = PRODUCTION_KEY,
    address: int = 0x7C00,
    discarded_low_words: bytes | None = None,
) -> bytes:
    """Encrypt 192 bytes of plaintext into a 256-byte Setup block.

    Each 8-byte ciphertext block encodes only 6 plaintext bytes; the other 2
    bytes (v0's low 16 bits) are not recoverable from the plaintext alone and
    must be supplied via `discarded_low_words` (32 x 2 bytes = 64 bytes, one
    per block) if a specific value is needed — e.g. to exactly reproduce a
    known ciphertext. Defaults to all-zero, which is NOT confirmed to match
    real ESC/configurator behavior (see BLHeliSuite32-Reverse2.en.md's nonce
    theory, still unverified) — only use a real captured value if bit-exact
    output matters.

    New evidence for the nonce theory (2026-09-07, real hardware, see
    docs/knowledge/hardware-findings.md): writing one ESC's real recovered
    discarded-low-words to another ESC (verified round-tripping to the exact
    source ciphertext locally before sending) produced a readback ciphertext
    that differed from the source in nearly every byte, while the decrypted
    plaintext stayed exactly identical — consistent with the device
    regenerating these bits itself on every write rather than storing
    whatever value is supplied. Still not proof, but a real data point.
    """
    if len(plaintext) != PLAINTEXT_SIZE:
        raise ValueError(f"plaintext must be {PLAINTEXT_SIZE} bytes, got {len(plaintext)}")
    num_blocks = SETUP_BLOCK_SIZE // BLOCK_SIZE
    if discarded_low_words is None:
        discarded_low_words = bytes(2 * num_blocks)
    elif len(discarded_low_words) != 2 * num_blocks:
        raise ValueError(f"discarded_low_words must be {2 * num_blocks} bytes")

    ciphertext = bytearray()
    tweak = address
    for i in range(num_blocks):
        p_off = i * KEPT_BYTES_PER_BLOCK
        low16 = int.from_bytes(discarded_low_words[i * 2 : i * 2 + 2], "little")
        high16 = int.from_bytes(plaintext[p_off : p_off + 2], "little")
        v0 = (high16 << 16) | low16
        v1 = int.from_bytes(plaintext[p_off + 2 : p_off + 6], "little")
        v0, v1 = _encrypt_block(v0, v1, key, tweak)
        ciphertext += v0.to_bytes(4, "little")
        ciphertext += v1.to_bytes(4, "little")
        tweak = (tweak + BLOCK_SIZE) & 0xFFFF
    return bytes(ciphertext)
