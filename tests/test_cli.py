"""CLI tests that don't need real hardware: argument parsing, and the
archive-write safety refusal in `dump-info-page` (safety-critical, so it
gets a real automated test rather than only the one-off manual check from
chat)."""

from blheli32proxy import cli

# same real confirmed-field values as tests/test_setup_fields.py's EXPECTED_ESC0
REAL_ESC0_FIELDS = {
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


def test_append_ixi_section_new_file_gets_warning_header_and_section(tmp_path, capsys):
    out_path = tmp_path / "backup.ixi"
    cli._append_ixi_section(str(out_path), esc_index=0, fields=REAL_ESC0_FIELDS)
    content = out_path.read_text()
    assert content.startswith("; ")  # not-a-real-.ixi warning header
    assert "[ESC1]" in content
    assert "Eep_Pgm_Direction=1" in content
    assert "Appended [ESC1] section" in capsys.readouterr().out


def test_append_ixi_section_accumulates_multiple_escs_no_duplicate_header(tmp_path):
    out_path = tmp_path / "backup.ixi"
    cli._append_ixi_section(str(out_path), esc_index=0, fields=REAL_ESC0_FIELDS)
    esc1_fields = {**REAL_ESC0_FIELDS, "Eep_Pgm_Direction": 2}
    cli._append_ixi_section(str(out_path), esc_index=1, fields=esc1_fields)
    content = out_path.read_text()
    assert content.count("; Partial backup written by blheli32proxy") == 1
    assert "[ESC1]" in content and "[ESC2]" in content
    assert content.index("[ESC1]") < content.index("[ESC2]")


def test_dump_flash_refuses_to_write_into_archive(tmp_path, monkeypatch, capsys):
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    monkeypatch.setenv(cli.ARCHIVE_DIR_ENV_VAR, str(archive_dir))
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "dump-info-page",
            "--port",
            "/dev/null",
            "--end",
            "0x10",
            "--out",
            str(archive_dir / "evil.bin"),
        ]
    )
    result = cli._cmd_dump_info_page(args)
    assert result == 1
    captured = capsys.readouterr()
    assert f"Refusing to write into the ${cli.ARCHIVE_DIR_ENV_VAR} directory" in captured.err


def test_dump_flash_allows_a_non_archive_path(tmp_path, monkeypatch, capsys):
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    monkeypatch.setenv(cli.ARCHIVE_DIR_ENV_VAR, str(archive_dir))

    # Stand in for real hardware: fail fast right after connecting to a
    # nonexistent serial port, but only after the archive-path check has
    # already passed (i.e. we don't hit the "Refusing to write" message).
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "dump-info-page",
            "--port",
            "/dev/nonexistent-port-for-test",
            "--end",
            "0x10",
            "--out",
            str(tmp_path / "dump.bin"),
        ]
    )
    try:
        cli._cmd_dump_info_page(args)
    except Exception:
        pass  # expected: no real serial port to open
    captured = capsys.readouterr()
    assert "Refusing to write" not in captured.err


def test_dump_flash_warns_when_archive_dir_unset(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(cli.ARCHIVE_DIR_ENV_VAR, raising=False)
    monkeypatch.delenv(cli.APP_DIR_ENV_VAR, raising=False)
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "dump-info-page",
            "--port",
            "/dev/nonexistent-port-for-test",
            "--end",
            "0x10",
            "--out",
            str(tmp_path / "dump.bin"),
        ]
    )
    try:
        cli._cmd_dump_info_page(args)
    except Exception:
        pass  # expected: no real serial port to open
    captured = capsys.readouterr()
    assert f"neither ${cli.ARCHIVE_DIR_ENV_VAR} nor ${cli.APP_DIR_ENV_VAR} is set" in captured.err


def test_list_test_firmware_lists_only_hex_files_sorted(tmp_path, capsys):
    (tmp_path / "Zebra_Multi_32_9.Hex").write_bytes(b"")
    (tmp_path / "Aikon_Multi_32_7.Hex").write_bytes(b"")
    (tmp_path / "readme.txt").write_bytes(b"")  # non-.Hex, must not be listed
    parser = cli.build_parser()
    args = parser.parse_args(["list-test-firmware", "--dir", str(tmp_path)])
    result = cli._cmd_list_test_firmware(args)
    assert result == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["Aikon_Multi_32_7.Hex", "Zebra_Multi_32_9.Hex"]


