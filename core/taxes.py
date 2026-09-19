"""Estimate take-home pay from median earnings four years after completion."""

from .constants import EARNINGS_LABEL
from .validation import fraction, nonnegative

TAX_YEAR = 2026
# Tax year 2026, single filer: IRS Rev. Proc. 2025-32, §4.01 Table 3, §4.14.
# https://www.irs.gov/irb/2025-45_IRB
STANDARD_DEDUCTION = 16100.0
# Each tuple gives a taxable-income lower bound and its marginal rate.
FEDERAL_BRACKETS = (
    (0.0, 0.10), (12400.0, 0.12), (50400.0, 0.22),
    (105700.0, 0.24), (201775.0, 0.32), (256225.0, 0.35),
    (640600.0, 0.37),
)
# Employee rates and 2026 wage base: IRS Publication 15 (2026).
# https://www.irs.gov/publications/p15
SOCIAL_SECURITY_RATE = 0.062
SOCIAL_SECURITY_WAGE_BASE = 184500.0
MEDICARE_RATE = 0.0145
# https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/personal-income-tax
PENNSYLVANIA_INCOME_TAX_RATE = 0.0307
# Resident city + school district EIT (3% total), not a nonresident rate.
# https://www.pittsburghpa.gov/City-Government/Finance-Budget/Taxes
PITTSBURGH_RESIDENT_EIT_RATE = 0.03


def federal_income_tax(annual_gross: float) -> float:
    """Apply the 2026 single-filer standard deduction and marginal brackets."""
    taxable = max(0.0, nonnegative(annual_gross, "Annual gross income") - STANDARD_DEDUCTION)
    tax = 0.0
    for index, (lower, rate) in enumerate(FEDERAL_BRACKETS):
        upper = FEDERAL_BRACKETS[index + 1][0] if index + 1 < len(FEDERAL_BRACKETS) else taxable
        tax += max(0.0, min(taxable, upper) - lower) * rate
    return tax


def take_home_pay(
    median_earnings_four_years_after_completion: float,
    *,
    local_tax_rate: float = PITTSBURGH_RESIDENT_EIT_RATE,
) -> dict:
    """Estimate net pay using median earnings four years after completion.

    Model wages for a single filer with the standard deduction. Follow the
    specified base FICA model: no tax credits, benefits deductions, additional
    Medicare surtax, local services tax, or PA tax forgiveness are modeled.
    """
    gross = nonnegative(median_earnings_four_years_after_completion, EARNINGS_LABEL)
    local_rate = fraction(local_tax_rate, "Local earned income tax rate")
    federal = federal_income_tax(gross)
    social_security = min(gross, SOCIAL_SECURITY_WAGE_BASE) * SOCIAL_SECURITY_RATE
    medicare = gross * MEDICARE_RATE
    state = gross * PENNSYLVANIA_INCOME_TAX_RATE
    local = gross * local_rate
    net = max(0.0, gross - federal - social_security - medicare - state - local)
    return {
        "earnings_label": EARNINGS_LABEL,
        "median_earnings_four_years_after_completion": gross,
        "tax_year": TAX_YEAR,
        "filing_status": "single",
        "standard_deduction": STANDARD_DEDUCTION,
        "federal_income_tax": federal,
        "social_security_tax": social_security,
        "medicare_tax": medicare,
        "pennsylvania_income_tax": state,
        "local_earned_income_tax": local,
        "local_tax_rate": local_rate,
        "local_tax_assumption": "Pittsburgh resident" if local_rate == PITTSBURGH_RESIDENT_EIT_RATE else "User-specified local rate",
        "annual_take_home": net,
        "monthly_take_home": net / 12,
        "assumptions": (
            "Median earnings four years after completion treated as annual wage income.",
            "2026 single filer, standard deduction, no tax credits or benefit deductions.",
            "Base FICA only; additional Medicare surtax is excluded.",
            "Pennsylvania flat tax; tax forgiveness and local services tax are excluded.",
        ),
    }
