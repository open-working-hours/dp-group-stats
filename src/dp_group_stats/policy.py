from __future__ import annotations

from enum import Enum


class PublicationStatus(str, Enum):
    """State machine for cell publication lifecycle.

    Transitions::

        suppressed --> warming_up --> published --> cooling_down --> suppressed
                                          ^                            |
                                          +----------------------------+
                                          (re-eligible before grace expires)

    - ``warming_up``: cell is above k_min but hasn't met the activation
      streak yet. No output, no epsilon cost.
    - ``published``: cell is actively published. Noise is generated and
      epsilon is recorded.
    - ``cooling_down``: cell dropped below eligibility but is within the
      grace period. Noise is still generated (sudden disappearance of
      noise is itself informative).
    - ``suppressed``: cell is below k_min or failed the dominance check.
      No output, no epsilon cost.
    """

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
    """Determine a cell's publication status based on eligibility streaks.

    Args:
        was_active: Whether the cell was in ``published`` or ``cooling_down``
            state in the previous period.
        consecutive_eligible: Number of consecutive periods the cell has
            met k_min and dominance requirements.
        consecutive_ineligible: Number of consecutive periods the cell has
            failed eligibility.
        activation_weeks: Required consecutive eligible periods before
            first publication.
        deactivation_grace_weeks: Grace periods below eligibility before
            suppression (noise continues during grace).
    """
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
