from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Protocol


CellKey = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BudgetEntry:
    """A single recorded epsilon expenditure."""

    cell_key: CellKey
    period_start: date
    epsilon: float


@dataclass(frozen=True, slots=True)
class EpsilonBreakdown:
    """Per-quantity epsilon breakdown for a single cell publication."""

    planned_sum: float
    actual_sum: float

    def __post_init__(self) -> None:
        if self.planned_sum < 0 or self.actual_sum < 0:
            raise ValueError("epsilon components must be non-negative")

    @property
    def total(self) -> float:
        return self.planned_sum + self.actual_sum


# ---------------------------------------------------------------------------
# Protocol: pluggable storage backend
# ---------------------------------------------------------------------------


class PrivacyLedger(Protocol):
    """Abstract interface for privacy budget accounting.

    Implementations track per-user and per-cell epsilon expenditure.
    The library ships with :class:`InMemoryPrivacyLedger`; applications
    can provide their own (e.g., SQL-backed) implementation.
    """

    def record(
        self,
        *,
        user_id: str,
        family: str,
        cell_key: str,
        period_start: date,
        epsilon: float,
    ) -> None:
        """Record an epsilon expenditure for a user in a cell."""
        ...

    def user_spent(self, user_id: str, since: date | None = None) -> float:
        """Return total epsilon spent by a user, optionally since a date."""
        ...

    def cell_spent(self, cell_key: str, since: date | None = None) -> float:
        """Return total epsilon spent on a cell, optionally since a date."""
        ...

    def all_user_totals(self, since: date | None = None) -> dict[str, float]:
        """Return {user_id: total_spent} for all users."""
        ...


# ---------------------------------------------------------------------------
# In-memory implementation
# ---------------------------------------------------------------------------


@dataclass
class _LedgerEntry:
    user_id: str
    family: str
    cell_key: str
    period_start: date
    epsilon: float


class InMemoryPrivacyLedger:
    """In-memory implementation of :class:`PrivacyLedger`.

    Suitable for testing, simulation, and short-lived pipelines.
    """

    def __init__(self) -> None:
        self._entries: list[_LedgerEntry] = []
        self._user_totals: dict[str, float] = defaultdict(float)
        self._cell_totals: dict[str, float] = defaultdict(float)

    def record(
        self,
        *,
        user_id: str,
        family: str,
        cell_key: str,
        period_start: date,
        epsilon: float,
    ) -> None:
        if epsilon < 0:
            raise ValueError("epsilon must be non-negative")
        self._entries.append(
            _LedgerEntry(
                user_id=user_id,
                family=family,
                cell_key=cell_key,
                period_start=period_start,
                epsilon=epsilon,
            )
        )
        self._user_totals[user_id] += epsilon
        self._cell_totals[cell_key] += epsilon

    def user_spent(self, user_id: str, since: date | None = None) -> float:
        if since is None:
            return self._user_totals.get(user_id, 0.0)
        return sum(
            e.epsilon for e in self._entries
            if e.user_id == user_id and e.period_start >= since
        )

    def cell_spent(self, cell_key: str, since: date | None = None) -> float:
        if since is None:
            return self._cell_totals.get(cell_key, 0.0)
        return sum(
            e.epsilon for e in self._entries
            if e.cell_key == cell_key and e.period_start >= since
        )

    def all_user_totals(self, since: date | None = None) -> dict[str, float]:
        if since is None:
            return dict(self._user_totals)
        totals: dict[str, float] = defaultdict(float)
        for e in self._entries:
            if e.period_start >= since:
                totals[e.user_id] += e.epsilon
        return dict(totals)

    def worst_case_user(self, since: date | None = None) -> tuple[str, float] | None:
        """Return (user_id, total_spent) for the highest-spending user."""
        totals = self.all_user_totals(since=since)
        if not totals:
            return None
        user_id = max(totals, key=totals.get)  # type: ignore[arg-type]
        return user_id, totals[user_id]

    def budget_summary(
        self,
        *,
        annual_cap: float,
        since: date | None = None,
    ) -> dict[str, object]:
        """Return a summary of budget utilization."""
        totals = self.all_user_totals(since=since)
        n_users = len(totals)
        if n_users == 0:
            return {
                "n_users": 0,
                "worst_case_spent": 0.0,
                "avg_spent": 0.0,
                "utilization_pct": 0.0,
                "annual_cap": annual_cap,
            }
        spends = list(totals.values())
        worst = max(spends)
        avg = sum(spends) / n_users
        return {
            "n_users": n_users,
            "worst_case_spent": worst,
            "avg_spent": avg,
            "utilization_pct": (worst / annual_cap * 100) if annual_cap > 0 else 0.0,
            "annual_cap": annual_cap,
        }


# ---------------------------------------------------------------------------
# Simple cell-level ledger (no user tracking)
# ---------------------------------------------------------------------------


class EpsilonLedger:
    """Lightweight cell-only epsilon ledger.

    Tracks total spend per cell without per-user breakdown.
    Useful for simple pipelines where per-user accounting
    is not needed.
    """

    def __init__(self) -> None:
        self._entries: list[BudgetEntry] = []
        self._totals_by_cell: dict[CellKey, float] = defaultdict(float)

    def record(self, *, cell_key: CellKey, period_start: date, epsilon: float) -> BudgetEntry:
        if epsilon < 0:
            raise ValueError("epsilon must be non-negative")
        entry = BudgetEntry(cell_key=cell_key, period_start=period_start, epsilon=epsilon)
        self._entries.append(entry)
        self._totals_by_cell[cell_key] += epsilon
        return entry

    def spent(self, cell_key: CellKey) -> float:
        return self._totals_by_cell.get(cell_key, 0.0)

    def entries_for_cell(self, cell_key: CellKey) -> list[BudgetEntry]:
        return [entry for entry in self._entries if entry.cell_key == cell_key]

    def all_entries(self) -> list[BudgetEntry]:
        return list(self._entries)


# ---------------------------------------------------------------------------
# Adaptive epsilon
# ---------------------------------------------------------------------------


def compute_adaptive_epsilon(
    *,
    config_epsilon: float,
    annual_cap: float,
    period_index: int,
    total_periods: int,
    spent_so_far: float,
) -> float:
    """Compute adaptive per-period epsilon that never overshoots the annual cap.

    Returns ``min(config_epsilon, remaining_budget / remaining_periods)``.
    This ensures graceful degradation: cells get noisier instead of going dark
    when the budget runs low.
    """
    remaining = max(0.0, annual_cap - spent_so_far)
    remaining_periods = max(1, total_periods - period_index)
    return min(config_epsilon, remaining / remaining_periods)
