"""setup_fields tests using real decrypted plaintext, read live from all 4
ESCs on a real Aikon AK32 4-in-1 (2026-09-04), cross-checked against a real
backup file produced by the official BLHeliSuite32xl app for the same
hardware — not invented test vectors."""

import pytest

from blheli32proxy.protocol import setup_fields as sf

# real decrypted plaintext, ESC channel 0 (matches BLHeliSuite32xl's "ESC1",
# Eep_Pgm_Direction=1 in the real .ixi backup). Re-verified 2026-09-07 against a fresh live
# capture (dumps/esc0-setup-20260907-155420.bin) -- the original transcription of this constant
# was missing 5 space (0x20) bytes around offset 135-140 (silently wrong until Eep_Name's
# discovery at offset 128 finally read that far into the plaintext; nothing before that touched
# past offset 31, so decode_confirmed_fields() never caught the truncation).
REAL_PLAINTEXT_ESC0 = bytes.fromhex(
    "20462c0132300002f603dc05c107018c00ff0100284658020000006450000001ff"
    "ffffffffffffffffffffffffffffff00ff00000000ffffffffffffffffff012341"
    "696b6f6e5f414b33325f34494e315f3335415f36535f56315f302320202023424c"
    "48656c695f33322a53544d33324630353178362320202020202020202020202020"
    "202020202020202020202020201720242730271820232823283033383322252a25"
    "2a323532353a35ffffffffffffffffffffffffffffffffffffffff"
)

# real decrypted plaintext, ESC channel 1 (matches BLHeliSuite32xl's "ESC2",
# Eep_Pgm_Direction=2 in the real .ixi backup) — differs only at offset 3. Re-verified 2026-09-07
# against dumps/esc1-setup-20260907-155420.bin, same fix as REAL_PLAINTEXT_ESC0 above.
REAL_PLAINTEXT_ESC1 = bytes.fromhex(
    "20462c0232300002f603dc05c107018c00ff0100284658020000006450000001ff"
    "ffffffffffffffffffffffffffffff00ff00000000ffffffffffffffffff012341"
    "696b6f6e5f414b33325f34494e315f3335415f36535f56315f302320202023424c"
    "48656c695f33322a53544d33324630353178362320202020202020202020202020"
    "202020202020202020202020201720242730271820232823283033383322252a25"
    "2a323532353a35ffffffffffffffffffffffffffffffffffffffff"
)

# real values from the .ixi backup's [ESC1] section (matches REAL_PLAINTEXT_ESC0)
EXPECTED_ESC0 = {
    "Eep_FW_Main_Revision": 32,
    "Eep_FW_Sub_Revision": 70,
    "Eep_Layout_Revision": 44,
    "Eep_Pgm_Direction": 1,
    "Eep_Pgm_Rampup_Pwr": 50,
    "Eep_Pgm_Pwm_Freq": 48,
    "Eep_Pgm_Pwm_Frequency_Lo": 48,
    "Eep_Pgm_Comm_Timing": 0,
    "Eep_Pgm_Demag_Comp": 2,
    "Eep_Pgm_Ppm_Min_Throttle": 1014,
    "Eep_Pgm_Ppm_Center_Throttle": 1500,
    "Eep_Pgm_Ppm_Max_Throttle": 1985,
    "Eep_Pgm_Enable_Throttle_Cal": 1,
    "Eep_Pgm_Temp_Prot_Enable": 140,
    "Eep_Pgm_Volt_Prot": 0,
    "Eep_Pgm_Curr_Prot": 255,
    "Eep_Pgm_Enable_Power_Prot": 1,
    "Eep_Pgm_Brake_On_Stop": 0,
    "Eep_Pgm_Beep_Strength": 40,
    "Eep_Pgm_Beacon_Strength": 70,
    "Eep_Pgm_Beacon_Delay": 600,
    "Eep_Pgm_LED_Control": 0,
    "Eep_Pgm_Max_Acceleration": 0,
    "Eep_Pgm_Nondamped_Mode": 0,
    "Eep_Pgm_Curr_Sense_Cal": 100,
    "Eep_Note_Config": 80,
    "Eep_Pgm_Sine_Mode": 0,
    "Eep_Pgm_Auto_Tlm_Mode": 0,
    "Eep_Pgm_Stall_Prot": 1,
    "Eep_Pgm_SBUS_Channel": 255,
    "Eep_Pgm_SPORT_Physical_ID": 255,
    "Eep_Pgm_Pwm_Frequency_Hi": 255,
    "Eep_Hw_Voltage_Sense_Capable": 0,
    "Eep_Hw_Current_Sense_Capable": 255,
    "Eep_Hw_LED_Capable_0": 0,
    "Eep_Hw_LED_Capable_1": 0,
    "Eep_Hw_LED_Capable_2": 0,
    "Eep_Hw_LED_Capable_3": 0,
    "Eep_Hw_Pwm_Freq_Min": 255,
    "Eep_Hw_Pwm_Freq_Max": 255,
    "Eep_SPORT_Capable": 255,
    "Eep_Nondamped_Capable": 1,
}


