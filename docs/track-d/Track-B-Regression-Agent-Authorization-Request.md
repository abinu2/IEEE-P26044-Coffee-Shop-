# Authorization Request - Track B Regression Agent

| Field | Value |
|---|---|
| Project | Coffee Shop Project |
| Track | D - Governance |
| Agent covered | Track B regression testing agent |
| Related Track B files | `scripts/run_track_b_regression.ps1`, `.github/workflows/track-b-regression.yml`, `scripts/track_b_live_smoke.py` |
| Date | 2026-08-21 |
| Status | Draft - pending human review |

## 1. Purpose

This authorization request explains what the Track B regression agent is allowed
to do for the coffee shop app.

The regression agent is the test setup that runs the Track B regression checks.
It is not a person and it is not making product decisions. It runs tests, reports
the result, and helps the team see if a change broke an important flow.

## 2. Approved Actions

The regression agent is approved to do these things:

1. Run the regression test suite locally through `scripts/run_track_b_regression.ps1`.
2. Run the same regression gate in GitHub Actions on pull requests and pushes to `main`.
3. Run the optional live smoke check when a live base URL is provided.
4. Report whether the test run passed or failed.
5. Mark the workflow as failed when required tests fail.
6. Show expected failures separately from real failures.

The agent can check these app flows:

1. Customer creation and duplicate email rejection.
2. Cart creation, pricing, and read back.
3. Checkout from an open cart.
4. Checkout consuming a cart so it cannot be used twice.
5. Reward points being earned and redeemed.
6. Rejection when a customer tries to redeem too many points.
7. Rejection when a customer tries to check out another customer's cart.
8. Order cancellation reversing reward entries.
9. Fulfillment scheduling.
10. Fulfillment state changes.

## 3. Not Approved Actions

The regression agent is not approved to do these things:

1. Deploy the app.
2. Approve a production release by itself.
3. Change source code by itself.
4. Edit tests to make a failing run pass.
5. Remove or ignore expected failures without human review.
6. Decide the open reward cancellation policy.
7. Create full fake production orders through the live smoke check.

## 4. Conditions For Use

The agent can be used as a supervised regression gate if these conditions are
met:

1. The tests must be run from the current codebase.
2. A failed test must be reviewed by a human before the change moves forward.
3. Any change to API paths or response fields must be reviewed before the test
   result is trusted.
4. Any expected failure must be documented and reviewed.
5. The remaining open reward cancellation policy must be resolved before that
   expected failure can be treated as normal.

## 5. Verification Against The Actual System

I checked this authorization request against the current Track B files.

The local runner is `scripts/run_track_b_regression.ps1`. It runs:

1. `tests/test_reward_ledger.py`
2. `tests/test_cart_fulfillment.py`
3. `tests/regression/test_track_b_regression_agent.py`

The CI workflow is `.github/workflows/track-b-regression.yml`. It runs on pull
requests, pushes to `main`, and manual workflow dispatch.

The live smoke check is `scripts/track_b_live_smoke.py`. It checks that the app
is reachable and that the expected API paths exist. It does not create full test
orders against a live URL.

## 6. Approval

This authorization should be approved by a human reviewer before the regression
agent is treated as a release gate.

Recommended approval decision:

**Approve for supervised use. Do not approve for unsupervised production release
approval.**
