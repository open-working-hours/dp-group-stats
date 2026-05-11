# dp-group-stats: Accounting Model Specification

**Created:** 2026-03-20
**Status:** Working draft
**Parent:** `dp-group-stats-requirements-v2.md`
**Purpose:** Define how privacy budget is structured, tracked, and enforced across release families, users, and time.

---

## 1. Release Families

### 1.1 Definition

A **release family** is a granularity tuple that picks one level from each dimension hierarchy:

```
Family = (geography_level, time_level, work_category_level)
```

The dimension hierarchies are:

```
Geography               Time              Work Category
─────────               ────              ─────────────
Germany                 Year              All workers
└─ State                └─ Quarter        └─ Specialty
   └─ Hospital             └─ Month         └─ Role
                              └─ Week
```

Examples of release families:

| Family | Geography | Time | Work Category | Typical cell |
|--------|-----------|------|---------------|-------------|
| F1 | State | Week | Specialty | (Bavaria, Week 12, Cardiology) |
| F2 | Hospital | Week | Specialty | (Charité, Week 12, Cardiology) |
| F3 | Germany | Week | Specialty | (Germany, Week 12, Cardiology) |
| F4 | State | Month | Specialty | (Bavaria, March, Cardiology) |

### 1.2 Disjointness within a family

Each family produces a set of **disjoint cells**: within a given time period, each user maps to exactly one cell in each family. This is guaranteed by the assignment snapshot rule — each finalized user-week freezes one (state, hospital, specialty, role) tuple.

**Enforcement:** the mobile app UX must ensure that a user cannot have split assignments within a single week. If a user changes hospital or specialty mid-week, that week is either not finalizable or counts under the original assignment.

### 1.3 Why this model, not a tree

> **Explainer:** An earlier design framed release families as trees — e.g., "national → state → state×specialty" as one family with hierarchical levels. This conflates two concerns: (1) which cells exist at what granularity, and (2) how composition works across them.
>
> The granularity-tuple model is cleaner because:
> - Every family is flat and disjoint internally — no within-family hierarchy to reason about
> - All cross-family overlap is handled uniformly: sequential composition
> - Consistency relationships between families (e.g., "national totals should approximate the sum of state totals") are declared separately, not baked into the family definition
> - Adding a new family doesn't restructure existing families
>
> The practical effect is the same — budget still splits across overlapping publications — but the model is easier to implement and generalize.

---

## 2. Composition Model

### 2.1 Within a family: parallel composition

Because cells within a family are disjoint, a user appears in exactly one cell per family per time period. Publishing all cells in a family costs the same as publishing one cell — parallel composition is free.

### 2.2 Across families: sequential composition

A user can appear in multiple families simultaneously. For example, a cardiologist at Charité in Berlin appears in:

- F1: (Berlin, Week 12, Cardiology)
- F2: (Charité, Week 12, Cardiology)
- F3: (Germany, Week 12, Cardiology)

Each family's publication is an independent use of the user's data. Under sequential composition, the total privacy cost for this user in Week 12 is:

```
ε_user_week = ε_F1 + ε_F2 + ε_F3
```

### 2.3 Overlapping categories compose the same way

> **Explainer:** The composition rule doesn't care *why* families overlap — only *whether* a given user appears in multiple families. Two families can overlap because one is a geographic rollup of the other (State vs. Germany), or because one work category is a subset of another (Surgeons vs. all Doctors). The accounting is identical: if user U appears in both, their ε values add.
>
> Example: F1 = (State, Week, Surgeons) and F2 = (State, Week, Doctors). A surgeon appears in both → cost = ε₁ + ε₂. A non-surgeon doctor appears only in F2 → cost = ε₂. The per-user budget must accommodate the worst case (the surgeon).

### 2.4 Time as a dimension

Including the time level in the family definition means that publishing both weekly and monthly aggregates counts as two separate families:

- F1 = (State, **Week**, Specialty) — ε₁ per week
- F4 = (State, **Month**, Specialty) — ε₄ per month

A user appearing in both pays ε₁ + ε₄ for weeks that fall within a published month.

This is different from **temporal coarsening**, where weekly publication is *replaced* by monthly when noise gets too high. Replacement doesn't add a family; it changes the cadence of an existing one. Addition always costs extra ε.

### 2.5 Across time: sequential composition

Each week's release composes sequentially with previous weeks. A user published in Week 12 and Week 13 of the same family accumulates:

```
ε_cumulative = ε_week_12 + ε_week_13
```

This is naive sequential composition. Tighter accounting (zCDP, PLD) is a future optimization.

---

## 3. Noise Calibration

### 3.1 Noise is per-family, data-independent