def test_decode_confirmed_fields_matches_real_ixi_values_esc0():
    assert sf.decode_confirmed_fields(REAL_PLAINTEXT_ESC0) == EXPECTED_ESC0


def test_decode_confirmed_fields_direction_varies_esc1():
    decoded = sf.decode_confirmed_fields(REAL_PLAINTEXT_ESC1)
    assert decoded["Eep_Pgm_Direction"] == 2
    # every other confirmed field is identical between ESC0 and ESC1
    for name, value in EXPECTED_ESC0.items():
        if name != "Eep_Pgm_Direction":
            assert decoded[name] == value


def test_decode_confirmed_fields_too_short_raises():
    with pytest.raises(ValueError):
        sf.decode_confirmed_fields(b"\x00" * 10)


def test_all_confirmed_offsets_fit_within_192_byte_plaintext():
    for name, (offset, width) in sf.CONFIRMED_FIELDS.items():
        assert offset + width <= 192, f"{name} at {offset}+{width} exceeds 192 bytes"


# Confirmed-fields lines this tool decodes, in the same order as a real .ixi lists the fields it
# has. NOT byte-for-byte identical to AK32's own real .ixi export: Eep_Pgm_Curr_Prot/Curr_Sense_Cal
# are confirmed real fields (differential-tested on a Furling32 that has current-sense hardware,
# see docs/knowledge/setup-block-fields.md) whose underlying bytes still exist and decode correctly
# on AK32 (255, 100) even though AK32 lacks that hardware and its own real .ixi omits both keys
# entirely -- this project's tool decodes every confirmed offset regardless of what a specific
# board's own .ixi export chooses to show. Same story for Eep_Pgm_SBUS_Channel/SPORT_Physical_ID
# (255, 255 on AK32 -- no SBUS/S.PORT support on that firmware at all) and Eep_Pgm_LED_Control (0
# on AK32, which does have LEDs but none configured/lit). Eep_Pgm_Pwm_Frequency_Lo is the reverse
# case: AK32's own real .ixi only ever shows this same offset as "Eep_Pgm_Pwm_Freq" (no _Lo/_Hi
# split on 32.7 firmware) -- this project's tool emits both names for the one byte, confirmed
# identical (48) on real AK32 hardware, since both names are real BLHeli_32 names for it depending
# on firmware version (see docs/knowledge/setup-block-fields.md's cross-version section).
REAL_IXI_ESC1_SECTION = """[ESC1]
Eep_FW_Main_Revision=32
Eep_FW_Sub_Revision=70
Eep_Layout_Revision=44
Eep_Pgm_Direction=1
Eep_Pgm_Rampup_Pwr=50
Eep_Pgm_Pwm_Freq=48
Eep_Pgm_Pwm_Frequency_Lo=48
Eep_Pgm_Comm_Timing=0
Eep_Pgm_Demag_Comp=2
Eep_Pgm_Ppm_Min_Throttle=1014
Eep_Pgm_Ppm_Center_Throttle=1500
Eep_Pgm_Ppm_Max_Throttle=1985
Eep_Pgm_Enable_Throttle_Cal=1
Eep_Pgm_Temp_Prot_Enable=140
Eep_Pgm_Volt_Prot=0
Eep_Pgm_Curr_Prot=255
Eep_Pgm_Enable_Power_Prot=1
Eep_Pgm_Brake_On_Stop=0
Eep_Pgm_Beep_Strength=40
Eep_Pgm_Beacon_Strength=70
Eep_Pgm_Beacon_Delay=600
Eep_Pgm_LED_Control=0
Eep_Pgm_Max_Acceleration=0
Eep_Pgm_Nondamped_Mode=0
Eep_Pgm_Curr_Sense_Cal=100
Eep_Note_Config=80
Eep_Pgm_Sine_Mode=0
Eep_Pgm_Auto_Tlm_Mode=0
Eep_Pgm_Stall_Prot=1
Eep_Pgm_SBUS_Channel=255
Eep_Pgm_SPORT_Physical_ID=255
Eep_Pgm_Pwm_Frequency_Hi=255
Eep_Hw_Voltage_Sense_Capable=0
Eep_Hw_Current_Sense_Capable=255
Eep_Hw_LED_Capable_0=0
Eep_Hw_LED_Capable_1=0
Eep_Hw_LED_Capable_2=0
Eep_Hw_LED_Capable_3=0
Eep_Hw_Pwm_Freq_Min=255
Eep_Hw_Pwm_Freq_Max=255
Eep_SPORT_Capable=255
Eep_Nondamped_Capable=1
"""


