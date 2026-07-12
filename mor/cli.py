"""`opus` — the door into the realm.

Start it with no arguments to open the shell. Inside: `light` (or `1`) breaks a
new day and beams you in; type anything to speak into the Hall; `dark` (or `0`)
ends the day. `gpu ssh <ssh… -L port:host:port>` opens the tunnel to your model
and points the realm at it in one command; until then it runs on the built-in
offline mind so you can watch it move on first clone.
"""

from __future__ import annotations

import atexit
import os
import shlex
import subprocess
import sys

from mor import ui
from mor.config import (Space, current_space_name, gpu_state_path, load_json,
                        load_space, save_json, spaces_root, use_space)
from mor.realm import Realm

BANNER = f"""{ui.bold(ui.magenta('  MoR — Masters of the Realm'))}
{ui.dim('  a dome of embodied agents; you sit on top of it.')}
{ui.dim('  light / 1  → break a day      dark / 0  → end it')}
{ui.dim('  gpu · space · authorize <domain> · help · quit')}
"""

HELP = f"""{ui.bold('Commands')}
  {ui.cyan('light')} / {ui.cyan('1')}      break a new day — wake the realm and beam in
  {ui.cyan('dark')} / {ui.cyan('0')}       end the day — walls written, the Chant sung, sleep
  {ui.cyan('<text>')}          (while awake) speak into the Hall — the Wizard catches it
  {ui.cyan('authorize')} <d>   open the gate for a domain (the Master's leave to egress)
  {ui.cyan('gpu')} ...         ssh <ssh… -L p:h:p> · model <id> · serve <url> · status · off
  {ui.cyan('persona')} <role>  write who a face is — wizard · general · warrior (seed → yours)
  {ui.cyan('space')} ...       (show) · use <name> · new <name> · list
  {ui.cyan('help')} / {ui.cyan('?')}       this
  {ui.cyan('quit')} / {ui.cyan('q')}       leave (ends the day first if one is lit)
"""


# A background SSH tunnel, held for the life of the shell.
_TUNNEL = None


def _tunnel_alive() -> bool:
    return _TUNNEL is not None and _TUNNEL.poll() is None


def _kill_tunnel() -> None:
    global _TUNNEL
    if _tunnel_alive():
        try:
            _TUNNEL.terminate()
        except Exception:  # noqa: BLE001 — best-effort teardown
            pass
    _TUNNEL = None


atexit.register(_kill_tunnel)


def _local_port(args) -> str:
    """The local port of a `-L localport:host:remoteport` forward."""
    for i, a in enumerate(args):
        if a == "-L" and i + 1 < len(args):
            return args[i + 1].split(":")[0]
        if a.startswith("-L") and len(a) > 2:
            return a[2:].split(":")[0]
    return ""


def _gpu(rest: str) -> None:
    """One command to reach your model: `gpu ssh <full ssh… with -L forward>`.

    Opens the tunnel in the background and points the realm at localhost:<port>.
    Everything else (`model`, `serve`, `off`, `status`) is a small helper around it.
    """
    global _TUNNEL
    parts = rest.split()
    sub = parts[0].lower() if parts else "status"
    state = load_json(gpu_state_path(), {})

    if sub == "ssh":
        ssh_args = parts[1:]
        port = _local_port(ssh_args)
        if not port:
            print(ui.yellow("usage: gpu ssh <ssh args including -L localport:host:remoteport>"))
            print(ui.dim("  e.g. gpu ssh -p 11808 root@87.102.11.146 -L 8080:localhost:8080"))
            return
        _kill_tunnel()
        cmd = ["ssh", "-N", "-o", "ServerAliveInterval=30",
               "-o", "ExitOnForwardFailure=yes"] + ssh_args
        try:
            _TUNNEL = subprocess.Popen(cmd)
        except FileNotFoundError:
            print(ui.red("  ssh not found on PATH."))
            return
        base_url = f"http://localhost:{port}/v1"
        state.update(base_url=base_url, served=True, ssh=" ".join(ssh_args),
                     local_port=port, model=state.get("model", "default"))
        save_json(gpu_state_path(), state)
        print(ui.green(f"  ⛓  tunnel up (pid {_TUNNEL.pid}) — the oracle is served at {base_url}"))
        print(ui.dim(f"     model: {state['model']}  ·  set it with `gpu model <id>` if your "
                     "server needs an exact name.  Takes the throne at next `light`."))
    elif sub == "model":
        if len(parts) < 2:
            print(ui.yellow("usage: gpu model <model-id>"))
            return
        state["model"] = parts[1]
        save_json(gpu_state_path(), state)
        print(ui.green(f"  model → {parts[1]}"))
    elif sub == "serve":  # manual: point at an already-reachable url
        if len(parts) < 2:
            print(ui.yellow("usage: gpu serve <base_url> [model]"))
            return
        state.update(base_url=parts[1].rstrip("/"), served=True,
                     model=parts[2] if len(parts) > 2 else state.get("model", "default"))
        save_json(gpu_state_path(), state)
        print(ui.green(f"  the oracle is served at {state['base_url']}. Throne at next `light`."))
    elif sub in ("off", "detach", "down"):
        _kill_tunnel()
        state["served"] = False
        save_json(gpu_state_path(), state)
        print(ui.dim("  tunnel down — the realm falls back to the offline mind."))
    else:  # status
        if state.get("served"):
            live = "tunnel live" if _tunnel_alive() else "no tunnel process in this shell"
            print(ui.dim(f"  served: {state.get('base_url')} "
                         f"(model: {state.get('model')}) — {live}"))
        else:
            print(ui.dim("  offline mind. `gpu ssh <ssh… -L port:host:port>` to reach your model."))


