from __future__ import annotations

from datetime import date

from dp_group_stats import compute_period_index, get_period_bounds, period_before


def test_get_period_bounds_weekly() -> None:
    start, end = get_period_bounds(date(2026, 3, 18), "weekly")
    assert start == date(2026, 3, 16)
    assert end == date(2026, 3, 22)


def test_get_period_bounds_biweekly() -> None:
    start, end = get_period_bounds(date(2026, 3, 18), "biweekly")
    assert start == date(2026, 3, 9)
    assert end == date(2026, 3, 22)


def test_get_period_bounds_monthly() -> None:
    start, end = get_period_bounds(date(2026, 3, 18), "monthly")
    assert start == date(2026, 3, 1)
    assert end == date(2026, 3, 31)


def test_get_period_bounds_monthly_february() -> None:
    start, end = get_period_bounds(date(2026, 2, 15), "monthly")
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_period_before_weekly() -> None:
    assert period_before(date(2026, 3, 16), "weekly") == date(2026, 3, 9)


def test_period_before_biweekly() -> None:
    assert period_before(date(2026, 3, 16), "biweekly") == date(2026, 3, 2)


def test_period_before_monthly() -> None:
    assert period_before(date(2026, 3, 1), "monthly") == date(2026, 2, 1)
    assert period_before(date(2026, 1, 1), "monthly") == date(2025, 12, 1)


def test_compute_period_index_weekly() -> None:
    assert compute_period_index(date(2026, 3, 16), "weekly") == 11


def test_compute_period_index_monthly() -> None:
    assert compute_period_index(date(2026, 1, 1), "monthly") == 0
    assert compute_period_index(date(2026, 12, 1), "monthly") == 11


def test_compute_period_index_biweekly() -> None:
    assert compute_period_index(date(2026, 1, 5), "biweekly") == 0
    assert compute_period_index(date(2026, 1, 12), "biweekly") == 1
