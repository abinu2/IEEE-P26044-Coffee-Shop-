# Requirements Specification — Profiles/Rewards, Checkout

| Field | Value |
|-------|-------|
| Project | IEEE P26044 / C/S2ESC — Coffee Shop Reference Project |
| Track | A (Build) |
| Feature verticals | Profiles and rewards; Checkout |
| Author | Allan |
| Date | 2026-07-30 |

## 1. Scope

This specification defines the requirements for the customer profile, rewards,
and checkout features of the coffee-ordering application. Requirements were
drafted with gen-AI assistance and subsequently reviewed; each was retained,
edited, or added by the author, and every domain assumption introduced by the
tool but not supplied to it is catalogued in Section 4.

## 2. Feature summary

- **Profiles.** A customer holds an account carrying order history. Rewards and
  discounts are derived from that history.
- **Rewards.** Points accrue against orders and are redeemable for checkout
  discounts. The authoritative model for points is defined in ADR-001.
- **Checkout.** The cart is priced, an optional reward redemption is applied, the
  order is confirmed, and the order is handed to fulfillment.

## 3. Requirements

Each requirement carries a disposition: *retained* (from the AI draft, unchanged),
*edited* (from the AI draft, revised by the author), or *authored* (added by the
author). Assumptions introduced by the tool are flagged and cross-referenced to
the gap log.

### 3.1 Profiles

| ID | Requirement | Disposition |
|----|-------------|-------------|
| R-P1 | As a customer, I want to hold an account identified by email, so that my order history and rewards persist across sessions. | [retained / edited / authored] |
| R-P2 | [Populate from reviewed draft.] | |

### 3.2 Rewards

| ID | Requirement | Disposition |
|----|-------------|-------------|
| R-R1 | As a customer, I want points to accrue against completed orders, so that I can redeem them for discounts. | |
| R-R2 | As a customer, I want a redemption to be rejected if it exceeds my available balance, so that my balance is never negative. | |
| R-R3 | [Populate from reviewed draft.] | |

### 3.3 Checkout

| ID | Requirement | Disposition |
|----|-------------|-------------|
| R-C1 | As a customer, I want to apply available points as a discount at checkout, so that I benefit from my rewards. | |
| R-C2 | As a customer, I want the order confirmed only after payment and redemption are validated, so that fulfillment receives a valid order. | |
| R-C3 | [Populate from reviewed draft.] | |

## 4. AI-assumption gap log

This log records domain assumptions introduced by the gen-AI tool during
requirements drafting that were not present in the prompt. It is retained as a
TP.1 observation: the characteristic behavior is the confident insertion of
unstated assumptions, which requires review by someone with knowledge of the
intended system to detect and resolve.

| # | Assumption introduced by the tool | Present in prompt | Resolution |
|---|-----------------------------------|-------------------|------------|
| 1 | [e.g., Points do not expire.] | No | [e.g., Rejected default; points expire 12 months after accrual.] |
| 2 | [e.g., A customer holds a single active cart.] | No | [Resolution.] |
| 3 | [e.g., Redemption is all-or-nothing rather than partial.] | No | [Resolution.] |

## References

[1] ADR-001, *Reward Points Calculation and Storage.*
[2] IEEE P26044, Technical Processes, TP.1 (Requirements Engineering).
