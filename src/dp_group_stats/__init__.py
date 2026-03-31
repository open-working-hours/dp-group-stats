"""dp-group-stats: Differentially private group statistics for working-hours data."""

__version__ = "0.1.0"

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
    DPGroupStatsV1Config,
    EpsilonSplit,
    PeriodType,
    ReleasePolicyConfig,
    periods_per_year,
)
from .mechanisms import laplace_ci_half_width, laplace_noise
from .periods import (
    compute_period_index,
    get_iso_week_bounds,
    get_period_bounds,
    period_before,
)
from .policy import PublicationStatus, get_publication_status

from .simulation import ScenarioResult, run_scenario

__all__ = [
    # simulation
    "run_scenario",
    "ScenarioResult",
    # config
    "PeriodType",
    "periods_per_year",
    "ContributionBounds",
    "EpsilonSplit",
    "ReleasePolicyConfig",
    "DPGroupStatsV1Config",
    # mechanisms
    "laplace_noise",
    "laplace_ci_half_width",
    # policy
    "PublicationStatus",
    "get_publication_status",
    # periods
    "get_iso_week_bounds",
    "get_period_bounds",
    "period_before",
    "compute_period_index",
    # accounting
    "CellKey",
    "BudgetEntry",
    "EpsilonBreakdown",
    "EpsilonLedger",
    "compute_adaptive_epsilon",
    "PrivacyLedger",
    "InMemoryPrivacyLedger",
]