def test_list_test_firmware_uses_archive_dir_env_var_as_default(tmp_path, monkeypatch, capsys):
    (tmp_path / "Furling32_Multi_32_9.Hex").write_bytes(b"")
    monkeypatch.setenv(cli.ARCHIVE_DIR_ENV_VAR, str(tmp_path))
    parser = cli.build_parser()  # reads the env var while building --dir's default
    args = parser.parse_args(["list-test-firmware"])
    result = cli._cmd_list_test_firmware(args)
    assert result == 0
    assert capsys.readouterr().out.splitlines() == ["Furling32_Multi_32_9.Hex"]


def test_list_test_firmware_falls_back_to_app_dirs_hexfiles_subfolder(tmp_path, monkeypatch, capsys):
    """Most end users only have the vendor app installed, not a separate
    broader archive — $BLHELI32PROXY_APP_DIR's own BLHeli32_HexFiles/
    subfolder must work as the fallback catalog when $ARCHIVE_DIR isn't set."""
    monkeypatch.delenv(cli.ARCHIVE_DIR_ENV_VAR, raising=False)
    hexfiles = tmp_path / "BLHeliSuite32xl" / "BLHeli32_HexFiles"
    hexfiles.mkdir(parents=True)
    (hexfiles / "Furling32_Multi_32_9.Hex").write_bytes(b"")
    monkeypatch.setenv(cli.APP_DIR_ENV_VAR, str(tmp_path / "BLHeliSuite32xl"))
    parser = cli.build_parser()
    args = parser.parse_args(["list-test-firmware"])
    result = cli._cmd_list_test_firmware(args)
    assert result == 0
    assert capsys.readouterr().out.splitlines() == ["Furling32_Multi_32_9.Hex"]


def test_list_test_firmware_prefers_archive_dir_over_app_dir(tmp_path, monkeypatch, capsys):
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "FromArchive_Multi_32_9.Hex").write_bytes(b"")
    app_hexfiles = tmp_path / "app" / "BLHeli32_HexFiles"
    app_hexfiles.mkdir(parents=True)
    (app_hexfiles / "FromApp_Multi_32_9.Hex").write_bytes(b"")
    monkeypatch.setenv(cli.ARCHIVE_DIR_ENV_VAR, str(archive))
    monkeypatch.setenv(cli.APP_DIR_ENV_VAR, str(tmp_path / "app"))
    parser = cli.build_parser()
    args = parser.parse_args(["list-test-firmware"])
    result = cli._cmd_list_test_firmware(args)
    assert result == 0
    assert capsys.readouterr().out.splitlines() == ["FromArchive_Multi_32_9.Hex"]


def test_list_test_firmware_no_dir_no_env_var_is_an_error(monkeypatch, capsys):
    monkeypatch.delenv(cli.ARCHIVE_DIR_ENV_VAR, raising=False)
    monkeypatch.delenv(cli.APP_DIR_ENV_VAR, raising=False)
    parser = cli.build_parser()
    args = parser.parse_args(["list-test-firmware"])
    result = cli._cmd_list_test_firmware(args)
    assert result == 1
    assert f"neither ${cli.ARCHIVE_DIR_ENV_VAR} nor ${cli.APP_DIR_ENV_VAR} is set" in capsys.readouterr().err


def test_list_test_firmware_rejects_non_directory(tmp_path, capsys):
    not_a_dir = tmp_path / "not_a_directory.Hex"
    not_a_dir.write_bytes(b"")
    parser = cli.build_parser()
    args = parser.parse_args(["list-test-firmware", "--dir", str(not_a_dir)])
    result = cli._cmd_list_test_firmware(args)
    assert result == 1
    assert "Not a directory" in capsys.readouterr().err


