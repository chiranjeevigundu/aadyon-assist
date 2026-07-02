"""Shared numeric helpers and constants for the metrics services.

Kept tiny and dependency-free so any service (dimensions, digital_me, future
ones) can reuse the same rounding/clamping/banding rules.
"""

DAYS_PER_YEAR = 365.2425
WEEKS_PER_MONTH = 52 / 12  # 4.333…


def f(x) -> float:
    """Coerce a possibly-None / Decimal value to float (None -> 0.0)."""
    return float(x) if x is not None else 0.0


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def rnd(x: float, n: int = 1) -> float:
    return round(x, n)


def band(score: float) -> str:
    """Coarse label for a 0-100 score."""
    if score >= 75:
        return "strong"
    if score >= 50:
        return "fair"
    if score >= 25:
        return "at risk"
    return "critical"
