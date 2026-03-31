"""Publication state machine: controls when cells are published, suppressed, or transitioning."""

from __future__ import annotations

from enum import Enum

__all__ = ["PublicationStatus", "get_publication_status"]


class PublicationStatus(str, Enum):
    """Lifecycle state of a release cell."""
    published = "published"
    suppressed = "suppressed"
    warming_up = "warming_up"
    cooling_down = "cooling_down"


def get_publication_status(
    *,
    was_active: bool,
    consecutive_eligible: int,
    consecutive_ineligible: int,
    activation_weeks: int,
    deactivation_grace_weeks: int,
) -> PublicationStatus:
    if activation_weeks < 1:
        raise ValueError("activation_weeks must be at least 1")
    if deactivation_grace_weeks < 1:
        raise ValueError("deactivation_grace_weeks must be at least 1")
    if consecutive_eligible < 0 or consecutive_ineligible < 0:
        raise ValueError("streak counters must be non-negative")

    if was_active:
        if consecutive_ineligible >= deactivation_grace_weeks:
            return PublicationStatus.suppressed
        if consecutive_ineligible > 0:
            return PublicationStatus.cooling_down
        return PublicationStatus.published

    if consecutive_eligible >= activation_weeks:
        return PublicationStatus.published
    if consecutive_eligible > 0:
        return PublicationStatus.warming_up
    return PublicationStatus.suppressed
