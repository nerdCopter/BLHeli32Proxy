"""Approval/activation server: stands in for BLHeli's dead activation server.

Reached by redirecting the real activation hostname to this server's bind
address at the OS level (see docs/USAGE.md) once that hostname is known
(PLAN.md §4). Until then, this server logs every request it receives in full —
which doubles as a second way to discover the real wire format if the user
points the real app at it speculatively, alongside the tcpdump/strace capture
already in progress.

Uses only the standard library (http.server) — no new dependency for something
this small. TLS is optional: pass certfile/keyfile to serve HTTPS (see
docs/USAGE.md for generating a self-signed certificate); PLAN.md §6 flags that
whether the real app will trust it at all is still unverified.
"""

from __future__ import annotations

import logging
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import codec
from .policy import ApprovalPolicy

logger = logging.getLogger("blheli32proxy.approval")


def _make_handler(policy: ApprovalPolicy) -> type[BaseHTTPRequestHandler]:
    class ApprovalRequestHandler(BaseHTTPRequestHandler):
        server_version = "BLHeli32ProxyApproval/0.1"

        def _send(self, payload: bytes, *, content_type: str, include_body: bool) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if include_body:
                self.wfile.write(payload)

        def _handle(self, *, include_body: bool) -> None:
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            headers = dict(self.headers.items())
            logger.info(
                "request: %s %s headers=%r body=%r",
                self.command,
                self.path,
                headers,
                body,
            )

            if codec.is_status_check_request(self.path):
                # CONFIRMED real endpoint — see codec.py's module docstring.
                query = codec.decode_status_check_query(self.path)
                logger.info("status-check request: product=%r version=%r", query.get("p"), query.get("v"))
                # UNVERIFIED guess (empty body = "no update, proceed normally") —
                # see encode_status_check_response's docstring.
                payload = codec.encode_status_check_response(None)
                self._send(payload, content_type="text/html", include_body=include_body)
                logger.info("status-check response: empty body (unverified 'all fine' guess)")
                return

            request = codec.decode_request(path=self.path, headers=headers, body=body)
            response = policy.evaluate(request)
            payload = codec.encode_response(response)
            logger.info("response: approved=%s remaining=%s", response.approved, response.remaining)
            self._send(payload, content_type="application/json", include_body=include_body)

        def do_GET(self) -> None:  # noqa: N802 - stdlib naming convention
            self._handle(include_body=True)

        def do_HEAD(self) -> None:  # noqa: N802
            self._handle(include_body=False)

        def do_POST(self) -> None:  # noqa: N802
            self._handle(include_body=True)

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
            logger.debug(format, *args)

    return ApprovalRequestHandler


def create_server(
    policy: ApprovalPolicy,
    host: str = "0.0.0.0",
    port: int = 8443,
    certfile: str | None = None,
    keyfile: str | None = None,
) -> ThreadingHTTPServer:
    """Build (but don't start) the approval server. Call .serve_forever() on the
    result, or use it as a context manager."""
    handler_cls = _make_handler(policy)
    httpd = ThreadingHTTPServer((host, port), handler_cls)
    if certfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    return httpd
