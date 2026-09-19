"""Combine loan consequences using median earnings four years after completion."""

from math import fsum

from .amortization import amortization_schedule, monthly_payment
from .burden import assess_burden
from .capitalization import capitalize, split_borrowing
from .constants import (
    DEFAULT_GRACE_MONTHS, DEFAULT_PRIVATE_RATE, DEFAULT_SUBSIDIZED_FRACTION,
    DEFAULT_TERM_MONTHS, DEFAULT_YEARS_IN_SCHOOL, DEPENDENT_ANNUAL_LIMITS,
    EARNINGS_LABEL, INDEPENDENT_ANNUAL_LIMITS, SUBSIDIZED_ANNUAL_LIMITS,
    UNDERGRADUATE_RATE,
)
from .taxes import PITTSBURGH_RESIDENT_EIT_RATE, take_home_pay


def analyze(
    amount_borrowed: float,
    median_earnings_four_years_after_completion: float,
    *,
    subsidized_fraction: float = DEFAULT_SUBSIDIZED_FRACTION,
    dependent: bool = True,
    federal_rate: float = UNDERGRADUATE_RATE,
    private_rate: float = DEFAULT_PRIVATE_RATE,
    term_months: int = DEFAULT_TERM_MONTHS,
    years_in_school: int = DEFAULT_YEARS_IN_SCHOOL,
    grace_months: float = DEFAULT_GRACE_MONTHS,
    local_tax_rate: float = PITTSBURGH_RESIDENT_EIT_RATE,
) -> dict:
    """Return pure model results based on median earnings four years after completion.

    Rates are decimal fractions. Private debt is explicitly assumed to accrue
    simple interest through enrollment and grace, capitalized once. Federal and
    private balances are amortized separately at their respective fixed rates.
    """
    allocation = split_borrowing(amount_borrowed, subsidized_fraction, dependent=dependent)
    federal = capitalize(
        allocation["federal_principal"], federal_rate,
        subsidized_principal=allocation["subsidized_principal"],
        years_in_school=years_in_school, grace_months=grace_months,
    )
    private = capitalize(
        allocation["private_principal"], private_rate,
        years_in_school=years_in_school, grace_months=grace_months,
    )
    federal_payment = monthly_payment(federal["repayment_principal"], federal_rate, term_months)
    private_payment = monthly_payment(private["repayment_principal"], private_rate, term_months)
    taxes = take_home_pay(median_earnings_four_years_after_completion, local_tax_rate=local_tax_rate)
    payment = federal_payment + private_payment
    repayment_principal = federal["repayment_principal"] + private["repayment_principal"]
    federal_schedule = amortization_schedule(federal["repayment_principal"], federal_rate, term_months)
    private_schedule = amortization_schedule(private["repayment_principal"], private_rate, term_months)
    schedule = []
    for index in range(term_months if amount_borrowed else 0):
        components = [rows[index] for rows in (federal_schedule, private_schedule) if rows]
        schedule.append({
            "month": index + 1,
            **{key: fsum(row[key] for row in components) for key in (
                "payment", "interest_portion", "principal_portion",
                "remaining_balance", "cumulative_interest",
            )},
        })
    annual_limits = DEPENDENT_ANNUAL_LIMITS if dependent else INDEPENDENT_ANNUAL_LIMITS
    annual_limit_warnings = []
    for row in federal["disbursements"]:
        index = min(row["academic_year"] - 1, 2)
        if row["principal"] > annual_limits[index] or row["subsidized_principal"] > SUBSIDIZED_ANNUAL_LIMITS[index]:
            annual_limit_warnings.append({
                "academic_year": row["academic_year"],
                "modeled_federal_principal": row["principal"],
                "federal_annual_limit": annual_limits[index],
                "modeled_subsidized_principal": row["subsidized_principal"],
                "subsidized_annual_limit": SUBSIDIZED_ANNUAL_LIMITS[index],
            })
    total_repaid = fsum(row["payment"] for row in schedule)
    return {
        "state": "empty" if amount_borrowed == 0 else "ready",
        "message": "Enter a loan amount greater than zero to estimate your payment." if amount_borrowed == 0 else None,
        "hero_monthly_payment": payment if amount_borrowed else None,
        "earnings_label": EARNINGS_LABEL,
        "median_earnings_four_years_after_completion": taxes["median_earnings_four_years_after_completion"],
        "allocation": allocation,
        "capitalization": {"federal": federal, "private": private},
        "repayment_principal": repayment_principal,
        "monthly_payment": payment,
        "federal_monthly_payment": federal_payment,
        "private_monthly_payment": private_payment,
        "total_repaid": total_repaid,
        "repayment_interest": fsum(row["interest_portion"] for row in schedule),
        "total_interest_including_capitalization": total_repaid - amount_borrowed,
        "schedule": schedule,
        "taxes": taxes,
        "burden": assess_burden(payment, repayment_principal, median_earnings_four_years_after_completion, taxes["monthly_take_home"]),
        "annual_limit_warnings": annual_limit_warnings,
        "assumptions": {
            "dependent_undergraduate": dependent,
            "subsidized_fraction_of_federal_debt": subsidized_fraction,
            "federal_rate": federal_rate,
            "private_rate": private_rate,
            "term_months": term_months,
            "years_in_school": years_in_school,
            "grace_months": grace_months,
            "disbursement_timing": "Equal academic-year amounts at each year's midpoint.",
            "interest_rates": "One fixed rate per loan type applied to all modeled disbursements.",
            "private_accrual": "Simple interest during enrollment and grace, capitalized at repayment; no private fees modeled.",
            "federal_limits": "Aggregate-cap estimate per AGENTS.md; annual limit conflicts are reported separately.",
            "origination_fee": "Unrounded federal fee estimate; actual disbursement fees are truncated to cents.",
            "income_basis": EARNINGS_LABEL,
            "taxes": taxes["assumptions"],
        },
    }
