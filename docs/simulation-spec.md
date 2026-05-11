# DP Group Stats — Simulation Spec

**Purpose:** Determine the 5+ parameters deferred in Section 12 of `dp-group-stats-accounting-model.md` through empirical simulation.

**Script:** `backend/scripts/simulate_aggregation.py`

---

## 1. Deferred Parameters

| # | Parameter | Working assumption | Decided by simulation? |
|---|-----------|-------------------|----------------------|
| 1 | Per-family ε | 1.0 | Yes |
| 2 | ε split (planned:actual) | 0.3:0.7 | Yes |
| 3 | Annual ε cap | None set | Yes |
| 4 | Dominance threshold | 0.30 | Yes |
| 5 | Utility thresholds for temporal coarsening | Not defined | Yes (noise std targets) |
| 6 | K_MIN value | 11 (medical data standard) | Yes — reconsidered for labor data |
| 7 | Temporal resolution | Weekly | Yes — monthly option for early-stage |

---

## 2. Distribution Modes

### 2.1 Spread Mode (Nationwide)

Users distributed across all 16 German states proportional to hospital count (1,220 hospitals from `datasets/german_hospitals/output/german_hospitals.csv`).

| State | Code | Hospitals | Weight |
|-------|------|-----------|--------|
| Nordrhein-Westfalen | NW | 202 | 16.6% |
| Bayern | BY | 193 | 15.8% |
| Baden-Württemberg | BW | 147 | 12.0% |
| Niedersachsen | NI | 136 | 11.1% |
| Hessen | HE | 104 | 8.5% |
| Schleswig-Holstein | SH | 61 | 5.0% |
| Rheinland-Pfalz | RP | 56 | 4.6% |
| Sachsen-Anhalt | ST | 49 | 4.0% |
| Berlin | BE | 48 | 3.9% |
| Sachsen | SN | 43 | 3.5% |
| Mecklenburg-Vorpommern | MV | 43 | 3.5% |
| Thüringen | TH | 40 | 3.3% |
| Hamburg | HH | 35 | 2.9% |
| Brandenburg | BB | 30 | 2.5% |
| Saarland | SL | 20 | 1.6% |
| Bremen | HB | 11 | 0.9% |

6 specialties: Internal Medicine (25%), Surgery (20%), Cardiology (15%), Pediatrics (15%), Anesthesiology (15%), Radiology (10%).

Total cells: 16 states × 6 specialties = 96.

### 2.2 Pilot Mode (Single Hospital in Berlin)

All users concentrated in state=Berlin (BE) with a hospital-realistic specialty distribution:

| Specialty | Pilot weight |
|-----------|-------------|
| Internal Medicine | 30% |
| Surgery | 25% |
| Cardiology | 20% |
| Anesthesiology | 15% |
| Radiology | 10% |

Total cells: 5 specialties (no Pediatrics — typical for a pilot with one department-heavy hospital).

This models the planned Berlin hospital pilot: 50-200 healthcare workers at a single institution.

---

## 3. Temporal Resolution

### Weekly (default)

One aggregation period = 1 week. Each period produces one set of noised statistics per cell. ε cost per user = ε per period × number of periods published.

### Monthly

One aggregation period = 4 weeks. User data is averaged across the 4-week block before aggregation. Benefits:

- **More users per cell** — users who join/leave mid-month still contribute partial data
- **Lower annual ε** — 13 periods/year instead of 52 (max ε/yr = ε × 13)
- **Better noise-to-signal** — same noise calibration but applied to more stable means

Trade-off: less timely data (monthly vs. weekly resolution).

---

## 4. Data Generation

### Working Hour Patterns

Per user per week:
- **Planned hours:** `clip(Normal(μ=39, σ=3), [20, 80])`
- **Actual hours:** `clip(planned + overtime, [0, 140])`
  - Standard users (95%): `overtime ~ Exponential(mean=5h)`
  - High-overtime users (5%): `overtime ~ Exponential(mean=15h)`

### User Churn

Per week:
- **Leave rate:** 2% of active users
- **Join rate:** 1% of original total
- Net: slight shrinkage, creates natural state transitions

