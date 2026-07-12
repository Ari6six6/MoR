"""The Theory of the World — the Wizard's map of everywhere the realm has reached.

The Warrior gathers the raw facts on his sorties (domains, IPs, paths, what came
back); the Wizard folds them into this persistent JSON map at dawn; the General
reads it for strategy. Plain data — a cartography of the outside, kept honest.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

from mor.config import load_json, save_json


def _domain_of(target: str) -> str:
    t = target.strip()
    if "://" not in t:
        t = "//" + t
    host = urlparse(t).hostname or target.strip()
    return host.lower()


def load(space) -> dict:
    return load_json(space.world_path(), {"places": {}})


def save(space, data) -> None:
    save_json(space.world_path(), data)


def record_sortie(space, target: str, note: str = "") -> dict:
    """Fold one Warrior sortie into the map. Returns the place record."""
    data = load(space)
    places = data.setdefault("places", {})
    domain = _domain_of(target)
    place = places.setdefault(domain, {
        "domain": domain,
        "first_seen": time.strftime("%Y-%m-%d"),
        "visits": 0,
        "notes": [],
    })
    place["visits"] += 1
    place["last_seen"] = time.strftime("%Y-%m-%d")
    if note:
        place["notes"] = (place.get("notes", []) + [note])[-5:]
    save(space, data)
    return place


def summary(space, limit: int = 6) -> str:
    """A one-line-per-place digest the Wizard can speak plainly in the Hall."""
    places = load(space).get("places", {})
    if not places:
        return "the map of the outside is still blank — we have touched nothing yet"
    ranked = sorted(places.values(), key=lambda p: p.get("visits", 0), reverse=True)
    bits = [f"{p['domain']} (seen {p.get('visits', 0)}×)" for p in ranked[:limit]]
    return "known places: " + ", ".join(bits)