Each release family has a configured ε value that determines the noise level. This ε is:
- **fixed by configuration** — set before any data is processed
- **data-independent** — does not change based on which users are in which cells
- **the same for every cell** in the family

> **Explainer:** Why can't different users in the same cell have different ε values? Because the published output for a cell is one number (e.g., "noisy sum of actual hours for Bavaria Cardiology"). That number has one noise level. The ε for that publication determines the privacy guarantee for *every* user in the cell equally — all users share the same guarantee from the same published number.
>
> Making the noise level depend on which specific users are in the cell (e.g., reducing ε because one user has low remaining budget) would itself leak information about cell composition.

### 3.2 Per-cell ε cost

For each published cell in each release period, the mechanism adds noise to two quantities:

| Quantity | Sensitivity | ε allocation |
|----------|------------|-------------|
| Planned sum | 80 | ε_planned |
| Actual sum | 120 | ε_actual |
| Count | not noised | 0 (public under substitution relation) |

The per-cell per-period cost is:

```
ε_cell = ε_planned + ε_actual
```

The split between ε_planned and ε_actual is a tuning parameter within the family's total ε. The family's configured ε equals ε_cell (since all cells in the family use the same value).

### 3.3 How per-family ε values are chosen

The library accepts per-family ε values as configuration. How those values are determined is the caller's responsibility:

- **Admin-set:** explicit values in config (simplest, sufficient for v1)
- **Formula-based:** proportional to 1/√(typical_N), so families with smaller groups automatically get more ε
- **Simulation-optimized:** derived from actual group-size distributions (Ko et al. 2025 approach)

The library's job is to **validate** that the configured values are consistent with the annual budget cap (see Section 4.3).

---

## 4. Per-User Budget Accounting

### 4.1 The budget lives with the user

> **Explainer:** An alternative model would allocate a budget to each release family and track spending per family. But this misses the point: the meaningful privacy guarantee is about *users*, not *cells*. A user who appears in three families has three times the privacy exposure of a user in one family, regardless of how the family budgets are set.
>
> The per-user ledger is the source of truth. It tracks the actual consequence of all noise decisions for each individual user.

For each release period, the system computes:

```
ε_user_period = Σ(ε_f)  for each family f the user appears in
```

The per-user cumulative exposure across time is:

```
ε_user_cumulative = Σ(ε_user_period)  over all periods
```

### 4.2 The ledger is accounting, not input to noise

The per-user ledger does **not** influence how much noise is added. Noise calibration is determined by per-family config (Section 3.1). The ledger tracks the *consequence* of those noise decisions.

This separation is essential: if noise levels depended on individual user budgets, the noise itself would leak information about which users are in which cells.

The ledger serves three purposes:
1. **Audit trail** — verify that the system behaves as designed
2. **Reporting** — surface actual vs. worst-case spending (useful for deciding whether to add new families)
3. **Anomaly detection** — flag if actual spending diverges from the planned schedule (indicates a bug or unexpected overlap pattern)

### 4.3 Annual budget cap

The system enforces a per-user annual cap: `ε_annual`.

The cap is enforced **at config time**, not reactively at runtime:

```
worst_case_per_week = Σ(ε_f)  for all families a user could appear in
worst_case_per_week × 52 ≤ ε_annual
```

If this constraint doesn't hold, the library should refuse to start and require the operator to reduce per-family ε values or remove families.

### 4.4 Unused budget

Not every user appears in every family. A user who only appears in one family has lower actual ε exposure than the worst-case user. This "unused" budget cannot be reclaimed without adaptive composition (much more complex).

**v1 approach:** accept the conservatism. Report actual vs. worst-case spending in the per-user ledger. This reporting is useful for future decisions — if most users only use 60% of their annual cap, there's headroom to add another family.

---

## 5. Budget Planning and Graceful Degradation

### 5.1 Pre-computed schedule (planning step)

Before publishing begins, the operator computes per-family ε values constrained by:

```
Σ(ε_f for all families) × periods_per_year ≤ ε_annual
```

If the pre-computation is correct and the set of families doesn't change, the system never hits the cap. ε stays constant all year.

### 5.2 Graceful degradation (runtime safety net)

Things that can change mid-year:
- A new family is added
- A family's ε is increased (product decision)
- The annual cap is revised

When the planned schedule changes, the time-based degradation formula absorbs it:

```
ε_week(t) = (ε_annual − planned_spent_so_far) / weeks_remaining
```

Key properties:
- **Time-based, not user-based** — every cell sees the same schedule
- **Data-independent** — uses planned spending (from config × weeks elapsed), not actual per-user data
- **Monotonically adjusting** — if overspent early (e.g., added a family), ε decreases for remaining weeks
- **No hard cutoff** — cells never go dark due to budget exhaustion; they just get noisier

### 5.3 Temporal coarsening