---

## 5. Parameter Sweeps

### 5.1 Spread Sweep (`--sweep`)

| Parameter | Values |
|-----------|--------|
| Total users | 500, 2000, 5000, 10000 |
| ε | 0.5, 1.0, 2.0, 4.0 |
| K_MIN | 5, 7, 11 |
| Period | weekly, monthly |
| Split | 0.3/0.7 (fixed — confirmed optimal) |
| Dominance | 0.30 (fixed — confirmed irrelevant at K_MIN≥5) |

Total: 4 × 4 × 3 × 2 = **96 scenarios**.

### 5.2 Pilot Sweep (`--sweep-pilot`)

| Parameter | Values |
|-----------|--------|
| Total users | 30, 50, 80, 120, 200 |
| ε | 1.0, 2.0, 4.0 |
| K_MIN | 3, 5, 7, 11 |
| Period | weekly, monthly |
| Split | 0.3/0.7 (fixed) |
| Dominance | 0.30 (fixed) |

Total: 5 × 3 × 4 × 2 = **120 scenarios**.

---

## 6. Output Metrics

For each scenario, measured at mid-point and end:

| Metric | Description |
|--------|-------------|
| pub%_mid / pub%_end | % of cells published at midpoint / endpoint |
| MAE_pln / MAE_act | Mean absolute error of noised vs. true mean (planned / actual hours) |
| dom_s% | % of cells suppressed by dominance (not K_MIN) |
| <3h% | % of published cells with noise std < 3h (policy-grade accuracy) |
| <5h% | % of published cells with noise std < 5h (campaign-grade accuracy) |
| max_eps/yr | Worst-case single-user cumulative ε after 52 weeks |

---

## 7. Simulation Results

### 7.1 Pilot Sweet Spots (Berlin hospital scenario)

Key findings from `--sweep-pilot` (120 scenarios):

**30 users:**
- K_MIN=11 → 0% published. Completely unusable.
- K_MIN=5, weekly, ε=2.0 → 40% published, MAE_act=12.66h. Still very noisy.
- K_MIN=3, weekly, ε=2.0 → 80% published, MAE_act=5.06h. Marginal.
- K_MIN=3, monthly, ε=4.0 → 80% published, MAE_act=6.29h. Usable but noisy.

**50 users:**
- K_MIN=11 → 20% published (weekly). Only 1 cell crosses threshold.
- K_MIN=5, weekly, ε=2.0 → 80% published, MAE_act=4.75h. Approaching useful.
- K_MIN=5, monthly, ε=4.0 → 100% published, MAE_act=2.02h. Good.

**80 users:**
- K_MIN=7, monthly, ε=2.0 → 80% published, MAE_act=3.13h, 25% <5h. Decent.
- K_MIN=5, monthly, ε=4.0 → 100% published, MAE_act=2.26h, 40% <5h. Good.
- K_MIN=7, monthly, ε=4.0 → 80% published, MAE_act=1.56h, 75% <5h. Best for 80 users.

**120 users:**
- K_MIN≤7, monthly, ε=2.0 → 100% published, MAE_act=1.88h, 20% <5h. All cells active.
- K_MIN≤7, monthly, ε=4.0 → 100% published, MAE_act=0.94h, 60% <5h. Policy-grade.

**200 users:**
- All K_MIN values give 100% published (cells are large enough).
- Monthly, ε=2.0 → MAE_act=2.27h, 60% <5h.
- Monthly, ε=4.0 → MAE_act=1.14h, 100% <5h. Excellent.

### 7.2 K_MIN Sensitivity Analysis

**Key finding:** K_MIN=11 (medical data standard) is too conservative for this use case.

Working hours are GDPR Article 6 personal data, not Article 9 special category (health) data. The DP noise already provides formal privacy guarantees — K_MIN is a secondary defense.

| K_MIN | Rationale | Pilot impact (80 users) |
|-------|-----------|------------------------|
| 11 | Medical statistics standard | 80% published, large cells only |
| 7 | Conservative for non-health data | 80-100% published |
| 5 | Standard for labor statistics | 100% published at 80+ users |
| 3 | Aggressive but defensible with DP | 100% published even at 30 users |

