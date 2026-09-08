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

**2 more fields (2026-09-07, cross-version differential capture)**:
`Eep_Pgm_Curr_Prot` (offset 17, literal Amp threshold, e.g. 200 = 200A) and
`Eep_Pgm_Curr_Sense_Cal` (offset 27, `raw - 100 = percent`, e.g. 1 = -99%) —
confirmed via a real differential test on a Furling32 (GD32F350x6, firmware
32.9.5), not the AK32 these other fields were confirmed against. AK32 lacks
current-sense hardware and its own real `.ixi` export never lists these two
field names at all, but the underlying bytes still physically exist there
(offset 17 = 0xFF, offset 27 = 100 on that hardware) — this DISPROVES an
earlier hypothesis that offset 17 was a retired BLHeli_S-heritage
placeholder (it seemed to fit that pattern before this field was found).
Working theory (unproven): the same physical byte slot may be unused/inert
on older or current-sense-less hardware and only actively written on
hardware that has the corresponding feature — 21 of the 22 other confirmed
fields held their exact offsets across both boards, so this is the one
place a real difference showed up, not evidence the whole map is
board-specific. See docs/knowledge/setup-block-fields.md's cross-version
section for the full account, including the earlier wrong guess.

**3 more fields (2026-09-07, same Furling32 session)**: `Eep_Pgm_LED_Control`
(offset 24 -- this closes the last of the original 3-gap chase; an earlier
guess that this offset was `Curr_Prot` is now known wrong, see above),
`Eep_Pgm_SBUS_Channel` (offset 32, raw = channel number), and
`Eep_Pgm_SPORT_Physical_ID` (offset 33, raw = ID number) -- all confirmed
via one differential pass changing all three to distinct values at once.
`LED_Control` packs multiple LEDs' state into one byte (e.g. `0x33` =
`0b00110011`, matching an observed "On, Off, On" 3-LED pattern via 2 bits
per LED) -- the offset and general packed-byte nature are confirmed by the
clean single-attributable diff; the exact bit-width/color encoding is
inferred from one data point, not exhaustively mapped. `SBUS_Channel` and
`SPORT_Physical_ID` don't exist on AK32 (no SBUS/S.PORT support in that
firmware) -- both read `255` (sentinel) there, same pattern as
`Curr_Prot`/`Curr_Sense_Cal`. `Eep_SPORT_Capable` (a non-`Pgm_` hardware
capability flag, same category as the `Eep_Hw_*` flags) remains unlocated
-- no user-facing control exists for it, so this method can't reach it.

**2 more fields (2026-09-08, third real board/MCU vendor -- a damaged FOXEER Reaper,
AT32F421/Artery Technology)**: `Eep_Pgm_Pwm_Frequency_Lo` added as a second name for the
already-confirmed offset 5 (same byte as `Eep_Pgm_Pwm_Freq` -- both are real BLHeli_32 names for
it depending on firmware version; the AK32-specific `Eep_Pgm_Pwm_Freq` entry is untouched, this is
purely additive). `Eep_Pgm_Pwm_Frequency_Hi` (offset 34, literal kHz value, same encoding as
`_Lo`) is a genuinely new offset, confirmed via a real differential test (128 -> 48, matching a UI
change from 128 kHz to 48 kHz exactly, single clean byte diff). All 22 fields from the AK32/
Furling32 work also confirmed correct on this third MCU vendor -- see
docs/knowledge/hardware-findings.md's "damaged unit" section for the full account.

