"""Desktop contract tests; these do not prove iOS WebView or lock-screen behavior."""
import asyncio
import json

import pytest

from ios.app.coding2api_ios import connection


@pytest.mark.parametrize("status,payload", [
    (200, connection.IDENTITY), (200, {"status": "ok"}),
    (302, connection.IDENTITY), (200, b"not json"),
])
def test_probe_validates_identity(monkeypatch, status, payload):
    closed = []

    class Response:
        def read(self, limit):
            assert limit == 4097
            return payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    Response.status = status

    class Client:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("127.0.0.1", 8001, 3)

        def request(self, method, path):
            assert (method, path) == ("GET", connection.IDENTITY_PATH)

        def getresponse(self):
            return Response()

        def close(self):
            closed.append(True)

    monkeypatch.setattr(connection.http.client, "HTTPConnection", Client)
    if status == 200 and payload == connection.IDENTITY:
        assert connection.probe_daemon() == "http://127.0.0.1:8001"
    else:
        with pytest.raises(ValueError):
            connection.probe_daemon()
    assert closed == [True]


def test_probe_closes_on_network_failure(monkeypatch):
    closed = []

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args):
            raise OSError("unavailable")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(connection.http.client, "HTTPConnection", Client)
    with pytest.raises(OSError, match="unavailable"):
        connection.probe_daemon()
    assert closed == [True]


@pytest.mark.parametrize("scope,identity", [
    ({"type": "http", "path": connection.IDENTITY_PATH, "method": "GET"}, True),
    ({"type": "http", "path": connection.IDENTITY_PATH, "method": "POST"}, False),
    ({"type": "http", "path": "/v1/models", "method": "GET"}, False),
    ({"type": "lifespan"}, False),
])
def test_wrapper_preserves_upstream_and_lifespan(scope, identity):
    messages = []
    forwarded = []

    async def upstream(scope, receive, send):
        forwarded.append(scope)

    async def receive():
        raise AssertionError("This test does not request input events")

    async def send(message):
        messages.append(message)

    asyncio.run(connection.DaemonIdentity(upstream)(scope, receive, send))
    if identity:
        assert not forwarded
        assert messages[0]["status"] == 200
        assert json.loads(messages[1]["body"]) == connection.IDENTITY
    else:
        assert forwarded == [scope]
        assert not messages
