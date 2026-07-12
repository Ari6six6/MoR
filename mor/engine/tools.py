"""The hands — what a face can actually do, beyond speaking.

A small, real toolset a face acts through inside the loop. Each tool returns a
plain observation string the face reads on its next turn.

Egress is a single chokepoint, and the two rails are enforced here, not asked for:
  - `run_shell` runs inside a face's container body, which sits on the INTERNAL
    dome (no route out) — so a shell, the Warrior's included, is kernel-air-gapped
    and cannot reach the internet at all.
  - `web_fetch` is therefore the realm's ONLY way out. It is Warrior-only, gated
    per-domain (the Master must `authorize` the domain), SSRF-guarded (it opens
    onto the public web, never the host's loopback/LAN or cloud metadata), and it
    taints the turn (the Eighth Evangelism) so the realm can require the Master's
    leave before acting on what came back.

web_fetch runs in the opus process (the host), not in a body — which is exactly
why the SSRF guard matters: without it, an open gate would reach the host's own
network. With it, an open gate reaches only the public internet.
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
    dome: object = None           # the bodies (Dome); None -> disembodied
    role: str = ""                # which face this context belongs to


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


def _blocked_ip(host: str) -> str:
    """'' if every address `host` resolves to is a public unicast address; a reason
    string if any is private/loopback/link-local/reserved/multicast (the SSRF rail:
    the gate opens onto the public web, never the host's own network or its cloud
    metadata endpoint at 169.254.169.254).

    Known limit, accepted deliberately: this is check-then-connect — the fetch
    resolves the name a second time, so a DNS server that rebinds between the two
    lookups can slip an address past the rail. Pinning the resolved address is
    ugly in pure stdlib (connect by IP, hand-set SNI and Host); until that's worth
    its weight, the rail stops honest infrastructure and mistakes, not a hostile
    resolver."""
    import ipaddress
    import socket
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        return f"could not resolve {host} ({type(e).__name__})"
    for info in infos:
        addr = info[4][0].split("%")[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return f"{host} resolves to a non-public address ({addr})"
    return ""


def _open_one_hop(req, timeout: float):
    """Open a request WITHOUT following redirects — the gate takes one hop, never
    a chain. A redirect target is a *different* place: a domain the Master never
    authorized, or (the classic SSRF pivot) the host's own metadata endpoint — and
    both rails only ran against the URL the Warrior asked for. A 3xx surfaces as
    an HTTPError and comes back as an observation instead: the Warrior reports the
    destination, and crossing to it takes the Master's leave like anywhere else."""
    import urllib.request

    class RefuseRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # refuse to follow: the 3xx surfaces as an HTTPError

    return urllib.request.build_opener(RefuseRedirect).open(req, timeout=timeout)


def _deliver(status: int, domain: str, raw: bytes, ctx) -> str:
    """Hand a response body to the face: tainted, and folded into the world map."""
    body = raw.decode("utf-8", "replace")
    ctx.tainted.append(domain)  # taint: it came from outside
    if ctx.space is not None:  # the Wizard's map grows from real sorties
        try:
            from mor import world
            world.record_sortie(ctx.space, domain, f"GET {status}, {len(body)} bytes")
        except Exception:  # noqa: BLE001 — never let bookkeeping break a sortie
            pass
    return f"[{status}] {domain} — {len(body)} bytes (TAINTED):\n{body[:2000]}"


def _web_fetch(args, ctx):
    url = (args.get("url") or "").strip()
    if not url:
        return "ERROR: no url"
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"DENIED: only http(s) may cross the gate, not {parsed.scheme!r}."
    domain = (parsed.hostname or "").lower()
    if not ctx.can_egress:
        return ("DENIED: only the Warrior may leave the dome. Ask the General to "
                "send a sortie.")
    if ctx.space is None or not ctx.space.egress_allowed(domain):
        return (f"DENIED: the gate is shut for {domain}. The General must get the "
                f"Master's leave first (`authorize {domain}`).")
    # The SSRF rail: even with the gate open, the outside is the *public* web —
    # never the host's loopback, LAN, or cloud metadata. Checked before we connect.
    blocked = _blocked_ip(domain)
    if blocked:
        return f"DENIED: {blocked} — the gate does not open onto private networks."
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "MoR-Warrior/0.1"})
    try:
        with _open_one_hop(req, timeout=15) as r:
            return _deliver(r.status, domain, r.read(4000), ctx)
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            where = e.headers.get("Location", "(no Location given)")
            return (f"DENIED: {domain} answered {e.code} redirecting to {where} — "
                    "the gate does not follow redirects. If the sortie needs that "
                    "destination, report it: its domain needs the Master's leave too.")
        # An HTTP error is still an answer from outside — deliver it, tainted.
        try:
            raw = e.read(4000)
        except Exception:  # noqa: BLE001
            raw = b""
        return _deliver(e.code, domain, raw, ctx)
    except Exception as e:  # noqa: BLE001
        return f"ERROR reaching {domain}: {type(e).__name__}"


def _run_shell(args, ctx):
    cmd = (args.get("command") or "").strip()
    if not cmd:
        return "ERROR: no command"
    if ctx.dome is None or not getattr(ctx.dome, "embodied", False):
        return "ERROR: you have no body to run commands in (the dome is not up)."
    rc, out, err = ctx.dome.exec(ctx.role, cmd)
    tail = (out or "") + (("\n" + err) if err and err.strip() else "")
    return f"[exit {rc}]\n{tail[:4000]}" if tail.strip() else f"[exit {rc}] (no output)"


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
    if ctx.dome is not None and getattr(ctx.dome, "embodied", False):
        ts.append(Tool(
            "run_shell", "Run a shell command inside your own body (a container on "
            "the dome). Only the Warrior's body can reach the outside.",
            {"type": "object", "properties": {"command": {"type": "string"}},
             "required": ["command"]}, _run_shell))
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
