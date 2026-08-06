"""Thin async MCP client wrapper used by the scheduler to call the two MCP servers.

Every call opens a short-lived streamable-HTTP session (flux F1a/F1b, "toutes
les minutes" — specs.md §9.3), invokes exactly one whitelisted tool, and
returns its result as a plain dict. No other capability (resources, prompts,
arbitrary code) is used — this is intentionally the narrowest possible
client to match the "agent sans autonomie d'action" principle (specs.md §9.4).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger("agent.mcp_clients")


class MCPCallError(RuntimeError):
    """Raised when a tool call fails or a server is unreachable — treated as UNKNOWN, never fatal."""


async def call_tool(server_url: str, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        async with streamable_http_client(server_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments or {})
    except Exception as exc:  # noqa: BLE001 — any transport/protocol failure becomes MCPCallError
        raise MCPCallError(f"{tool_name} on {server_url} failed: {exc}") from exc

    if getattr(result, "is_error", False):
        raise MCPCallError(f"{tool_name} on {server_url} returned an error result: {result}")

    structured = getattr(result, "structured_content", None)
    if structured:
        return structured

    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue

    raise MCPCallError(f"{tool_name} on {server_url} returned no parseable content")


async def safe_call(server_url: str, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Same as call_tool but never raises — logs and returns None so callers degrade to UNKNOWN."""
    try:
        return await call_tool(server_url, tool_name, arguments)
    except MCPCallError as exc:
        logger.warning("MCP call failed: %s", exc)
        return None
