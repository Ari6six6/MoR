"""The day itself — the scheduler that runs on names, and light→word→dark whole.

Runs with no GPU, no Docker, no network: the offline mind walks the same loop
the served mind does, and a scripted oracle drives the branches the fixed beats
could never take.
"""

from __future__ import annotations

from mor.engine import ScriptBackend
from mor.realm import Realm
from mor.scheduler import named, resolve_addressee


# --- the name-mention scheduler (THE_REALM §10.2) ---------------------------
def test_named_keeps_order_and_dedupes():
    assert named("General, take the Warrior — and General, be quick.") == \
        ["general", "warrior"]


def test_resolve_skips_the_speakers_own_name():
    assert resolve_addressee("wizard", "The Wizard sees far. Warrior, go look.") == \
        "warrior"


def test_only_the_general_speaks_with_the_master():
    # Rule 3/4: anyone else naming the Master is routed to the Master's voice.
    assert resolve_addressee("wizard", "Master, I saw it!") == "general"
    assert resolve_addressee("warrior", "Master, the gate held.") == "general"
    assert resolve_addressee("general", "Master, we stand ready.") == "master"


def test_unnamed_lines_fall_to_the_hub_and_the_general_closes():
    assert resolve_addressee("wizard", "Hm. So it is.") == "general"
    assert resolve_addressee("warrior", "Nothing to report.") == "general"
    # A General with no one left to name turns to the Master — the close.
    assert resolve_addressee("general", "So be it.") == "master"


# --- a whole day, offline ----------------------------------------------------
def _realm(space, monkeypatch) -> Realm:
    monkeypatch.setattr("mor.engine.dome.probe_runtime", lambda: "")
    return Realm(space, echo=False)


def test_a_full_offline_day(space, monkeypatch):
    r = _realm(space, monkeypatch)
    r.light()
    day = r.day
    r.master_says("Take stock of the realm.")

    entries = r.hall.entries()
    speakers = [e["speaker"] for e in entries]
    # Rule 2: the Wizard catches the Master's word first.
    assert speakers[speakers.index("master") + 1] == "wizard"
    # The round closed: the General turned to the Master.
    assert entries[-1]["speaker"] == "general"
    assert entries[-1]["addressee"] == "master"
    # Rule 1, in the council: every line after the Master's word addresses someone.
    council = entries[speakers.index("master") + 1:]
    assert council and all(e["addressee"] for e in council)

    r.dark()
    for role in ("wizard", "general", "warrior"):
        assert space.inside_wall_path(role).exists()
        assert space.outside_wall_path(role).exists()
    assert space.chant_path(day).exists()
    assert space.state()["last_day"] == day
    assert r.awake is False


def test_council_branches_where_the_words_point(space, monkeypatch):
    """The old fixed beats could only run wizard→general→wizard→general→warrior.
    With the scheduler, the Wizard can send the Warrior on an errand directly
    (rule 3) and the round still closes through the General."""
    r = _realm(space, monkeypatch)
    r.light()
    r.backend = ScriptBackend([
        {"text": "A plain errand — Warrior, read the gate ledger and say what you find."},
        {"text": "Done. General, the ledger is clean — nothing crossed today."},
        {"text": "Master — the ledger is clean and the realm is quiet. Your word?"},
    ])
    r.master_says("Is the gate ledger clean?")
    tail = [(e["speaker"], e["addressee"]) for e in r.hall.entries()[-4:]]
    assert tail == [("master", None), ("wizard", "warrior"),
                    ("warrior", "general"), ("general", "master")]


def test_a_wandering_council_is_closed_by_the_general(space, monkeypatch):
    """The leash: a council that never settles gets a bounded number of turns,
    then the General is made to bring where things stand to the Master."""
    r = _realm(space, monkeypatch)
    r.light()
    bounce = [{"text": "Wizard, are you sure?"},
              {"text": "General, quite sure — ask me again."}]
    r.backend = ScriptBackend([{"text": "General, weigh this with me."}] + bounce * 12)
    before = len(r.hall.entries())
    r.master_says("Ponder this forever.")
    entries = r.hall.entries()[before:]
    last = entries[-1]
    assert last["speaker"] == "general" and last["addressee"] == "master"
    assert len(entries) <= 13  # the Master's word + the cap + the forced close


def test_taint_flag_rides_the_close(space, monkeypatch):
    """Whatever the Warrior pulls from outside flags the General's close —
    the Eighth Evangelism, surviving the move to dynamic turns."""
    r = _realm(space, monkeypatch)
    r.light()
    r._tainted.append("example.com")  # as web_fetch would, mid-round

    class Tainting(ScriptBackend):
        def __init__(self, realm, script):
            super().__init__(script)
            self.realm = realm

        def chat(self, messages, tools=None):
            res = super().chat(messages, tools)
            if res.content and res.content.startswith("Done"):
                self.realm._tainted.append("outside.example")
            return res

    r.backend = Tainting(r, [
        {"text": "Warrior, fetch the notice from outside.example."},
        {"text": "Done. General, I crossed and brought it home."},
        {"text": "Master — we have the notice. Your word?"},
    ])
    r.master_says("Bring me the notice.")
    close = r.hall.entries()[-1]
    assert close["addressee"] == "master"
    assert "tainted" in close["text"]
    assert "outside.example" in close["text"]
    # ...and only what THIS round touched is flagged, not the whole day's list.
    assert "example.com" not in close["text"]
