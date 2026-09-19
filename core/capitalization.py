"""Academic-year simple-interest accrual and federal/private borrowing allocation."""

from math import fsum

from .constants import (
    DEFAULT_GRACE_MONTHS, DEFAULT_SUBSIDIZED_FRACTION, DEFAULT_YEARS_IN_SCHOOL,
    DEPENDENT_AGGREGATE_LIMIT, INDEPENDENT_AGGREGATE_LIMIT,
    ORIGINATION_FEE_RATE, SUBSIDIZED_AGGREGATE_LIMIT, UNDERGRADUATE_RATE,
)
from .validation import fraction, nonnegative, positive_integer


def split_borrowing(
    amount_borrowed: float,
    subsidized_fraction: float = DEFAULT_SUBSIDIZED_FRACTION,
    *,
    dependent: bool = True,
) -> dict:
    """Apply aggregate caps; the requested subsidy fraction applies to federal debt.

    Annual eligibility is reported separately by analyze; this allocation follows
    the aggregate-limit model in AGENTS.md. The fee is an unrounded estimate.
    """
    amount = nonnegative(amount_borrowed, "Amount borrowed")
    share = fraction(subsidized_fraction, "Subsidized fraction")
    if not isinstance(dependent, bool):
        raise ValueError("Dependent status must be a boolean.")
    limit = DEPENDENT_AGGREGATE_LIMIT if dependent else INDEPENDENT_AGGREGATE_LIMIT
    federal = min(amount, limit)
    subsidized = min(federal * share, SUBSIDIZED_AGGREGATE_LIMIT)
    private = amount - federal
    fee = federal * ORIGINATION_FEE_RATE
    return {
        "amount_borrowed": amount,
        "federal_principal": federal,
        "subsidized_principal": subsidized,
        "unsubsidized_principal": federal - subsidized,
        "private_principal": private,
        "has_private_debt": private > 0,
        "aggregate_federal_limit": limit,
        "requested_subsidized_fraction": share,
        "effective_subsidized_fraction": subsidized / federal if federal else 0.0,
        "origination_fee_estimate": fee,
        "net_disbursed_estimate": amount - fee,
    }


def capitalize(
    principal: float,
    annual_rate: float = UNDERGRADUATE_RATE,
    *,
    subsidized_principal: float = 0.0,
    years_in_school: int = DEFAULT_YEARS_IN_SCHOOL,
    grace_months: float = DEFAULT_GRACE_MONTHS,
) -> dict:
    """Accrue simple interest per academic year, then capitalize once.

    Equal annual disbursements occur at each academic year's midpoint. For four
    years and six months of grace, durations are 4, 3, 2, and 1 years. Subsidized
    principal accrues no interest during enrollment or grace, per AGENTS.md.
    """
    principal = nonnegative(principal, "Principal")
    annual_rate = nonnegative(annual_rate, "Annual interest rate")
    subsidized = nonnegative(subsidized_principal, "Subsidized principal")
    years = positive_integer(years_in_school, "Years in school")
    grace = nonnegative(grace_months, "Grace in months") / 12
    if subsidized > principal:
        raise ValueError("Subsidized principal cannot exceed principal.")
    unsubsidized = principal - subsidized
    rows = []
    for year in range(1, years + 1):
        years_accruing = years - year + 0.5 + grace
        rows.append({
            "academic_year": year,
            "principal": principal / years,
            "subsidized_principal": subsidized / years,
            "unsubsidized_principal": unsubsidized / years,
            "years_accruing": years_accruing,
            "accrued_interest": (unsubsidized / years) * annual_rate * years_accruing,
        })
    accrued = fsum(row["accrued_interest"] for row in rows)
    return {
        "amount_borrowed": principal,
        "accrued_interest": accrued,
        "repayment_principal": principal + accrued,
        "disbursements": rows,
    }
