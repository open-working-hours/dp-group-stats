# dp-group-stats

A lightweight Python library for publishing differentially private aggregate statistics over small groups, with k-anonymity gating and privacy budget accounting.

[![PyPI version](https://img.shields.io/pypi/v/dp-group-stats.svg)](https://pypi.org/project/dp-group-stats/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What this solves

When publishing aggregate statistics (means, sums) for small professional groups on a recurring schedule, you need:

1. **Differential privacy** — calibrated noise so individual contributions can't be reverse-engineered
2. **K-anonymity gating** — suppress groups that are too small to publish safely
3. **Budget accounting** — track cumulative privacy spend per user across groups and time
4. **Graceful degradation** — when budget runs low, statistics get noisier instead of disappearing

Existing DP libraries are either massive frameworks (OpenDP, TensorFlow Privacy) or bare mechanism implementations. `dp-group-stats` is the pipeline layer in between: configuration, noise, publication policy, and budget tracking in one focused package with zero dependencies.

## Install

```bash
pip install dp-group-stats
```

**Requirements:** Python 3.10+ — no dependencies beyond the standard library.

## Quick start

```python
from datetime import date
from dp_group_stats import (
    DPGroupStatsConfig,
    InMemoryPrivacyLedger,
    PublicationStatus,
    compute_adaptive_epsilon,
    get_period_bounds,
    get_publication_status,
    laplace_noise,
    laplace_ci_half_width,
)

# 1. Configure the pipeline
config = DPGroupStatsConfig(
    period_type="weekly",
    annual_epsilon_cap=150.0,
)

# 2. Check publication eligibility
status = get_publication_status(
    was_active=False,
    consecutive_eligible=3,
    consecutive_ineligible=0,
    activation_weeks=config.release_policy.activation_weeks,
    deactivation_grace_weeks=config.release_policy.deactivation_grace_weeks,
)
assert status == PublicationStatus.published

# 3. Clip contributions and add noise
raw_actual_hours = [42.0, 55.0, 38.0, 61.0, 200.0, 44.0]
clipped = [config.bounds.clip_actual(h) for h in raw_actual_hours]
true_sum = sum(clipped)

noisy_sum = true_sum + laplace_noise(
    epsilon=config.epsilon_split.actual_sum,
    sensitivity=config.bounds.actual_sensitivity,
)
noisy_mean = noisy_sum / len(clipped)

# 4. Compute confidence intervals
ci_half, n_display = laplace_ci_half_width(
    epsilon=config.epsilon_split.actual_sum,
    sensitivity=config.bounds.actual_sensitivity,
    n_users=len(clipped),
)
print(f"Mean: {noisy_mean:.1f}h [±{ci_half:.1f}h 90% CI] (~{n_display} reporters)")

# 5. Track budget
ledger = InMemoryPrivacyLedger()
for user_id in ["u1", "u2", "u3", "u4", "u5", "u6"]:
    ledger.record(
        user_id=user_id,
        family="state_specialty",
        cell_key="DEU/BE/cardiology",
        period_start=date(2026, 3, 16),
        epsilon=config.epsilon_split.total,
    )

summary = ledger.budget_summary(annual_cap=config.annual_epsilon_cap)
print(f"Worst-case user: {summary['worst_case_spent']:.1f}ε of {summary['annual_cap']}ε cap")
```

## Components

### Configuration (`dp_group_stats.config`)

- **`ContributionBounds`** — clipping bounds that limit sensitivity (default: planned [0, 80h], actual [0, 120h])
- **`EpsilonSplit`** — how per-cell epsilon is divided across quantities (default: 0.2 planned, 0.8 actual)
- **`ReleasePolicyConfig`** — k-anonymity threshold, dominance rule, activation/deactivation streaks
- **`DPGroupStatsConfig`** — top-level config with budget validation at construction time

### Mechanisms (`dp_group_stats.mechanisms`)

- **`laplace_noise()`** — Laplace mechanism with injectable RNG for deterministic testing
- **`laplace_ci_half_width()`** — confidence intervals with rounded group size to avoid leaking exact n

### Policy (`dp_group_stats.policy`)

Publication state machine: `suppressed → warming_up → published → cooling_down → suppressed`

- Cells must pass k_min *and* dominance checks for N consecutive periods before publishing
- Grace period before suppression (noise continues during cooldown to prevent information leakage)

### Accounting (`dp_group_stats.accounting`)

- **`PrivacyLedger`** (Protocol) — pluggable interface for budget tracking
- **`InMemoryPrivacyLedger`** — reference implementation for testing/simulation
- **`EpsilonLedger`** — lightweight cell-only tracker
- **`compute_adaptive_epsilon()`** — graceful degradation that scales epsilon down as the annual cap approaches

Bring your own storage backend by implementing the `PrivacyLedger` protocol (e.g., SQL-backed for production).

### Periods (`dp_group_stats.periods`)

- **`get_period_bounds()`** — weekly/biweekly/monthly period boundaries
- **`period_before()`** / **`compute_period_index()`** — temporal navigation

## Design decisions

This library makes specific choices documented in the [design specs](https://github.com/open-working-hours/dp-group-stats/tree/main/docs):

- **Substitution neighboring relation**: DP protects contribution *values*, not user *presence*. Counts are public; only sums are noised.
- **Per-user budget accounting**: the privacy guarantee lives with users, not cells. A user appearing in multiple release families accumulates epsilon across all of them.
- **Time-based degradation**: adaptive epsilon is computed from elapsed time and configured spending, not from actual per-user data (which would itself leak information).
- **K-anonymity as policy, not proof**: k_min and dominance rules are publication safeguards layered on top of DP, not substitutes for it.

## Developed for

This library was extracted from [Open Working Hours](https://openworkinghours.org), a privacy-first platform for healthcare workers to track and report working hours. The design was validated through [200+ simulation scenarios](https://github.com/open-working-hours/dp-group-stats/blob/main/docs/simulation-spec.md) covering parameter selection for workforce statistics.

## Use of generative AI

This project is developed with an AI assistant (Anthropic's Claude, via the Claude Code CLI). It is used in three ways: as a research aid (finding and summarising methods, papers and comparable projects, which are then checked against the sources), as a reviewer (pressure-testing designs, code and documents), and as a pair programmer.

The division of labour:

- **Human-authored:** the privacy mechanism design and the specification documents in [`docs/`](https://github.com/open-working-hours/dp-group-stats/tree/main/docs) (neighboring relation, accounting model, simulation spec), parameter decisions, and review of every change before it is committed.
- **Assistant-assisted:** implementation drafts written against those specs, test scaffolding, review of diffs, and documentation drafts.

Provenance: commits that contain assistant-generated code carry a `Co-Authored-By` trailer naming the model and version, and state in the commit message how the assistant was used, with the prompts or a summary of the interaction. Purely human-authored commits carry no trailer. This follows the [NLnet generative AI policy](https://nlnet.nl/foundation/policies/generativeAI/); commits before September 2026 carry the trailer but not the prompt summary.

The maintainer reviews all assistant output for correctness and for licence compatibility before it is committed, can explain every design and code decision in this repository, and takes full responsibility for the result regardless of how it was drafted.

## License

MIT
