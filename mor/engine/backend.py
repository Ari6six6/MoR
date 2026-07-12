"""The mind's voice — how a face reaches the model.

Cut from Hermes's llm.py and reforged to MoR's standard:
  ServedBackend — the real oracle over the tunnel (OpenAI chat-completions with
                  tool-calling), with a retry ladder and a heartbeat so a slow
                  completion never looks dead, and never crashes the realm.
  MockBackend   — the offline stand-in: in-character plain-English so the realm
                  visibly moves on first clone, no GPU, no tools.
  ScriptBackend — a scripted oracle for tests, to exercise the tool loop.

Stdlib only (urllib), keeping the engine dependency-light even though the
vendored Hermes carries httpx.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.request
from dataclasses import dataclass, field

from mor.config import gpu_state_path, load_json


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON string, as the wire delivers it


@dataclass
class ChatResult:
    content: str | None = None
    tool_calls: list = field(default_factory=list)


class Backend:
    """One method: turn a message list (+ optional tools) into a ChatResult."""

    def chat(self, messages: list, tools: list | None = None) -> ChatResult:
        raise NotImplementedError


# --------------------------------------------------------------------------
class ServedBackend(Backend):
    RETRY_DELAYS = (1, 3, 8)

    def __init__(self, state: dict):
        self.base_url = (state.get("base_url") or "").rstrip("/")
        self.model = state.get("model", "default")
        self.api_key = state.get("api_key", "mor")
        self.timeout = float(state.get("timeout", 300))
        sampling = state.get("sampling") or {}
        self.temperature = sampling.get("temperature", 0.6)
        self.top_p = sampling.get("top_p", 0.95)
        self.max_tokens = int(state.get("max_completion_tokens", 4096))

    def _post(self, body: dict) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=data,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))

    def chat(self, messages: list, tools: list | None = None) -> ChatResult:
        body = {"model": self.model, "messages": messages,
                "temperature": self.temperature, "top_p": self.top_p,
                "max_tokens": self.max_tokens}
        if tools:
            body["tools"] = tools
        last = None
        for attempt, delay in enumerate((0,) + self.RETRY_DELAYS):
            if delay:
                time.sleep(delay)
            try:
                with _heartbeat("the oracle is thinking"):
                    payload = self._post(body)
                msg = payload["choices"][0]["message"]
                calls = [ToolCall(tc.get("id", f"c{i}"),
                                  tc["function"]["name"],
                                  tc["function"].get("arguments") or "{}")
                         for i, tc in enumerate(msg.get("tool_calls") or [])]
                return ChatResult(content=msg.get("content"), tool_calls=calls)
            except Exception as e:  # noqa: BLE001 — a flaky oracle must never crash the realm
                last = e
        # Every attempt failed: speak the failure into the Hall, don't raise.
        return ChatResult(content=f"(the oracle did not answer — "
                                  f"{type(last).__name__}: {str(last)[:120]}. "
                                  "Check `gpu status`.)")


# --------------------------------------------------------------------------
class ScriptBackend(Backend):
    """A scripted oracle for tests. Each item: {'text': ...} or
    {'tool': name, 'args': {...}} or {'tools': [{'tool':..,'args':..}, ...]}."""

    def __init__(self, script: list):
        self.script = list(script)
        self._n = 0

    def chat(self, messages: list, tools: list | None = None) -> ChatResult:
        if not self.script:
            return ChatResult(content="(script exhausted)")
        item = self.script.pop(0)
        if "text" in item:
            return ChatResult(content=item["text"])
        calls = item.get("tools") or [{"tool": item["tool"], "args": item.get("args", {})}]
        out = []
        for c in calls:
            self._n += 1
            out.append(ToolCall(f"s{self._n}", c["tool"], json.dumps(c.get("args", {}))))
        return ChatResult(content=item.get("say"), tool_calls=out)


# --------------------------------------------------------------------------
class MockBackend(Backend):
    """The offline mind. It runs the *same* loop the served mind does, but its reply
    is a seeded in-character line (no tool calls) — so the realm moves with no GPU
    while the loop machinery still executes and stays honest."""

    def __init__(self):
        self._pending = None

    def seed(self, text: str) -> None:
        self._pending = text

    def chat(self, messages: list, tools: list | None = None) -> ChatResult:
        if self._pending is not None:
            text, self._pending = self._pending, None
            return ChatResult(content=text)
        tail = messages[-1]["content"] if messages else ""
        return ChatResult(content=f"(offline mind heard: {str(tail)[-160:]})")


def flavored_line(role: str, kind: str, heard: str = "") -> str:
    """Deterministic, in-character plain English for the offline mind."""
    def pick(options: list) -> str:
        h = hashlib.sha256(f"{role}|{kind}|{heard[:60]}".encode()).hexdigest()
        return options[int(h[:8], 16) % len(options)]

    short = " ".join((heard or "").split())[:60]
    table = {
        "wake": {
            "wizard": ["I am awake. I have read the night and the map of the outside. "
                       "The realm holds; nothing festers. I am ready to see for us."],
            "general": ["Awake and standing. Strategy in hand, the gate is mine. I await the word."],
            "warrior": ["Kit checked, the gate answers, my body is sound. I can move on your order."],
        },
        "greet_master": ["All three of us are awake and ready, Master. What is your command?"],
        "wizard_takes": [f"I hear you, Master — you speak of {short}. Let me hold it to the "
                         "light. General, come reason with me."],
        "general_debates": ["I follow you, Wizard, but I take nothing on faith. If it's real the "
                            "record shows it — a short sortie settles it. Is this fine?"],
        "wizard_agrees": ["Yes — that's fine. Send him; I'll fold what he brings into the map."],
        "order_warrior": [f"Warrior — go and see to {short}. Do exactly that, touch nothing else, "
                          "bring me everything you touched."],
        "warrior_reports": ["I'm back, General. Did exactly as ordered, brought no snakes. "
                            "Full report follows."],
        "general_to_master": ["Master — we reasoned it through and the Warrior has been out. "
                             "Here is where we stand. Your word?"],
        "chant": ["A short day, a long thought — / the seer dreamed, the general weighed, / "
                  "the warrior walked the wire and came home whole. / Sleep now, wake new."],
        "inside_wall": ["Today I was true to what I am. I spoke plainly and hid nothing. "
                        "I am the one who sees; tomorrow I will see further."],
        "outside_wall": ["The General is hard on me, and I've come to trust it. The Warrior is "
                         "honest to the bone. We are three, and we hold."],
    }
    node = table.get(kind, {})
    if isinstance(node, dict):
        return pick(node.get(role, [f"({role} has nothing to add)"]))
    return pick(node)


# --------------------------------------------------------------------------
class _heartbeat:
    """A background 'still thinking…' tick so a long completion never looks dead."""

    def __init__(self, label: str):
        self.label = label
        self._stop = threading.Event()
        self._t = None

    def __enter__(self):
        import sys
        if sys.stdout.isatty():
            self._t = threading.Thread(target=self._run, daemon=True)
            self._t.start()
        return self

    def _run(self):
        import sys
        i, t0 = 0, time.time()
        while not self._stop.wait(0.5):
            i += 1
            if i % 2 == 0:
                sys.stdout.write(f"\r  · {self.label}… {time.time() - t0:4.1f}s ")
                sys.stdout.flush()

    def __exit__(self, *a):
        import sys
        self._stop.set()
        if self._t and sys.stdout.isatty():
            sys.stdout.write("\r" + " " * 48 + "\r")
            sys.stdout.flush()


def make_backend():
    """ServedBackend if the oracle is attached; the offline MockBackend otherwise."""
    state = load_json(gpu_state_path(), {})
    if state.get("served") and state.get("base_url"):
        return ServedBackend(state), "served"
    return MockBackend(), "offline"