**12 more fields (2026-09-08, same session)**: a THIRD confirmation method beyond differential
capture and direct real-.ixi value matching -- cross-board value correlation. With 3 independent
real boards' raw plaintext AND their real .ixi values on hand (AK32, Furling32, this damaged
Reaper), searched every offset 0-191 for a byte pattern matching each remaining field's known
per-board .ixi value simultaneously across all 3 boards. `Eep_FW_Sub_Revision` (offset 1),
`Eep_Layout_Revision` (2), `Eep_Hw_LED_Capable_0/1/2` (50/51/52), and `Eep_Hw_Pwm_Freq_Min/Max`
(54/55) each had exactly ONE matching offset across all 192 positions -- unambiguous. 6 more
(`Eep_FW_Main_Revision` offset 0, `Eep_Hw_Voltage_Sense_Capable` 48, `Eep_Hw_Current_Sense_Capable`
49, `Eep_Hw_LED_Capable_3` 53, `Eep_SPORT_Capable` 62, `Eep_Nondamped_Capable` 63) had multiple raw
candidates individually, resolved by eliminating any offset already assigned to a different
confirmed field, which in every case left exactly one remaining candidate -- and every resolved
offset lands in a clean, unbroken sequential run matching the real `.ixi`'s own declared field
order exactly (`FW_Main_Revision, FW_Sub_Revision, Layout_Revision` at 0-2; `Hw_Voltage_Sense_Capable`
through `Hw_Pwm_Freq_Max` at 48-55; `SPORT_Capable, Nondamped_Capable` at 62-63), strong structural
corroboration beyond the value match alone. **`Eep_ESC_Mode` (value `2` on all 3 boards) could NOT
be located** -- the literal byte value `2` does not appear ANYWHERE in the Reaper's 192-byte
plaintext, at all, which suggests this field may not be a directly-stored byte in this structure at
all (possibly derived from firmware/layout metadata the app already has, not read from the ESC).
Left unconfirmed rather than guessed.

