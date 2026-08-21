# Audit Trail Spec - Track B Regression Agent

| Field | Value |
|---|---|
| Project | Coffee Shop Project |
| Track | D - Governance |
| Agent covered | Track B regression testing agent |
| Date | 2026-08-21 |
| Status | Draft - pending human review |

## 1. Purpose

This document defines what should be logged when the Track B regression agent
runs.

The goal is simple: after a test run, the team should be able to answer what was
tested, what happened, and what a human decided to do next.

## 2. Events To Log

The audit trail should record these events:

1. A regression test run starts.
2. A regression test run finishes.
3. A test fails.
4. An expected failure appears.
5. An expected failure is added, removed, or changed.
6. A live smoke check runs.
7. A human reviews a failed or risky result.
8. A final decision is made to continue, fix, hold, or release.

## 3. Fields To Capture For Every Run

Each regression run should log:

| Field | Meaning |
|---|---|
| `run_id` | Unique ID for the test run |
| `timestamp` | Date and time of the run |
| `trigger` | Pull request, push to main, manual run, or local run |
| `actor` | Person or system that started the run |
| `commit_sha` | Commit tested |
| `branch` | Branch tested |
| `command` | Test command used |
| `environment` | Local, CI, or live smoke check |
| `result` | Passed, failed, or passed with expected failures |
| `passed_count` | Number of passed tests |
| `failed_count` | Number of failed tests |
| `xfailed_count` | Number of expected failures |
| `failed_tests` | Names of failed tests |
| `expected_failures` | Names and reasons for expected failures |
| `human_review_required` | Yes or no |
| `human_reviewer` | Name of reviewer, if required |
| `final_decision` | Continue, fix, hold, or release |

## 4. What Gets Logged For A Failed Test

For each failed test, log:

1. Test name.
2. File path.
3. Error message.
4. Whether the failure blocks release.
5. Who reviewed it.
6. What action was taken.

Example:

```json
{
  "event_type": "TEST_FAILED",
  "test_name": "test_checkout_redeems_points_and_keeps_balance_non_negative",
  "file": "tests/regression/test_track_b_regression_agent.py",
  "blocks_release": true,
  "reviewer": "Bhargav",
  "decision": "fix before release"
}
```

## 5. What Gets Logged For Expected Failures

Expected failures should be logged separately because they are known gaps, not
surprises.

For each expected failure, log:

1. Test name.
2. Reason it is expected.
3. Owner of the missing decision or missing feature.
4. Date first added.
5. Date last reviewed.
6. Condition for removing the expected failure.

Current expected failure:

| Test area | Reason |
|---|---|
| Reward cancellation policy | Track A still needs to decide what happens when earned points are spent and the original order is later cancelled |

## 6. Human Review Log

When a human reviews the result, log:

1. Reviewer name.
2. Date and time.
3. What was reviewed.
4. Decision made.
5. Reason for the decision.

Example:

```json
{
  "event_type": "HUMAN_REVIEW",
  "reviewer": "Bhargav",
  "reviewed_result": "37 passed, 1 xfailed",
  "decision": "continue",
  "reason": "only expected failure is the known reward cancellation policy gap"
}
```

## 7. Where The Audit Trail Can Live

For this class project, the audit trail can be recorded in:

1. GitHub Actions run history.
2. Pull request comments.
3. Commit status checks.
4. Track B report updates.
5. A simple markdown log if the team wants one.

In a real production setup, this should be stored in a system that cannot be
edited casually, such as CI logs or a release-management tool.

## 8. Retention

Keep the audit trail for every test run that affects a merge or release
decision.

At minimum, keep:

1. All failed runs.
2. All runs with expected failures.
3. All runs used to approve a release.
4. All runs after API contract changes.

## 9. Verification Against Current System

The current workflow already records some audit information through GitHub
Actions:

1. Trigger.
2. Commit.
3. Branch.
4. Timestamp.
5. Test command.
6. Pass/fail result.

What is not fully enforced yet:

1. A required human reviewer for failed runs.
2. A required record explaining expected failures.
3. A required final release decision record.

So the current audit trail is partly present, but not complete.
