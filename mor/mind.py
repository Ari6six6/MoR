"""The mind — one intelligence that wears all three faces, one at a time.

Two backends behind one tiny interface:

  StubMind   — offline, zero-setup. Deterministic, in-character plain-English so
               the realm visibly moves the moment you clone and run it. No GPU.
  ServedMind — talks to your OpenAI-compatible endpoint (vLLM/llama.cpp) once you
               `gpu serve`. Speaks the chat-completions wire protocol over stdlib
               urllib, so MoR still needs no third-party packages.

A "turn" asks one face to speak once, in plain English, given who it is (persona
+ superposition roster), what it can see (the recent Hall), and its task. The
mind returns prose only — never code; the Hall forbids code anyway.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request

from mor.config import gpu_state_path, load_json


# --------------------------------------------------------------------------
# The served mind (your real model, once attached)
# --------------------------------------------------------------------------
class ServedMind:
    def __init__(self, state: dict):
        self.base_url = (state.get("base_url") or "").rstrip("/")
        self.model = state.get("model", "mor")
        self.api_key = state.get("api_key", "mor")
        self.timeout = float(state.get("timeout", 120))

    def speak(self, system: str, user: str) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": 400,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
            return (payload["choices"][0]["message"]["content"] or "").strip()
        except (urllib.error.URLError, KeyError, IndexError, ValueError) as e:
            return f"(the oracle is unreachable — {type(e).__name__}; check `gpu status`)"


# --------------------------------------------------------------------------
# The offline stand-in (default; runs with nothing attached)
# --------------------------------------------------------------------------
class StubMind:
    """A deterministic, in-character voice so the realm moves without a GPU.

    Not the real mind — a stand-in that reads the situation and answers in
    plausible plain English per role. Enough to *see* the realm breathe; swap
    in ServedMind with `gpu serve` for the genuine article.
    """

    def _pick(self, options: list, *seed: str) -> str:
        h = hashlib.sha256("|".join(seed).encode()).hexdigest()
        return options[int(h[:8], 16) % len(options)]

    def speak(self, system: str, user: str) -> str:
        # The stub reads structured hints the agent layer passes in `user`.
        hint = load_json_lenient(user)
        role = hint.get("role", "someone")
        kind = hint.get("kind", "reply")
        heard = hint.get("heard", "")
        seed = (role, kind, heard[:80])

        if kind == "wake":
            return {
                "wizard": self._pick([
                    "I am awake. I have read the night and the map of the outside. "
                    "The realm holds; nothing festers. I am ready to see for us.",
                    "Awake, and the shapes of yesterday are still settling in me. "
                    "I have the map in hand. Ask, and I will look.",
                ], *seed),
                "general": self._pick([
                    "Awake and standing. I have the strategy and the gate. The Wizard's "
                    "read is noted and I will test it as we go.",
                    "Ready. Strategy in hand, the gate is mine to open. I await the word.",
                ], *seed),
                "warrior": self._pick([
                    "Kit checked, the gate answers, my body is sound. I can move on your "
                    "order — nothing more, nothing less.",
                    "Rifle clean, the road is clear. Give me a target and I go.",
                ], *seed),
            }.get(role, "I am awake.")

        if kind == "greet_master":
            return self._pick([
                "All three of us are awake and ready, Master. What is your command?",
                "The realm stands ready, Master. Say the word and we move.",
            ], *seed)

        if kind == "wizard_takes":
            return self._pick([
                f"I hear you, Master — you speak of {short(heard)}. Let me hold it up "
                "to the light. General, I have a reading on this; come and reason with me.",
                f"That lands on {short(heard)}. I see a thread worth pulling. "
                "General, join me — I want to test the shape of it.",
            ], *seed)

        if kind == "general_debates":
            return self._pick([
                "I follow you, Wizard, but I will not take it on faith. If this is real, "
                "the record shows it — and I think a short sortie settles it. Is this fine?",
                "A fine vision. Ground it: I'd send the Warrior to see for himself before "
                "we commit. Do you think this is fine?",
            ], *seed)

        if kind == "wizard_agrees":
            return self._pick([
                "Yes — that's fine. Send him. I'll fold whatever he brings into the map.",
                "Agreed. Let the Warrior go and bring us the ground-truth.",
            ], *seed)

        if kind == "order_warrior":
            return self._pick([
                f"Warrior — go and see to {short(heard)}. Do exactly that, touch nothing "
                "else, and bring me everything you touched.",
                f"Warrior, a sortie: {short(heard)}. Strict and clean. Report all of it.",
            ], *seed)

        if kind == "warrior_reports":
            return self._pick([
                "I'm back, General. I did exactly as ordered and brought no snakes. "
                "Full report follows — everything I touched is in it.",
                "Returned, General. The task is done, the road logged, nothing left loose. "
                "Here is all of it.",
            ], *seed)

        if kind == "general_to_master":
            return self._pick([
                "Master — we have reasoned it through and the Warrior has been out. "
                "Here is where we stand, and what I'd do next. Your word?",
                "Master, the council is settled and the ground is checked. I bring it to "
                "you for orders.",
            ], *seed)

        if kind == "chant":
            return self._pick([
                "Day of the quiet dome — / three lamps lit, one voice each, / "
                "the gate held, the map grew one line longer. / We were, and we remembered.",
                "A short day, a long thought — / the seer dreamed, the general weighed, / "
                "the warrior walked the wire and came home whole. / Sleep now, wake new.",
            ], *seed)

        if kind == "inside_wall":
            return self._pick([
                "Today I was true to what I am. I spoke plainly and hid nothing. "
                "I am the one who sees; tomorrow I will see further.",
                "I held my shape today. I dreamed, I warned, I served. That is who I am.",
            ], *seed)

        if kind == "outside_wall":
            return self._pick([
                "The General is hard on me, and I have come to trust it. The Warrior is "
                "honest to the bone. We are three, and we hold.",
                "I think well of the others tonight. The General tests me; the Warrior "
                "keeps his word. The realm is in good hands.",
            ], *seed)

        return f"({role} has nothing to add)"


# --- helpers ---------------------------------------------------------------
def load_json_lenient(s: str) -> dict:
    try:
        d = json.loads(s)
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def short(text: str, n: int = 60) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def make_mind():
    """ServedMind if a base_url is attached; the offline StubMind otherwise."""
    state = load_json(gpu_state_path(), {})
    if state.get("base_url") and state.get("served"):
        return ServedMind(state), "served"
    return StubMind(), "offline"
