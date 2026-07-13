"""The think→act loop — one face's turn, for real.

Given a face (its system voice + task) and its hands (tools), run the model until
it stops acting and says its plain-English line into the Hall. Carries the reflex
cut from Hermes's agent loop: if a face acts several times without ever reasoning
out loud, push it to think before it acts again — the guard against a small mind
tool-thrashing its way past the point.

The offline mind never enters the loop: it speaks one in-character line and stops,
so the realm still moves with no oracle attached.
"""

from __future__ import annotations

from mor.engine.backend import MockBackend, flavored_line
from mor.engine.tools import execute

# How many act-only turns (tool calls, no reasoning) before we push to think.
_REFLECT_AFTER = 2
_MAX_STEPS = 8

_REFLECT_NUDGE = (
    "You have acted several times without reasoning out loud. Stop. In plain "
    "English, say what you have found so far and what it means — then decide your "
    "next move. Do not call another tool until you have thought."
)

_BUDGET_NUDGE = (
    "Two steps remain. Stop exploring; consolidate what you have and say your line."
)


def think_and_act(backend, *, role: str, kind: str, heard: str, system: str,
                  user: str, tools: list, ctx, log=lambda *_: None,
                  max_steps: int = _MAX_STEPS):
    """Run one face's turn and return (spoken_line, tainted).

    The offline mind doesn't bypass the loop — it seeds an in-character line and
    then runs the *same* loop the served mind does (it just doesn't call tools), so
    the machinery is live and validated even with no GPU attached.
    """
    if isinstance(backend, MockBackend):
        backend.seed(flavored_line(role, kind, heard))

    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    openai_tools = [t.openai() for t in tools] if tools else None
    act_streak = 0
    last_text = ""
    warned = False

    for step in range(max_steps):
        # The budget valve: with two steps left on a long leash, tell the face once
        # to stop exploring and land its answer — so it consolidates rather than
        # getting cut off mid-reach and made to speak cold.
        if not warned and step == max_steps - 2 and max_steps > 2:
            messages.append({"role": "user", "content": _BUDGET_NUDGE})
            warned = True

        res = backend.chat(messages, openai_tools)
        if not res.tool_calls:
            # A plain-English answer — this is the face's line in the Hall.
            return (res.content or last_text or "(said nothing)").strip(), bool(ctx.tainted)

        # It's acting. Record the assistant turn (with its calls) verbatim.
        if res.content:
            last_text = res.content
        messages.append({"role": "assistant", "content": res.content or "",
                         "tool_calls": [{"id": c.id, "type": "function",
                                         "function": {"name": c.name,
                                                      "arguments": c.arguments}}
                                        for c in res.tool_calls]})
        for c in res.tool_calls:
            obs = execute(tools, c, ctx)
            log(f"    · {c.name} → {obs.splitlines()[0][:80] if obs else ''}")
            messages.append({"role": "tool", "tool_call_id": c.id, "content": obs})

        # Reflect reflex: acting without thinking gets pushed to think.
        act_streak = act_streak + 1 if not (res.content or "").strip() else 0
        if act_streak >= _REFLECT_AFTER:
            messages.append({"role": "user", "content": _REFLECT_NUDGE})
            act_streak = 0

    # Out of steps: make it say its piece rather than vanish.
    messages.append({"role": "user", "content":
                     "Enough acting. Say your line now, in plain English, for the Hall."})
    res = backend.chat(messages, None)
    return (res.content or last_text or "(ran out of turns)").strip(), bool(ctx.tainted)
