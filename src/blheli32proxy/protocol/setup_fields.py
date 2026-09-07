"""Named-field decoding of the 192-byte decrypted Setup block plaintext.

Only covers fields whose byte offset was empirically confirmed by
cross-referencing this project's own decrypted plaintext against a real
backup file (and, for the 2026-09-07 batch, a real differential capture —
see below) produced by the official BLHeliSuite32xl app for the same
hardware (Aikon AK32 4-in-1, firmware 32.7).

**Original 13 fields (2026-09-04)**: `Eep_Pgm_Direction` is the only byte
that differs across the 4 ESCs (values 1,2,2,1) and it matches the real
app's per-ESC direction settings exactly; the remaining 12 were placed by
matching literal integer values (e.g. byte 0x8c = 140 = the real app's
`Eep_Pgm_Temp_Prot_Enable`) at their natural sequential position.

**8 more fields (2026-09-07)**, via differential capture: set every
changeable field to a distinct value in the real app at once, Write Setup,
diff the raw plaintext against a pre-change backup byte-by-byte, match each
changed byte against the `.ixi`'s new field values. Where multiple fields
changed simultaneously and collided (offsets 26/29/30/31 all flipping
0<->1 on the same pass), resolved with follow-up single-field toggles until
each offset was isolated to exactly one field — see
docs/knowledge/setup-block-fields.md for the full method and evidence.
`Eep_Pgm_Volt_Prot` and `Eep_Pgm_Max_Acceleration` store the raw on-flash
byte here (consistent with every other field in this table) — the app UI
shows them divided by 10 (byte 27 -> "2.70 V", byte 58 -> "5.8% per ms");
that division is an observed correlation, not confirmed to be the real
`.ixi` text file's own on-disk representation, so it is not applied here.

**1 more field (2026-09-07, same session)**: `Eep_Note_Config` (offset 28,
single byte, packed as `Length<<4 | Interval` — byte 0x50 decoded to the
real app's "Length 05 Interval 00", byte 0x37 to "Length 3 Interval 7";
matches the real `.ixi`'s own `Eep_Note_Config=80` literal value for the
first case, confirming this raw-byte representation is exactly the `.ixi`
file's own on-disk format, not just this module's convention).
`Eep_Note_Array` (the actual melody note sequence) remains undecoded —
substantially more complex, a variable-length sequence, not attempted.

BLHeli_S's public source (bitdump/BLHeli, BLHeli_S.asm) confirms some field
*names* but NOT these offsets or widths — BLHeli_32 (closed-source) widened
several fields (e.g. throttle values: 1 scaled byte in BLHeli_S vs. 2 raw
bytes here) and reordered others. No public source exists for BLHeli_32-only
fields — remaining undecoded: `Eep_Note_Array` (melody note sequence, byte
layout not attempted), all `Eep_Hw_*` capability flags (expected
read-only/immutable, not user-settable so not reachable via this method),
`Eep_Name`, `Eep_ESC_Layout`, `Eep_ESC_Mode`, `Eep_FW_*_Revision`,
`Eep_Layout_Revision` (identity/version fields, also immutable). Do not
guess offsets for these; leave them undecoded rather than emit a wrong
value. In particular, never use this module's output to drive a
write-back/restore path — it is read-only reporting, not a validated
round-trip format.
"""

from __future__ import annotations

