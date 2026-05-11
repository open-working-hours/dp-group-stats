"""Differentially private publication pipeline for aggregate group statistics.

``dp-group-stats`` provides the building blocks for publishing aggregate
statistics over small groups while protecting individual contributions
with differential privacy and k-anonymity gating.

Key components:

- **Configuration** (:mod:`.config`): contribution bounds, epsilon splits,
  release policy parameters, and top-level pipeline config with budget validation.
- **Mechanisms** (:mod:`.mechanisms`): Laplace noise sampling and confidence
  interval computation.
- **Policy** (:mod:`.policy`): publication state machine with activation
  streaks and cooling-down grace periods.
- **Accounting** (:mod:`.accounting`): epsilon budget tracking with a
  pluggable :class:`PrivacyLedger` protocol and an in-memory implementation.
- **Periods** (:mod:`.periods`): temporal coarsening utilities for weekly,
  biweekly, and monthly aggregation.
"""

from .accounting import (
    BudgetEntry,
    CellKey,
    EpsilonBreakdown,
    EpsilonLedger,
    InMemoryPrivacyLedger,
    PrivacyLedger,
    compute_adaptive_epsilon,
)
from .config import (
    ContributionBounds,
    DPGroupStatsConfig,
    EpsilonSplit,
    PeriodType,
    ReleasePolicyConfig,
    periods_per_year,
)
from .mechanisms import laplace_ci_half_width, laplace_noise
from .periods import compute_period_index, get_period_bounds, period_before
from .policy import PublicationStatus, get_publication_status

__version__ = "0.1.1"

__all__ = [
    # config
    "ContributionBounds",
    "DPGroupStatsConfig",
    "EpsilonSplit",
    "PeriodType",
    "ReleasePolicyConfig",
    "periods_per_year",
    # mechanisms
    "laplace_ci_half_width",
    "laplace_noise",
    # policy
    "PublicationStatus",
    "get_publication_status",
    # accounting
    "BudgetEntry",
    "CellKey",
    "EpsilonBreakdown",
    "EpsilonLedger",
    "InMemoryPrivacyLedger",
    "PrivacyLedger",
    "compute_adaptive_epsilon",
    # periods
    "compute_period_index",
    "get_period_bounds",
    "period_before",
]