When per-week noise exceeds a utility threshold (e.g., noise std > 10 hours on the mean), the system can automatically switch to longer aggregation periods (monthly or quarterly). This produces fewer, more accurate releases from the same remaining budget.

Temporal coarsening is a change in cadence within the same family — it does not add a new family and does not cost additional ε.

### 5.4 Design goal

Eliminate budget-based suppression entirely. Cells are suppressed only for K_MIN or dominance reasons (fixed policy). The public output shape stays stable; only precision changes over time.

---

## 6. Non-DP Suppression Rules

### 6.1 Minimum group threshold (K_MIN)

Do not publish cells with fewer than K_MIN users. Current default: K_MIN = 5 (validated by simulation; working hours are Art. 6 GDPR data, not Art. 9 health data, so k=5 is appropriate for labour statistics when combined with DP noise).

K_MIN is checked against the true (non-noised) count. Cells below K_MIN are suppressed with a generic `suppressed` status and no public reason code.

### 6.2 Dominance / concentration rule

> **Explainer:** Even with DP noise and K_MIN ≥ 5, a cell can be too revealing if one user dominates the aggregate. Example: 6 users in a cell, but one worked 120h (clipping max) while the other 5 worked 20h each. That user accounts for 55% of the total — the aggregate is essentially their data with noise. An attacker who knows the other 5 users' rough hours can infer the outlier's contribution.
>
> The dominance rule catches these cases. It's a publication policy, not a substitute for DP — it layers on top of the formal mechanism.

**v1 rule:** suppress if the top contributor's clipped actual hours exceed 30% of the cell's total clipped actual hours.

Design choices:
- **Top-1 only** (not top-k) — sufficient for healthcare working hours where coordinated cliques are unlikely
- **Actual hours only** — wider range (0–120) makes concentration more dangerous than planned hours (0–80)
- **Clipped values** — the dominance check uses the same clipped values that enter the DP mechanism
- **Threshold: 30%** — with K_MIN = 5, the equal-share baseline is 20% per user; 30% means one person contributes 1.5× the average share

The 30% threshold has been validated by simulation.

### 6.3 Temporal activation and deactivation

- **Activation:** publish only after N = 2 consecutive weeks above K_MIN and passing dominance
- **Deactivation:** suppress only after a 2-week grace period below eligibility

These rules reduce threshold-crossing leakage (the information revealed by a cell suddenly appearing or disappearing from the public output).

### 6.4 ε cost of suppressed cells

| Status | Noise generated? | ε recorded? | Rationale |
|--------|-----------------|-------------|-----------|
| `published` | Yes | Yes | Normal publication |
| `warming_up` | No | No | Cell has never been published; no output to protect |
| `suppressed` (K_MIN or dominance) | No | No | No output means no privacy cost |
| `cooling_down` | Yes | Yes | Cell was recently published; sudden disappearance of noise is itself informative |

> **Explainer:** For warming_up and suppressed cells, no noise is generated and no output is published, so there is no privacy event to account for. But cooling_down is different — the cell was recently active, and stopping noise abruptly could let an attacker detect that something changed (e.g., a user left the group). During the grace period, the mechanism continues to run normally.

---

## 7. Ledger Implementation

### 7.1 Per-cell ledger (existing)

The `StateSpecialtyPrivacyLedger` table records one row per cell per period:

| Field | Type | Purpose |
|-------|------|---------|
| cell identifier (country, state, specialty) | String | Which cell |
| period_start | Date | Which week |
| mechanism | String | "laplace" (v1) |
| publication_status | String | published / cooling_down |
| planned_sum_epsilon | Decimal(6,3) | ε spent on planned sum |
| actual_sum_epsilon | Decimal(6,3) | ε spent on actual sum |
| total_epsilon | Decimal(6,3) | Sum of above |

### 7.2 Per-user ledger (new)

A new table tracks per-user cumulative exposure:

| Field | Type | Purpose |
|-------|------|---------|
| user_id | UUID | Which user |
| period_start | Date | Which week |
| family_key | String | Which release family (e.g., "state_specialty") |
| cell_key | String | Which specific cell (e.g., "DEU:BY:cardiology") |
| epsilon_spent | Decimal(6,3) | ε cost for this user from this cell this period |
| recorded_at | DateTime | When recorded |

Derived queries:
- **Per-user cumulative:** `SUM(epsilon_spent) WHERE user_id = ? AND period_start >= year_start`
- **Per-user per-week:** `SUM(epsilon_spent) WHERE user_id = ? AND period_start = ?`
- **Worst-case user:** `MAX(per_user_cumulative)` across all users
- **Actual vs. worst-case:** compare per-user cumulative to `worst_case_per_week × weeks_elapsed`

