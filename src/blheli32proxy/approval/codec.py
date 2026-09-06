"""Translation between real wire bytes and the schema-agnostic ActivationRequest/
Response model (models.py).

PLACEHOLDER SCHEMA — see PLAN.md §4. The real BLHeliSuite32xl activation request's
exact wire format (hostname, path, body encoding) was not recoverable from static
analysis of the binary and has not yet been captured live. This codec is
deliberately permissive on decode (tries several plausible JSON field-name
variants, never raises on unrecognized input) and clearly documents an
easily-replaceable encode step, so that once the real format is captured
(PLAN.md §5 phase 2), only this file needs to change — the server and policy
engine do not need to know or care about the wire format.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from .models import ActivationRequest, ActivationResponse

# CONFIRMED real endpoint, captured live 2026-09-04 via tcpdump + SSLKEYLOGFILE
# decryption (see PLAN.md §4): BLHeliSuite32xl's "check for updates" action (and,
# per the same capture, entering the Flash tab — no separate endpoint was found
# for either) sends:
#   GET/HEAD https://blheli.org/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044
# over HTTP/2 (ALPN offers "h2,http/1.1" — http/1.1 fallback is acceptable to the
# client, confirmed from the same capture, so this project's HTTP/1.1-only server
# does not need HTTP/2 support). `v=1044` matches the app's own version 1.0.4.4.
# The confirmed error response body (content-type text/html) is BLHeli's own
# small text format, NOT JSON:
#   SERVER>text=Server is down for maintenance. Please try again later. Thank you for your patience.;
# This is a distinct, simpler protocol from the still-unconfirmed ESC-activation
# call (which needs an actual flash+activate attempt to capture) — the generic
# JSON-based decode_request()/encode_response() below remain a placeholder for
# that separate, still-unknown endpoint.
STATUS_CHECK_PATH_PREFIX = "/BLHeli32_2017_1/status.php"


def is_status_check_request(path: str) -> bool:
    return urlparse(path).path == STATUS_CHECK_PATH_PREFIX


def decode_status_check_query(path: str) -> dict[str, str]:
    """Parse the confirmed `p`/`v` query parameters from a status-check request."""
    query = parse_qs(urlparse(path).query)
    return {k: v[0] for k, v in query.items() if v}


def encode_status_check_response(message: str | None = None) -> bytes:
    """Encode a response in BLHeli's own confirmed `SERVER>key=value;...;` format.

    Only the error/maintenance case is confirmed from real traffic (`message` set
    to the exact captured string reproduces it exactly). The "no update needed,
    proceed normally" case has never been observed — passing `message=None`
    returns an empty body as an **unverified guess** at what that looks like
    (empty-body-means-fine is a common convention for this kind of ping, but this
    has not been confirmed against the real app's actual behavior on receiving
    one). Verify this empirically once possible, per PLAN.md §4.
    """
    if message is None:
        return b""
    safe_message = message.replace(";", "").replace("=", "")
    return f"SERVER>text={safe_message};".encode("utf-8")

# Plausible field-name variants to check, in order, since the real names are
# unknown. Extend this list once real traffic is captured rather than guessing
# further — see PLAN.md §4.
_UUID_KEYS = ("uuid", "UUID", "escUuid", "esc_uuid", "deviceId", "device_id")
_TYPE_KEYS = ("escType", "esc_type", "type", "model", "escModel")
_FIRMWARE_KEYS = ("firmware", "firmwareName", "firmware_name", "fw")


def decode_request(*, path: str, headers: dict[str, str], body: bytes) -> ActivationRequest:
    """Best-effort decode of an inbound activation request. Never raises —
    falls back to an all-None request (still logged in full by the server) if
    the body isn't recognizable JSON."""
    esc_type = uuid = firmware_name = None
    if body:
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = None
        if isinstance(data, dict):
            uuid = _first_present(data, _UUID_KEYS)
            esc_type = _first_present(data, _TYPE_KEYS)
            firmware_name = _first_present(data, _FIRMWARE_KEYS)
    return ActivationRequest(
        esc_type=esc_type,
        uuid=uuid,
        firmware_name=firmware_name,
        raw_body=body,
        raw_headers=dict(headers),
        raw_path=path,
    )


def _first_present(data: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in data and data[key] is not None:
            return str(data[key])
    return None


def encode_response(response: ActivationResponse) -> bytes:
    """Placeholder response encoding: a generic JSON body. Replace with the
    real schema once captured — see module docstring."""
    payload = {
        "approved": response.approved,
        "success": response.approved,  # common alternate field name, included defensively
        "remaining": response.remaining,
        "message": response.message,
    }
    return json.dumps(payload).encode("utf-8")
