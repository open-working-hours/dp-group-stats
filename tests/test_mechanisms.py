from __future__ import annotations

import math

import pytest

from dp_group_stats.mechanisms import laplace_ci_half_width, laplace_noise


class StubRng:
    def __init__(self, value: float) -> None:
        self.value = value

    def uniform(self, a: float, b: float) -> float:
        return self.value


def test_laplace_noise_returns_zero_for_zero_sensitivity() -> None:
    assert laplace_noise(epsilon=1.0, sensitivity=0.0) == 0.0


def test_laplace_noise_uses_injected_rng() -> None:
    # u=0.25 >= 0 → -scale * log(1 - 2*0.25) = -10 * log(0.5) ≈ 6.931
    noise = laplace_noise(epsilon=1.0, sensitivity=10.0, rng=StubRng(0.25))
    assert noise == pytest.approx(-10.0 * math.log(0.5))


def test_laplace_noise_rejects_negative_epsilon() -> None:
    with pytest.raises(ValueError, match="epsilon must be positive"):
        laplace_noise(epsilon=-1.0, sensitivity=10.0)


def test_laplace_noise_rejects_negative_sensitivity() -> None:
    with pytest.raises(ValueError, match="sensitivity must be non-negative"):
        laplace_noise(epsilon=1.0, sensitivity=-1.0)


def test_laplace_noise_statistical_properties() -> None:
    """Verify the distribution is actually Laplace: mean, variance, kurtosis, tails."""
    import random
    rng = random.Random(42)
    eps, sens = 2.0, 10.0
    scale = sens / eps  # b = 5
    samples = [laplace_noise(epsilon=eps, sensitivity=sens, rng=rng) for _ in range(50_000)]
    n = len(samples)
    mean = sum(samples) / n
    variance = sum((x - mean) ** 2 for x in samples) / n
    m4 = sum((x - mean) ** 4 for x in samples) / n
    excess_kurtosis = m4 / variance**2 - 3
    tail_fraction = sum(1 for x in samples if abs(x) > scale) / n

    assert abs(mean) < 0.5  # mean ≈ 0
    assert variance == pytest.approx(2 * scale**2, rel=0.15)  # Var = 2b²
    assert excess_kurtosis == pytest.approx(3.0, abs=1.0)  # Laplace kurtosis = 3
    assert tail_fraction > 0.25  # Laplace: P(|X|>b) ≈ 0.368; uniform: 0


def test_ci_basic_calculation() -> None:
    ci_half, n_disp = laplace_ci_half_width(1.0, 120.0, 10)
    expected = 120.0 * math.log(20) / 10
    assert ci_half == pytest.approx(expected, rel=1e-4)
    assert n_disp == 10


def test_ci_n_display_rounding() -> None:
    _, n7 = laplace_ci_half_width(1.0, 120.0, 7)
    assert n7 == 5

    _, n12 = laplace_ci_half_width(1.0, 120.0, 12)
    assert n12 == 10

    _, n5 = laplace_ci_half_width(1.0, 120.0, 5)
    assert n5 == 5

    _, n3 = laplace_ci_half_width(1.0, 120.0, 3)
    assert n3 == 5  # max(5, 0) = 5
