from __future__ import annotations

import pytest

from dp_group_stats.policy import PublicationStatus, get_publication_status


def test_suppressed_when_never_active_and_not_eligible() -> None:
    status = get_publication_status(
        was_active=False,
        consecutive_eligible=0,
        consecutive_ineligible=0,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )
    assert status == PublicationStatus.suppressed


def test_warming_up_before_first_release() -> None:
    status = get_publication_status(
        was_active=False,
        consecutive_eligible=1,
        consecutive_ineligible=0,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )
    assert status == PublicationStatus.warming_up


def test_publishes_after_activation_threshold() -> None:
    status = get_publication_status(
        was_active=False,
        consecutive_eligible=2,
        consecutive_ineligible=0,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )
    assert status == PublicationStatus.published


def test_stays_published_while_eligible() -> None:
    status = get_publication_status(
        was_active=True,
        consecutive_eligible=5,
        consecutive_ineligible=0,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )
    assert status == PublicationStatus.published


def test_cooling_down_before_deactivation() -> None:
    status = get_publication_status(
        was_active=True,
        consecutive_eligible=0,
        consecutive_ineligible=1,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )
    assert status == PublicationStatus.cooling_down


def test_suppresses_after_grace_period() -> None:
    status = get_publication_status(
        was_active=True,
        consecutive_eligible=0,
        consecutive_ineligible=2,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )
    assert status == PublicationStatus.suppressed


def test_rejects_invalid_activation_weeks() -> None:
    with pytest.raises(ValueError):
        get_publication_status(
            was_active=False,
            consecutive_eligible=0,
            consecutive_ineligible=0,
            activation_weeks=0,
            deactivation_grace_weeks=2,
        )


def test_rejects_negative_streak() -> None:
    with pytest.raises(ValueError):
        get_publication_status(
            was_active=False,
            consecutive_eligible=-1,
            consecutive_ineligible=0,
            activation_weeks=2,
            deactivation_grace_weeks=2,
        )
