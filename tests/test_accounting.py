from __future__ import annotations

from datetime import date

import pytest

from dp_group_stats.accounting import (
    EpsilonBreakdown,
    EpsilonLedger,
    InMemoryPrivacyLedger,
    compute_adaptive_epsilon,
)
from dp_group_stats.config import EpsilonSplit


# === EpsilonLedger (cell-only) ===


def test_epsilon_ledger_tracks_total_spend_per_cell() -> None:
    ledger = EpsilonLedger()
    cell_key = ("DEU", "BE", "cardiology")

    ledger.record(cell_key=cell_key, period_start=date(2026, 3, 16), epsilon=0.3)
    ledger.record(cell_key=cell_key, period_start=date(2026, 3, 23), epsilon=0.2)

    assert ledger.spent(cell_key) == pytest.approx(0.5)
    assert len(ledger.entries_for_cell(cell_key)) == 2


def test_epsilon_ledger_separate_cells() -> None:
    ledger = EpsilonLedger()
    cell_a = ("DEU", "BE", "cardiology")
    cell_b = ("DEU", "BY", "surgery")

    ledger.record(cell_key=cell_a, period_start=date(2026, 3, 16), epsilon=1.0)
    ledger.record(cell_key=cell_b, period_start=date(2026, 3, 16), epsilon=2.0)

    assert ledger.spent(cell_a) == pytest.approx(1.0)
    assert ledger.spent(cell_b) == pytest.approx(2.0)
    assert len(ledger.all_entries()) == 2


def test_epsilon_ledger_rejects_negative() -> None:
    ledger = EpsilonLedger()
    with pytest.raises(ValueError):
        ledger.record(cell_key=("DEU",), period_start=date(2026, 1, 1), epsilon=-0.1)


# === InMemoryPrivacyLedger (per-user) ===


def test_privacy_ledger_tracks_user_spending() -> None:
    ledger = InMemoryPrivacyLedger()
    ledger.record(
        user_id="user-1",
        family="state_specialty",
        cell_key="DEU/BE/cardiology",
        period_start=date(2026, 3, 16),
        epsilon=1.0,
    )
    ledger.record(
        user_id="user-1",
        family="state_specialty",
        cell_key="DEU/BE/cardiology",
        period_start=date(2026, 3, 23),
        epsilon=1.0,
    )

    assert ledger.user_spent("user-1") == pytest.approx(2.0)
    assert ledger.user_spent("user-2") == pytest.approx(0.0)


def test_privacy_ledger_tracks_cell_spending() -> None:
    ledger = InMemoryPrivacyLedger()
    ledger.record(
        user_id="user-1",
        family="state_specialty",
        cell_key="DEU/BE/cardiology",
        period_start=date(2026, 3, 16),
        epsilon=0.5,
    )
    ledger.record(
        user_id="user-2",
        family="state_specialty",
        cell_key="DEU/BE/cardiology",
        period_start=date(2026, 3, 16),
        epsilon=0.5,
    )

    assert ledger.cell_spent("DEU/BE/cardiology") == pytest.approx(1.0)


def test_privacy_ledger_user_spent_since() -> None:
    ledger = InMemoryPrivacyLedger()
    ledger.record(
        user_id="user-1",
        family="f1",
        cell_key="c1",
        period_start=date(2026, 1, 6),
        epsilon=1.0,
    )
    ledger.record(
        user_id="user-1",
        family="f1",
        cell_key="c1",
        period_start=date(2026, 6, 1),
        epsilon=2.0,
    )

    assert ledger.user_spent("user-1") == pytest.approx(3.0)
    assert ledger.user_spent("user-1", since=date(2026, 3, 1)) == pytest.approx(2.0)


def test_privacy_ledger_all_user_totals() -> None:
    ledger = InMemoryPrivacyLedger()
    ledger.record(user_id="a", family="f1", cell_key="c1",
                  period_start=date(2026, 1, 1), epsilon=1.0)
    ledger.record(user_id="b", family="f1", cell_key="c1",
                  period_start=date(2026, 1, 1), epsilon=3.0)
    ledger.record(user_id="a", family="f1", cell_key="c1",
                  period_start=date(2026, 1, 8), epsilon=1.0)

    totals = ledger.all_user_totals()
    assert totals["a"] == pytest.approx(2.0)
    assert totals["b"] == pytest.approx(3.0)


def test_privacy_ledger_worst_case_user() -> None:
    ledger = InMemoryPrivacyLedger()
    ledger.record(user_id="low", family="f1", cell_key="c1",
                  period_start=date(2026, 1, 1), epsilon=1.0)
    ledger.record(user_id="high", family="f1", cell_key="c1",
                  period_start=date(2026, 1, 1), epsilon=5.0)

    result = ledger.worst_case_user()
    assert result is not None
    assert result == ("high", 5.0)


def test_privacy_ledger_budget_summary() -> None:
    ledger = InMemoryPrivacyLedger()
    ledger.record(user_id="a", family="f1", cell_key="c1",
                  period_start=date(2026, 1, 1), epsilon=5.0)

    summary = ledger.budget_summary(annual_cap=150.0)
    assert summary["n_users"] == 1
    assert summary["worst_case_spent"] == pytest.approx(5.0)
    assert summary["utilization_pct"] == pytest.approx(5.0 / 150.0 * 100)


def test_privacy_ledger_rejects_negative() -> None:
    ledger = InMemoryPrivacyLedger()
    with pytest.raises(ValueError):
        ledger.record(user_id="a", family="f1", cell_key="c1",
                      period_start=date(2026, 1, 1), epsilon=-0.1)


# === Adaptive epsilon ===


def test_adaptive_epsilon_no_spending() -> None:
    result = compute_adaptive_epsilon(
        config_epsilon=1.0,
        annual_cap=150.0,
        period_index=0,
        total_periods=52,
        spent_so_far=0.0,
    )
    assert result == pytest.approx(1.0)


def test_adaptive_epsilon_partial_year() -> None:
    result = compute_adaptive_epsilon(
        config_epsilon=2.0,
        annual_cap=100.0,
        period_index=26,
        total_periods=52,
        spent_so_far=50.0,
    )
    expected = min(2.0, 50.0 / 26)
    assert result == pytest.approx(expected)


def test_adaptive_epsilon_over_cap() -> None:
    result = compute_adaptive_epsilon(
        config_epsilon=1.0,
        annual_cap=50.0,
        period_index=40,
        total_periods=52,
        spent_so_far=50.0,
    )
    assert result == pytest.approx(0.0)


def test_adaptive_preserves_split_ratio() -> None:
    split = EpsilonSplit(planned_sum=0.2, actual_sum=0.8)
    adaptive = compute_adaptive_epsilon(
        config_epsilon=split.total,
        annual_cap=150.0,
        period_index=0,
        total_periods=52,
        spent_so_far=0.0,
    )
    scale = adaptive / split.total
    effective = EpsilonBreakdown(
        planned_sum=split.planned_sum * scale,
        actual_sum=split.actual_sum * scale,
    )
    assert effective.planned_sum / effective.actual_sum == pytest.approx(0.2 / 0.8)


# === EpsilonBreakdown ===


def test_epsilon_breakdown_total() -> None:
    b = EpsilonBreakdown(planned_sum=0.2, actual_sum=0.8)
    assert b.total == pytest.approx(1.0)


def test_epsilon_breakdown_rejects_negative() -> None:
    with pytest.raises(ValueError):
        EpsilonBreakdown(planned_sum=-0.1, actual_sum=0.8)