BLHeli_S's public source (bitdump/BLHeli, BLHeli_S.asm) confirms some field
*names* but NOT these offsets or widths — BLHeli_32 (closed-source) widened
several fields (e.g. throttle values: 1 scaled byte in BLHeli_S vs. 2 raw
bytes here) and reordered others. No public source exists for BLHeli_32-only
fields — remaining undecoded: `Eep_Note_Array` (melody note sequence, byte
layout not attempted), `Eep_ESC_Layout` (recoverable via
`extract_identity_strings()`'s delimiter search, not a fixed offset — not
the same as a confirmed numeric offset), and `Eep_ESC_Mode` (see above — not
even confirmed to be a literal stored byte). Do not guess offsets for these;
leave them undecoded rather than emit a wrong value. In particular, never
use this module's output to drive a write-back/restore path — it is
read-only reporting, not a validated round-trip format.
"""

from __future__ import annotations

# name -> (offset, width_bytes); width 1 = plain byte, 2 = little-endian uint16
CONFIRMED_FIELDS: dict[str, tuple[int, int]] = {
    # confirmed 2026-09-08 via 3-way cross-board value correlation (AK32/Furling32/Reaper), not a
    # differential test -- see module docstring's "12 more fields" note for method and confidence
    "Eep_FW_Main_Revision": (0, 1),
    "Eep_FW_Sub_Revision": (1, 1),
    "Eep_Layout_Revision": (2, 1),
    "Eep_Pgm_Direction": (3, 1),
    "Eep_Pgm_Rampup_Pwr": (4, 1),
    "Eep_Pgm_Pwm_Freq": (5, 1),  # AK32/32.7 name; same byte as Eep_Pgm_Pwm_Frequency_Lo below on 32.9+
    "Eep_Pgm_Pwm_Frequency_Lo": (5, 1),  # 32.9+ name for the same offset -- added, not a replacement
    "Eep_Pgm_Comm_Timing": (6, 1),
    "Eep_Pgm_Demag_Comp": (7, 1),
    "Eep_Pgm_Ppm_Min_Throttle": (8, 2),
    "Eep_Pgm_Ppm_Center_Throttle": (10, 2),
    "Eep_Pgm_Ppm_Max_Throttle": (12, 2),
    "Eep_Pgm_Enable_Throttle_Cal": (14, 1),
    "Eep_Pgm_Temp_Prot_Enable": (15, 1),
    "Eep_Pgm_Volt_Prot": (16, 1),
    "Eep_Pgm_Curr_Prot": (17, 1),
    "Eep_Pgm_Enable_Power_Prot": (18, 1),
    "Eep_Pgm_Brake_On_Stop": (19, 1),
    "Eep_Pgm_Beep_Strength": (20, 1),
    "Eep_Pgm_Beacon_Strength": (21, 1),
    "Eep_Pgm_Beacon_Delay": (22, 2),
    "Eep_Pgm_LED_Control": (24, 1),
    "Eep_Pgm_Max_Acceleration": (25, 1),
    "Eep_Pgm_Nondamped_Mode": (26, 1),
    "Eep_Pgm_Curr_Sense_Cal": (27, 1),
    "Eep_Note_Config": (28, 1),
    "Eep_Pgm_Sine_Mode": (29, 1),
    "Eep_Pgm_Auto_Tlm_Mode": (30, 1),
    "Eep_Pgm_Stall_Prot": (31, 1),
    "Eep_Pgm_SBUS_Channel": (32, 1),
    "Eep_Pgm_SPORT_Physical_ID": (33, 1),
    "Eep_Pgm_Pwm_Frequency_Hi": (34, 1),
    # confirmed 2026-09-08, same cross-board correlation method as the block at the top of this dict
    "Eep_Hw_Voltage_Sense_Capable": (48, 1),
    "Eep_Hw_Current_Sense_Capable": (49, 1),
    "Eep_Hw_LED_Capable_0": (50, 1),
    "Eep_Hw_LED_Capable_1": (51, 1),
    "Eep_Hw_LED_Capable_2": (52, 1),
    "Eep_Hw_LED_Capable_3": (53, 1),
    "Eep_Hw_Pwm_Freq_Min": (54, 1),
    "Eep_Hw_Pwm_Freq_Max": (55, 1),
    "Eep_SPORT_Capable": (62, 1),
    "Eep_Nondamped_Capable": (63, 1),
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


# Eep_Name: confirmed 2026-09-07 via differential capture — setting the app's "Name" field to a
# 16-character string changed exactly these 16 bytes, none else. Matches BLHeli_S's own EEPROM
# comment for this same field name ("Name tag (16 Bytes)") exactly. Kept separate from
# CONFIRMED_FIELDS (an int-only table) since this is a fixed-width space-padded ASCII string, not
# an integer.
EEP_NAME_OFFSET = 128
EEP_NAME_WIDTH = 16


def decode_name(plaintext: bytes) -> str:
    """Decode Eep_Name (offset 128, 16 bytes, space-padded ASCII) — see EEP_NAME_OFFSET's
    comment. Trailing spaces stripped, matching how a real .ixi's Eep_Name value appears
    (blank when unset, e.g. "Eep_Name=")."""
    if EEP_NAME_OFFSET + EEP_NAME_WIDTH > len(plaintext):
        raise ValueError(f"plaintext too short ({len(plaintext)} bytes) for Eep_Name")
    raw = plaintext[EEP_NAME_OFFSET : EEP_NAME_OFFSET + EEP_NAME_WIDTH]
    return raw.decode("ascii", errors="replace").rstrip(" ")


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
    "; protocol/setup_fields.py). NOT a complete .ixi: missing Eep_ESC_Layout,\n"
    "; Eep_ESC_Mode, and Eep_Note_Array. Do not load this into BLHeliSuite32xl\n"
    "; or any other tool expecting a real .ixi — it will misinterpret the\n"
    "; missing fields.\n"
)


def format_ixi_section(esc_index: int, fields: dict[str, int], name: str | None = None) -> str:
    """Format confirmed fields as one `[ESCn]` section (1-based, matching
    BLHeliSuite32xl's real .ixi numbering) for a partial backup file. Emits
    only CONFIRMED_FIELDS (plus Eep_Name, first, if `name` is given — matching
    a real .ixi's own field order), never fabricating the unconfirmed fields
    to make this look like a complete backup. `name` is optional and omitted
    by default so existing callers that don't have it need no changes."""
    lines = [f"[ESC{esc_index + 1}]"]
    if name is not None:
        lines.append(f"Eep_Name={name}")
    for field_name in CONFIRMED_FIELDS:
        lines.append(f"{field_name}={fields[field_name]}")
    return "\n".join(lines) + "\n"
