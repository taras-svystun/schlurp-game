# Schlurp

A local Schlurp game (the Microscope puzzle from "The 7th Guest", also known as Ataxx) in Python (Pygame) for playing people and AI agents, and a lab for writing and comparing AI agents.

- `CONTEXT.md`: the glossary. Use its terms in code, docs and commit messages.
- `docs/PLAN.md`: the roadmap and what we agreed. Read it when starting a step.
- `docs/adr/`: decisions and their reasons. Read before changing the rules, the engine or a tech choice.
- `docs/journal.md`: plain-English history of every finished step.
- `docs/agents/`: one file per AI agent, explaining how it works.

## Working with Taras

Taras knows Python well and is new to AI-assisted coding. Reply to him in Ukrainian. Write everything in the repo (code, comments, docs, commits) in plain, simple English, so it reads like he wrote it.

Tournaments heat up Taras's laptop. We have no plain Minimax agent: search agents start at AlphaBeta, which plays the same moves for far less work. Ask Taras before running a tournament that will take more than about 10 minutes.

This project is built on the patterns of Taras's Awalé project in `/Users/taras-svystun/Documents/Projects/awale-game`. That folder is read-only: read it for ideas, but never change, commit to or run tournaments in it.

AI agents are a shared lesson. I write every agent, with its tests and Tournament wiring. For each one I explain it to Taras in detail and in simple words: the idea behind it, how the code works step by step, and why it plays the way it does. Taras reads, asks questions and experiments with it.

## Finishing a step

A step is one item in `docs/PLAN.md`, or a smaller piece agreed in chat. It is done when all of these are true:

1. Tests pass: `.venv/bin/pytest`.
2. `README.md` has a copy-paste command for every way to run the project. Taras should never guess a command.
3. `docs/journal.md` has a new entry: what we did, why, and how, in a few short lines.
4. If the step adds or changes an agent, `docs/agents/<agent>.md` explains it: the idea, how the code works, an example on a real position, and what tournaments show about it.
5. The step is ticked in `docs/PLAN.md`.
6. The work is committed. Subject: imperative, under 72 characters. Body: why the change exists, so a reader a year later understands the reason. One commit per logical change.
7. The commits are pushed to `origin`.
8. My reply to Taras has a short summary (what, why, how) and a "check it yourself" list: exact commands to run and things to click. If the step adds an agent, the reply also explains it in detail, in Ukrainian.