def test_format_ixi_section_matches_real_ixi_lines_exactly():
    assert sf.format_ixi_section(0, EXPECTED_ESC0) == REAL_IXI_ESC1_SECTION


def test_format_ixi_section_esc_numbering_is_one_based():
    # motor-index 3 (0-based) is real ESC4 (1-based) in BLHeliSuite32xl's own numbering
    section = sf.format_ixi_section(3, EXPECTED_ESC0)
    assert section.startswith("[ESC4]\n")


def test_format_ixi_section_never_fabricates_unconfirmed_fields():
    section = sf.format_ixi_section(0, EXPECTED_ESC0)
    # only CONFIRMED_FIELDS lines — none of the real .ixi's still-unconfirmed fields
    # (as of 2026-09-08: only Eep_ESC_Mode remains unconfirmed, see setup_fields.py's docstring)
    assert "Eep_ESC_Mode" not in section


def test_format_ixi_section_missing_field_raises():
    incomplete = {k: v for k, v in EXPECTED_ESC0.items() if k != "Eep_Pgm_Beacon_Delay"}
    with pytest.raises(KeyError):
        sf.format_ixi_section(0, incomplete)


# real decrypted plaintext, ESC channel 0, after setting the app's "Name" field to
# "TESTNAME12345678" (16 chars, fills the field exactly) and Write Setup (2026-09-07) — confirmed
# the only bytes that changed from REAL_PLAINTEXT_ESC0-like state were offsets 128-143
REAL_PLAINTEXT_ESC0_NAMED = bytes.fromhex(
    "20462c03032d1b03b7034306290801491bff001845698402003a006437000101"
    "ffffffffffffffffffffffffffffffff00ff00000000ffffffffffffffffff01"
    "2341696b6f6e5f414b33325f34494e315f3335415f36535f56315f3023202020"
    "23424c48656c695f33322a53544d333246303531783623202020202020202020"
    "544553544e414d4531323334353637382017202427302718202328232830333833"
    "22252a252a323532353a35ffffffffffffffffffffffffffffffffffffffff"
)


def test_decode_name_blank_when_unset():
    assert sf.decode_name(REAL_PLAINTEXT_ESC0) == ""


def test_decode_name_strips_trailing_padding():
    assert sf.decode_name(REAL_PLAINTEXT_ESC0_NAMED) == "TESTNAME12345678"


def test_decode_name_too_short_raises():
    with pytest.raises(ValueError):
        sf.decode_name(b"\x00" * 10)


def test_format_ixi_section_includes_name_when_given():
    section = sf.format_ixi_section(0, EXPECTED_ESC0, name="TESTNAME12345678")
    assert section.startswith("[ESC1]\nEep_Name=TESTNAME12345678\n")


def test_format_ixi_section_omits_name_line_when_not_given():
    section = sf.format_ixi_section(0, EXPECTED_ESC0)
    assert "Eep_Name" not in section


def test_decode_esc_layout_from_real_ak32_plaintext():
    assert sf.decode_esc_layout(REAL_PLAINTEXT_ESC0) == "Aikon_AK32_4IN1_35A_6S_V1_0"


