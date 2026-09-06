"""CLI tests that don't need real hardware: argument parsing, and the
archive-write safety refusal in `dump-flash` (safety-critical, so it gets a
real automated test rather than only the one-off manual check from chat)."""

from blheli32proxy import cli

# same real confirmed-field values as tests/test_setup_fields.py's EXPECTED_ESC0
REAL_ESC0_FIELDS = {
    "Eep_Pgm_Direction": 1,
    "Eep_Pgm_Rampup_Pwr": 50,
    "Eep_Pgm_Pwm_Freq": 48,
    "Eep_Pgm_Comm_Timing": 0,
    "Eep_Pgm_Demag_Comp": 2,
    "Eep_Pgm_Ppm_Min_Throttle": 1014,
    "Eep_Pgm_Ppm_Center_Throttle": 1500,
    "Eep_Pgm_Ppm_Max_Throttle": 1985,
    "Eep_Pgm_Enable_Throttle_Cal": 1,
    "Eep_Pgm_Temp_Prot_Enable": 140,
    "Eep_Pgm_Beep_Strength": 40,
    "Eep_Pgm_Beacon_Strength": 70,
    "Eep_Pgm_Beacon_Delay": 600,
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
            "dump-flash",
            "--port",
            "/dev/null",
            "--end",
            "0x10",
            "--out",
            str(archive_dir / "evil.bin"),
        ]
    )
    result = cli._cmd_dump_flash(args)
    assert result == 1
    captured = capsys.readouterr()
    assert "Refusing to write into the archived BLHeli directory" in captured.err


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
            "dump-flash",
            "--port",
            "/dev/nonexistent-port-for-test",
            "--end",
            "0x10",
            "--out",
            str(tmp_path / "dump.bin"),
        ]
    )
    try:
        cli._cmd_dump_flash(args)
    except Exception:
        pass  # expected: no real serial port to open
    captured = capsys.readouterr()
    assert "Refusing to write" not in captured.err


def test_dump_flash_warns_when_archive_dir_unset(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(cli.ARCHIVE_DIR_ENV_VAR, raising=False)
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "dump-flash",
            "--port",
            "/dev/nonexistent-port-for-test",
            "--end",
            "0x10",
            "--out",
            str(tmp_path / "dump.bin"),
        ]
    )
    try:
        cli._cmd_dump_flash(args)
    except Exception:
        pass  # expected: no real serial port to open
    captured = capsys.readouterr()
    assert f"${cli.ARCHIVE_DIR_ENV_VAR} is not set" in captured.err


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


def test_list_test_firmware_no_dir_no_env_var_is_an_error(monkeypatch, capsys):
    monkeypatch.delenv(cli.ARCHIVE_DIR_ENV_VAR, raising=False)
    parser = cli.build_parser()
    args = parser.parse_args(["list-test-firmware"])
    result = cli._cmd_list_test_firmware(args)
    assert result == 1
    assert f"${cli.ARCHIVE_DIR_ENV_VAR} is not set" in capsys.readouterr().err


def test_list_test_firmware_rejects_non_directory(tmp_path, capsys):
    not_a_dir = tmp_path / "not_a_directory.Hex"
    not_a_dir.write_bytes(b"")
    parser = cli.build_parser()
    args = parser.parse_args(["list-test-firmware", "--dir", str(not_a_dir)])
    result = cli._cmd_list_test_firmware(args)
    assert result == 1
    assert "Not a directory" in capsys.readouterr().err


def test_probe_flash_and_dump_flash_registered_in_parser():
    parser = cli.build_parser()
    args = parser.parse_args(["probe-flash", "--port", "/dev/ttyACM0"])
    assert args.func is cli._cmd_probe_flash
    assert args.address == "0x0000"
    assert args.length == 16

    args2 = parser.parse_args(["dump-flash", "--port", "/dev/ttyACM0", "--end", "0x100", "--out", "x.bin"])
    assert args2.func is cli._cmd_dump_flash
