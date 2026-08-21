# Risk Profile - Track B Regression Agent

| Field | Value |
|---|---|
| Project | Coffee Shop Project |
| Track | D - Governance |
| Agent covered | Track B regression testing agent |
| Date | 2026-08-21 |
| Status | Draft - pending human review |

## 1. Short Summary

The Track B regression agent is **medium risk**.

It does not directly change customer data, edit the app, or deploy code. That
keeps it below high risk.

But it can affect release decisions. If the tests are wrong, the agent could
miss a bad change or block a good change. That makes it more than low risk.

## 2. What The Agent Does

The agent runs regression tests for the coffee shop app. It checks the main app
flows after Track A changes the code.

It checks profiles, carts, checkout, rewards, cancellation, and fulfillment.

The agent reports:

1. Tests passed.
2. Tests failed.
3. Expected failures.
4. Live smoke check result, if a live URL is provided.

## 3. Main Risks

### Risk 1 - False Pass

The tests could pass even though the app still has a bug.

This can happen if the risky path is not covered by a test. This is the most
important risk because it can create false confidence.

Current mitigation:

1. The tests cover the main API flows.
2. The suite includes both API regression tests and lower-level reward ledger
   tests.
3. Remaining gaps are marked as expected failures instead of hidden.

Remaining gap:

The open reward cancellation policy is still not fully resolved.

### Risk 2 - False Fail

The tests could fail even though the app is actually okay.

This can delay a change or make the team spend time investigating a test issue.

Current mitigation:

1. The tests use an isolated SQLite database.
2. The runner gives a clear pass/fail result.
3. Expected failures are separated from real failures.

### Risk 3 - Expected Failures Become Ignored

If an expected failure stays in the suite too long, people may stop paying
attention to it.

Current mitigation:

The Track B report names the expected failure and says it should be resolved
when the reward cancellation rule is decided.

### Risk 4 - Human Approval Is Assumed But Not Fully Enforced

GitHub Actions can show the regression gate as failed. But that only truly
blocks a merge or release if branch protection or a manual release rule is
enabled.

Current mitigation:

The human approval boundary document states that final release approval must
come from a person.

Remaining gap:

There is no evidence in this repo that branch protection is enabled. So the
boundary is partly technical and partly procedural.

## 4. Risk Tier

| Category | Rating |
|---|---|
| Data change ability | Low |
| Code change ability | Low |
| Deployment authority | Low |
| Impact on release decisions | Medium |
| Risk of false confidence | Medium |
| Need for human review | Medium |

Overall risk tier:

**Tier 2 - Medium / supervised gate required**

Reason:

The agent is not allowed to deploy or change code, but it is used to support
release decisions. A wrong pass or wrong fail can affect the team. Because of
that, a human still needs to review failures, expected failures, and API changes.

## 5. Difference From The Runbook AI

The regression agent is different from the runbook-generation AI.

The regression agent runs tests and reports pass or fail. It does not recommend
incident fixes.

The runbook AI creates operational guidance that a support person might follow
during an incident. That can carry a different risk because wrong advice could
send someone toward the wrong root cause.

So the regression agent should be governed as a supervised release-checking
tool, not as an incident-response decision maker.

## 6. Decision

Recommended decision:

**Continue using the regression agent with mandatory human review for failures,
expected-failure changes, API changes, and production release decisions.**
