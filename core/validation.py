"""Shared numeric validation without coercing strings or booleans."""

from math import isfinite


def nonnegative(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite nonnegative number.")
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number.")
    return float(value)


def fraction(value: float, name: str) -> float:
    value = nonnegative(value, name)
    if value > 1:
        raise ValueError(f"{name} must be between 0 and 1.")
    return value


def positive_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value