# name -> (offset, width_bytes); width 1 = plain byte, 2 = little-endian uint16
CONFIRMED_FIELDS: dict[str, tuple[int, int]] = {
    "Eep_Pgm_Direction": (3, 1),
    "Eep_Pgm_Rampup_Pwr": (4, 1),
    "Eep_Pgm_Pwm_Freq": (5, 1),
    "Eep_Pgm_Comm_Timing": (6, 1),
    "Eep_Pgm_Demag_Comp": (7, 1),
    "Eep_Pgm_Ppm_Min_Throttle": (8, 2),
    "Eep_Pgm_Ppm_Center_Throttle": (10, 2),
    "Eep_Pgm_Ppm_Max_Throttle": (12, 2),
    "Eep_Pgm_Enable_Throttle_Cal": (14, 1),
    "Eep_Pgm_Temp_Prot_Enable": (15, 1),
    "Eep_Pgm_Volt_Prot": (16, 1),
    "Eep_Pgm_Enable_Power_Prot": (18, 1),
    "Eep_Pgm_Brake_On_Stop": (19, 1),
    "Eep_Pgm_Beep_Strength": (20, 1),
    "Eep_Pgm_Beacon_Strength": (21, 1),
    "Eep_Pgm_Beacon_Delay": (22, 2),
    "Eep_Pgm_Max_Acceleration": (25, 1),
    "Eep_Pgm_Nondamped_Mode": (26, 1),
    "Eep_Note_Config": (28, 1),
    "Eep_Pgm_Sine_Mode": (29, 1),
    "Eep_Pgm_Auto_Tlm_Mode": (30, 1),
    "Eep_Pgm_Stall_Prot": (31, 1),
}


def decode_confirmed_fields(plaintext: bytes) -> dict[str, int]:
    """Decode only the fields listed in CONFIRMED_FIELDS. Raises ValueError
    if `plaintext` is too short for any confirmed offset."""
    result: dict[str, int] = {}
    for name, (offset, width) in CONFIRMED_FIELDS.items():
        if offset + width > len(plaintext):
            raise ValueError(
                f"plaintext too short ({len(plaintext)} bytes) for field {name} "
                f"at offset {offset} width {width}"
            )
        result[name] = int.from_bytes(plaintext[offset : offset + width], "little")
    return result


def extract_identity_strings(plaintext: bytes) -> tuple[str | None, str | None]:
    """Extract the board-layout name and MCU string directly from the real
    Setup block, e.g. "#Furling32_4in1_C#...#BLHeli_32*GD32F350x6#" ->
    ("Furling32_4in1_C", "GD32F350x6") — confirmed live against multiple real
    boards (AK32/STM32F051x6, Furling32_4in1_C/GD32F350x6). Scans for
    '#'-delimited printable-ASCII text anywhere in the plaintext rather than
    a fixed numeric offset (CONFIRMED_FIELDS' own caution against guessing
    offsets applies here too — a delimiter search is robust to minor layout
    differences a fixed slice wouldn't be). Returns (None, None) for either
    piece not found, never a guessed/fabricated value."""
    text = "".join(chr(b) if 32 <= b < 127 else "\x00" for b in plaintext)
    # only a segment with ZERO non-printable bytes counts as real text — binary config bytes
    # coincidentally fall in the printable-ASCII range often enough that a laxer check (e.g. "any
    # printable character present") picks up noise from the numeric fields before the real string
    segments = [s.strip() for s in text.split("#") if s and "\x00" not in s and s.strip()]
    layout = segments[0] if segments else None
    cpu = None
    for seg in segments[1:]:
        if seg.startswith("BLHeli_32*"):
            cpu = seg[len("BLHeli_32*") :]
            break
    return layout, cpu


IXI_PARTIAL_BACKUP_WARNING = (
    "; Partial backup written by blheli32proxy — confirmed fields only (see\n"
    "; protocol/setup_fields.py). NOT a complete .ixi: missing header fields\n"
    "; (Eep_ESC_Layout, Eep_FW_*_Revision, etc.) and ~16 undecoded Eep_Note_Array/\n"
    "; Eep_Hw_* fields. Do not load this into BLHeliSuite32xl or any other\n"
    "; tool expecting a real .ixi — it will misinterpret the missing fields.\n"
)


def format_ixi_section(esc_index: int, fields: dict[str, int]) -> str:
    """Format confirmed fields as one `[ESCn]` section (1-based, matching
    BLHeliSuite32xl's real .ixi numbering) for a partial backup file. Emits
    only CONFIRMED_FIELDS, in the same order as a real .ixi — never fabricate
    the unconfirmed fields to make this look like a complete backup."""
    lines = [f"[ESC{esc_index + 1}]"]
    for name in CONFIRMED_FIELDS:
        lines.append(f"{name}={fields[name]}")
    return "\n".join(lines) + "\n"
