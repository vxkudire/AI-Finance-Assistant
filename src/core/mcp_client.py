"""Synchronous bridge from LangGraph nodes to the local finance MCP server."""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


async def _call_tools(calls: list[tuple[str, dict]]) -> list[dict]:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp_server"],
        cwd=_REPOSITORY_ROOT,
        env=os.environ.copy(),
    )
    results = []
    tool_error = None
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            for name, arguments in calls:
                result = await session.call_tool(name, arguments)
                if result.isError:
                    detail = "\n".join(
                        item.text for item in result.content if getattr(item, "text", None)
                    )
                    tool_error = RuntimeError(f"MCP tool {name!r} failed: {detail or 'unknown error'}")
                    break
                structured = getattr(result, "structuredContent", None)
                if structured is not None:
                    results.append(structured)
                    continue
                text = "\n".join(
                    item.text for item in result.content if getattr(item, "text", None)
                )
                try:
                    results.append(json.loads(text))
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"MCP tool {name!r} returned invalid JSON") from exc
    if tool_error is not None:
        raise tool_error
    return results


def call_mcp_tools(calls: list[tuple[str, dict]]) -> list[dict]:
    """Call one or more local finance MCP tools over stdio in a shared session."""
    if not calls:
        return []
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call_tools(calls))
    raise RuntimeError("The synchronous LangGraph MCP bridge cannot run inside an active event loop.")


def format_mcp_result(result: dict) -> str:
    """Format MCP output for an agent's grounded context."""
    return json.dumps(result, ensure_ascii=False, default=str)
