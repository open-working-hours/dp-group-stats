from __future__ import annotations

from datetime import date

import pytest

from dp_group_stats import (
    EpsilonBreakdown,
    EpsilonLedger,
    EpsilonSplit,
    InMemoryPrivacyLedger,
    PrivacyLedger,
    compute_adaptive_epsilon,
)


def test_epsilon_ledger_tracks_total_spend_per_cell() -> None:
    ledger = EpsilonLedger()
    cell_key = ("DEU", "BE", "cardiology")

    ledger.record(cell_key=cell_key, period_start=date(2026, 3, 16), epsilon=0.3)
    ledger.record(cell_key=cell_key, period_start=date(2026, 3, 23), epsilon=0.2)

    assert ledger.spent(cell_key) == pytest.approx(0.5)
    assert len(ledger.entries_for_cell(cell_key)) == 2


def test_adaptive_epsilon_no_spending() -> None:
    """Fresh year with no spending -> returns config_epsilon."""
    result = compute_adaptive_epsilon(
        config_epsilon=1.0,
        annual_cap=150.0,
        period_index=0,
        total_periods=52,
        spent_so_far=0.0,
    )
    assert result == pytest.approx(1.0)


def test_adaptive_epsilon_partial_year() -> None:
    """Half-year spent 50 of 100 cap, 26 periods remaining -> 50/26."""
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
    """Spent >= cap -> returns 0."""
    result = compute_adaptive_epsilon(
        config_epsilon=1.0,
        annual_cap=50.0,
        period_index=40,
        total_periods=52,
        spent_so_far=50.0,
    )
    assert result == pytest.approx(0.0)


def test_adaptive_preserves_split_ratio() -> None:
    """Verify the split ratio is maintained when scaling."""
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


# --- InMemoryPrivacyLedger tests ---


def test_in_memory_ledger_satisfies_protocol() -> None:
    """InMemoryPrivacyLedger is a valid PrivacyLedger."""
    assert isinstance(InMemoryPrivacyLedger(), PrivacyLedger)


def test_in_memory_ledger_record_and_query() -> None:
    ledger = InMemoryPrivacyLedger()

    ledger.record(user_id="u1", family="F1", cell="DE/BY/cardio",
                  period=date(2026, 3, 16), epsilon=0.5)
    ledger.record(user_id="u1", family="F1", cell="DE/BY/cardio",
                  period=date(2026, 3, 23), epsilon=0.5)
    ledger.record(user_id="u2", family="F1", cell="DE/BE/neuro",
                  period=date(2026, 3, 16), epsilon=1.0)

    assert ledger.user_spent("u1", since=date(2026, 1, 1)) == pytest.approx(1.0)
    assert ledger.user_spent("u2", since=date(2026, 1, 1)) == pytest.approx(1.0)
    assert ledger.user_spent("u1", since=date(2026, 3, 20)) == pytest.approx(0.5)

    assert ledger.cell_spent("DE/BY/cardio", since=date(2026, 1, 1)) == pytest.approx(1.0)
    assert ledger.cell_spent("DE/BE/neuro", since=date(2026, 1, 1)) == pytest.approx(1.0)


def test_in_memory_ledger_all_user_totals() -> None:
    ledger = InMemoryPrivacyLedger()

    ledger.record(user_id="u1", family="F1", cell="c1",
                  period=date(2026, 3, 16), epsilon=0.5)
    ledger.record(user_id="u1", family="F1", cell="c1",
                  period=date(2026, 3, 23), epsilon=0.3)
    ledger.record(user_id="u2", family="F1", cell="c2",
                  period=date(2026, 3, 16), epsilon=1.0)

    totals = ledger.all_user_totals(since=date(2026, 1, 1))
    assert totals["u1"] == pytest.approx(0.8)
    assert totals["u2"] == pytest.approx(1.0)


def test_in_memory_ledger_rejects_negative_epsilon() -> None:
    ledger = InMemoryPrivacyLedger()
    with pytest.raises(ValueError, match="non-negative"):
        ledger.record(user_id="u1", family="F1", cell="c1",
                      period=date(2026, 3, 16), epsilon=-0.1)
