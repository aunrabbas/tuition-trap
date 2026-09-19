import pytest

from core.constants import EARNINGS_LABEL
from core.taxes import federal_income_tax, take_home_pay


# IRS Rev. Proc. 2025-32 Table 3 cumulative tax at each bracket boundary.
# https://www.irs.gov/irb/2025-45_IRB
@pytest.mark.parametrize("taxable,tax,next_rate", [
    (0, 0, .10), (12400, 1240, .12), (50400, 5800, .22),
    (105700, 17966, .24), (201775, 41024, .32),
    (256225, 58448, .35), (640600, 192979.25, .37),
])
def test_2026_single_bracket_boundaries(taxable, tax, next_rate):
    assert federal_income_tax(taxable + 16100) == pytest.approx(tax)
    assert federal_income_tax(taxable + 16101) == pytest.approx(tax + next_rate)


@pytest.mark.parametrize("gross", [0, 1, 16099, 16100])
def test_income_at_or_below_standard_deduction(gross):
    assert federal_income_tax(gross) == 0


def test_complete_tax_breakdown_at_60000():
    result = take_home_pay(60000)
    assert result["earnings_label"] == EARNINGS_LABEL
    assert result["median_earnings_four_years_after_completion"] == 60000
    assert result["federal_income_tax"] == 5020
    assert result["social_security_tax"] == 3720
    assert result["medicare_tax"] == pytest.approx(870)
    assert result["pennsylvania_income_tax"] == 1842
    assert result["local_earned_income_tax"] == 1800
    assert result["annual_take_home"] == 46748
    assert result["monthly_take_home"] == pytest.approx(3895.6666666666665)
    assert result["tax_year"] == 2026
    assert result["filing_status"] == "single"
    assert result["local_tax_assumption"] == "Pittsburgh resident"


@pytest.mark.parametrize("gross,ss,medicare", [
    (184499, 11438.938, 2675.2355),
    (184500, 11439, 2675.25),
    (300000, 11439, 4350),
])
def test_social_security_cap_and_uncapped_base_medicare(gross, ss, medicare):
    result = take_home_pay(gross)
    assert result["social_security_tax"] == pytest.approx(ss)
    assert result["medicare_tax"] == pytest.approx(medicare)


def test_local_override_and_nonnegative_take_home():
    baseline = take_home_pay(60000)
    no_local = take_home_pay(60000, local_tax_rate=0)
    assert no_local["monthly_take_home"] - baseline["monthly_take_home"] == pytest.approx(150)
    assert no_local["local_tax_assumption"] == "User-specified local rate"
    assert take_home_pay(0)["monthly_take_home"] == 0
    assert take_home_pay(1)["monthly_take_home"] > 0
    assert take_home_pay(60000, local_tax_rate=1)["monthly_take_home"] == 0


@pytest.mark.parametrize("gross", [-1, float("nan"), float("inf"), True])
def test_invalid_income(gross):
    with pytest.raises(ValueError, match="Median earnings four years after completion"):
        take_home_pay(gross)


@pytest.mark.parametrize("rate", [-1, 1.1, float("nan")])
def test_invalid_local_rate(rate):
    with pytest.raises(ValueError):
        take_home_pay(60000, local_tax_rate=rate)
