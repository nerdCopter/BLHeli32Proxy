"""Named-field decoding of the 192-byte decrypted Setup block plaintext.

Only covers fields whose byte offset was empirically confirmed (2026-09-04)
by cross-referencing this project's own decrypted plaintext, read live from
all 4 ESCs on a real Aikon AK32 4-in-1, against a real backup file produced
by the official BLHeliSuite32xl app for the same hardware. Confirmation
method: `Eep_Pgm_Direction` is the only byte that differs across the 4 ESCs
(values 1,2,2,1) and it matches the real app's per-ESC direction settings
exactly; the remaining fields were placed by matching literal integer values
(e.g. byte 0x8c = 140 = the real app's `Eep_Pgm_Temp_Prot_Enable`) at their
natural sequential position following Direction.

BLHeli_S's public source (bitdump/BLHeli, BLHeli_S.asm) confirms these field
*names* but NOT these offsets or widths — BLHeli_32 (closed-source) widened
several fields (e.g. throttle values: 1 scaled byte in BLHeli_S vs. 2 raw
bytes here) and reordered others. No public source exists for BLHeli_32-only
fields (Eep_Note_Array, all Eep_Hw_* capability flags, Sine_Mode,
Auto_Tlm_Mode, Stall_Prot, ESC_Layout, ESC_Mode) — do not guess offsets for
these; leave them undecoded rather than emit a wrong value. In particular,
never use this module's output to drive a write-back/restore path — it is
read-only reporting, not a validated round-trip format.
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
    "Eep_Pgm_Beep_Strength": (20, 1),
    "Eep_Pgm_Beacon_Strength": (21, 1),
    "Eep_Pgm_Beacon_Delay": (22, 2),
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


IXI_PARTIAL_BACKUP_WARNING = (
    "; Partial backup written by blheli32proxy — confirmed fields only (see\n"
    "; protocol/setup_fields.py). NOT a complete .ixi: missing header fields\n"
    "; (Eep_ESC_Layout, Eep_FW_*_Revision, etc.) and ~26 undecoded Eep_Pgm_*/\n"
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