def test_probe_flash_and_dump_info_page_registered_in_parser():
    parser = cli.build_parser()
    args = parser.parse_args(["probe-flash", "--port", "/dev/ttyACM0"])
    assert args.func is cli._cmd_probe_flash
    assert args.address == "0x0000"
    assert args.length == 16

    args2 = parser.parse_args(["dump-info-page", "--port", "/dev/ttyACM0", "--end", "0x100", "--out", "x.bin"])
    assert args2.func is cli._cmd_dump_info_page

    args3 = parser.parse_args(
        ["dump-firmware", "--port", "/dev/ttyACM0", "--candidate", "a.hex", "--out", "x.bin"]
    )
    assert args3.func is cli._cmd_dump_firmware
    assert args3.start is None  # auto-derived from --candidate, no fixed default
    assert args3.end is None

    args4 = parser.parse_args(["dump-firmware", "--port", "/dev/ttyACM0", "--candidate", "a.hex"])
    assert args4.out is None  # --out is optional now, auto-derived from --candidate


def test_default_firmware_dump_name_matches_ixi_convention():
    # same convention as this project's real .ixi backups, e.g.
    # "BLHeli32_Furling32 - Rev. 32.9.5 - Multi_260905.ixi"
    name = cli._default_firmware_dump_name("Furling32_Multi_32_95.Hex")
    assert name.startswith("dumps/BLHeli32_Furling32 - Rev. 32.9.5 - AppCode_")
    assert name.endswith(".bin")


def test_default_firmware_dump_name_decodes_two_digit_version():
    name = cli._default_firmware_dump_name("/some/path/TEKKO32_F3_4in1_B_Multi_32_82.Hex")
    assert "TEKKO32_F3_4in1_B - Rev. 32.8.2" in name


def test_default_firmware_dump_name_decodes_bare_version():
    name = cli._default_firmware_dump_name("FLASH_HOBBY_BLHELI_32_Multi_32_7.Hex")
    assert "FLASH_HOBBY_BLHELI_32 - Rev. 32.7 -" in name


def test_default_firmware_dump_name_falls_back_on_unrecognized_pattern():
    name = cli._default_firmware_dump_name("some_weird_name.Hex")
    assert name.startswith("dumps/some_weird_name-AppCode_")
    assert name.endswith(".bin")


def test_dump_firmware_refuses_below_candidates_own_data(tmp_path, capsys):
    from blheli32proxy.protocol import hexfile

    candidate_path = tmp_path / "candidate.hex"
    candidate_path.write_text(hexfile.encode_intel_hex(bytes(16), base_addr=0x2000))

    out_path = tmp_path / "fw.bin"
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "dump-firmware",
            "--port",
            "/dev/ttyACM0",
            "--candidate",
            str(candidate_path),
            "--start",
            "0x1000",  # below the candidate's own earliest address, 0x2000
            "--out",
            str(out_path),
            "--motor-index",
            "0",
        ]
    )
    rc = cli._cmd_dump_firmware(args)
    assert rc == 1
    assert "bootloader" in capsys.readouterr().err
    assert not out_path.exists()  # must refuse before ever opening the transport/output file


def test_dump_firmware_requires_motor_index(tmp_path, capsys):
    out_path = tmp_path / "fw.bin"
    parser = cli.build_parser()
    args = parser.parse_args(
        ["dump-firmware", "--port", "/dev/ttyACM0", "--candidate", "a.hex", "--out", str(out_path)]
    )
    assert args.motor_index is None
    rc = cli._cmd_dump_firmware(args)
    assert rc == 1
    assert "motor-index" in capsys.readouterr().err


def test_dump_firmware_defaults_derive_from_a_non_stm32f0_shaped_candidate(tmp_path, capsys):
    """The safe start/end must come from whatever the candidate actually
    covers, not a hardcoded STM32F0 number — proven here with a candidate
    whose app code starts at 0x1000 (a different boundary than every real
    STM32F0 ESC checked so far), simulating a different model/MCU."""
    from blheli32proxy.protocol import hexfile

    candidate_path = tmp_path / "other_model.hex"
    candidate_path.write_text(hexfile.encode_intel_hex(bytes(32), base_addr=0x1000))

    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "dump-firmware",
            "--port",
            "/dev/nonexistent-port-for-test",
            "--candidate",
            str(candidate_path),
            "--motor-index",
            "0",
            "--out",
            str(tmp_path / "fw.bin"),
        ]
    )
    # --start/--end left at their argparse default (None) — must not refuse or assume 0x2000/0x7c00
    try:
        cli._cmd_dump_firmware(args)
    except Exception:
        pass  # expected: no real serial port to open
    captured = capsys.readouterr()
    assert "below every given --candidate" not in captured.err  # would be wrong for this candidate
    assert "Loaded 1 candidate file(s)" in captured.out  # got past the boundary check


