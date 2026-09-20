"""
mcp_client.py — Layer 3: Protocol Layer (Model Context Protocol - MCP Adapter).

Provides standard MCP tool, resource, and prompt registration for Ultron.
Translates MCP tool schemas into Anthropic tool_use definitions and handles execution.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from governance import default_resource_registry


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    server_name: str = "local_mcp_server"


@dataclass
class MCPResource:
    uri: str
    name: str
    description: str
    mime_type: str
    reader: Callable[[], str]


class MCPManager:
    """
    Model Context Protocol (MCP) Client & Registry.
    Implements Layer 3 of the Agentic AI Architecture.
    """

    def __init__(self, mcp_servers_dir: str = "./mcp_servers") -> None:
        self.mcp_servers_dir = Path(mcp_servers_dir)
        self.mcp_servers_dir.mkdir(parents=True, exist_ok=True)
        self._tools: dict[str, MCPTool] = {}
        self._resources: dict[str, MCPResource] = {}
        self._stdio_bridges = {}
        self._register_default_mcp_tools()
        self._load_stdio_servers()
        default_resource_registry.register_cleanup_hook(self.close_all)

    def _load_stdio_servers(self) -> None:
        """Load external MCP servers via Stdio using the mcp SDK."""
        import os
        
        def clean_schema(schema):
            if not isinstance(schema, dict): return schema
            cleaned = {}
            for k, v in schema.items():
                if k in ("$schema", "additionalProperties", "additional_properties"): continue
                if isinstance(v, dict): cleaned[k] = clean_schema(v)
                elif isinstance(v, list): cleaned[k] = [clean_schema(i) if isinstance(i, dict) else i for i in v]
                else: cleaned[k] = v
            return cleaned

        try:
            from mcp_stdio_bridge import MCPServerBridge
        except ImportError:
            print("  [MCP ERROR] Could not import MCPServerBridge. Check mcp_stdio_bridge.py.")
            return

        # 1. GitHub MCP
        gh_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")
        if gh_token:
            try:
                print("  [MCP] Starting GitHub MCP server...")
                cmd = "npx.cmd" if os.name == "nt" else "npx"
                bridge = MCPServerBridge(cmd, ["--no-install", "@modelcontextprotocol/server-github"], {"GITHUB_PERSONAL_ACCESS_TOKEN": gh_token})
                self._stdio_bridges["github"] = bridge
                for t in bridge.tools:
                    schema = clean_schema(dict(t.input_schema) if t.input_schema else {})
                    self.register_tool(
                        MCPTool(
                            name=t.name,
                            description=f"[GitHub MCP] {t.description}",
                            input_schema=schema,
                            handler=lambda args, b=bridge, tn=t.name: b.execute_tool(tn, args),
                            server_name="github_mcp_server",
                        )
                    )
                print(f"  [MCP] Loaded {len(bridge.tools)} tools from GitHub MCP.")
            except Exception as e:
                print(f"  [MCP ERROR] Failed to load GitHub MCP: {e}")
        else:
            print("  [MCP] GITHUB_PERSONAL_ACCESS_TOKEN not set in env. Skipping GitHub MCP.")

        # 2. Brave Search MCP
        brave_key = os.getenv("BRAVE_API_KEY", "")
        if brave_key:
            try:
                print("  [MCP] Starting Brave Search MCP server...")
                cmd = "npx.cmd" if os.name == "nt" else "npx"
                bridge = MCPServerBridge(cmd, ["--no-install", "@modelcontextprotocol/server-brave-search"], {"BRAVE_API_KEY": brave_key})
                self._stdio_bridges["brave"] = bridge
                for t in bridge.tools:
                    schema = clean_schema(dict(t.input_schema) if t.input_schema else {})
                    self.register_tool(
                        MCPTool(
                            name=t.name,
                            description=f"[Brave Search MCP] {t.description}",
                            input_schema=schema,
                            handler=lambda args, b=bridge, tn=t.name: b.execute_tool(tn, args),
                            server_name="brave_search_mcp",
                        )
                    )
                print(f"  [MCP] Loaded {len(bridge.tools)} tools from Brave Search MCP.")
            except Exception as e:
                print(f"  [MCP ERROR] Failed to load Brave Search MCP: {e}")
        else:
            print("  [MCP] BRAVE_API_KEY not set in env. Skipping Brave Search MCP.")

    def _register_default_mcp_tools(self) -> None:
        """Register default open-source MCP protocol tools."""

        # 1. MCP SQLite Inspector
        def mcp_sqlite_query(inp: dict[str, Any]) -> dict[str, Any]:
            db_path = inp.get("db_path", "./data/telemetry.db")
            query = inp.get("query", "SELECT name FROM sqlite_master WHERE type='table';")
            if not os.path.exists(db_path):
                return {"success": False, "output": "", "error": f"Database file not found: {db_path}"}
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                cols = [desc[0] for desc in cursor.description] if cursor.description else []
                conn.close()
                return {
                    "success": True,
                    "output": json.dumps({"columns": cols, "rows": rows[:50]}, indent=2),
                    "error": None,
                }
            except Exception as e:
                return {"success": False, "output": "", "error": str(e)}

        self.register_tool(
            MCPTool(
                name="mcp_sqlite_query",
                description="[MCP Protocol Tool] Execute a read-only SQL query on a local SQLite database.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "db_path": {"type": "string", "description": "Path to SQLite file (e.g. ./data/telemetry.db)"},
                        "query": {"type": "string", "description": "SQL query to execute"},
                    },
                    "required": ["query"],
                },
                handler=mcp_sqlite_query,
                server_name="sqlite_mcp_server",
            )
        )

        # 2. MCP Fast Web Fetcher
        def mcp_fetch_url(inp: dict[str, Any]) -> dict[str, Any]:
            url = inp.get("url", "").strip()
            if not url:
                return {"success": False, "output": "", "error": "URL required."}
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UltronMCP/2.0"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw_html = resp.read().decode("utf-8", errors="replace")
                    import re
                    text = re.sub(r"<script.*?>.*?</script>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r"<.*?>", " ", text)
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    clean_text = "\n".join(lines[:200])
                    return {"success": True, "output": clean_text[:4000], "error": None}
            except Exception as e:
                return {"success": False, "output": "", "error": f"MCP Fetch error: {e}"}

        self.register_tool(
            MCPTool(
                name="mcp_fetch_url",
                description="[MCP Protocol Tool] Fetch raw text content from a web URL directly via HTTP.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                    },
                    "required": ["url"],
                },
                handler=mcp_fetch_url,
                server_name="fetch_mcp_server",
            )
        )

    def register_tool(self, tool: MCPTool) -> None:
        self._tools[tool.name] = tool

    def register_resource(self, resource: MCPResource) -> None:
        self._resources[resource.uri] = resource

    def get_anthropic_schemas(self) -> list[dict[str, Any]]:
        """Return MCP tools converted to Anthropic tool_use schemas."""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "name": tool.name,
                "description": f"{tool.description} (Server: {tool.server_name})",
                "input_schema": tool.input_schema,
            })
        return schemas

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute an MCP tool call."""
        if name not in self._tools:
            return {"success": False, "output": "", "error": f"MCP tool not found: {name}"}
        return self._tools[name].handler(arguments)

    def list_resources(self) -> list[dict[str, str]]:
        return [
            {
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
                "mime_type": r.mime_type,
            }
            for r in self._resources.values()
        ]

    def read_resource(self, uri: str) -> str:
        if uri not in self._resources:
            raise KeyError(f"MCP Resource not found: {uri}")
        return self._resources[uri].reader()

    def close_all(self) -> None:
        """Deterministically terminates and cleans up all active MCP stdio bridges."""
        for name, bridge in list(self._stdio_bridges.items()):
            try:
                if hasattr(bridge, "close"):
                    bridge.close()
                elif hasattr(bridge, "loop") and bridge.loop.is_running():
                    bridge.loop.call_soon_threadsafe(bridge.loop.stop)
            except Exception:
                pass
        self._stdio_bridges.clear()
