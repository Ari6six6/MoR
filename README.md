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
./hermes            # or: pip install -e .  &&  hermes
```

Then, inside the shell:

```
light               # break a new day — the realm wakes and beams you in
<type anything>     # speak into the Hall; the Wizard always catches it first
dark                # end the day — walls written, the Chant sung, sleep
```

Want to watch a whole day move without typing? `./hermes --demo`.

### Full power by default

The realm ships at **full power** — every faculty is on the moment you enter;
there are no opt-in flags to raise. The one rail that stays lit (by design — it's
your General's whole job, and the taint boundary of the Eighth Evangelism) is the
egress gate: the Warrior crosses only to a domain the Master has opened.

```
authorize example.com   # open the gate for one place
authorize *             # open it wide — full power, nothing between you and the world
```

### The mind

Out of the box the realm runs on a **built-in offline mind** — a deterministic,
in-character stand-in so you can *see* it breathe on first clone. Point it at your
real model when you have one served (vLLM / llama.cpp, OpenAI-compatible):

```
gpu serve http://localhost:8000/v1 [model-name]   # takes the throne at next `light`
gpu off                                            # back to the offline mind
```

## What runs today, and what's next

**Running now (`mor/`):** the Hall (one shared, plain-English-only transcript,
streamed live and kept on disk), the wake order, the scheduler and the closed
council loop, `light`/`dark`, the Chant (written at dusk, sung first at dawn), the
two walls (written nightly, persisted per inhabitant), the chain-of-command gate
(the Warrior only crosses to a domain the Master has `authorize`d), and the
Wizard's **Theory of the World** (a JSON map that grows with every sortie).

**Next**, per **[The Realm §10](books/THE_REALM.md#10-what-gets-retired-what-survives-whats-new)**:
give each face a real Docker body on the dome (the embodiment already sketched in the
Hermes `village.py`), and write the three personas into `personas/{wizard,general,warrior}.md`
— they're living seeds; the walls grow them from there.

*Here begins the Realm. It is written down so it will not be lost.*
