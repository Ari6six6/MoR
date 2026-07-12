"""`hermes` — the door into the realm.

Start it with no arguments to open the shell. Inside: `light` (or `1`) breaks a
new day and beams you in; type anything to speak into the Hall; `dark` (or `0`)
ends the day. `gpu serve <url>` points the realm at your real model; until then
it runs on the built-in offline mind so you can watch it move on first clone.
"""

from __future__ import annotations

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
  {ui.cyan('gpu')} ...         serve <url> [model] · attach <host> · status · off
  {ui.cyan('space')} ...       (show) · use <name> · new <name> · list
  {ui.cyan('help')} / {ui.cyan('?')}       this
  {ui.cyan('quit')} / {ui.cyan('q')}       leave (ends the day first if one is lit)
"""


def _gpu(rest: str) -> None:
    parts = rest.split()
    sub = parts[0].lower() if parts else "status"
    state = load_json(gpu_state_path(), {})
    if sub == "serve":
        if len(parts) < 2:
            print(ui.yellow("usage: gpu serve <base_url> [model]"))
            return
        state.update(base_url=parts[1].rstrip("/"), served=True,
                     model=parts[2] if len(parts) > 2 else state.get("model", "mor"))
        save_json(gpu_state_path(), state)
        print(ui.green(f"  The oracle is served at {state['base_url']} "
                       f"(model: {state['model']}). It takes the throne at next `light`."))
    elif sub == "attach":
        if len(parts) < 2:
            print(ui.yellow("usage: gpu attach <host> [user] [port]"))
            return
        state.update(host=parts[1], user=parts[2] if len(parts) > 2 else "root",
                     port=int(parts[3]) if len(parts) > 3 else 22)
        save_json(gpu_state_path(), state)
        print(ui.green(f"  GPU box noted: {state.get('user')}@{state['host']}. "
                       "Serve a model on it and `gpu serve <url>` to use it."))
    elif sub in ("off", "detach"):
        state["served"] = False
        save_json(gpu_state_path(), state)
        print(ui.dim("  The realm falls back to the offline mind."))
    else:  # status
        if state.get("served"):
            print(ui.dim(f"  served: {state.get('base_url')} (model: {state.get('model')})"))
        else:
            print(ui.dim("  offline mind (no served oracle). `gpu serve <url>` to attach one."))


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
