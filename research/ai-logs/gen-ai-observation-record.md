# Gen-AI Observation Record — Track A (Profiles/Rewards, Checkout)

| Field | Value |
|-------|-------|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Track | A (Build) — Profiles and rewards; Checkout |
| Author | Allan |
| Process area | Technical Processes (TP.1–TP.3) |

## Purpose

This record documents gen-AI tool behavior observed at each lifecycle stage of
the Track A feature verticals. Each entry records the tool interaction, the output
received, the value it provided, the errors or omissions identified, and the human
correction applied. Entries are recorded at the time the work is performed, so
that the account reflects observed behavior rather than reconstruction.

The intent is consistent with the P26044 Technical Processes objective: to
establish, from grounded observation, where gen-AI tool use produces trustworthy
engineering outcomes and where it does not.

## Record structure

Each stage is recorded under the following headings: tool and model; prompt as
issued; output received; value provided; errors or omissions; human correction
applied; cross-track impact.

---

## Stage 1 — Requirements Engineering (TP.1)

**Tool and model.** [e.g., Claude Opus 4.8]
**Feature.** Profiles and rewards; Checkout
**Prompt as issued.**

```
[Paste the requirements-drafting prompt.]
```

**Output received.** [Record the requirement statements the tool produced.]

**Value provided.** [Record the genuine contribution — e.g., rapid conversion of
the feature brief into structured requirement statements in a consistent format.]

**Errors or omissions.** The tool introduced domain assumptions that were not
present in the prompt. Each is catalogued in the requirements specification
gap log (`docs/requirements/requirements-profiles-rewards-checkout.md`). The
tool did not, on its own, distinguish assumptions it had introduced from
requirements that had been supplied to it. [Record the specific assumptions.]

**Human correction applied.** [Record which requirements were kept, edited, or
rejected, and how each introduced assumption was resolved.]

**Cross-track impact.** [Record whether any requirement affects an interface
consumed by another track.]

---

## Stage 2 — Architecture and Design (TP.2)

**Tool and model.** [e.g., Claude Opus 4.8]
**Feature.** Rewards calculation and storage

**Summary.** This stage is recorded in full in ADR-001, Section 5. In brief: the
tool's initial design output defaulted to a persisted mutable-balance model and
omitted the reversibility and concurrency constraints that ultimately governed
the decision. The immutable-ledger model was not surfaced until those constraints
were named by the practitioner. The observation — that AI-assisted design
produces structurally coherent artifacts calibrated to the training distribution,
with silent domain-specific omissions detectable only through domain expertise —
is developed there, together with its implication for the TP.2 sub-process
definition.

**Cross-reference.** `docs/adr/ADR-001-reward-points-calculation-and-storage.md`, Section 5.

---

## Stage 3 — Implementation (TP.3)

**Tool and model.** [e.g., Claude Opus 4.8]
**Feature.** [profiles / rewards / checkout]
**Prompt as issued.**

```
[Paste the implementation prompt.]
```

**Output received.** [Record the generated code at a functional level.]

**Value provided.** [Record the genuine contribution — e.g., generation of
boilerplate and routine structure, measurable time saving on repetitive work.]

**Errors or omissions.** [Record any generated code that passed a surface check
while carrying latent defects or technical debt — the concern that Track B and
Track C subsequently inherit. Record security-relevant issues separately.]

**Human correction applied.** [Record what was changed and the reason.]

**Cross-track impact.** [Record endpoint or contract changes relevant to Tracks
B, C, or D.]
