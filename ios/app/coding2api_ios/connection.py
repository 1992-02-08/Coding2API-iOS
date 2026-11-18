"""Loopback-only daemon discovery; no credentials or database access in the IPA."""
from __future__ import annotations

import http.client
import json

DAEMON_URL = "http://127.0.0.1:8001"
IDENTITY_PATH = "/_coding2api/identity"
IDENTITY = {"application": "coding2api", "protocol": 1, "mode": "daemon"}


def probe_daemon():
    # HTTPConnection bypasses environment proxies and never follows redirects.
    connection = http.client.HTTPConnection("127.0.0.1", 8001, timeout=3)
    try:
        connection.request("GET", IDENTITY_PATH)
        response = connection.getresponse()
        if response.status != 200 or json.loads(response.read(4097)) != IDENTITY:
            raise ValueError("8001 不是兼容的 Coding2API 常驻服务")
    finally:
        connection.close()
    return DAEMON_URL


class DaemonIdentity:
    """ASGI wrapper outside the upstream SPA catch-all, including lifespan forwarding."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http" and scope["path"] == IDENTITY_PATH
                and scope["method"] == "GET"):
            body = json.dumps(IDENTITY).encode()
            await send({"type": "http.response.start", "status": 200, "headers": [
                (b"content-type", b"application/json"), (b"cache-control", b"no-store"),
            ]})
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
