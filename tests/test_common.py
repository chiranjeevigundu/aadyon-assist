"""Unit tests for the shared numeric helpers (pure, no DB)."""
from app.services.common import band, clamp, f, rnd


def test_f_coerces_none_and_strings():
    assert f(None) == 0.0
    assert f("3") == 3.0
    assert f(2) == 2.0


def test_clamp_bounds():
    assert clamp(150) == 100.0
    assert clamp(-5) == 0.0
    assert clamp(50) == 50.0
    assert clamp(5, lo=10, hi=20) == 10.0


def test_rnd():
    assert rnd(1.2345, 2) == 1.23
    assert rnd(2.0) == 2.0


def test_band_labels():
    assert band(80) == "strong"
    assert band(60) == "fair"
    assert band(30) == "at risk"
    assert band(10) == "critical"
