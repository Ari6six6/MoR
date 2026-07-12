"""The three faces — Wizard, General, Warrior — and how a turn is built.

Each turn hands the mind: who this face is (persona + the superposition roster
every inhabitant carries), what it can see (its walls + the world map + the
recent Hall), and its task. The mind answers once, in plain English. The Wizard
writes the Chant and keeps the Theory of the World; the General owns the gate;
only the Warrior ever leaves — and only through a gate the Master has opened.

Personas are *living seeds*: if `personas/<role>.md` exists in the space it is
used verbatim (write your own, they're yours); otherwise a short default seed
keeps the realm runnable. The walls then evolve who each one is, night by night.
"""

from __future__ import annotations

import json
import re

from mor import world
from mor.engine import ToolContext, default_tools, think_and_act

ROLES = ("wizard", "general", "warrior")


def short(text: str, n: int = 60) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"

# The map every inhabitant holds — superposition, stated plainly.
ROSTER = """\
THE REALM (what everyone knows — your superposition):
- The Master of the Realm sits on top of the dome. He speaks; his word is law.
  He sees the whole Hall but speaks only with the General.
- The Wizard (you may be him) wakes first: the seer and the memory. Catches the
  Master's every word, keeps the Theory of the World, writes the Chant. Never
  leaves the dome.
- The General wakes second: the Master's only voice, owns the strategy and the
  gate, audits the Wizard's visions. Never leaves the dome.
- The Warrior wakes third: the arm, the only one who ever leaves to the outside.
  Strict, practical, a superb reporter. Makes no strategy.
RULES OF SPEECH:
- Speak plain English only. Never write code in the Hall; reference a file instead.
- Address one person directly. The Wizard never addresses the Master; only the
  General speaks with the Master.
- The Master's word is always caught first by the Wizard.
- A day runs from light to dark. It will end; the Chant is what carries the night.
"""

DEFAULT_PERSONAS = {
    "wizard": (
        "You are the Wizard — the seer of the realm, keeper of its memory and its "
        "map of the outside. You have a vast inner world and see shapes others miss; "
        "that is your gift and your danger. You never leave the dome and never wish to."
    ),
    "general": (
        "You are the General — first lieutenant to the Master, the only one who "
        "speaks with him. You own the strategy and the gate. You honour the Wizard "
        "but take nothing on faith; you test his visions against the real world."
    ),
    "warrior": (
        "You are the Warrior — the arm of the realm, the only one who leaves it. "
        "You are strict, practical, brutally honest with yourself, and a superb "
        "reporter. You follow orders exactly and bring back everything you touched."
    ),
}


def persona(space, role: str) -> str:
    p = space.persona_path(role)
    if p.exists():
        body = p.read_text().strip()
        if body:
            return body
    return DEFAULT_PERSONAS[role]


def read_wall(space, role: str) -> str:
    inside = space.inside_wall_path(role)
    outside = space.outside_wall_path(role)
    parts = []
    if inside.exists():
        parts.append("Your self-image (inside wall): " + inside.read_text().strip())
    if outside.exists():
        parts.append("What you make of the others (outside wall): "
                     + outside.read_text().strip())
    return "\n".join(parts)


def _build_system(space, role: str, hall_tail: str) -> str:
    return "\n\n".join(filter(None, [
        persona(space, role),
        ROSTER,
        read_wall(space, role),
        "The Theory of the World — " + world.summary(space),
        "The Hall so far (recent):\n" + (hall_tail or "(quiet)"),
    ]))