**Recommendation:** K_MIN=5 for production (defensible for labor data with DP noise), with the option to increase if regulatory feedback requires it.

### 7.3 Temporal Coarsening Impact

Monthly aggregation consistently:
- **Reduces max ε/yr by 4×** (13 periods vs. 52)
- **Improves published %** at small user counts (more users accumulate per period)
- **Trades timeliness for accuracy** — MAE improves because means are more stable

For the pilot phase (< 200 users), monthly aggregation is clearly superior.

### 7.4 Dominance Threshold

Dominance suppression = 0% across all 120 pilot scenarios and all 96 spread scenarios. With K_MIN≥5 and actual hours clipped to [0, 140], no single user can exceed 30% of cell total even in the worst case (one user at 140h, 4 others at ~44h each = 140/316 = 44% — would trigger at K_MIN=5 only in extreme cases). At K_MIN=7+, mathematically impossible.

**Recommendation:** Keep threshold at 0.30 as a safety net, but document that it's operationally redundant at K_MIN≥5 with current bounds.

### 7.5 Spread Mode Highlights

From `--sweep` (nationwide distribution):

| Users | K_MIN | Period | ε | pub%_end | MAE_act | <5h% | max_eps/yr |
|-------|-------|--------|---|----------|---------|------|-----------|
| 2000 | 5 | monthly | 2.0 | ~65% | ~2.5h | ~30% | 26 |
| 5000 | 5 | weekly | 2.0 | ~90% | ~1.7h | ~55% | 102 |
| 10000 | 5 | weekly | 1.0 | ~97% | ~2.5h | ~40% | 51 |
| 10000 | 5 | monthly | 2.0 | ~97% | ~1.3h | ~80% | 26 |

---

## 8. Recommended Parameters

Based on simulation results:

| Parameter | Pilot phase (< 200 users) | Scale phase (1000+ users) |
|-----------|--------------------------|--------------------------|
| **K_MIN** | 5 | 5 (increase to 7 if regulatory) |
| **Bounds (actual_weekly_max)** | 120h | 120h |
| **ε split (planned:actual)** | 0.2 / 0.8 | 0.2 / 0.8 |
| **Annual cap** | 150 | 150 |
| **Dominance** | 0.30 | 0.30 |
| **Period** | Monthly (→ biweekly/weekly as cells grow) | Weekly |
| **Mechanism** | Laplace (Gaussian/zCDP later) | Gaussian/zCDP |

**Rationale for key changes from initial assumptions:**

- **Bounds 140→120h:** 110h real-world cases exist, 120h covers 99.9%. Reduces sensitivity by 14%, directly reduces noise.
- **Split 0.3/0.7→0.2/0.8:** Actual hours (overtime) is the primary stakeholder metric. Planned hours are less variable and less interesting. Giving 80% of ε to actual hours improves the metric that matters.
- **Annual cap 150:** Defensible for non-health employment data with central DP. Working hours are GDPR Article 6, not Article 9. Any finite ε is strictly better than existing labor statistics practice (no DP at all). 150 allows ε≈2.9/week or ε≈11.5/month.
- **Gaussian/zCDP (future):** ~10-15% noise reduction via √n composition. Worth implementing but not blocking the pilot.

### Pilot noise budget (Pflege n=25, weekly, bounds=120, split 0.2/0.8, cap=150):

```
noise_std ≈ 2.9h  →  90% CI: ±6.7h  →  detects 5h+ systematic overtime
```

---

## 9. Cell Granularity Strategy

### Within-Hospital Cells

| Model | Cells | Min users | Use case |
|-------|-------|-----------|----------|
| **Staff group** (Pflege / Assistenzarzt / Facharzt / Oberarzt) | 4 | ~80 | **Pilot — start here** |
| Staff group, hospital-level (no specialty) | 1 | ~25 | Quick win, coarsest |
| Specialty × career stage | 11 | ~300 | Full breakdown, needs scale |