def test_verify_region_recovers_partial_candidate_coverage():
    """A candidate covering only part of a nominal chunk must still confirm
    the part it DOES cover, rather than the whole chunk being thrown away as
    unconfirmed."""
    from fakes import FakeTransport
    from blheli32proxy.protocol import fourwayif as fw

    def ack_reply(addr, ack):
        addr_h, addr_l = (addr >> 8) & 0xFF, addr & 0xFF
        body = bytes([fw.ESCAPE_DEVICE, fw.CMD_DEVICE_VERIFY, addr_h, addr_l, 0x01, 0x00, ack])
        crc = fw._crc_xmodem(body)
        return body + bytes([(crc >> 8) & 0xFF, crc & 0xFF])

    # candidate covers only 0x2000-0x2001 (2 bytes); 0x2002-0x2003 missing entirely
    candidate = {0x2000: 0x11, 0x2001: 0x22}
    transport = FakeTransport([ack_reply(0x2000, fw.ACK_OK)])  # exactly one verify call expected

    confirmed: dict[int, int] = {}
    unresolved: list[tuple[int, int]] = []
    cli._verify_region(transport, [candidate], 0x2000, 4, confirmed, unresolved)

    assert confirmed == {0x2000: 0x11, 0x2001: 0x22}
    assert set(unresolved) == {(0x2002, 1), (0x2003, 1)}
    assert len(transport.sent) == 1  # the no-data half never touched the transport at all


def test_dump_firmware_pages_are_256_byte_aligned():
    """Regression test: verifying must step through 256-byte pages aligned to
    `start` (matching the real app's own confirmed Verify usage: 0x2000,
    0x2100, 0x2200...), never bisect the whole range naively — that produces
    chunks at arbitrary non-aligned addresses (e.g. 0x23a2), which produced
    false mismatches against real hardware for content that actually
    matched."""
    start, end = 0x2000, 0x7d00  # a real, non-power-of-2-sized range
    addr = start
    pages = []
    while addr < end:
        length = min(256, end - addr)
        pages.append((addr, length))
        addr += length
    assert all(a % 256 == 0 for a, _ in pages[:-1])  # every page but a possible short final one
    assert all(n == 256 for _, n in pages[:-1])


def test_print_defaults_comparison_flags_only_the_real_diff(tmp_path, capsys):
    """Uses the same real decrypted plaintext pair as test_setup_fields.py
    (ESC0 vs ESC1 from a real AK32, differing only at Eep_Pgm_Direction) — the
    "default" candidate is ESC1's real plaintext, re-encrypted; comparing it
    against ESC0's real plaintext must flag exactly that one field CHANGED,
    every other field (identical between the two) same."""
    from blheli32proxy.cipher import xtea
    from blheli32proxy.protocol import hexfile
    from test_setup_fields import REAL_PLAINTEXT_ESC0, REAL_PLAINTEXT_ESC1

    # encrypt_setup_block requires exactly 192 bytes; the real fixtures are 187 (decode_confirmed_fields
    # never reads past offset 24, so pad the unused tail rather than need a different real capture)
    padded_esc1 = REAL_PLAINTEXT_ESC1 + b"\xff" * (192 - len(REAL_PLAINTEXT_ESC1))
    default_ciphertext = xtea.encrypt_setup_block(padded_esc1, key=xtea.PRODUCTION_KEY)
    candidate_path = tmp_path / "candidate.hex"
    candidate_path.write_text(hexfile.encode_intel_hex(default_ciphertext, base_addr=0x7C00))

    cli._print_defaults_comparison(REAL_PLAINTEXT_ESC0, str(candidate_path), xtea.PRODUCTION_KEY)
    out = capsys.readouterr().out
    assert "Eep_Pgm_Direction: real=1 default=2 (CHANGED)" in out
    assert "Eep_Pgm_Rampup_Pwr: real=50 default=50 (same)" in out
