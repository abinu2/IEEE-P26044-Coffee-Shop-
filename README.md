# IEEE P26044 — Coffee Shop Reference Project

**Project:** IEEE P26044 / C/S2ESC — Week 3 Group Assignment
**Process areas exercised:** Technical Processes (TP.1–TP.6), Governance Processes (GP.1–GP.4)
**Track A owner (Profiles/Rewards, Checkout):** Allan
**Date:** 07-30-2026

## 1. Purpose

This repository contains a small online coffee-ordering application built as a
shared instrument for empirical observation of gen-AI tool behavior across the
software engineering lifecycle. The application is not the deliverable. The
deliverable is a grounded, honestly-represented record of where AI-assisted
development produced trustworthy output, where it produced output that was
structurally plausible but semantically incomplete, and what human judgment was
required to close that gap at each lifecycle stage.

This purpose follows directly from the P26044 Technical Processes framing: the
objective is to identify and evaluate potential best practices, not to document
typical practice as though it were trustworthy. A considerable amount of current
gen-AI tool use may not meet the bar the standard is designed to establish, and
that distinction can only be drawn by recording actual observed behavior rather
than assumed capability.

## 2. Track structure

The application is examined concurrently from four tracks. The coordination
required between them constitutes the System Integration (TP.5) experience; it is
observed through the hand-off artifacts in `docs/comms/`, not through any single
report.

| Track | Scope | P26044 mapping |
|-------|-------|----------------|
| A — Build | Requirements, architecture, and implementation of the application | TP.1–TP.3 |
| B — Regression | AI agent executing regression tests as a deployment gate | TP.4 |
| C — Runbooks | AI-generated incident-response runbooks derived from Track A code | TP.6 |
| D — Governance | Authorization, risk tiering, and audit applied to the Track B and C agents | GP.1–GP.4 |

## 3. Track A ownership

Track A is divided by feature vertical rather than by lifecycle activity, so that
each owner carries their features from requirements through implementation and
test without contention over shared layers.

| Owner | Features | Architecture decision record |
|-------|----------|------------------------------|
| Allan | Profiles and rewards; Checkout | ADR-001 (reward calculation and storage) |
| [Teammate name] | Cart; Fulfillment | ADR-002 (fulfillment state model) |

The interface between the two verticals — the shared database schema and the
cart→checkout and checkout→fulfillment API contracts — is fixed before parallel
implementation begins. It is recorded in `docs/comms/day-one-contract.md`.

## 4. Repository structure

```
docs/
  adr/            Architecture decision records, one decision per record
  requirements/   Requirements specifications and AI-assumption gap logs
  comms/          Inter-track coordination: interface contracts and increment log
  reference/      Assignment brief and supporting material
research/
  ai-logs/        Per-stage gen-AI observation records
app/
  main.py         FastAPI application entry point
  models.py       SQLAlchemy schema (day-one contract, Section 2)
  schemas.py      Pydantic request/response models (contracts, Section 3)
  db.py           Session and transaction configuration
  routers/        HTTP surface, one module per feature area
  services/       Domain logic; rewards.py is the ADR-001 implementation
tests/            pytest; test_reward_ledger.py holds the ADR-001 invariant
```

## 4a. Running it

```
pip install -r requirements.txt
uvicorn app.main:app --reload      # API at 127.0.0.1:8000, contracts at /docs
pytest                             # invariant suite
```

The database file (`coffee.db`) is created on first start and is not committed;
the schema is reproducible from `app/models.py` alone.

## 5. Technology stack

Python with FastAPI (typed request and response models, making the API contract
explicit for downstream tracks); SQLite via SQLAlchemy (single-file store,
identical across all contributors, zero infrastructure setup); pytest for tests;
GitHub Actions for continuous integration. The stack is deliberately conventional
so that observed AI behavior reflects the tooling rather than the novelty of the
environment.

## 6. Track A deliverables

- The application source (`app/`) and the ADR-001 invariant suite (`tests/`)
- Requirements specification with AI-assumption gap log (`docs/requirements/`)
- Architecture decision record ADR-001 (`docs/adr/`)
- Per-stage gen-AI observation record (`research/ai-logs/`)
- Interface contract and increment log (`docs/comms/`)

## References

[1] IEEE P26044, *Software and Systems Engineering: Reference Model on
Capabilities of Generative Artificial Intelligence Tools for Software
Engineering* (in development), IEEE Computer Society S2ESC.
[2] ISO/IEC/IEEE 12207:2017, *Systems and Software Engineering — Software Life
Cycle Processes.*
