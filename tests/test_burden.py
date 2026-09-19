import pytest

from core.burden import assess_burden


@pytest.mark.parametrize("payment,verdict", [
    (399.99, "manageable"), (400, "tight"), (750, "tight"), (750.01, "dangerous"),
])
def test_gross_payment_thresholds_are_inclusive(payment, verdict):
    result = assess_burden(payment, 1, 60000, 3500)
    assert result["payment_verdict"] == verdict
    assert result["verdict"] == verdict


@pytest.mark.parametrize("debt,verdict", [
    (59999.99, "manageable"), (60000, "tight"), (90000, "tight"), (90000.01, "dangerous"),
])
def test_debt_thresholds_are_inclusive(debt, verdict):
    result = assess_burden(1, debt, 60000, 3500)
    assert result["debt_verdict"] == verdict
    assert result["verdict"] == verdict


def test_worse_verdict_and_take_home_share_does_not_set_verdict():
    result = assess_burden(350, 10000, 60000, 2000)
    assert result["payment_share_of_gross_median_earnings_four_years_after_completion"] == .07
    assert result["payment_share_of_take_home"] == .175
    assert result["verdict"] == "manageable"
    assert assess_burden(350, 95000, 60000, 2000)["verdict"] == "dangerous"
    assert assess_burden(900, 10000, 60000, 2000)["verdict"] == "dangerous"


def test_zero_income_has_undefined_ratios_and_dangerous_verdict():
    result = assess_burden(100, 10000, 0, 0)
    assert result["verdict"] == "dangerous"
    assert result["payment_share_of_take_home"] is None
    assert result["debt_to_median_earnings_four_years_after_completion"] is None
    assert result["income_unavailable_for_ratios"] is True
    assert assess_burden(0, 0, 0, 0)["verdict"] == "manageable"


def test_negative_input_is_not_a_negative_burden():
    with pytest.raises(ValueError):
        assess_burden(-1, 100, 100, 10)