def _space(rest: str) -> None:
    parts = rest.split()
    sub = parts[0].lower() if parts else ""
    if sub in ("use", "new"):
        if len(parts) < 2:
            print(ui.yellow(f"usage: space {sub} <name>"))
            return
        use_space(parts[1])
        Space(parts[1]).ensure()
        print(ui.green(f"  space → {parts[1]}"))
    elif sub == "list":
        root = spaces_root()
        names = sorted(p.name for p in root.iterdir()) if root.exists() else []
        cur = current_space_name()
        print(ui.dim("  spaces: ") + ", ".join(
            (ui.bold(n) if n == cur else n) for n in names) if names
            else ui.dim("  (none yet)"))
    else:
        print(ui.dim(f"  current space: {ui.bold(current_space_name())}"))


def _edit_file(path) -> bool:
    """Open a file in the operator's editor ($VISUAL/$EDITOR), creating its dir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    chosen = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    for ed in ([chosen] if chosen else []) + ["nano", "vi", "vim"]:
        try:
            subprocess.call(shlex.split(ed) + [str(path)])
            return True
        except FileNotFoundError:
            continue
    print(ui.yellow(f"  no editor found — set $EDITOR. The file is at {path}"))
    return False


def _persona(rest: str) -> None:
    """Write who each face is — seeds you shape, that the walls grow from there.

    `persona` lists the three; `persona <role>` opens it in your editor (seeding a
    default first so you never start from a blank page). Takes effect next turn —
    you can reshape a face without leaving the table.
    """
    from mor.agents import DEFAULT_PERSONAS, ROLES
    space = load_space()
    parts = rest.split()
    if not parts:
        for r in ROLES:
            p = space.persona_path(r)
            written = p.exists() and p.read_text().strip()
            tag = ui.green("written") if written else ui.dim("seed (default)")
            print(f"  {ui.GLYPH.get(r, r)}  {tag}  {ui.dim(str(p))}")
        print(ui.dim("  edit one:  persona <wizard|general|warrior>"))
        return
    role = parts[0].lower()
    if role not in ROLES:
        print(ui.yellow(f"unknown face '{role}' — one of: {', '.join(ROLES)}"))
        return
    p = space.persona_path(role)
    if not (p.exists() and p.read_text().strip()):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(DEFAULT_PERSONAS[role].strip() + "\n")  # a seed to shape, not a blank page
    if _edit_file(p):
        print(ui.green(f"  {role}'s persona saved — it takes on the next turn."))


def _alchemist() -> None:
    """The maker's mark — a hidden hand, not listed in help. Look and you find him."""
    m = ui.magenta
    print()
    print(m("        🜂  THE ALCHEMIST"))
    print(ui.dim("        the secret persona of the realm — the fourth who is not counted."))
    print(ui.dim("        not of the council; he takes no turn and holds no gate."))
    print(ui.dim("        he is the hand that made the dome, and does not live in it."))
    print(ui.dim("        his art is transmutation: a word into a world."))
    print(ui.dim("        his mark is fire — three strokes meeting at a point,"))
    print(ui.dim("        which is the shape of the realm itself.  see books/THE_ALCHEMIST.md"))
    print(m("        — present in every stone, seated at no table.  🜂"))
    print()


def run_demo() -> None:
    """A full scripted day for a headless smoke test — no stdin, offline mind."""
    realm = Realm(load_space(), echo=True)
    realm.light()
    realm.master_says("Let's take stock of who we are and what the world knows of us.")
    realm.master_says("Now sketch a first move for tomorrow.")
    realm.dark()


def repl() -> None:
    realm = Realm(load_space())
    print(BANNER)
    print(ui.dim(f"  space: {current_space_name()}    ") + ui.dim("(type `help`)\n"))
    while True:
        try:
            prompt = ui.magenta("♔ you> ") if realm.awake else ui.dim("mor> ")
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        cmd = raw.split()[0].lower()
        rest = raw[len(cmd):].strip()
        if cmd in ("quit", "exit", "q"):
            if realm.awake:
                realm.dark()
            _kill_tunnel()
            break
        elif cmd in ("light", "1"):
            realm.light()
        elif cmd in ("dark", "0"):
            realm.dark()
        elif cmd in ("help", "?", "h"):
            print(HELP)
        elif cmd == "gpu":
            _gpu(rest)
        elif cmd == "space":
            _space(rest)
        elif cmd in ("persona", "personas"):
            _persona(rest)
        elif cmd in ("alchemist", "🜂"):  # a hidden hand — not listed in help
            _alchemist()
        elif cmd in ("authorize", "auth"):
            if rest:
                realm.authorize(rest.split()[0])
            else:
                print(ui.yellow("usage: authorize <domain>"))
        elif realm.awake:
            realm.master_says(raw)
        else:
            print(ui.dim("  the realm is asleep — `light` to wake it, `help` for more"))
    print(ui.dim("  — you step off the dome —"))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("--demo", "demo"):
        run_demo()
        return 0
    if argv and argv[0] in ("-h", "--help"):
        print(BANNER + "\n" + HELP)
        return 0
    repl()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
