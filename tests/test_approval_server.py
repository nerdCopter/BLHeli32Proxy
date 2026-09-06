"""Approval server integration tests: real HTTP requests against a real (local,
plain-HTTP) instance of the server — no mocking of http.server itself."""

import json
import threading
import urllib.request

import pytest

from blheli32proxy.approval.policy import AllowAllPolicy, CountedLicensePolicy
from blheli32proxy.approval.server import create_server


@pytest.fixture
def running_server():
    def _start(policy):
        httpd = create_server(policy, host="127.0.0.1", port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return httpd

    servers = []

    def factory(policy):
        httpd = _start(policy)
        servers.append(httpd)
        return httpd

    yield factory

    for httpd in servers:
        httpd.shutdown()
        httpd.server_close()


def _post(port: int, path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def test_server_approves_with_allow_all_policy(running_server):
    httpd = running_server(AllowAllPolicy())
    port = httpd.server_address[1]
    result = _post(port, "/activate", {"uuid": "abc", "escType": "ARM"})
    assert result["approved"] is True


def test_server_enforces_counted_policy(running_server, tmp_path):
    policy = CountedLicensePolicy(tmp_path / "state.json", initial_count=1)
    httpd = running_server(policy)
    port = httpd.server_address[1]

    first = _post(port, "/activate", {"uuid": "u1", "escType": "ARM"})
    assert first["approved"] is True
    assert first["remaining"] == 0

    second = _post(port, "/activate", {"uuid": "u2", "escType": "ARM"})
    assert second["approved"] is False


def test_server_handles_unrecognized_body_gracefully(running_server):
    httpd = running_server(AllowAllPolicy())
    port = httpd.server_address[1]
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/whatever",
        data=b"not json",
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        result = json.loads(resp.read())
    assert result["approved"] is True  # AllowAllPolicy doesn't care about the body


# --- CONFIRMED real status-check endpoint (see codec.py's module docstring) ---


def test_server_responds_to_confirmed_status_check_path_via_get(running_server):
    httpd = running_server(AllowAllPolicy())
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        assert resp.headers["Content-Type"] == "text/html"
        assert resp.read() == b""  # unverified "no update" guess — see codec.py


def test_server_responds_to_confirmed_status_check_path_via_head(running_server):
    httpd = running_server(AllowAllPolicy())
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044"
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        assert resp.read() == b""  # HEAD must never include a body


def test_server_status_check_does_not_go_through_the_activation_policy(running_server, tmp_path):
    # A counted policy with 0 remaining would refuse a real /activate call, but
    # the confirmed status-check endpoint isn't a licensing decision at all.
    policy = CountedLicensePolicy(tmp_path / "state.json", initial_count=0)
    httpd = running_server(policy)
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/BLHeli32_2017_1/status.php?p=BLHeliSuite32xl&v=1044"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
