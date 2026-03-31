from __future__ import annotations

import math

import pytest

from dp_group_stats import laplace_ci_half_width, laplace_noise


class StubRng:
    def __init__(self, value: float) -> None:
        self.value = value

    def uniform(self, a: float, b: float) -> float:
        return self.value


def test_laplace_noise_returns_zero_for_zero_sensitivity() -> None:
    assert laplace_noise(epsilon=1.0, sensitivity=0.0) == 0.0


def test_laplace_noise_uses_injected_rng() -> None:
    noise = laplace_noise(epsilon=1.0, sensitivity=10.0, rng=StubRng(0.25))

    assert noise == pytest.approx(-5.0)


def test_ci_basic_calculation() -> None:
    """Known values: eps=1.0, sensitivity=120, n=10, 90% CI."""
    ci_half, n_disp = laplace_ci_half_width(1.0, 120.0, 10)
    expected = 120.0 * math.log(20) / 10
    assert ci_half == pytest.approx(expected, rel=1e-4)
    assert n_disp == 10


def test_ci_n_display_rounding() -> None:
    """n_display rounds down to nearest 5, floored at 5."""
    _, n7 = laplace_ci_half_width(1.0, 120.0, 7)
    assert n7 == 5

    _, n12 = laplace_ci_half_width(1.0, 120.0, 12)
    assert n12 == 10

    _, n5 = laplace_ci_half_width(1.0, 120.0, 5)
    assert n5 == 5

    _, n3 = laplace_ci_half_width(1.0, 120.0, 3)
    assert n3 == 5
