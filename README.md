# dp-group-stats

Differentially private group statistics for working-hours data. Pure Python, zero runtime dependencies.

**Status: Alpha** — API may change. Extracted from [Open Working Hours](https://openworkinghours.org).

## What it does

- **Laplace mechanism** with configurable epsilon and sensitivity
- **Publication state machine** (warming up / published / cooling down / suppressed) to prevent threshold-crossing leakage
- **Contribution clipping** with configurable bounds (planned hours, actual hours)
- **K-anonymity** + dominance rule (top-1 concentration check)
- **Temporal coarsening** — weekly, biweekly, or monthly aggregation periods
- **Adaptive epsilon schedule** — never overshoots an annual privacy budget cap
- **Confidence intervals** for Laplace-noised means
- **Privacy ledger protocol** — pluggable budget tracking (in-memory reference impl included)

## Install

```bash
pip install git+https://github.com/open-working-hours/dp-group-stats.git
```

For development:

```bash
git clone https://github.com/open-working-hours/dp-group-stats.git
cd dp-group-stats
pip install -e ".[dev]"
pytest -v
```

## Quick example

```python
from datetime import date
from dp_group_stats import (
    DPGroupStatsV1Config,
    laplace_noise,
    get_publication_status,
    compute_adaptive_epsilon,
    InMemoryPrivacyLedger,
)

# Configure the DP pipeline
config = DPGroupStatsV1Config()  # defaults: K_MIN=5, eps=1.0, weekly

# Add calibrated noise to a sum
sensitivity = config.bounds.actual_weekly_max  # 120h
noise = laplace_noise(epsilon=config.epsilon_split.actual_sum, sensitivity=sensitivity)
noisy_sum = 342.5 + noise

# Check publication eligibility
status = get_publication_status(
    was_active=False, consecutive_eligible=3, consecutive_ineligible=0,
    activation_weeks=config.release_policy.activation_weeks,
    deactivation_grace_weeks=config.release_policy.deactivation_grace_weeks,
)
print(status)  # PublicationStatus.published

# Track privacy budget
ledger = InMemoryPrivacyLedger()
ledger.record(user_id="u1", family="state_specialty", cell="DE/BY/cardiology",
              period=date(2026, 3, 16), epsilon=1.0)
print(ledger.user_spent("u1", since=date(2026, 1, 1)))  # 1.0
```

## Modules

| Module | Contents |
|--------|----------|
| `config` | `DPGroupStatsV1Config`, `ContributionBounds`, `EpsilonSplit`, `ReleasePolicyConfig`, `PeriodType` |
| `mechanisms` | `laplace_noise`, `laplace_ci_half_width` |
| `policy` | `PublicationStatus`, `get_publication_status` |
| `periods` | `get_period_bounds`, `period_before`, `compute_period_index` |
| `accounting` | `EpsilonLedger`, `compute_adaptive_epsilon`, `PrivacyLedger` (Protocol), `InMemoryPrivacyLedger` |
| `simulation` | `run_scenario`, `ScenarioResult` — parameter sweep over synthetic data |

## Simulation

The package includes a simulation module for validating parameter choices (epsilon, K_MIN, split ratios, dominance thresholds) over realistic synthetic data with user churn.

```bash
# Single scenario
dp-group-stats-sim --users 2000 --epsilon 1.0 --k-min 5

# Nationwide parameter sweep (96 combinations)
dp-group-stats-sim --sweep --csv > results.csv

# Pilot hospital scenario (Berlin, small groups)
dp-group-stats-sim --sweep-pilot

# Compare static vs dynamic temporal schedules
dp-group-stats-sim --sweep-dynamic
```

Or use programmatically:

```python
from dp_group_stats.simulation import run_scenario

result = run_scenario(n_users=2000, epsilon=1.0, split_planned_ratio=0.2,
                      dominance_threshold=0.30, seed=42, k_min=5)
print(f"Published: {result.pub_pct_end:.0f}%, MAE actual: {result.mae_actual_end:.1f}h")
```

## License

Apache 2.0. See [LICENSE](LICENSE).
