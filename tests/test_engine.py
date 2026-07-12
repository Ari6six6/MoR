"""The suite that should have existed — it drives the engine and pins the two rails.

Runs with no GPU, no Docker, no network (faked where needed). `pytest -q`.
"""

from __future__ import annotations

import os

import pytest

from mor.engine import (Dome, MockBackend, ScriptBackend, ToolContext,
                        default_tools, hall_view, think_and_act)
from mor.engine.backend import Backend, ChatResult, ToolCall
from mor.engine.loop import _REFLECT_NUDGE
from mor.engine.tools import _blocked_ip, _safe, _web_fetch, execute


@pytest.fixture()
def space(tmp_path, monkeypatch):
    monkeypatch.setenv("MOR_HOME", str(tmp_path))
    from mor.config import Space
    return Space("test").ensure()


def _ctx(space, role="warrior", can_egress=True):
    ws = space.root / "population" / role / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ToolContext(workspace=ws, space=space, can_egress=can_egress,
                       tainted=[], role=role)


# --- the loop --------------------------------------------------------------
def test_loop_executes_a_tool_and_grounds_its_answer(space):
    ctx = _ctx(space, role="wizard", can_egress=False)
    (ctx.workspace / "note.txt").write_text("the east ford is out")
    backend = ScriptBackend([
        {"tool": "read_file", "args": {"path": "note.txt"}},
        {"text": "The east ford is out; we route north."},
    ])
    line, tainted = think_and_act(
        backend, role="wizard", kind="wake", heard="", system="You are the Wizard.",
        user="read note.txt", tools=default_tools(ctx), ctx=ctx)
    assert "north" in line
    assert tainted is False


def test_offline_mind_runs_the_loop_in_character(space):
    ctx = _ctx(space, role="general", can_egress=False)
    line, _ = think_and_act(
        MockBackend(), role="general", kind="wake", heard="", system="s", user="u",
        tools=default_tools(ctx), ctx=ctx)
    assert "offline mind heard" not in line  # seeded flavor, not the raw echo
    assert line.strip()


def test_reflect_reflex_pushes_to_think_after_acting_without_reasoning(space):
    ctx = _ctx(space, role="wizard", can_egress=False)
    (ctx.workspace / "f").write_text("x")

    class Capture(Backend):
        def __init__(self):
            self.last = []

        def chat(self, messages, tools=None):
            self.last = list(messages)
            # act (no content) three times, then finish
            acted = sum(1 for m in messages if m.get("role") == "tool")
            if acted < 3:
                return ChatResult(content=None,
                                  tool_calls=[ToolCall("c", "read_file", '{"path": "f"}')])
            return ChatResult(content="done")

    b = Capture()
    think_and_act(b, role="wizard", kind="wake", heard="", system="s", user="u",
                  tools=default_tools(ctx), ctx=ctx)
    assert any(m.get("content") == _REFLECT_NUDGE for m in b.last)


# --- the gate (finding #1) -------------------------------------------------
def test_non_warrior_cannot_egress(space):
    ctx = _ctx(space, role="wizard", can_egress=False)
    space.authorize("*")
    assert "web_fetch" not in [t.name for t in default_tools(ctx)]
    assert _web_fetch({"url": "https://example.com"}, ctx).startswith("DENIED")


def test_gate_shut_refuses(space):
    ctx = _ctx(space)
    assert _web_fetch({"url": "https://example.com"}, ctx).startswith("DENIED: the gate")


def test_run_shell_absent_and_air_gapped_when_disembodied(space):
    ctx = _ctx(space)  # no dome attached
    # With no body, the shell isn't even offered as a tool...
    assert "run_shell" not in [t.name for t in default_tools(ctx)]
    # ...and calling it directly refuses (it only runs inside an air-gapped body).
    from mor.engine.tools import _run_shell
    assert "no body" in _run_shell({"command": "curl http://x"}, ctx)


# --- the SSRF rail (finding #2) --------------------------------------------
@pytest.mark.parametrize("addr", ["127.0.0.1", "169.254.169.254", "10.0.0.5",
                                  "192.168.1.1", "::1"])
def test_ssrf_blocks_non_public(space, monkeypatch, addr):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", (addr, 0))])
    ctx = _ctx(space)
    space.authorize("*")
    assert _web_fetch({"url": "http://totally-public.example/"}, ctx).startswith("DENIED")


def test_bad_scheme_refused(space):
    ctx = _ctx(space)
    space.authorize("*")
    assert _web_fetch({"url": "file:///etc/passwd"}, ctx).startswith("DENIED")


def test_public_fetch_taints_and_maps(space, monkeypatch):
    import socket
    import urllib.request
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])

    class FakeResp:
        status = 200

        def read(self, n=None):
            return b"<html>outside</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResp())
    ctx = _ctx(space)
    space.authorize("example.com")
    out = _web_fetch({"url": "http://example.com/"}, ctx)
    assert "TAINTED" in out
    assert ctx.tainted == ["example.com"]
    from mor import world
    assert "example.com" in world.load(space).get("places", {})


# --- path safety -----------------------------------------------------------
def test_path_escape_is_blocked(space):
    ctx = _ctx(space)
    with pytest.raises(ValueError):
        _safe(ctx, "../../etc/passwd")
    out = execute(default_tools(ctx),
                  ToolCall("c", "read_file", '{"path": "../../etc/passwd"}'), ctx)
    assert out.startswith("ERROR")


# --- compaction ------------------------------------------------------------
def test_hall_folds_when_long(space):
    from mor.hall import Hall
    h = Hall(space, 1, echo=False)
    for i in range(6):
        h.post("general", "wizard", f"line {i}")
    assert "folded" not in hall_view(h, MockBackend())
    for i in range(50):
        h.post("wizard", "general", f"detail {i}")
    view = hall_view(h, MockBackend())
    assert "folded" in view and "RECENT (verbatim)" in view and "detail 49" in view


# --- the dome degrades -----------------------------------------------------
def test_dome_degrades_without_runtime(space, monkeypatch):
    monkeypatch.setattr("mor.engine.dome.probe_runtime", lambda: "")
    d = Dome(space)
    assert d.up(["wizard", "general", "warrior"]) is False
    assert d.embodied is False
    assert d.exec("warrior", "echo hi")[0] == 127


def test_blocked_ip_helper_passes_public(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    assert _blocked_ip("example.com") == ""