def test_decode_esc_layout_too_short_raises():
    with pytest.raises(ValueError):
        sf.decode_esc_layout(b"\x00" * 10)


def test_format_ixi_section_includes_layout_when_given():
    section = sf.format_ixi_section(0, EXPECTED_ESC0, layout="Aikon_AK32_4IN1_35A_6S_V1_0")
    assert section.startswith("[ESC1]\nEep_ESC_Layout=Aikon_AK32_4IN1_35A_6S_V1_0\n")


def test_format_ixi_section_omits_layout_line_when_not_given():
    section = sf.format_ixi_section(0, EXPECTED_ESC0)
    assert "Eep_ESC_Layout" not in section


# real melody: this AK32's actual configured startup tune, decoded from
# REAL_PLAINTEXT_ESC0's offset 144-191 -- confirmed byte-exact against this same board's real
# .ixi Eep_Note_Array value (see docs/knowledge/setup-block-fields.md)
REAL_NOTE_ARRAY_ESC0 = (
    "C68G58C68E68G68C78G68G#58C68D#68G#68D#68G#68C78D#78G#78D#78D68"
    "F68A#68F68A#68D78F78D78F78A#78F78"
)


def test_decode_note_array_from_real_ak32_plaintext():
    assert sf.decode_note_array(REAL_PLAINTEXT_ESC0) == REAL_NOTE_ARRAY_ESC0


def test_decode_note_array_empty_when_all_ff():
    plaintext = REAL_PLAINTEXT_ESC0[:144] + b"\xff" * 48
    assert sf.decode_note_array(plaintext) == ""


def test_decode_note_array_too_short_raises():
    with pytest.raises(ValueError):
        sf.decode_note_array(b"\x00" * 10)


def test_decode_note_array_half_note_and_full_pause_range():
    """Real differential test, damaged Reaper (2026-09-08): typed the vendor app's own Music
    Editor script "C42 P1 P2 P4 P8 P16 P32 P64 P128" (exact syntax from its tooltip), Write Setup,
    read back. Confirms the previously-untested half-note duration and reveals pauses support 8
    lengths (wider than notes' 4) via a pitch-code (60 vs 61) acting as a x16 scale bit."""
    raw = bytes.fromhex("80fcbc7c3cfdbd7d3d") + b"\xff" * (48 - 9)
    plaintext = b"\x00" * 144 + raw
    assert sf.decode_note_array(plaintext) == "C42P1P2P4P8P16P32P64P128"


def test_format_ixi_section_includes_note_array_when_given():
    section = sf.format_ixi_section(0, EXPECTED_ESC0, note_array=REAL_NOTE_ARRAY_ESC0)
    assert section.rstrip("\n").endswith(f"Eep_Note_Array={REAL_NOTE_ARRAY_ESC0}")


def test_format_ixi_section_omits_note_array_line_when_not_given():
    section = sf.format_ixi_section(0, EXPECTED_ESC0)
    assert "Eep_Note_Array" not in section


def test_extract_identity_strings_from_real_ak32_plaintext():
    layout, cpu = sf.extract_identity_strings(REAL_PLAINTEXT_ESC0)
    assert layout == "Aikon_AK32_4IN1_35A_6S_V1_0"
    assert cpu == "STM32F051x6"


def test_extract_identity_strings_never_returns_binary_noise_as_layout():
    """Regression test: binary config bytes coincidentally fall in the
    printable-ASCII range often enough that a laxer non-empty check picked up
    noise from the numeric fields before the real '#'-delimited string —
    confirmed live against real AK32 plaintext during development."""
    # bytes before the first real '#' (offset 0x23 in this real capture) are pure
    # config data, no delimiters at all, but the incomplete plaintext still has a
    # trailing garbage byte pattern if truncated mid-field — this must return the
    # real layout name, not a fragment of the leading binary region
    layout, _ = sf.extract_identity_strings(REAL_PLAINTEXT_ESC0)
    assert layout is not None
    assert all(32 <= ord(c) < 127 for c in layout)  # must be clean printable text, not \x00 noise


def test_extract_identity_strings_returns_none_for_plaintext_with_no_delimiters():
    assert sf.extract_identity_strings(bytes(192)) == (None, None)