**Pilot strategy:** Start with staff-group-only cells. Pflege as one cell is publishable from day 1 at even 25 users with monthly resolution. Specialty breakdown added later as user base grows.

### Cross-Hospital Cells (State-Level)

| Model | Cells | Min users | Use case |
|-------|-------|-----------|----------|
| State × specialty × career stage | ~480 | ~5000 nationwide | Systemic overtime patterns |
| State × career stage | ~64 | ~1000 nationwide | Broad career-stage comparison |

Specialty × career stage within one hospital is not viable at typical German hospital sizes (~50-200 app users). This granularity works at state level across hospitals.

---

## 10. Error Bars and Transparency

Published statistics should include confidence intervals to communicate data quality.

### Approach: Conservative rounded display

Since exact error bars reveal exact cell size n (via `n = bounds / (noise_std × ε / √2)`), we round n **down** to the nearest 5 before computing the displayed CI:

```
n_display = (n // 5) * 5    # e.g., 23 → 20, 27 → 25
```

This ensures:
- Displayed CI is always **wider** than the true CI (conservative)
- Cell size is revealed only approximately (±5)
- Stakeholders get useful accuracy information

**Example output:**

```
Average actual hours (Pflege, KW12):  44.3h  [±6.7h 90% CI]  (~25 reporters)
Average actual hours (Assistenzärzte, KW12):  48.1h  [±9.2h 90% CI]  (~15 reporters)
```

### DESIGN DECISION — Discuss with stakeholders (ver.di)

**Should n be published exactly or approximately?**

Arguments for exact n:
- Transparency builds trust ("87 nurses reported this week")
- Unions may want precise participation numbers for legitimacy
- n is not health data — it's just app adoption

Arguments for approximate n:
- Avoids revealing exact workforce composition per department
- Conservative default, can be relaxed later

**Current default: round down to nearest 5. Flag for discussion with ver.di (meeting 2026-03-28).**

---

## 11. CLI Reference

```bash
# Single run (default: spread, 2000 users, ε=1.0, K_MIN=11, weekly)
python scripts/simulate_aggregation.py

# Pilot single run
python scripts/simulate_aggregation.py --pilot --users 80 --epsilon 2.0 --k-min 5 --period monthly

# Pilot with annual cap (computes ε automatically)
python scripts/simulate_aggregation.py --pilot --users 80 --annual-cap 150 --k-min 5 --period monthly

# Compare static vs dynamic schedules at cap=100
python scripts/simulate_aggregation.py --sweep-dynamic

# Hospital-level (no specialty split)
python scripts/simulate_aggregation.py --pilot --hospital --users 80 --annual-cap 150

# Dynamic schedule (monthly→biweekly→weekly)
python scripts/simulate_aggregation.py --pilot --dynamic --users 80 --annual-cap 150

# Full sweeps
python scripts/simulate_aggregation.py --sweep           # Nationwide (96 scenarios)
python scripts/simulate_aggregation.py --sweep-pilot      # Pilot (120 scenarios)
python scripts/simulate_aggregation.py --sweep-dynamic    # Dynamic/hospital comparison

# CSV output for analysis
python scripts/simulate_aggregation.py --sweep-pilot --csv > pilot_results.csv
```

---

## 12. Next Steps

### Decided — implement now
1. Update `config.py` defaults: K_MIN=5, bounds=120, split 0.2/0.8
2. Add annual cap = 150 to config validation
3. Implement temporal coarsening (monthly aggregation) in backend
4. Add `n_display = (n // 5) * 5` rounding for published error bars

### Decided — implement later
5. Gaussian/zCDP mechanism (~10-15% noise improvement)
6. Dynamic temporal schedule (monthly→biweekly→weekly)
7. Multiple release families (staff-group cells + specialty cells simultaneously)

### Discuss with stakeholders (ver.di meeting 2026-03-28)
8. Exact vs approximate n in published stats
9. Which cell granularity unions find most useful (staff group vs specialty)
10. Acceptable noise level for policy use ("can you work with ±3h error bars?")
11. K_MIN=5 justification for labor data (vs medical K_MIN=11)
