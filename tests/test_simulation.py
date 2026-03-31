from __future__ import annotations

import pytest

from dp_group_stats.simulation import (
    ScenarioResult,
    build_schedule,
    create_users,
    run_scenario,
)


def test_build_schedule_weekly() -> None:
    sched = build_schedule("weekly", 52, dynamic=False)
    assert len(sched) == 52
    assert all(w == 1 for w in sched)


def test_build_schedule_monthly() -> None:
    sched = build_schedule("monthly", 52, dynamic=False)
    assert len(sched) == 13
    assert all(w == 4 for w in sched)


def test_build_schedule_dynamic() -> None:
    sched = build_schedule("weekly", 52, dynamic=True)
    # Phase 1: 2 monthly (4w each) = 8w
    # Phase 2: 6 biweekly (2w each) = 12w
    # Phase 3: 32 weekly (1w each) = 32w
    # Total: 40 periods, 52 weeks
    assert len(sched) == 40
    assert sched[:2] == [4, 4]
    assert sched[2:8] == [2, 2, 2, 2, 2, 2]
    assert all(w == 1 for w in sched[8:])


def test_create_users_spread() -> None:
    from random import Random
    users = create_users(100, Random(42), pilot=False)
    assert len(users) == 100
    states = {u.state for u in users}
    assert len(states) > 1  # spread across states


def test_create_users_pilot() -> None:
    from random import Random
    users = create_users(50, Random(42), pilot=True)
    assert all(u.state == "BE" for u in users)


def test_run_scenario_basic() -> None:
    """Smoke test: run a small scenario and check result structure."""
    result = run_scenario(
        n_users=100,
        epsilon=1.0,
        split_planned_ratio=0.3,
        dominance_threshold=0.30,
        seed=42,
        n_weeks=8,
        k_min=5,
    )
    assert isinstance(result, ScenarioResult)
    assert result.users == 100
    assert result.epsilon == pytest.approx(1.0)
    assert result.n_periods == 8


def test_run_scenario_pilot_monthly() -> None:
    result = run_scenario(
        n_users=50,
        epsilon=2.0,
        split_planned_ratio=0.2,
        dominance_threshold=0.30,
        seed=99,
        n_weeks=12,
        k_min=3,
        pilot=True,
        period="monthly",
    )
    assert result.label == "pilot"
    assert result.n_periods == 3  # 12 weeks / 4


def test_run_scenario_with_annual_cap() -> None:
    """annual_cap overrides epsilon to cap/n_periods."""
    result = run_scenario(
        n_users=200,
        epsilon=999.0,  # should be overridden
        split_planned_ratio=0.3,
        dominance_threshold=0.30,
        seed=42,
        n_weeks=52,
        k_min=5,
        annual_cap=52.0,
    )
    assert result.epsilon == pytest.approx(1.0)  # 52/52
    assert result.n_periods == 52
