"""Privacy budget accounting: ledgers, adaptive epsilon, and the PrivacyLedger protocol."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

__all__ = [
    "CellKey",
    "BudgetEntry",
    "EpsilonBreakdown",
    "EpsilonLedger",
    "compute_adaptive_epsilon",
    "PrivacyLedger",
    "InMemoryPrivacyLedger",
]

CellKey = tuple[str, ...]
"""A tuple identifying a release cell, e.g. ``("DEU", "BE", "cardiology")``."""


@dataclass(frozen=True, slots=True)
class BudgetEntry:
    """Single epsilon expenditure record for a cell in a given period."""

    cell_key: CellKey
    period_start: date
    epsilon: float


@dataclass(frozen=True, slots=True)
class EpsilonBreakdown:
    """Epsilon split into planned-sum and actual-sum components."""

    planned_sum: float
    actual_sum: float

    def __post_init__(self) -> None:
        if self.planned_sum < 0 or self.actual_sum < 0:
            raise ValueError("epsilon components must be non-negative")

    @property
    def total(self) -> float:
        return self.planned_sum + self.actual_sum


class EpsilonLedger:
    """In-memory per-cell epsilon ledger for tracking cumulative budget spend."""

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


def compute_adaptive_epsilon(
    *,
    config_epsilon: float,
    annual_cap: float,
    period_index: int,
    total_periods: int,
    spent_so_far: float,
) -> float:
    """Compute adaptive per-period epsilon that never overshoots the annual cap.

    Returns min(config_epsilon, remaining_budget / remaining_periods).
    """
    remaining = max(0.0, annual_cap - spent_so_far)
    remaining_periods = max(1, total_periods - period_index)
    return min(config_epsilon, remaining / remaining_periods)


# ---------------------------------------------------------------------------
# PrivacyLedger Protocol — generalized interface for budget tracking
# (See accounting model spec Section 7.3)
# ---------------------------------------------------------------------------


@runtime_checkable
class PrivacyLedger(Protocol):
    """Storage-agnostic interface for privacy budget accounting.

    Implementations: InMemoryPrivacyLedger (reference), SQL-backed (OWH backend),
    pandas-backed (analysis scripts).
    """

    def record(
        self, *, user_id: str, family: str, cell: str, period: date, epsilon: float
    ) -> None: ...

    def user_spent(self, user_id: str, *, since: date) -> float: ...

    def cell_spent(self, cell: str, *, since: date) -> float: ...

    def all_user_totals(self, *, since: date) -> dict[str, float]: ...


class InMemoryPrivacyLedger:
    """Reference implementation of PrivacyLedger backed by plain lists."""

    @dataclass(frozen=True, slots=True)
    class _Entry:
        user_id: str
        family: str
        cell: str
        period: date
        epsilon: float

    def __init__(self) -> None:
        self._entries: list[InMemoryPrivacyLedger._Entry] = []

    def record(
        self, *, user_id: str, family: str, cell: str, period: date, epsilon: float
    ) -> None:
        if epsilon < 0:
            raise ValueError("epsilon must be non-negative")
        self._entries.append(self._Entry(user_id=user_id, family=family, cell=cell, period=period, epsilon=epsilon))

    def user_spent(self, user_id: str, *, since: date) -> float:
        return sum(e.epsilon for e in self._entries if e.user_id == user_id and e.period >= since)

    def cell_spent(self, cell: str, *, since: date) -> float:
        return sum(e.epsilon for e in self._entries if e.cell == cell and e.period >= since)

    def all_user_totals(self, *, since: date) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for e in self._entries:
            if e.period >= since:
                totals[e.user_id] += e.epsilon
        return dict(totals)
