from __future__ import annotations

import pytest

from dp_group_stats.config import (
    ContributionBounds,
    DPGroupStatsConfig,
    EpsilonSplit,
    ReleasePolicyConfig,
    periods_per_year,
)


def test_contribution_bounds_clip_values() -> None:
    bounds = ContributionBounds()
    assert bounds.clip_planned(-5.0) == 0.0
    assert bounds.clip_planned(120.0) == 80.0
    assert bounds.clip_actual(-1.0) == 0.0
    assert bounds.clip_actual(180.0) == 120.0


def test_contribution_bounds_sensitivity() -> None:
    bounds = ContributionBounds()
    assert bounds.planned_sensitivity == 80.0
    assert bounds.actual_sensitivity == 120.0


def test_contribution_bounds_custom() -> None:
    bounds = ContributionBounds(planned_weekly_min=10, planned_weekly_max=50,
                                actual_weekly_min=5, actual_weekly_max=100)
    assert bounds.clip_planned(5) == 10
    assert bounds.clip_actual(200) == 100
    assert bounds.planned_sensitivity == 40.0
    assert bounds.actual_sensitivity == 95.0


def test_contribution_bounds_invalid() -> None:
    with pytest.raises(ValueError):
        ContributionBounds(planned_weekly_min=80, planned_weekly_max=10)


def test_epsilon_split_total() -> None:
    split = EpsilonSplit(planned_sum=0.2, actual_sum=0.8)
    assert split.total == pytest.approx(1.0)


def test_epsilon_split_defaults() -> None:
    split = EpsilonSplit()
    assert split.planned_sum == 0.2
    assert split.actual_sum == 0.8
    assert split.total == pytest.approx(1.0)


def test_epsilon_split_rejects_zero() -> None:
    with pytest.raises(ValueError):
        EpsilonSplit(planned_sum=0, actual_sum=0.5)


def test_release_policy_config_validates_positive_values() -> None:
    with pytest.raises(ValueError):
        ReleasePolicyConfig(activation_weeks=0)


def test_dominance_threshold_in_config() -> None:
    config = ReleasePolicyConfig()
    assert config.dominance_threshold == 0.30

    custom = ReleasePolicyConfig(dominance_threshold=0.5)
    assert custom.dominance_threshold == 0.5

    with pytest.raises(ValueError):
        ReleasePolicyConfig(dominance_threshold=0.0)

    with pytest.raises(ValueError):
        ReleasePolicyConfig(dominance_threshold=1.5)


def test_config_validates_annual_budget_cap() -> None:
    config = DPGroupStatsConfig()
    assert config.annual_epsilon_cap == 150.0

    config = DPGroupStatsConfig(annual_epsilon_cap=52.0)
    assert config.annual_epsilon_cap == 52.0

    with pytest.raises(ValueError, match="exceeds annual cap"):
        DPGroupStatsConfig(annual_epsilon_cap=10.0)


def test_config_annual_cap_with_period_type() -> None:
    config = DPGroupStatsConfig(period_type="monthly")
    assert config.period_type == "monthly"

    config = DPGroupStatsConfig(period_type="monthly", annual_epsilon_cap=12.0)
    assert config.annual_epsilon_cap == 12.0

    with pytest.raises(ValueError, match="exceeds annual cap"):
        DPGroupStatsConfig(period_type="monthly", annual_epsilon_cap=5.0)


def test_periods_per_year() -> None:
    assert periods_per_year("weekly") == 52
    assert periods_per_year("biweekly") == 26
    assert periods_per_year("monthly") == 12
