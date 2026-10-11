"""Wilson 95% intervals and sample size for a two-proportion test. Standard library only.

Sample size uses the normal approximation with the pooled rate under the null and
unpooled variances under the alternative, for any split between holdout and treatment.
With a 50/50 split, 15% to 12%, alpha 0.05 (two-sided) and power 0.8 it gives 2,036 per arm.
"""
from __future__ import annotations

import math
from statistics import NormalDist

Z95 = NormalDist().inv_cdf(0.975)


def wilson(successes: int, n: int, z: float = Z95):
    """Wilson score interval for a proportion. Returns (rate, low, high); all None when n == 0."""
    if n <= 0:
        return None, None, None
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    low = 0.0 if successes == 0 else max(0.0, center - half)
    high = 1.0 if successes == n else min(1.0, center + half)
    return p, low, high


def required_sample(baseline: float, target: float, holdout_share: float = 0.5,
                    alpha: float = 0.05, power: float = 0.8) -> dict:
    """Bookings needed in each arm to detect baseline (holdout) vs target (treatment).

    Returns a dict with holdout, treatment, total (all whole bookings, rounded up),
    plus the exact total before rounding and the rule-of-thumb factor versus 50/50.
    """
    if not (0 < baseline < 1 and 0 < target < 1):
        raise ValueError("Rates need to be between 0 and 1, for example 0.15")
    if baseline == target:
        raise ValueError("Baseline and target need to differ")
    if not 0 < holdout_share < 1:
        raise ValueError("Holdout share needs to be between 0 and 1, for example 0.5")
    h, t = holdout_share, 1 - holdout_share
    za = NormalDist().inv_cdf(1 - alpha / 2)
    zb = NormalDist().inv_cdf(power)
    pbar = h * baseline + t * target
    a = math.sqrt(pbar * (1 - pbar) * (1 / h + 1 / t))
    b = math.sqrt(baseline * (1 - baseline) / h + target * (1 - target) / t)
    n_total = ((za * a + zb * b) / abs(baseline - target)) ** 2
    n_hold = math.ceil(h * n_total - 1e-9)
    n_treat = math.ceil(t * n_total - 1e-9)
    return {
        "holdout": n_hold,
        "treatment": n_treat,
        "total": n_hold + n_treat,
        "exact_total": n_total,
        "rule_of_thumb_factor": 1 / (4 * h * t),
        "alpha": alpha,
        "power": power,
    }


def split_table(baseline: float, target: float, shares=(0.5, 0.3, 0.2), alpha=0.05, power=0.8):
    base = required_sample(baseline, target, 0.5, alpha, power)["total"]
    rows = []
    for s in shares:
        r = required_sample(baseline, target, s, alpha, power)
        r["holdout_share"] = s
        r["vs_5050"] = r["total"] / base
        rows.append(r)
    return rows
