import json
from math import fsum

import pytest

from core import analyze
from core.amortization import monthly_payment
from core.constants import EARNINGS_LABEL


def test_acceptance_zero_loan_returns_empty_state_without_zero_hero():
    result = analyze(0, 0)
    assert result["state"] == "empty"
    assert result["hero_monthly_payment"] is None
    assert result["message"] == "Enter a loan amount greater than zero to estimate your payment."
    assert result["schedule"] == []
    assert result["total_repaid"] == 0
    json.dumps(result, allow_nan=False)


def test_acceptance_500000_loan_triggers_private_flag_and_valid_results():
    result = analyze(500000, 108680)
    assert result["state"] == "ready"
    assert result["allocation"]["has_private_debt"] is True
    assert result["allocation"]["federal_principal"] == 31000
    assert result["allocation"]["private_principal"] == 469000
    assert result["assumptions"]["private_rate"] == .09
    assert result["monthly_payment"] > 0
    assert result["burden"]["verdict"] == "dangerous"
    assert len(result["schedule"]) == 120
    assert result["schedule"][-1]["remaining_balance"] == 0
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("median_earnings_four_years_after_completion", [0, .01, 100, 1000])
def test_acceptance_low_median_earnings_four_years_after_completion(median_earnings_four_years_after_completion):
    result = analyze(31000, median_earnings_four_years_after_completion)
    assert result["burden"]["verdict"] == "dangerous"
    assert result["taxes"]["monthly_take_home"] >= 0
    assert result["earnings_label"] == EARNINGS_LABEL
    json.dumps(result, allow_nan=False)


def test_mixed_debt_is_amortized_at_separate_rates_and_totals_reconcile():
    result = analyze(80000, 108680)
    federal = result["capitalization"]["federal"]
    private = result["capitalization"]["private"]
    assert federal["repayment_principal"] == pytest.approx(34031.8)
    assert private["repayment_principal"] == pytest.approx(60025)
    assert result["monthly_payment"] == pytest.approx(
        monthly_payment(34031.8, .0652) + monthly_payment(60025, .09)
    )
    assert result["federal_monthly_payment"] + result["private_monthly_payment"] == result["monthly_payment"]
    assert fsum(r["principal_portion"] for r in result["schedule"]) == pytest.approx(result["repayment_principal"])
    assert result["total_repaid"] == pytest.approx(result["repayment_principal"] + result["repayment_interest"])
    assert result["total_interest_including_capitalization"] == pytest.approx(
        result["repayment_interest"] + federal["accrued_interest"] + private["accrued_interest"]
    )
    assert result["burden"]["debt_to_median_earnings_four_years_after_completion"] == pytest.approx(result["repayment_principal"] / 108680)


def test_overrides_propagate_and_annual_cap_conflicts_are_visible():
    result = analyze(80000, 60000, dependent=False, subsidized_fraction=1, private_rate=0, federal_rate=0, term_months=12, years_in_school=2, grace_months=0, local_tax_rate=0)
    assert result["allocation"]["subsidized_principal"] == 23000
    assert result["allocation"]["federal_principal"] == 57500
    assert result["repayment_principal"] == 80000
    assert result["monthly_payment"] == pytest.approx(80000 / 12)
    assert len(result["annual_limit_warnings"]) == 2
    assert result["taxes"]["local_earned_income_tax"] == 0
    assert analyze(10000, 60000)["annual_limit_warnings"] == []


def test_private_rate_override_affects_only_private_debt():
    baseline = analyze(80000, 60000)
    higher = analyze(80000, 60000, private_rate=.12)
    assert higher["private_monthly_payment"] > baseline["private_monthly_payment"]
    assert higher["federal_monthly_payment"] == baseline["federal_monthly_payment"]
