import asyncio
import json
from types import SimpleNamespace

import pytest

from src.core import mcp_client


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def install_fake_session(monkeypatch, response):
    class Session:
        def __init__(self, read, write):
            self.response = response

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def initialize(self):
            return None

        async def call_tool(self, name, arguments):
            return self.response

    monkeypatch.setattr(mcp_client, "stdio_client", lambda server: AsyncContext(("read", "write")))
    monkeypatch.setattr(mcp_client, "ClientSession", Session)


def test_mcp_client_handles_empty_calls_and_structured_results(monkeypatch):
    assert mcp_client.call_mcp_tools([]) == []
    install_fake_session(monkeypatch, SimpleNamespace(
        isError=False, structuredContent={"value": 1}, content=[]
    ))
    assert mcp_client.call_mcp_tools([("tool", {})]) == [{"value": 1}]


def test_mcp_client_parses_text_json_and_formats_unicode(monkeypatch):
    install_fake_session(monkeypatch, SimpleNamespace(
        isError=False, structuredContent=None,
        content=[SimpleNamespace(text=json.dumps({"message": "café"}))],
    ))
    result = asyncio.run(mcp_client._call_tools([("tool", {})]))
    assert result == [{"message": "café"}]
    assert "café" in mcp_client.format_mcp_result(result[0])


def test_mcp_client_reports_invalid_json_and_tool_errors(monkeypatch):
    install_fake_session(monkeypatch, SimpleNamespace(
        isError=False, structuredContent=None, content=[SimpleNamespace(text="not json")]
    ))
    with pytest.raises(RuntimeError, match="returned invalid JSON"):
        asyncio.run(mcp_client._call_tools([("bad-json", {})]))

    install_fake_session(monkeypatch, SimpleNamespace(
        isError=True, structuredContent=None, content=[SimpleNamespace(text="bad arguments")]
    ))
    with pytest.raises(RuntimeError, match="MCP tool 'invalid' failed: bad arguments"):
        asyncio.run(mcp_client._call_tools([("invalid", {})]))


def test_mcp_sync_bridge_rejects_an_active_event_loop():
    async def call_inside_loop():
        with pytest.raises(RuntimeError, match="cannot run inside an active event loop"):
            mcp_client.call_mcp_tools([("tool", {})])

    asyncio.run(call_inside_loop())
