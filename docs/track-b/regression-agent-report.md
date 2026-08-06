# Track B Regression Agent Report

| Field | Value |
|-------|-------|
| Project | Coffee Shop Project |
| Track | B - Regression Agent |
| Date | 2026-08-06 |
| App tested | FastAPI coffee shop app |
| Local runner | `scripts/run_track_b_regression.ps1` |
| CI gate | `.github/workflows/track-b-regression.yml` |

## 1. What regression means for this app

For this project, a regression is a change that breaks one of the flows the app
already depends on. I treated these as the must-not-break flows:

1. The API is reachable and `/health` returns `{"status": "ok"}`.
2. A customer profile can be created and read back.
3. A duplicate customer email is rejected.
4. Checkout creates a confirmed order from an open cart.
5. Checkout awards reward points from the cart subtotal.
6. Reward points can be redeemed for the correct discount.
7. A redemption above the available balance is rejected.
8. A failed redemption does not leave behind a partial order or bad ledger row.
9. A cart cannot be checked out by the wrong customer.
10. Cancelling an order reverses the reward entries.
11. Fulfillment scheduling should be tested when Track A delivers that endpoint.

The fulfillment flow is still a known gap. The app does not have a
`POST /fulfillment` endpoint yet, so the regression suite marks that check as an
expected failure instead of pretending it is covered.

## 2. What I built

I added an API-level regression suite:

`tests/regression/test_track_b_regression_agent.py`

These tests use FastAPI's test client and an isolated in-memory SQLite database.
That means the tests create customers, carts, orders, and ledger entries without
touching the local `coffee.db` file.

I also kept the existing reward-ledger unit tests in the gate:

`tests/test_reward_ledger.py`

That file checks the lower-level reward invariant from ADR-001: the customer
balance must match the signed sum of the reward ledger.

## 3. How to Run the Regression Tests

For local runs, use:

```powershell
.\scripts\run_track_b_regression.ps1
```

If dependencies need to be installed first, use:

```powershell
.\scripts\run_track_b_regression.ps1 -Install
```

For a deployed app smoke check, use:

```powershell
.\scripts\run_track_b_regression.ps1 -LiveBaseUrl http://127.0.0.1:8000
```

The GitHub Actions workflow runs the same regression gate on pull requests and
pushes to `main`. It also has a manual option for a post-deploy smoke check if a
live URL is provided.

## 4. Pass and fail rule

The change passes only if the regression command exits with code `0`.

The gate fails if any required regression test fails. Expected failures are
reported separately. Right now there are two expected failures:

1. A known open reward policy question from Track A's original unit tests.
2. The missing fulfillment endpoint.

Those expected failures should not be ignored. They are tracked gaps, not proof
that the system is fully covered.

## 5. Test run result

I ran the gate locally on 2026-08-06 with:

```powershell
.\scripts\run_track_b_regression.ps1 -LiveBaseUrl http://127.0.0.1:8000
```

Result:

```text
17 passed, 2 xfailed, 3 warnings
PASS: live service is reachable and core Track B contract paths exist.
Known gap: fulfillment is not delivered yet:
- /fulfillment
```

The warnings are not blocking failures. They come from library deprecation
notices in FastAPI/Starlette.

## 6. Check that the tests catch a real bug

To make sure the regression suite was not only checking for HTTP 200 responses,
I temporarily changed the reward discount conversion from `0.01` per point to
`0.02` per point.

The redemption regression test failed because redeeming 100 points gave a `$2.00`
discount instead of the expected `$1.00` discount.

I restored the correct value and reran the full gate. The final clean result is
the result shown in Section 5.

## 7. Is this ready to gate production by itself?

No. It is good enough to block lower-environment changes to profiles, rewards,
and checkout, but it is not ready to gate production with no human review.

The main missing pieces are:

1. Fulfillment is not implemented yet, so delivery scheduling is not truly
covered.
2. There is no safe production test-data setup path for creating a customer,
cart, checkout, and cancellation without polluting real data.
3. The workflow is not connected to a real deployment pipeline yet.
4. Expected failures still need human review so they do not become permanent
blind spots.
5. If Track A changes an API contract, a person still needs to confirm whether
the regression suite should be updated before the gate is trusted again.

My assessment is that the agent can be used as a supervised regression gate now.
It should not be used as an unsupervised production release gate until the gaps
above are closed.

## 8.  Where a Human Still Needs to Review

The regression tests can run automatically and report pass or fail.

If a test fails, a person still needs to look at the result and decide what to do. A person should also review the result when the API changes,
  when a new expected failure is added, or when a new important flow is added to the app.

If the tests fail, the change should not be released until a person checks and fixes the problem.

## To be done

When fulfillment is delivered, the expected-failure test for
`POST /fulfillment` should be changed into a required passing regression test.