### 7.3 Ledger as generalized structure

For the open-source package, the ledger should be abstracted behind an interface:

```python
class PrivacyLedger(Protocol):
    def record(self, user_id: str, family: str, cell: str,
               period: date, epsilon: float) -> None: ...
    def user_spent(self, user_id: str, since: date) -> float: ...
    def cell_spent(self, cell: str, since: date) -> float: ...
    def all_user_totals(self, since: date) -> dict[str, float]: ...
```

Concrete implementations: SQL-backed (for OWH backend), in-memory (for testing/simulation), pandas-backed (for analysis scripts).

---

## 8. Validation Checklist

The accounting model introduces these testable properties:

### Mechanism correctness
- [ ] Per-user per-week ε equals sum of family ε values for families the user appears in
- [ ] Per-user cumulative ε equals sum of per-week values over time
- [ ] Suppressed cells (K_MIN, dominance, warming_up) record zero ε
- [ ] Cooling_down cells record full ε
- [ ] Dominance check uses clipped actual values and 30% threshold
- [ ] Config validation rejects family sets where worst-case × 52 > annual cap
- [ ] Graceful degradation formula produces correct ε values after mid-year config changes

### Accounting integrity
- [ ] Per-user ledger matches per-cell ledger (cross-check: sum of per-user entries for a cell equals the cell's ledger entry)
- [ ] No ε recorded for periods where no output was published (except cooling_down)
- [ ] Ledger entries are immutable once recorded

### Budget planning
- [ ] Pre-computed schedule produces constant ε when no config changes occur
- [ ] Schedule adjusts downward when a new family is added mid-year
- [ ] Temporal coarsening triggers when per-period noise exceeds utility threshold

---

## 9. v1 Defaults

| Parameter | Value | Status |
|-----------|-------|--------|
| Release families | F1: (State, Week, Specialty) only | Fixed for v1 |
| Per-family ε | 1.0 (working assumption) | To be validated by simulation |
| ε split | ε_planned = 0.2, ε_actual = 0.8 | Validated by simulation (see simulation-spec.md) |
| Annual cap | 150 per user | Validated by simulation (see simulation-spec.md) |
| K_MIN | 5 | Validated by simulation (see simulation-spec.md) |
| Clipping bounds | planned [0, 80], actual [0, 120] | Validated by simulation (see simulation-spec.md) |
| Dominance threshold | 30% top-1, clipped actual | Validated by simulation (see simulation-spec.md) |
| Activation weeks | 2 | Fixed for v1 |
| Deactivation grace | 2 weeks | Fixed for v1 |
| Composition | Naive sequential | Fixed for v1 |
| Consistency post-processing | None | Not a v1 priority |

### v1 simplifications

With only one release family and no hierarchy:
- Worst-case per-user per-week = ε_F1 (no cross-family composition)
- All cells within the family compose in parallel (disjoint)
- Per-user ledger tracks one entry per user per week
- Budget planning is trivial: ε_F1 × 52 ≤ ε_annual

The multi-family composition model is designed in but only activated when a second family is added.

---

## 10. Future Extensions

These are explicitly out of scope for v1 but the architecture should not prevent them:

- **Additional release families** (hospital × specialty, state × role, national totals)
- **Per-family budget allocation formulas** (proportional to 1/√N, Ko et al. optimization)
- **Tighter composition accounting** (zCDP, PLD accountants)
- **Consistency post-processing** within declared parent-child family pairs
- **Adaptive per-user budget management** (reclaiming unused budget from users in fewer families)
- **Public count bands** (e.g., "5-10 users" instead of exact count)

---

## 11. Relationship to Other Specs

| Document | Relationship |
|----------|-------------|
| `dp-group-stats-requirements-v2.md` | Parent spec. This document refines Sections 4, 5, and 7. |
| `dp-group-stats-implementation-checklist.md` | This document informs Phases 3, 4, 5, and 7. |
| `privacy_architecture.md` | The neighboring relation (substitution, §4.3 of requirements) should be documented there. |

---

## 12. Open Items

| Item | Status | Notes |
|------|--------|-------|
| Exact ε per family | Deferred to simulation | Working assumption: 1.0 |
| Exact annual cap | **Resolved: 150** | Validated by simulation |
| Exact dominance threshold | **Resolved: 30%** | Validated by simulation |
| ε split (planned vs actual) | **Resolved: 0.2 / 0.8** | Validated by simulation |
| K_MIN | **Resolved: 5** | Validated by simulation |
| Clipping bounds (actual) | **Resolved: [0, 120]** | Validated by simulation |
| Utility thresholds for temporal coarsening | Deferred to simulation | e.g., noise std > 10h on mean |
| Neighboring relation documentation | To be written | Should go in privacy_architecture.md |
