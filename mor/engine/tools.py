"""The hands — what a face can actually do, beyond speaking.

A small, real toolset a face acts through inside the loop. Each tool returns a
plain observation string the face reads on its next turn. The realm's two laws
are enforced here, not asked for:
  - the gate: only the Warrior's egress is allowed, and only to a domain the
    Master has opened (`web_fetch` refuses otherwise);
  - taint: anything pulled from outside marks the turn tainted (the Eighth
    Evangelism, cut from Hermes) so the realm can require the Master's leave.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class ToolContext:
    workspace: Path
    space: object = None          # carries the gate (egress_allowed / allowlist)
    can_egress: bool = False      # only the Warrior's body may reach the outside
    tainted: list = field(default_factory=list)  # domains pulled from outside


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: object  # (args: dict, ctx: ToolContext) -> str

    def openai(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.parameters}}


def _safe(ctx: ToolContext, rel: str) -> Path:
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    p = (ctx.workspace / (rel or ".")).resolve()
    if ctx.workspace.resolve() not in p.parents and p != ctx.workspace.resolve():
        raise ValueError("path escapes the workspace")
    return p


def _read_file(args, ctx):
    p = _safe(ctx, args.get("path", ""))
    if not p.exists():
        return f"ERROR: no such file: {args.get('path')}"
    return p.read_text("utf-8", "replace")[:8000]


def _write_file(args, ctx):
    p = _safe(ctx, args.get("path", ""))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(args.get("content", ""))
    return f"wrote {len(args.get('content', ''))} chars to {args.get('path')}"


def _list_dir(args, ctx):
    p = _safe(ctx, args.get("path", "."))
    if not p.exists():
        return "(empty)"
    return "\n".join(sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir())) or "(empty)"


def _web_fetch(args, ctx):
    url = (args.get("url") or "").strip()
    if not url:
        return "ERROR: no url"
    if "://" not in url:
        url = "https://" + url
    domain = (urlparse(url).hostname or "").lower()
    if not ctx.can_egress:
        return ("DENIED: only the Warrior may leave the dome. Ask the General to "
                "send a sortie.")
    allowed = ctx.space is not None and ctx.space.egress_allowed(domain)
    if not allowed:
        return (f"DENIED: the gate is shut for {domain}. The General must get the "
                f"Master's leave first (`authorize {domain}`).")
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "MoR-Warrior/0.1"})
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read(4000).decode("utf-8", "replace")
            status = r.status
        ctx.tainted.append(domain)  # taint: it came from outside
        return f"[{status}] {domain} — {len(body)} bytes (TAINTED):\n{body[:2000]}"
    except Exception as e:  # noqa: BLE001
        return f"ERROR reaching {domain}: {type(e).__name__}"


def default_tools(ctx: ToolContext) -> list:
    ts = [
        Tool("read_file", "Read a file in your workspace.",
             {"type": "object", "properties": {"path": {"type": "string"}},
              "required": ["path"]}, _read_file),
        Tool("write_file", "Write a file in your workspace.",
             {"type": "object", "properties": {"path": {"type": "string"},
                                               "content": {"type": "string"}},
              "required": ["path", "content"]}, _write_file),
        Tool("list_dir", "List a directory in your workspace.",
             {"type": "object", "properties": {"path": {"type": "string"}}}, _list_dir),
    ]
    if ctx.can_egress:
        ts.append(Tool(
            "web_fetch", "Fetch a URL from outside the dome (Warrior only; the "
            "General must have opened the gate for its domain).",
            {"type": "object", "properties": {"url": {"type": "string"}},
             "required": ["url"]}, _web_fetch))
    return ts


def execute(tools: list, call, ctx: ToolContext) -> str:
    by_name = {t.name: t for t in tools}
    t = by_name.get(call.name)
    if t is None:
        return f"ERROR: no such tool '{call.name}'"
    try:
        args = json.loads(call.arguments or "{}")
    except json.JSONDecodeError:
        return "ERROR: arguments were not valid JSON"
    try:
        return t.fn(args, ctx)
    except Exception as e:  # noqa: BLE001
        return f"ERROR in {call.name}: {type(e).__name__}: {e}"
