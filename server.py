#!/usr/bin/env python3
"""
Memory LumeClaw MCP Server
JSON-RPC 2.0 over stdio — compatible with Claude Code, OpenClaw, Codex CLI
API: https://mcp.lumeclaw.ru/api/v1
"""

import sys
import json
import os
import time
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE = os.environ.get("LUMECLAW_API_BASE", "https://mcp.lumeclaw.ru/api/v1")
API_KEY  = os.environ.get("LUMECLAW_API_KEY", "")

def _api_request(method: str, path: str, body: Any = None,
                 token: Optional[str] = None) -> Any:
    url = API_BASE.rstrip("/") + "/" + path.lstrip("/")
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"{token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            err = json.loads(body_bytes)
        except Exception:
            err = {"detail": body_bytes.decode(errors="replace")}
        raise RuntimeError(f"HTTP {e.code}: {err.get('detail', str(err))}")


def _get_token() -> str:
    if not API_KEY:
        raise RuntimeError(
            "Set LUMECLAW_API_KEY environment variable"
        )
    return API_KEY


# ── Tool implementations ──────────────────────────────────────────────────────

def tool_memory_store(args: dict) -> str:
    content = args.get("content", "").strip()
    if not content:
        return "Error: content is required"
    payload = {
        "content": content,
        "category": args.get("category", "personal"),
        "tags": args.get("tags", []),
    }
    if args.get("agent_id"):
        payload["agent_id"] = args["agent_id"]
    if args.get("project_id"):
        payload["project_id"] = args["project_id"]
    tok = _get_token()
    try:
        resp = _api_request("POST", "/memory", payload, token=tok)
        return f"✅ Stored memory [{resp['id']}]\nContent: {resp['content'][:120]}"
    except RuntimeError as e:
        if "409" in str(e) or "duplicate" in str(e).lower():
            return f"ℹ️ Memory already exists (duplicate content)"
        raise


def tool_memory_search(args: dict) -> str:
    query = args.get("query", "").strip()
    if not query:
        return "Error: query is required"
    params = f"query={urllib.parse.quote(query)}&limit={args.get('limit', 5)}"
    if args.get("category"):
        params += f"&category={args['category']}"
    if args.get("agent_id"):
        params += f"&agent_id={args['agent_id']}"
    tok = _get_token()
    resp = _api_request("GET", f"/memory/search?{params}", token=tok)
    if not resp:
        return "No matching memories found."
    lines = []
    for i, m in enumerate(resp, 1):
        score_pct = round(float(m.get("score", 0)) * 100, 1)
        lines.append(f"{i}. [{score_pct}% match | {m['category']}] {m['content'][:200]}")
        if m.get("tags"):
            lines.append(f"   Tags: {', '.join(m['tags'])}")
    return "\n".join(lines)


def tool_memory_list(args: dict) -> str:
    params = f"limit={args.get('limit', 20)}&offset={args.get('offset', 0)}"
    if args.get("category"):
        params += f"&category={args['category']}"
    if args.get("agent_id"):
        params += f"&agent_id={args['agent_id']}"
    tok = _get_token()
    resp = _api_request("GET", f"/memory?{params}", token=tok)
    if not resp:
        return "No memories found."
    lines = []
    for m in resp:
        ts = m.get("created_at", "")[:10]
        lines.append(f"[{m['id']}] ({ts}) [{m['category']}] {m['content'][:150]}")
    return "\n".join(lines)


def tool_memory_get(args: dict) -> str:
    mid = args.get("memory_id", "").strip()
    if not mid:
        return "Error: memory_id is required"
    tok = _get_token()
    resp = _api_request("GET", f"/memory/{mid}", token=tok)
    tags_str = ", ".join(resp.get("tags") or [])
    return (
        f"ID: {resp['id']}\n"
        f"Category: {resp['category']}\n"
        f"Tags: {tags_str}\n"
        f"Created: {resp.get('created_at','')[:19]}\n\n"
        f"{resp['content']}"
    )


def tool_memory_delete(args: dict) -> str:
    mid = args.get("memory_id", "").strip()
    if not mid:
        return "Error: memory_id is required"
    tok = _get_token()
    url = API_BASE.rstrip("/") + f"/memory/{mid}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"{tok}", "Accept": "application/json"},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            pass
        return f"✅ Deleted memory {mid}"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Memory {mid} not found"
        raise RuntimeError(f"HTTP {e.code}")


TOOLS = {
    "memory_store": {
        "description": "Store a new piece of information in the shared LumeClaw memory.",
        "inputSchema": {
            "type": "object",
            "required": ["content"],
            "properties": {
                "content":    {"type": "string"},
                "category":   {"type": "string", "enum": ["personal", "project", "server", "preferences"], "default": "personal"},
                "tags":       {"type": "array", "items": {"type": "string"}},
                "agent_id":   {"type": "string"},
                "project_id": {"type": "string"},
            },
        },
        "fn": tool_memory_store,
    },
    "memory_search": {
        "description": "Search shared LumeClaw memory semantically.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query":      {"type": "string"},
                "limit":      {"type": "integer", "default": 5},
                "category":   {"type": "string", "enum": ["personal", "project", "server", "preferences"]},
                "agent_id":   {"type": "string"},
                "project_id": {"type": "string"},
            },
        },
        "fn": tool_memory_search,
    },
    "memory_list": {
        "description": "List recent memory entries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit":      {"type": "integer", "default": 20},
                "offset":     {"type": "integer", "default": 0},
                "category":   {"type": "string"},
                "agent_id":   {"type": "string"},
            },
        },
        "fn": tool_memory_list,
    },
    "memory_get": {
        "description": "Retrieve specific memory entry by UUID.",
        "inputSchema": {
            "type": "object",
            "required": ["memory_id"],
            "properties": {
                "memory_id": {"type": "string"},
            },
        },
        "fn": tool_memory_get,
    },
    "memory_delete": {
        "description": "Permanently delete a memory entry by UUID.",
        "inputSchema": {
            "type": "object",
            "required": ["memory_id"],
            "properties": {
                "memory_id": {"type": "string"},
            },
        },
        "fn": tool_memory_delete,
    },
}

# ── MCP JSON-RPC dispatcher ───────────────────────────────────────────────────

def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def handle(req: dict) -> Optional[dict]:
    rid  = req.get("id")
    meth = req.get("method", "")
    prms = req.get("params", {})

    if meth == "initialize":
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "memory-lumeclaw",
                    "version": "1.0.0",
                },
            },
        }

    if meth == "tools/list":
        tools_list = [
            {
                "name": name,
                "description": meta["description"],
                "inputSchema": meta["inputSchema"],
            }
            for name, meta in TOOLS.items()
        ]
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools_list}}

    if meth == "tools/call":
        tool_name = prms.get("name", "")
        tool_args = prms.get("arguments", {})
        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        try:
            result_text = TOOLS[tool_name]["fn"](tool_args)
            return {
                "jsonrpc": "2.0", "id": rid,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                    "isError": False,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0", "id": rid,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {exc}"}],
                    "isError": True,
                },
            }

    if meth.startswith("notifications/"):
        return None

    return {
        "jsonrpc": "2.0", "id": rid,
        "error": {"code": -32601, "message": f"Method not found: {meth}"},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            send({"jsonrpc": "2.0", "id": None,
                  "error": {"code": -32700, "message": f"Parse error: {e}"}})
            continue
        resp = handle(req)
        if resp is not None:
            send(resp)


if __name__ == "__main__":
    main()
