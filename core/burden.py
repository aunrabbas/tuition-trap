"""Debt burden using median earnings four years after completion."""

from .constants import EARNINGS_LABEL
from .validation import nonnegative


def _ratio(numerator: float, denominator: float) -> float | None:
    # None is JSON-safe and means undefined, never zero burden for positive debt.
    return numerator / denominator if denominator else (0.0 if numerator == 0 else None)


def _verdict(ratio: float | None, lower: float, upper: float) -> str:
    if ratio is None or ratio > upper:
        return "dangerous"
    return "manageable" if ratio < lower else "tight"


def assess_burden(
    payment: float,
    total_debt: float,
    median_earnings_four_years_after_completion: float,
    monthly_take_home: float,
) -> dict:
    """Use the worse benchmark against median earnings four years after completion.

    Debt means the repayment-start balance, including capitalized interest.
    Verdict thresholds use gross income; the headline share uses take-home pay.
    Ratios with a zero denominator and positive numerator are None and dangerous.
    """
    payment = nonnegative(payment, "Monthly payment")
    debt = nonnegative(total_debt, "Total debt")
    gross = nonnegative(median_earnings_four_years_after_completion, EARNINGS_LABEL)
    net = nonnegative(monthly_take_home, "Monthly take-home pay")
    gross_share = _ratio(payment, gross / 12)
    net_share = _ratio(payment, net)
    debt_ratio = _ratio(debt, gross)
    payment_verdict = _verdict(gross_share, 0.08, 0.15)
    debt_verdict = _verdict(debt_ratio, 1.0, 1.5)
    ranks = {"manageable": 0, "tight": 1, "dangerous": 2}
    return {
        "earnings_label": EARNINGS_LABEL,
        "payment_share_of_gross_median_earnings_four_years_after_completion": gross_share,
        "payment_share_of_take_home": net_share,
        "debt_to_median_earnings_four_years_after_completion": debt_ratio,
        "payment_verdict": payment_verdict,
        "debt_verdict": debt_verdict,
        "verdict": max((payment_verdict, debt_verdict), key=ranks.get),
        "debt_basis": "Repayment-start balance including capitalized interest",
        "income_unavailable_for_ratios": gross == 0,
    }
