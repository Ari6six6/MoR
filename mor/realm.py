"""The day — light to dark — and the scheduler that runs it.

`light` opens a day: the last Chant is posted first, then Wizard, General, and
Warrior wake in that order (forced by the single shared mind — they queue at the
one oracle), each runs its waking, and the General greets the Master. From then
the Master's word drives a closed loop through the Hall until he says `dark`,
when each writes its walls, the Wizard sings the day's Chant, and the loop closes.
"""

from __future__ import annotations

from mor import agents, world
from mor.agents import ROLES, line
from mor.hall import Hall
from mor.engine import make_backend
from mor import ui


class Realm:
    def __init__(self, space, *, echo: bool = True):
        self.space = space
        self.echo = echo
        self.backend, self.mode = make_backend()
        self.day = None
        self.hall = None
        self.awake = False

    # -- dawn ------------------------------------------------------------
    def light(self) -> None:
        if self.awake:
            print(ui.yellow("The day is already lit. Say `dark` to end it."))
            return
        # Refresh the mind so a `gpu serve` since startup takes the throne now.
        self.backend, self.mode = make_backend()
        self.day = self.space.next_day_number()
        self.hall = Hall(self.space, self.day, echo=self.echo)
        print(ui.bold(ui.green(
            f"\n  ☀  Day {self.day} breaks over the realm  ")) + ui.dim(
            f"(mind: {self.mode})") + "\n")

        # The morning song: yesterday's Chant, first thing in the Hall.
        prev = self.space.chant_path(self.day - 1)
        if prev.exists():
            self.hall.post("chant", None, prev.read_text().strip())

        # Wake in order — Wizard, General, Warrior — each queues at the one mind.
        tail = self.hall.tail_text()
        for role in ROLES:
            addressee = None
            self.hall.post(role, addressee, line(self.backend, self.space, role, "wake",
                                                 hall_tail=tail))
            tail = self.hall.tail_text()

        # The General turns to the Master and asks for the word.
        self.hall.post("general", "master",
                       line(self.backend, self.space, "general", "greet_master",
                            hall_tail=self.hall.tail_text()))
        self.awake = True

    # -- the living loop -------------------------------------------------
    def master_says(self, text: str) -> None:
        if not self.awake:
            print(ui.yellow("The realm is asleep. Say `light` to wake it."))
            return
        h = self.hall
        # The Master's word — addressed to no one, caught automatically.
        h.post("master", None, text)

        def say(role, kind, heard):
            addr = {"wizard": "general", "general": "wizard",
                    "warrior": "general"}.get(role)
            out = line(self.backend, self.space, role, kind, heard=heard,
                       hall_tail=h.tail_text())
            h.post(role, addr, out)
            return out

        # Rule 2: the Wizard always catches the Master's word first.
        w = say("wizard", "wizard_takes", text)
        # Council: General tests it, Wizard agrees — mutual consent closes it.
        g = say("general", "general_debates", w)
        say("wizard", "wizard_agrees", g)
        # The General opens the gate: a sortie for the Warrior.
        order = line(self.backend, self.space, "general", "order_warrior", heard=text,
                     hall_tail=h.tail_text())
        h.post("general", "warrior", order)

        sortie = agents.warrior_sortie(self.space, order)
        h.post("warrior", "general",
               line(self.backend, self.space, "warrior", "warrior_reports", heard=text,
                    hall_tail=h.tail_text()))
        h.post("warrior", "general", sortie["report"])

        if sortie["escalate"]:
            # Chain of command: the General escalates to the Master for the gate.
            h.post("general", "master",
                   f"We must reach {sortie['escalate']}, but the gate is shut for it. "
                   f"Say `authorize {sortie['escalate']}` to open it, and I send him again.")
            return

        # The General brings the settled council back to the Master.
        h.post("general", "master",
               line(self.backend, self.space, "general", "general_to_master", heard=text,
                    hall_tail=h.tail_text()))

    def authorize(self, domain: str) -> None:
        self.space.authorize(domain)
        print(ui.green(f"  ⛬  The gate is now open for {domain}."))
        if self.awake and self.hall:
            self.hall.post("master", "general", f"The gate is open for {domain}.")
            self.hall.post("general", "master",
                           f"Understood, Master. The gate stands open for {domain}; "
                           "the Warrior may cross there on the next order.")

    # -- dusk ------------------------------------------------------------
    def dark(self) -> None:
        if not self.awake:
            print(ui.yellow("The realm is already asleep."))
            return
        print(ui.bold(ui.blue(f"\n  ☾  Night falls on Day {self.day}  ")) + "\n")
        h = self.hall
        # Each reminisces and writes its walls (bodies die nightly, walls persist).
        for role in ROLES:
            inside = line(self.backend, self.space, role, "inside_wall",
                          hall_tail=h.tail_text())
            outside = line(self.backend, self.space, role, "outside_wall",
                           hall_tail=h.tail_text())
            self.space.inside_wall_path(role).parent.mkdir(parents=True, exist_ok=True)
            self.space.inside_wall_path(role).write_text(inside.strip() + "\n")
            self.space.outside_wall_path(role).write_text(outside.strip() + "\n")
            print(ui.dim(f"  {ui.GLYPH.get(role, role)} wrote its walls."))

        # The Wizard sings the day's Chant — the one memory that crosses the night.
        chant = line(self.backend, self.space, "wizard", "chant", hall_tail=h.tail_text())
        self.space.chant_path(self.day).write_text(chant.strip() + "\n")
        print("\n" + ui.hall_line("chant", None, chant.strip()) + "\n")

        self.space.commit_day(self.day)
        print(ui.dim(f"  Day {self.day} is sealed. The realm sleeps. "
                     f"Say `light` to wake it new.\n"))
        self.awake = False
        self.day = None
        self.hall = None
