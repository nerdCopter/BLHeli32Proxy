"""Placeholder codec tests — see codec.py docstring for why this schema is a guess."""

import json

from blheli32proxy.approval import codec
from blheli32proxy.approval.models import ActivationResponse


def test_decode_request_finds_uuid_and_type_variants():
    body = json.dumps({"uuid": "abc-123", "escType": "ARM_BLB"}).encode()
    req = codec.decode_request(path="/activate", headers={}, body=body)
    assert req.uuid == "abc-123"
    assert req.esc_type == "ARM_BLB"


def test_decode_request_handles_alternate_field_names():
    body = json.dumps({"device_id": "xyz", "type": "SIL_BLB"}).encode()
    req = codec.decode_request(path="/activate", headers={}, body=body)
    assert req.uuid == "xyz"
    assert req.esc_type == "SIL_BLB"


def test_decode_request_never_raises_on_garbage():
    req = codec.decode_request(path="/activate", headers={}, body=b"not json at all {{{")
    assert req.uuid is None
    assert req.esc_type is None
    assert req.raw_body == b"not json at all {{{"


def test_decode_request_handles_empty_body():
    req = codec.decode_request(path="/", headers={}, body=b"")
    assert req.uuid is None


def test_encode_response_round_trips_through_json():
    response = ActivationResponse(approved=True, remaining=41, message="ok")
    encoded = codec.encode_response(response)
    decoded = json.loads(encoded)
    assert decoded["approved"] is True
    assert decoded["remaining"] == 41


# --- CONFIRMED real status-check endpoint (see codec.py's module docstring) ---


def test_is_status_check_request_matches_confirmed_path():
    assert codec.is_status_check_request("/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044")
    assert codec.is_status_check_request("/BLHeli32_2017_1/status.php")


def test_is_status_check_request_rejects_other_paths():
    assert not codec.is_status_check_request("/activate")
    assert not codec.is_status_check_request("/")
    assert not codec.is_status_check_request("/BLHeli32_2017_1/status.php.evil")


def test_decode_status_check_query_extracts_confirmed_params():
    query = codec.decode_status_check_query("/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044")
    assert query == {"p": "BLHeliSuite32xl", "v": "1044"}


def test_decode_status_check_query_handles_missing_params():
    assert codec.decode_status_check_query("/BLHeli32_2017_1/status.php") == {}


def test_encode_status_check_response_matches_real_captured_bytes():
    # Exact bytes captured live 2026-09-04 via tcpdump + SSLKEYLOGFILE decryption.
    message = "Server is down for maintenance. Please try again later. Thank you for your patience."
    assert codec.encode_status_check_response(message) == f"SERVER>text={message};".encode()


def test_encode_status_check_response_empty_for_none():
    # Unverified guess (see docstring) — just confirms the documented behavior.
    assert codec.encode_status_check_response(None) == b""


def test_encode_status_check_response_strips_delimiter_characters():
    # Defensive: a message containing the format's own delimiters shouldn't break it.
    result = codec.encode_status_check_response("a;b=c")
    assert result == b"SERVER>text=abc;"
