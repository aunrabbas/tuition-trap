from decimal import Decimal, localcontext
from math import fsum

import pytest

from core.amortization import amortization_schedule, monthly_payment


def test_acceptance_payment_matches_independent_loan_calculator():
    # Calculator.net live response retrieved 2026-09-19, monthly compounding:
    # https://www.calculator.net/loan-calculator.html?cloanamount=80000&cloanterm=10&cloantermmonth=0&cinterestrate=6.52&ccompound=monthly&cpayback=month&x=Calculate&type=1
    # Payment Every Month $909.20; Total of 120 Payments $109,103.77.
    assert round(monthly_payment(80000, 0.0652, 120), 2) == 909.20
    assert round(fsum(r["payment"] for r in amortization_schedule(80000)), 2) == 109103.77


def test_payment_matches_independent_decimal_present_value_solver():
    # Independent numerical root solve of discounted cash flows, not the formula.
    with localcontext() as context:
        context.prec = 50
        discount = 1 + Decimal("0.0652") / 12
        low, high = Decimal(0), Decimal(80000)
        for _ in range(180):
            candidate = (low + high) / 2
            value = sum(candidate / discount ** month for month in range(1, 121))
            if value < 80000:
                low = candidate
            else:
                high = candidate
        assert monthly_payment(80000) == pytest.approx(float((low + high) / 2), abs=1e-10)


@pytest.mark.parametrize("principal,rate,months", [(80000, .0652, 120), (500000, .09, 120), (100, 0, 3), (1, 1e-12, 360), (1, .0652, 120), (25000, .0652, 1)])
def test_acceptance_schedule_conserves_principal_and_ends_exactly_zero(principal, rate, months):
    rows = amortization_schedule(principal, rate, months)
    assert len(rows) == months
    assert fsum(r["principal_portion"] for r in rows) == pytest.approx(principal, abs=.000001)
    assert rows[-1]["remaining_balance"] == 0
    balance = principal
    interest_sum = 0
    for month, row in enumerate(rows, 1):
        assert row["month"] == month
        assert row["interest_portion"] == pytest.approx(balance * rate / 12)
        assert row["payment"] == pytest.approx(row["principal_portion"] + row["interest_portion"])
        assert row["remaining_balance"] == pytest.approx(balance - row["principal_portion"], abs=1e-10)
        assert row["remaining_balance"] >= 0
        assert row["principal_portion"] >= 0
        interest_sum += row["interest_portion"]
        assert row["cumulative_interest"] == pytest.approx(interest_sum)
        balance = row["remaining_balance"]
    assert fsum(r["payment"] for r in rows) == pytest.approx(principal + interest_sum)


def test_zero_rate_and_final_fractional_cent_adjustment():
    assert monthly_payment(100, 0, 3) == 100 / 3
    rows = amortization_schedule(100, 0, 3)
    assert rows[0]["payment"] != 33.33
    assert rows[-1]["payment"] == pytest.approx(100 - 2 * (100 / 3), abs=1e-12)
    assert rows[-1]["payment"] == rows[-2]["remaining_balance"]
    assert fsum(r["interest_portion"] for r in rows) == 0


def test_zero_principal():
    assert monthly_payment(0) == 0
    assert amortization_schedule(0) == []


@pytest.mark.parametrize("kwargs", [
    {"principal": -1}, {"principal": float("nan")}, {"principal": float("inf")},
    {"principal": True}, {"principal": "80000"},
    {"principal": 1, "annual_rate": -1}, {"principal": 1, "annual_rate": float("inf")},
    {"principal": 1, "term_months": 0}, {"principal": 1, "term_months": 1.5},
    {"principal": 1, "term_months": True},
])
def test_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        monthly_payment(**kwargs)
    with pytest.raises(ValueError):
        amortization_schedule(**kwargs)
