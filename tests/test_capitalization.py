import pytest

from core.capitalization import capitalize, split_borrowing


def test_acceptance_unsubsidized_yearly_simple_interest_and_subsidized_exemption():
    result = capitalize(20000, .0652)
    assert [r["years_accruing"] for r in result["disbursements"]] == [4, 3, 2, 1]
    assert [r["accrued_interest"] for r in result["disbursements"]] == pytest.approx([1304, 978, 652, 326])
    assert result["accrued_interest"] == pytest.approx(3260)
    assert result["repayment_principal"] == pytest.approx(23260)
    subsidized = capitalize(20000, .0652, subsidized_principal=20000)
    assert subsidized["repayment_principal"] == 20000
    assert subsidized["accrued_interest"] == 0


def test_mixed_default_and_grace_override():
    split = split_borrowing(20000)
    assert split["subsidized_principal"] == 8000
    result = capitalize(20000, subsidized_principal=8000)
    assert result["accrued_interest"] == pytest.approx(1956)
    no_grace = capitalize(20000, subsidized_principal=8000, grace_months=0)
    assert result["accrued_interest"] - no_grace["accrued_interest"] == pytest.approx(391.2)


def test_two_year_timing_and_zero_rate():
    result = capitalize(10000, .1, years_in_school=2)
    assert result["repayment_principal"] == 11500
    assert capitalize(10000, 0)["repayment_principal"] == 10000
    assert capitalize(0)["repayment_principal"] == 0


@pytest.mark.parametrize("dependent,limit", [(True, 31000), (False, 57500)])
def test_aggregate_and_subsidized_caps(dependent, limit):
    result = split_borrowing(80000, 1, dependent=dependent)
    assert result["federal_principal"] == limit
    assert result["private_principal"] == 80000 - limit
    assert result["subsidized_principal"] == 23000
    assert result["unsubsidized_principal"] == limit - 23000
    assert result["has_private_debt"] is True


@pytest.mark.parametrize("amount,private", [(0, 0), (31000, 0), (31000.01, .01), (500000, 469000)])
def test_private_split_boundary_and_no_rejection(amount, private):
    result = split_borrowing(amount)
    assert result["private_principal"] == pytest.approx(private)
    assert result["has_private_debt"] == (private > 0)


def test_origination_fee_reduces_cash_not_debt_and_excludes_private_principal():
    result = split_borrowing(80000)
    assert result["origination_fee_estimate"] == pytest.approx(327.67)
    assert result["net_disbursed_estimate"] == pytest.approx(79672.33)
    assert result["federal_principal"] + result["private_principal"] == 80000


@pytest.mark.parametrize("kwargs", [
    {"subsidized_principal": 10001}, {"subsidized_principal": -1},
    {"years_in_school": 0}, {"years_in_school": 2.5}, {"grace_months": -1},
])
def test_invalid_capitalization(kwargs):
    with pytest.raises(ValueError):
        capitalize(10000, **kwargs)


@pytest.mark.parametrize("share", [-.01, 1.01, float("nan"), True])
def test_invalid_subsidized_share(share):
    with pytest.raises(ValueError):
        split_borrowing(10000, share)
