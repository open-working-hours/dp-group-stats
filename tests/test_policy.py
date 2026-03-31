from __future__ import annotations

from dp_group_stats import PublicationStatus, get_publication_status


def test_publication_status_warms_up_before_first_release() -> None:
    status = get_publication_status(
        was_active=False,
        consecutive_eligible=1,
        consecutive_ineligible=0,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )

    assert status == PublicationStatus.warming_up


def test_publication_status_publishes_after_activation_threshold() -> None:
    status = get_publication_status(
        was_active=False,
        consecutive_eligible=2,
        consecutive_ineligible=0,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )

    assert status == PublicationStatus.published


def test_publication_status_cools_down_before_deactivation() -> None:
    status = get_publication_status(
        was_active=True,
        consecutive_eligible=0,
        consecutive_ineligible=1,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )

    assert status == PublicationStatus.cooling_down


def test_publication_status_suppresses_after_grace_period() -> None:
    status = get_publication_status(
        was_active=True,
        consecutive_eligible=0,
        consecutive_ineligible=2,
        activation_weeks=2,
        deactivation_grace_weeks=2,
    )

    assert status == PublicationStatus.suppressed
