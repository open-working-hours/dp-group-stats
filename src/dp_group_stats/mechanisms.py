"""Laplace mechanism for differential privacy: noise generation and confidence intervals."""

from __future__ import annotations

import math
import secrets
from typing import Protocol

__all__ = ["laplace_noise", "laplace_ci_half_width"]


class _UniformRng(Protocol):
    def uniform(self, a: float, b: float) -> float: ...


def laplace_noise(epsilon: float, sensitivity: float, rng: _UniformRng | None = None) -> float:
    """Sample Laplace noise calibrated to the given epsilon and sensitivity.

    Uses ``secrets.SystemRandom`` by default; inject *rng* for deterministic tests.
    """
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    if sensitivity < 0:
        raise ValueError("sensitivity must be non-negative")
    if sensitivity == 0:
        return 0.0

    scale = sensitivity / epsilon
    rand = rng if rng is not None else secrets.SystemRandom()
    u = rand.uniform(-0.5, 0.5)

    if u < 0:
        return scale * (1 + u * 2)
    return -scale * (1 - u * 2)


def laplace_ci_half_width(
    epsilon: float,
    sensitivity: float,
    n_users: int,
    confidence: float = 0.90,
    rounding: int = 5,
) -> tuple[float, int]:
    """Compute half-width of a confidence interval for a Laplace-noised mean.

    Returns (ci_half_width, n_display) where n_display is n_users rounded
    down to the nearest multiple of `rounding` (floored at `rounding`).
    """
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    alpha = (1 - confidence) / 2  # 0.05 for 90%
    scale = sensitivity / epsilon
    n_display = max(rounding, (n_users // rounding) * rounding)
    ci_half = scale * math.log(1 / alpha) / n_display
    return ci_half, n_display
