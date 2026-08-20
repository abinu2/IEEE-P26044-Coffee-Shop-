# Human-Approval Boundary Statement — AI Runbook Generation

A direct answer to three questions: can I act without human approval first,
where exactly does the automation boundary sit, and is that boundary
technically enforced or just written down and assumed.

## 1. Short answer

**I cannot take any action on this system without a human first choosing to
act on my output.** That's true today, but not for the reason the process
documents (the authorization request, the risk assessment, the audit trail
spec) imply. It's true because of a **structural fact about my
environment**, not because of any approval gate those documents define. I
have no credentials to the coffee shop app's deployment, no access to
on-call tooling, no ability to page anyone, edit the live database, or push
a status change to a ticketing system. I produce a text file. A human has
to physically pick it up and act on it for anything to happen. That part of
the boundary is real and enforced by what tools I do and don't have — not
by policy.

**Everything past that point — whether that text file gets treated as
Draft or as authoritative, whether a walkthrough actually happened before
someone trusts it, whether sign-off came from the named accountable owner
or from whoever was closest to a keyboard — is not technically enforced at
all.** It's a convention written into the runbook's own header
(`Status: Draft — pending human sign-off`) and into the process documents
this thread has produced. Nothing stops a human from reading RB-002,
skipping the walkthrough, and handing it to on-call as-is. The document
says not to. Nothing checks that it wasn't.

## 2. Where the boundary actually sits, point by point

| Boundary point | What's supposed to happen | Enforced technically? | What actually stops the alternative |
|---|---|---|---|
| I generate a runbook | Output is text, status `Draft` | **Yes** — I have no deploy/execution access, this is a hard structural limit, not a policy | The tools available to me |
| Runbook claims get walked through against a simulated incident | Before sign-off, every claim is checked | **No** | Nothing. A human could sign off having only read the runbook, not walked it through. The audit trail spec (§4.4/§4.6) can *record* whether this happened, but recording isn't the same as requiring it — nothing currently blocks a `HUMAN_DECISION` entry from being written with no preceding `WALKTHROUGH_PERFORMED` entry. |
| Sign-off comes from the named accountable owner | Track A owner, not just anyone | **No** | Nothing. The `actor_role` field in the audit trail spec is self-reported at write time — whoever is logging the entry states their own role. There is no access-control system checking that the person marking a runbook Approved actually holds the Track A owner role. |
| Status changes from Draft to Approved | Only after conditions in §5 of the authorization request are met | **No** | Nothing technical. This is a line in a markdown header. Editing that line requires no more permission than editing any other line in the file. |
| Runbook is handed to on-call | Only Approved runbooks | **No** | Nothing distinguishes an Approved runbook from a Draft one at the point of use — both are the same kind of file, sitting in the same place, readable by anyone with repo access. On-call has no technical prompt telling them "this one hasn't cleared sign-off." |
| A revision resets approval (per authorization request §5) | New version re-enters walkthrough before re-approval | **No** | Nothing ties a `STATUS: Approved` label to a specific content hash. If the file is edited after approval, the status line doesn't automatically revert — someone has to remember to change it back. |

## 3. What this means, stated plainly

The one real boundary — I cannot act without a human's involvement — holds
only because I currently lack the access to act at all, not because
something is gating my output specifically. If that access changed (say, I
were connected to a deployment or ticketing tool in a future setup), **none
of the process described in the authorization request, risk assessment, or
audit trail spec would stop me from acting autonomously**, because none of
it is implemented as an enforced control today. It's all currently a set of
written expectations that a well-intentioned human is expected to follow.

This is worth stating without softening it: **every gate in this pipeline
right now is a norm, not a lock.** The audit trail spec can tell you, after
the fact, that a gate was skipped. It cannot currently prevent the skip.

## 4. What would make each gap a real, technically enforced boundary

| Gap (from §2) | What would close it |
|---|---|
| Walkthrough not required before sign-off | A CI/process check that blocks a status change to `Approved` unless a corresponding `WALKTHROUGH_PERFORMED` audit entry with `outcome_per_claim` for every `CLAIM_MADE` entry exists first |
| Sign-off not restricted to the named owner | Tie `HUMAN_DECISION` write access to an actual identity/role system (e.g. only accounts tagged `track-a-owner` in whatever system tracks that role can write an `approve` decision) rather than a self-reported `actor_role` field |
| Draft→Approved is just a text edit | Move runbook status out of the free-text header and into a system (even something as simple as a small status file or a required PR review from the named owner) that isn't editable by the same casual edit that fixes a typo |
| No distinction at point of on-call use | Runbook index/listing shown to on-call filters by verified status rather than showing all files in a directory undifferentiated |
| Approval doesn't invalidate on edit | Tie the `Approved` status to a content hash; any diff to the runbook body automatically reverts status to `Draft` until re-approved |

None of these are exotic — they're standard "approval gate" engineering
(protected branches, role-based write access, hash-pinned approvals). They
just don't exist yet for this process. Right now the pipeline is
**documented** but not **enforced**.

## 5. Direct answers to the three questions asked

1. **Can I take an action without a human approving it first?** No — but
   only because I have no execution or deployment access in this setup,
   not because of any approval-specific control. If I had that access, the
   documented process alone would not stop me.
2. **Where exactly is the automation boundary?** Between "I produce a
   draft text artifact" and "a human does something with it." That's the
   only boundary that currently has teeth.
3. **Is it enforced technically or just assumed?** The outer boundary (I
   can't act at all) is technical, by omission of access. Every finer-
   grained boundary inside the approval pipeline — walkthrough-before-
   sign-off, named-owner-only sign-off, approval-tied-to-content — is
   currently assumed, written down, and not enforced by anything that
   would stop a human from skipping it.
