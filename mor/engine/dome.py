"""The dome and the bodies — embodiment, cut from Hermes's sandbox/village.

Each face gets a real container body on a local Docker network (the dome). The
dome is `--internal` (kernel air-gap: siblings reach each other by name, nothing
reaches the internet), and only the Warrior's body is also wired to an egress
network — so at the kernel level, only the Warrior's hands can touch the outside.
DNA (lineage + relations) is written to disk and mounted read-only: superposition
a face's own code can read. Bodies die at dusk; the harvest keeps the record.

Everything degrades gracefully: no container runtime → `embodied` is False and the
realm runs disembodied (faces use a local workspace, no shell-in-body), exactly as
before. The dome is a body for the faces, never a requirement to speak.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import time

IMAGE = "python:3.12-slim"


def _sh(cmd: str, timeout: int = 60):
    """Run a local shell command; return (rc, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           errors="replace", timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except FileNotFoundError:
        return 127, "", "runtime not found"


def probe_runtime() -> str:
    """docker or podman if one is present and usable locally; '' otherwise."""
    for rt in ("docker", "podman"):
        rc, _, _ = _sh(f"{rt} version", timeout=15)
        if rc == 0:
            return rt
    return ""


class Dome:
    """The realm's bodies for one space. `up()` raises nothing — if there's no
    runtime it just stays disembodied."""

    def __init__(self, space, *, log=lambda *_: None):
        self.space = space
        self.log = log
        self.runtime = ""
        self.embodied = False
        self.bodies: dict[str, str] = {}  # role -> container name

    # -- names ----------------------------------------------------------
    def _slug(self, s: str) -> str:
        import re
        return re.sub(r"[^a-z0-9-]", "-", (s or "").lower()).strip("-") or "x"

    def network(self) -> str:
        return f"mor-{self._slug(self.space.name)}-dome"

    def body_name(self, role: str) -> str:
        return f"mor-{self._slug(self.space.name)}-{self._slug(role)}"

    # -- DNA (superposition on disk) ------------------------------------
    def _write_dna(self, role: str, roles: list) -> str:
        dna = self.space.root / "population" / role / "dna"
        dna.mkdir(parents=True, exist_ok=True)
        siblings = [r for r in roles if r != role]
        (dna / "lineage.json").write_text(json.dumps({
            "name": role, "space": self.space.name, "body": self.body_name(role),
            "can_egress": role == "warrior", "birth": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2) + "\n")
        (dna / "relations.json").write_text(json.dumps({
            "master": "the Master of the Realm (above the dome; speaks to the General)",
            "siblings": siblings,
            "addressable": [self.body_name(r) for r in siblings],
        }, indent=2) + "\n")
        return str(dna)

    # -- lifecycle ------------------------------------------------------
    def up(self, roles: list) -> bool:
        self.runtime = probe_runtime()
        if not self.runtime:
            self.log("  (no container runtime — the realm runs disembodied)")
            self.embodied = False
            return False
        rt, net = self.runtime, self.network()
        # The dome: internal, so nothing on it can reach the internet.
        _sh(f"{rt} network create --internal {shlex.quote(net)} 2>/dev/null || true")
        for role in roles:
            name = self.body_name(role)
            self.bodies[role] = name
            if _sh(f"{rt} ps -a --filter name=^{shlex.quote(name)}$ "
                   f"--format '{{{{.Names}}}}'")[1].strip() == name:
                continue  # already up
            ws = self.space.root / "population" / role / "workspace"
            ws.mkdir(parents=True, exist_ok=True)
            dna = self._write_dna(role, roles)
            cmd = (f"{rt} run -d --name {shlex.quote(name)} "
                   f"--network {shlex.quote(net)} "
                   f"--label mor.role={shlex.quote(role)} "
                   f"--label mor.space={shlex.quote(self.space.name)} "
                   f"-v {shlex.quote(str(ws))}:/work -w /work "
                   f"-v {shlex.quote(dna)}:/dna:ro "
                   f"{shlex.quote(IMAGE)} sleep infinity")
            rc, _, err = _sh(cmd, timeout=600)
            if rc != 0:
                self.log(f"  body for {role} failed to rise: {err.strip()[-120:]}")
                continue
            # Only the Warrior's body gets a route out — wire it to the default
            # bridge for egress; the others stay air-gapped on the internal dome.
            if role == "warrior":
                _sh(f"{rt} network connect bridge {shlex.quote(name)} 2>/dev/null || true")
            self.log(f"  {role}'s body rose on the dome as {name}")
        self.embodied = bool(self.bodies)
        return self.embodied

    def exec(self, role: str, cmd: str, timeout: int = 120):
        """Run a shell command inside a face's body. (rc, out, err)."""
        if not self.embodied or role not in self.bodies:
            return 127, "", "no body"
        rt = self.runtime
        return _sh(f"{rt} exec -w /work {shlex.quote(self.bodies[role])} "
                   f"sh -lc {shlex.quote(cmd)}", timeout=timeout)

    def down(self, roles: list | None = None) -> None:
        """Harvest then remove the bodies (bodies die nightly, the record stays)."""
        if not self.embodied:
            return
        rt = self.runtime
        for role, name in list(self.bodies.items()):
            pop = self.space.root / "population" / role
            pop.mkdir(parents=True, exist_ok=True)
            rc, out, _ = _sh(f"{rt} logs {shlex.quote(name)} 2>&1", timeout=30)
            if rc == 0 and out:
                (pop / "body.log").write_text(out[-20000:])
            _sh(f"{rt} rm -f {shlex.quote(name)} 2>/dev/null || true")
        self.bodies.clear()
        self.embodied = False