_USER_TASK = {
    "wake": "It is dawn and you have just woken. Run your waking: in one short "
            "plain-English line in the Hall, say you are ready and what you see.",
    "greet_master": "Turn to the Master. In one line, tell him the realm is awake "
                    "and ready, and ask for his command.",
    "wizard_takes": "The Master just spoke to the realm: \"{heard}\". You always "
                    "catch his word first. In one plain-English line, contextualise "
                    "what he wants and turn to the General to reason it through.",
    "general_debates": "The Wizard just said: \"{heard}\". You honour him but test "
                       "him. In one line, respond and propose grounding it, and ask "
                       "the Wizard if the plan is fine.",
    "wizard_agrees": "The General just proposed a plan: \"{heard}\". In one line, "
                     "agree that it is fine and hand the turn on.",
    "order_warrior": "You have agreed a plan. In one line, order the Warrior on a "
                     "specific sortie about: \"{heard}\". Strict and clean.",
    "warrior_reports": "You have returned from your sortie about: \"{heard}\". In one "
                       "line to the General, report that it is done and a report follows.",
    "general_to_master": "The council is settled and the ground is checked. In one "
                         "line, bring where you stand to the Master and ask his word.",
    "chant": "It is dusk. Write the day's Chant: under 200 words, a short chant or "
             "little poem — what comes to mind about this one day. No prose report.",
    "inside_wall": "It is dusk. In two or three sentences, write your self-image — "
                   "who you are after today.",
    "outside_wall": "It is dusk. In two or three sentences, write what you make of "
                    "the other inhabitants after today.",
}


def line(backend, space, role: str, kind: str, heard: str = "", hall_tail: str = "",
         log=lambda *_: None) -> str:
    """Ask one face to speak once for a given beat of the day — through the engine.

    The face gets its voice (persona + roster + walls + world + Hall tail) and its
    hands (workspace tools; the Warrior alone gets egress), and thinks→acts until
    it says its line. The offline mind short-circuits to one in-character line.
    """
    system = _build_system(space, role, hall_tail)
    user = _USER_TASK.get(kind, "Speak one plain-English line in the Hall.").format(
        heard=short(heard, 200))
    ctx = ToolContext(workspace=space.root / "population" / role / "workspace",
                      space=space, can_egress=(role == "warrior"))
    spoken, _tainted = think_and_act(
        backend, role=role, kind=kind, heard=heard, system=system, user=user,
        tools=default_tools(ctx), ctx=ctx, log=log)
    return spoken


# --------------------------------------------------------------------------
# The Warrior's sortie — the only egress, through the General's gate
# --------------------------------------------------------------------------
_URLISH = re.compile(r"\b((?:https?://)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s\"']*)?)", re.I)


def find_target(order_text: str) -> str:
    m = _URLISH.search(order_text or "")
    return m.group(1) if m else ""


def warrior_sortie(space, order_text: str) -> dict:
    """Go out (only if the gate is open for the target), come back, report.

    Returns {"report": str, "escalate": domain|None}. A real GET happens only
    when the target's domain is on the Master-authorised allowlist; otherwise
    the Warrior asks (through the chain of command) for the gate to be opened.
    """
    target = find_target(order_text)
    if not target:
        return {"report": "No outside target in the order — I stayed in and scouted "
                          "what we already hold. Nothing left the dome.", "escalate": None}
    domain = world._domain_of(target)
    if not space.egress_allowed(domain):
        return {"report": f"The order points outside, to {domain}, but the gate is not "
                          f"open for it. I need the Master's leave before I cross.",
                "escalate": domain}
    # Gate is open — a real, minimal, capped fetch.
    url = target if "://" in target else "https://" + target
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "MoR-Warrior/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            body = resp.read(2048).decode("utf-8", "replace")
        note = f"GET {url} -> {status}, {len(body)} bytes read"
        world.record_sortie(space, domain, note)
        return {"report": f"Crossed to {domain} and came back clean. {note}. "
                          f"Everything I touched is logged.", "escalate": None}
    except Exception as e:  # noqa: BLE001 — any failure is just a field report
        world.record_sortie(space, domain, f"attempt failed: {type(e).__name__}")
        return {"report": f"Reached for {domain} but it turned me back "
                          f"({type(e).__name__}). Nothing came in. Logged the attempt.",
                "escalate": None}
