from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PeriodType = Literal["weekly", "biweekly", "monthly"]


def periods_per_year(period_type: PeriodType) -> int:
    """Return the number of aggregation periods in a year."""
    if period_type == "weekly":
        return 52
    elif period_type == "biweekly":
        return 26
    elif period_type == "monthly":
        return 12
    raise ValueError(f"Unknown period_type: {period_type}")


@dataclass(frozen=True, slots=True)
class ContributionBounds:
    """Clipping bounds for user contributions per period.

    Values outside these bounds are clipped before aggregation,
    bounding the sensitivity of the DP mechanism.
    """

    planned_weekly_min: float = 0.0
    planned_weekly_max: float = 80.0
    actual_weekly_min: float = 0.0
    actual_weekly_max: float = 120.0

    def __post_init__(self) -> None:
        if self.planned_weekly_max <= self.planned_weekly_min:
            raise ValueError("planned_weekly_max must be greater than planned_weekly_min")
        if self.actual_weekly_max <= self.actual_weekly_min:
            raise ValueError("actual_weekly_max must be greater than actual_weekly_min")

    def clip_planned(self, value: float) -> float:
        return min(max(value, self.planned_weekly_min), self.planned_weekly_max)

    def clip_actual(self, value: float) -> float:
        return min(max(value, self.actual_weekly_min), self.actual_weekly_max)

    @property
    def planned_sensitivity(self) -> float:
        return self.planned_weekly_max - self.planned_weekly_min

    @property
    def actual_sensitivity(self) -> float:
        return self.actual_weekly_max - self.actual_weekly_min


@dataclass(frozen=True, slots=True)
class EpsilonSplit:
    """How total per-cell epsilon is divided across noised quantities."""

    planned_sum: float = 0.2
    actual_sum: float = 0.8

    def __post_init__(self) -> None:
        if self.planned_sum <= 0 or self.actual_sum <= 0:
            raise ValueError("all epsilon split components must be positive")

    @property
    def total(self) -> float:
        return self.planned_sum + self.actual_sum


@dataclass(frozen=True, slots=True)
class ReleasePolicyConfig:
    """Non-DP publication safeguards layered on top of the DP mechanism."""

    k_min: int = 5
    activation_weeks: int = 2
    deactivation_grace_weeks: int = 2
    publish_counts: bool = False
    dominance_threshold: float = 0.30

    def __post_init__(self) -> None:
        if self.k_min < 1:
            raise ValueError("k_min must be at least 1")
        if self.activation_weeks < 1:
            raise ValueError("activation_weeks must be at least 1")
        if self.deactivation_grace_weeks < 1:
            raise ValueError("deactivation_grace_weeks must be at least 1")
        if not (0.0 < self.dominance_threshold <= 1.0):
            raise ValueError("dominance_threshold must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class DPGroupStatsConfig:
    """Top-level configuration for the DP group statistics pipeline.

    Validates that the configured epsilon budget is consistent with
    the annual cap at construction time.
    """

    bounds: ContributionBounds = field(default_factory=ContributionBounds)
    epsilon_split: EpsilonSplit = field(default_factory=EpsilonSplit)
    release_policy: ReleasePolicyConfig = field(default_factory=ReleasePolicyConfig)
    annual_epsilon_cap: float | None = 150.0
    period_type: PeriodType = "weekly"

    def __post_init__(self) -> None:
        if self.annual_epsilon_cap is not None:
            n_periods = periods_per_year(self.period_type)
            annual_spend = self.epsilon_split.total * n_periods
            if annual_spend > self.annual_epsilon_cap:
                raise ValueError(
                    f"Per-period epsilon ({self.epsilon_split.total}) x {n_periods} = {annual_spend} "
                    f"exceeds annual cap ({self.annual_epsilon_cap})"
                )
