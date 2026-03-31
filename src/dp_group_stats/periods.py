"""Temporal period utilities: bounds, predecessor, and index for weekly/biweekly/monthly periods."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from .config import PeriodType

__all__ = ["get_iso_week_bounds", "get_period_bounds", "period_before", "compute_period_index"]


def get_iso_week_bounds(target_date: date) -> tuple[date, date]:
    """Return (Monday, Sunday) of the ISO week containing *target_date*."""
    iso_year, iso_week, _ = target_date.isocalendar()
    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _get_biweekly_bounds(target_date: date) -> tuple[date, date]:
    """ISO weeks paired 1-2, 3-4, ..., 51-52. Week 53 pairs with 52."""
    iso_year, iso_week, _ = target_date.isocalendar()
    if iso_week == 53:
        # Pair week 53 with week 52 → biweek starts at week 51
        pair_start_week = 51
    elif iso_week % 2 == 1:
        pair_start_week = iso_week
    else:
        pair_start_week = iso_week - 1
    start = date.fromisocalendar(iso_year, pair_start_week, 1)
    end = start + timedelta(days=13)
    return start, end


def _get_monthly_bounds(target_date: date) -> tuple[date, date]:
    """Calendar month: 1st to last day."""
    start = target_date.replace(day=1)
    last_day = calendar.monthrange(target_date.year, target_date.month)[1]
    end = target_date.replace(day=last_day)
    return start, end


def get_period_bounds(target_date: date, period_type: PeriodType) -> tuple[date, date]:
    """Return (start, end) dates for the period containing *target_date*."""
    if period_type == "weekly":
        return get_iso_week_bounds(target_date)
    elif period_type == "biweekly":
        return _get_biweekly_bounds(target_date)
    elif period_type == "monthly":
        return _get_monthly_bounds(target_date)
    raise ValueError(f"Unknown period_type: {period_type}")


def period_before(period_start: date, period_type: PeriodType) -> date:
    """Return the start date of the previous period."""
    if period_type == "weekly":
        return period_start - timedelta(days=7)
    elif period_type == "biweekly":
        return period_start - timedelta(days=14)
    elif period_type == "monthly":
        # Previous month's 1st
        if period_start.month == 1:
            return date(period_start.year - 1, 12, 1)
        return date(period_start.year, period_start.month - 1, 1)
    raise ValueError(f"Unknown period_type: {period_type}")


def compute_period_index(period_start: date, period_type: PeriodType) -> int:
    """0-based index of the period within its year."""
    if period_type == "weekly":
        _, iso_week, _ = period_start.isocalendar()
        return iso_week - 1
    elif period_type == "biweekly":
        _, iso_week, _ = period_start.isocalendar()
        return (iso_week - 1) // 2
    elif period_type == "monthly":
        return period_start.month - 1
    raise ValueError(f"Unknown period_type: {period_type}")
