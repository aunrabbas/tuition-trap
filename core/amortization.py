"""Fixed-rate amortization with no currency rounding before display."""

from math import expm1, log1p

from .constants import DEFAULT_TERM_MONTHS, UNDERGRADUATE_RATE
from .validation import nonnegative, positive_integer


def monthly_payment(
    principal: float,
    annual_rate: float = UNDERGRADUATE_RATE,
    term_months: int = DEFAULT_TERM_MONTHS,
) -> float:
    """Return P*r*(1+r)**n / ((1+r)**n - 1), or P/n at zero rate."""
    principal = nonnegative(principal, "Principal")
    annual_rate = nonnegative(annual_rate, "Annual interest rate")
    term_months = positive_integer(term_months, "Term in months")
    r = annual_rate / 12
    if r == 0:
        return principal / term_months
    # Algebraically equivalent closed form, stable for rates near zero.
    return principal * r / -expm1(-term_months * log1p(r))


def amortization_schedule(
    principal: float,
    annual_rate: float = UNDERGRADUATE_RATE,
    term_months: int = DEFAULT_TERM_MONTHS,
) -> list[dict]:
    """Return monthly rows; adjust the final payment to retire all principal."""
    payment = monthly_payment(principal, annual_rate, term_months)
    if principal == 0:
        return []
    balance = float(principal)
    cumulative_interest = 0.0
    rows = []
    for month in range(1, term_months + 1):
        interest = balance * (annual_rate / 12)
        principal_portion = payment - interest
        actual_payment = payment
        if month == term_months:
            principal_portion = balance
            actual_payment = balance + interest
            balance = 0.0
        else:
            balance -= principal_portion
        cumulative_interest += interest
        rows.append({
            "month": month,
            "payment": actual_payment,
            "interest_portion": interest,
            "principal_portion": principal_portion,
            "remaining_balance": balance,
            "cumulative_interest": cumulative_interest,
        })
    return rows
