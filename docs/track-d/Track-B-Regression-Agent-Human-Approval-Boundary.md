# Human Approval Boundary - Track B Regression Agent

| Field | Value |
|---|---|
| Project | Coffee Shop Project |
| Track | D - Governance |
| Agent covered | Track B regression testing agent |
| Date | 2026-08-21 |
| Status | Draft - pending human review |

## 1. Short Answer

The regression agent can run tests automatically.

The regression agent can report pass or fail automatically.

The regression agent should not approve a production release by itself.

A human must review failed tests, expected-failure changes, API contract changes,
and final production release decisions.

## 2. What The Agent Can Do Without Human Approval

The agent can do these actions without asking a human first:

1. Run the local regression script.
2. Run the GitHub Actions regression workflow.
3. Run the optional live smoke check if a URL is provided.
4. Report pass, fail, or expected failure.
5. Mark a CI workflow as failed when tests fail.

These actions are acceptable because they do not change app code, deploy the app,
or change customer data.

## 3. What Needs Human Approval

A human must review before the team moves forward when:

1. Any required regression test fails.
2. An expected failure is added.
3. An expected failure is removed.
4. An expected failure changes meaning.
5. A public API path changes.
6. A response field changes.
7. A new must-not-break flow is added.
8. The live smoke check reports a missing path.
9. The team wants to approve a production release.

## 4. What The Agent Is Not Allowed To Decide

The agent is not allowed to decide:

1. Whether the app is production-ready.
2. Whether a failed test can be ignored.
3. Whether the reward cancellation policy is correct.
4. Whether API contract changes are acceptable.
5. Whether a release can go out after a failed run.

Those are human decisions.

## 5. Is The Boundary Technically Enforced?

The boundary is only partly enforced.

Technically enforced:

1. The regression agent has no deploy command in the current workflow.
2. The local runner only runs tests.
3. The live smoke check only checks health and API paths.
4. GitHub Actions can mark the workflow as failed.

Not fully enforced:

1. This repo does not prove that branch protection is enabled.
2. A failed GitHub Actions run only blocks merge if branch protection requires it.
3. A human review rule is written in the process, but not fully enforced in code.
4. A person could still ignore the result unless the repository settings prevent it.

So the honest answer is:

**The agent's ability to run tests is automated. The final approval boundary is
partly technical and partly procedural.**

## 6. What Would Make The Boundary Stronger

To make the approval boundary real, the team should add:

1. Branch protection requiring the Track B regression workflow to pass.
2. Required pull request review before merge.
3. A rule that expected failures must be reviewed before they are accepted.
4. A release checklist that records the regression result and human decision.
5. A rule that production release cannot happen if required regression tests fail.

## 7. Final Boundary Statement

The Track B regression agent may run tests and report results automatically.

It may help stop a risky change by failing the CI workflow.

It may not approve a production release by itself.

The final release decision must be made by a human reviewer, especially when
tests fail, expected failures change, or the API contract changes.
