"""The two files install.ps1 writes that the monitor cannot run without."""
import pytest

import monitor


def test_the_secret_is_hex_with_whitespace_around_it_allowed(tmp_path):
    f = tmp_path / "secret.txt"
    f.write_text("0a0B0c\r\n", encoding="utf-8")
    assert monitor.load_secret(f) == b"\x0a\x0b\x0c"


def test_a_missing_or_unusable_secret_is_empty_so_no_code_is_accepted(tmp_path):
    f = tmp_path / "secret.txt"
    assert monitor.load_secret(f) == b""
    f.write_text("not hex", encoding="utf-8")
    assert monitor.load_secret(f) == b""
    f.write_text("abc", encoding="utf-8")  # odd number of digits
    assert monitor.load_secret(f) == b""
    f.write_text("", encoding="utf-8")
    assert monitor.load_secret(f) == b""


def test_the_target_user_is_read_as_written_by_powershell(tmp_path):
    f = tmp_path / "target_user.txt"
    f.write_bytes(b"\xef\xbb\xbfkid\r\n")  # utf-8 BOM and CRLF, as Out-File leaves it
    assert monitor.load_target_user(f) == "kid"


def test_a_missing_or_empty_target_user_is_an_error_not_a_default(tmp_path):
    f = tmp_path / "target_user.txt"
    with pytest.raises(ValueError):
        monitor.load_target_user(f)
    f.write_text(" \n", encoding="utf-8")
    with pytest.raises(ValueError):
        monitor.load_target_user(f)
