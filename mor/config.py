"""Paths, the project `space`, day counter, gate allowlist, and GPU state.

MoR keeps its home under $MOR_HOME (default ~/.mor). A *space* is one realm's
world on disk — its days, chants, walls, world-map, personas, and gate. The
`space` convention survives from Hermes: `space use <name>` / `space new <name>`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def mor_home() -> Path:
    return Path(os.environ.get("MOR_HOME", str(Path.home() / ".mor")))


def gpu_state_path() -> Path:
    return mor_home() / "gpu.json"


def current_space_file() -> Path:
    return mor_home() / "current_space"


def spaces_root() -> Path:
    return mor_home() / "spaces"


def current_space_name() -> str:
    f = current_space_file()
    if f.exists():
        name = f.read_text().strip()
        if name:
            return name
    return "realm"


def use_space(name: str) -> None:
    mor_home().mkdir(parents=True, exist_ok=True)
    current_space_file().write_text(name.strip() + "\n")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


class Space:
    """One realm's world on disk."""

    def __init__(self, name: str):
        self.name = name
        self.root = spaces_root() / name

    # --- lifecycle -------------------------------------------------------
    def ensure(self) -> "Space":
        for sub in ("personas", "population", "chants", "days"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        return self

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    def state(self) -> dict:
        return load_json(self.state_path, {"last_day": 0})

    def save_state(self, state: dict) -> None:
        save_json(self.state_path, state)

    def next_day_number(self) -> int:
        st = self.state()
        return int(st.get("last_day", 0)) + 1

    def commit_day(self, n: int) -> None:
        st = self.state()
        st["last_day"] = int(n)
        self.save_state(st)

    # --- artifacts -------------------------------------------------------
    def hall_path(self, day: int) -> Path:
        return self.root / "days" / f"day-{day:04d}" / "hall.jsonl"

    def chant_path(self, day: int) -> Path:
        return self.root / "chants" / f"day-{day:04d}.md"

    def persona_path(self, role: str) -> Path:
        return self.root / "personas" / f"{role}.md"

    def inside_wall_path(self, role: str) -> Path:
        return self.root / "population" / role / "inside_wall.md"

    def outside_wall_path(self, role: str) -> Path:
        return self.root / "population" / role / "outside_wall.md"

    def world_path(self) -> Path:
        return self.root / "world.json"

    def gate_path(self) -> Path:
        return self.root / "gate.json"

    # --- gate (egress allowlist) ----------------------------------------
    # The gate is the always-lit safety rail (the Eighth Evangelism, the taint
    # boundary): the Warrior crosses only to a domain the Master has authorized.
    # `authorize *` opens it wide in one word — full power, zero friction — for a
    # Master who wants nothing between him and the world.
    def allowlist(self) -> list:
        return load_json(self.gate_path(), {"domains": []}).get("domains", [])

    def egress_allowed(self, domain: str) -> bool:
        al = self.allowlist()
        return "*" in al or domain in al

    def authorize(self, domain: str) -> None:
        data = load_json(self.gate_path(), {"domains": []})
        domains = data.setdefault("domains", [])
        if domain not in domains:
            domains.append(domain)
        save_json(self.gate_path(), data)


def load_space() -> Space:
    return Space(current_space_name()).ensure()
