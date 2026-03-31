# Design Overview

This document summarizes the privacy architecture of dp-group-stats. For the full specification, see the [accounting model spec](https://github.com/open-working-hours/dp-group-stats/blob/main/DESIGN.md) (this document) and the threat model (forthcoming).

## Problem

Publishing aggregate statistics about small professional groups (e.g., "average actual working hours for cardiologists in Bavaria") on a recurring schedule, while providing formal privacy guarantees for each individual contributor.

## Architecture

dp-group-stats combines three layers of protection:

### 1. K-anonymity suppression

Cells with fewer than `K_MIN` users are never published. A **dominance rule** additionally suppresses cells where a single contributor accounts for more than 30% of the total clipped value — even if the cell passes the K_MIN threshold.

### 2. Differential privacy (Laplace mechanism)

Calibrated Laplace noise is added to each published aggregate (planned hours sum, actual hours sum). **Contribution bounding** clips individual inputs to configurable ranges (default: 0–80h planned, 0–120h actual) before aggregation, ensuring bounded sensitivity.

The epsilon budget is split between planned and actual sums (default: 0.2 / 0.8) to allocate more precision to the quantity with higher utility value.

### 3. Publication state machine

To prevent inference attacks at group boundaries (a cell appearing or disappearing reveals that someone joined or left), publication follows a state machine:

```
              eligible ≥ N weeks
suppressed ──────────────────────► published
     ▲                                │
     │ ineligible ≥ grace period      │ ineligible
     │                                ▼
     ◄──────────────────────── cooling_down
                                      │
              eligible again           │
     warming_up ◄─────────────────────┘
```

- **warming_up**: Cell is eligible but hasn't been published yet (N consecutive weeks required)
- **published**: Cell is eligible and actively published (noise added, epsilon recorded)
- **cooling_down**: Cell dropped below threshold but was recently published (noise continues to prevent timing inference)
- **suppressed**: Cell is below threshold and the grace period has elapsed

## Release families and composition

A **release family** is a granularity tuple: `(geography_level, time_level, work_category_level)`.

Example families:
- F1: (State, Week, Specialty) — "Bavaria, Week 12, Cardiology"
- F2: (Hospital, Week, Specialty) — "Charité, Week 12, Cardiology"
- F3: (Germany, Month, Specialty) — "Germany, March, Cardiology"

**Within a family**, cells are disjoint (each user maps to exactly one cell), so publishing all cells costs the same as publishing one cell (parallel composition).

**Across families**, a user may appear in multiple cells simultaneously. These compose sequentially: `ε_user_week = ε_F1 + ε_F2 + ε_F3`.

**Across time**, each period's release composes sequentially with previous periods. An adaptive epsilon schedule ensures the annual budget cap is never exceeded:

```python
ε_period = min(config_ε, remaining_budget / remaining_periods)
```

## Temporal coarsening

When per-period noise is too high for useful publication (e.g., very small groups), the aggregation period can be lengthened from weekly to biweekly or monthly. This produces fewer, more accurate releases from the same budget — it does not add a new family or cost additional epsilon.

## Privacy ledger

All epsilon expenditure is recorded in a **privacy ledger** — both per-cell (which cells were published and at what cost) and per-user (cumulative exposure for each individual).

The library provides a `PrivacyLedger` Protocol with an `InMemoryPrivacyLedger` reference implementation. Production deployments (e.g., Open Working Hours) provide SQL-backed implementations.

The per-user ledger serves three purposes:
1. **Audit trail** — verify the system behaves as designed
2. **GDPR transparency** (Art. 15) — users can query their own cumulative epsilon exposure
3. **Anomaly detection** — flag if spending diverges from the planned schedule

## Confidence intervals

Published statistics include 90% Laplace confidence intervals. The displayed user count (`n_display`) is rounded down to the nearest 5 (floored at 5) to avoid leaking exact group size.

## Current status (v0.1.0)

- One release family active: (State, Week, Specialty)
- Naive sequential composition (zCDP/PLD accounting planned)
- Laplace mechanism with contribution clipping
- K-anonymity + dominance rule
- Publication state machine with 2-week activation and 2-week deactivation grace
- Adaptive epsilon schedule with annual budget cap (default: 150.0)
- Temporal coarsening (weekly / biweekly / monthly)
- Confidence intervals for noised means
- Simulation framework for parameter validation
- 43 tests, zero runtime dependencies
