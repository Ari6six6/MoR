# MoR — Masters of the Realm

*A dome of embodied agents who know who they are, who the others are, where everyone
lives, and how they relate. One mind, many bodies, one Master on top of the dome.*

MoR is the next evolution of the Hermes harness: not one agent driven from a phone,
but a small **realm** of embodied personas living on a local network — each with its
own private inner voice, all speaking plainly in one shared **Hall** the Master can
watch and steer. The word that started it was **superposition**: every inhabitant
holds the map of all the others.

---

## The realm, in one breath

- **The Master of the Realm** — you. On top of the dome. Speaks to one, sees all.
- **The Wizard** — the seer and the memory. Wakes first, sings the **Chant**, keeps
  the **Theory of the World**. Never leaves.
- **The General** — the first lieutenant. The only one who talks with the Master.
  Owns the **strategy** and the **gate**. Audits the Wizard. Never leaves.
- **The Warrior** — the arm. The only one who ever leaves the dome to the web. Strict,
  practical, a superb reporter. Brings the world home.

A **day** runs from `light` to `dark`. Everyone wakes in order, does their morning
routine, and lives one conversation in the Hall until the Master ends the day. At
dusk they write their **walls** (who I am / what I make of the others) and the Wizard
writes the day's **Chant** — the one song that carries across the night.

---

## The three books

Read them in order. They are the realm's scripture — the agents read them too.

1. **[Genesis](books/GENESIS.md)** — where the harness came from and the day it was
   given shoes. The covenant: *where there was data, there will be data.*
2. **[The Evangelisms](books/EVANGELISMS.md)** — the nine capabilities the harness
   learned, each with the sin it answers.
3. **[The Realm](books/THE_REALM.md)** — the design of what it is becoming. The full
   spec of the dome, the Hall, the day, the roles, and the rules. **Start here to
   build.**

And the record: **[The Founding](books/THE_FOUNDING.md)** — the verbatim transcript
of the conversation that designed and built the realm, kept whole in the covenant of
Genesis.

---

## Run it

The realm runs on the Python standard library — **no pip installs required.**

```sh
git clone https://github.com/Ari6six6/MoR.git
cd MoR
./opus                      # or: pip install -e .  &&  opus
```

Then, inside the shell:

```
light                       # break a new day — the realm wakes and beams you in
<type anything>             # speak into the Hall; the Wizard always catches it first
dark                        # end the day — walls written, the Chant sung, sleep
```

> The command is **`opus`**, never `hermes` — so it can't collide with the real
> Hermes harness (and its `gpu serve`). `./opus` is the local wrapper (no install);
> `pip install -e .` gives you a bare `opus`.

### Reaching your model — one command

```
gpu ssh -p 11808 root@87.102.11.146 -L 8080:localhost:8080
```

That opens the SSH tunnel in the background *and* points the realm at
`http://localhost:8080/v1` — the served mind takes the throne at the next `light`.
`gpu model <id>` if your server needs an exact model name; `gpu off` to drop the
tunnel and fall back to the offline mind; `gpu status` to check.

Want to watch a whole day move without typing? `./opus --demo`.

### What you get on first clone (the honest version)

There are no opt-in flags to raise — but a first run with **no model attached** is a
*deterministic stand-in*, not the full engine. The offline mind seeds each face's
line so the realm visibly moves and the loop runs, but it never calls a tool: the
real thinking, the Warrior's sorties, the taint rail, and the container bodies only
come alive once you attach a served model and (for bodies) Docker. `./opus --demo`
shows the stand-in moving; the engine itself is exercised by the test suite
(`pytest -q`) and by a served run.

### The gate

The realm's one egress is the Warrior's `web_fetch`, and it stays shut until you open
it. `run_shell` runs inside a container on the **internal** dome, so no shell can
reach the internet at all — `web_fetch` is the single, guarded way out.

```
authorize example.com   # open the gate for one domain
authorize *             # open it to any PUBLIC site
```

`authorize *` opens the gate to the public web only — the SSRF rail still refuses the
host's loopback, LAN, and cloud-metadata addresses even when the gate is wide open,
and the gate takes **one hop, never a chain**: redirects are not followed (a 3xx comes
back as a report naming the destination, which needs your leave like anywhere else).
Everything the Warrior brings back is tainted and flagged for your leave.

One honest limit of the taint rail: the flag guards what the realm *does* next — the
Warrior has already **read** what came back by the time you're asked. Reading is the
exposure a fetch inherently is; the rail ensures nothing is *acted on* without you.

### The mind

Out of the box the realm runs on a **built-in offline stand-in** — deterministic and
in-character so you can *see* it breathe on first clone (see the honest note above).
Reach your real model (vLLM / llama.cpp, OpenAI-compatible) with the one command:

```
gpu ssh -p <port> root@<host> -L 8080:localhost:8080   # tunnel + serve, one command
gpu model <model-id>                                    # if your server needs an exact name
gpu off                                                 # back to the offline mind
```

## What runs today, and what's next

MoR stands on **its own engine** (`mor/engine/`) — no framework underneath, Python
standard library only. It was cut from the wisdom of the Hermes harness (which lives
on in its own repo), but nothing of Hermes is vendored here; the realm runs on itself.

**Running now:**
- the **Hall** (one shared, plain-English-only transcript, streamed live, kept on
  disk) with the **bounded view** (a long day folds its middle, keeps the recent tail)
- the wake order, the closed council loop, `light`/`dark`
- the **name-mention scheduler** (the spec's §10.2): no fixed beats — the face a
  line names speaks next, the Wizard still catches the Master's word first, only
  the General closes to the Master, and a hard cap of turns makes a wandering
  council close honestly instead of talking the day away
- the **engine**: a real think→act loop (a face reasons, calls tools, reads results,
  speaks), with the reflex that pushes it to think when it acts without reasoning
- the **bodies**: at `light` each face gets a real container on the dome (DNA mounted,
  the Warrior's body alone wired to egress), harvested at `dark`
- the **gate + taint rail**: the Warrior only crosses to a Master-`authorize`d domain,
  one hop only (redirects refused, reported instead), and anything pulled from
  outside is flagged for the Master's leave
- the **Chant**, the **two walls**, and the Wizard's **Theory of the World** (grown
  from real sorties)

**Next** (cut MoR-native from the Hermes reference as they land): how *well* the
council deliberates now rests on the mind you attach — the honest note is that the
offline stand-in walks one fixed branch of the scheduler, and genuine branching only
shows with a served model. Then the **verify/skeptic** reflex (the General re-running
the Wizard's claims, not just flagging them), a wider toolbox, and `gpu` polish. And
the personas are yours — write them into `personas/{wizard,general,warrior}.md`;
they're living seeds the walls grow from there.

*Here begins the Realm. It is written down so it will not be lost.*
