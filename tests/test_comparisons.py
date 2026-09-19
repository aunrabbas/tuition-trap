from copy import deepcopy
from decimal import Decimal
import json
from math import fsum

import pytest

from core.analysis import analyze
from core.capitalization import capitalize
from core.comparisons import compare_paths


def program(code="1107", earnings=60000, level=3, title="Source program title"):
    return {"code": code, "title": title, "credential_level": level,
            "credential_title": "Source credential title",
            "median_earnings_four_years_after_completion": earnings,
            "earnings_label": "Median earnings four years after completion"}


def institution(school_id=1, tuition=20000):
    return {"id": school_id, "school": {"name": f"School {school_id}"},
            "latest": {"cost": {"tuition": {"in_state": tuition}}}}


def inputs():
    return {"school": institution(), "major": program(),
            "majors": [program(), program("1419", 90000)], "amount_borrowed": 80000,
            "public_schools": [{"school": institution(2, 10000), "majors": [program(earnings=65000)]}],
            "community_college": {"school": institution(3, 5000), "majors": []}}


def scenarios(**changes):
    return compare_paths(**(inputs() | changes))


def test_public_uses_tuition_delta_and_exact_programs_without_mutating_inputs():
    data = inputs()
    before = deepcopy(data)
    result = compare_paths(**data)[0]
    assert data == before
    assert result["status"] == "ready"
    assert result["result"]["school"]["id"] == 2
    assert result["result"]["major"]["code"] == "1107"
    assert result["annual_borrowing"] == [10000] * 4
    assert result["annual_tuition"] == [10000] * 4
    assert result["borrowing_reduction"] == 40000
    expected = analyze(40000, 65000)
    for key in ("monthly_payment", "taxes", "burden", "schedule", "total_repaid", "allocation"):
        assert result["result"][key] == expected[key]


def test_public_selects_lowest_matching_tuition_and_excludes_original_school():
    data = inputs()
    data["public_schools"] += [
        {"school": institution(1, 100), "majors": [program()]},
        {"school": institution(4, 100), "majors": [program("9999"), program(level=2)]},
        {"school": institution(5, 1000), "majors": [program()]},
        {"school": institution(6, 1000), "majors": [program()]},
    ]
    assert compare_paths(**data)[0]["result"]["school"]["id"] == 5


def test_transfer_interest_uses_actual_annual_borrowing_not_equal_annual_debt():
    comparison = scenarios()[1]
    result = comparison["result"]
    assert comparison["annual_borrowing"] == [5000, 5000, 20000, 20000]
    assert result["allocation"]["amount_borrowed"] == 50000
    assert result["major"]["median_earnings_four_years_after_completion"] == 60000
    assert result["school"]["id"] == 1
    # Independent Decimal calculation: weighted duration = (5k*4 + 5k*3 + 20k*2 + 20k*1)/50k.
    duration = Decimal("1.9")
    federal_interest = Decimal("18600") * Decimal(".0652") * duration
    private_interest = Decimal("19000") * Decimal(".09") * duration
    assert result["capitalization"]["federal"]["accrued_interest"] == pytest.approx(float(federal_interest))
    assert result["capitalization"]["private"]["accrued_interest"] == pytest.approx(float(private_interest))
    assert result["repayment_principal"] == pytest.approx(float(Decimal("50000") + federal_interest + private_interest))
    assert result["repayment_principal"] < analyze(50000, 60000)["repayment_principal"]
    expected_payment = Decimal(0)
    for principal, interest, annual_rate in ((Decimal(31000), federal_interest, Decimal('.0652')),
                                              (Decimal(19000), private_interest, Decimal('.09'))):
        r = annual_rate / 12
        expected_payment += (principal + interest) * r / (1 - (1 + r) ** -120)
    assert result["monthly_payment"] == pytest.approx(float(expected_payment), abs=1e-8)
    assert result["schedule"][-1]["remaining_balance"] == 0
    assert fsum(row["principal_portion"] for row in result["schedule"]) == pytest.approx(result["repayment_principal"])
    assert result["annual_limit_warnings"]


def test_transfer_zero_borrowing_in_first_years_still_accrues_later_years_correctly():
    comparison = scenarios(amount_borrowed=20000)[1]
    assert comparison["annual_borrowing"] == [0, 0, 5000, 5000]
    result = comparison["result"]
    assert [row["principal"] for row in result["capitalization"]["federal"]["disbursements"]] == [0, 0, 5000, 5000]
    assert result["capitalization"]["federal"]["accrued_interest"] == pytest.approx(6000 * .0652 * 1.5)


def test_different_major_keeps_debt_uses_best_other_same_credential_with_stable_tie():
    majors = [program(), program("1419", 90000), program("1101", 90000), program("9999", 999999, 5)]
    result = scenarios(majors=majors)[2]["result"]
    assert result["major"]["code"] == "1101"
    baseline = analyze(80000, 60000)
    for key in ("allocation", "monthly_payment", "total_repaid", "schedule", "capitalization"):
        assert result[key] == baseline[key]
    assert result["taxes"]["monthly_take_home"] > baseline["taxes"]["monthly_take_home"]
    assert result["burden"]["payment_share_of_take_home"] < baseline["burden"]["payment_share_of_take_home"]


def test_higher_cost_public_is_not_mislabeled_as_savings():
    comparison = scenarios(public_schools=[{"school": institution(2, 25000), "majors": [program()]}])[0]
    assert comparison["borrowing_reduction"] == -20000
    assert comparison["result"]["allocation"]["amount_borrowed"] == 100000
    assert "not lower" in comparison["message"]


@pytest.mark.parametrize("amount", [0, .01, 500000])
def test_zero_small_and_large_debt_stay_finite_and_honor_private_cap(amount):
    results = scenarios(amount_borrowed=amount)
    json.dumps(results, allow_nan=False)
    for item in results:
        result = item["result"]
        assert result["allocation"]["amount_borrowed"] >= 0
        assert result["taxes"]["monthly_take_home"] >= 0
        if amount == 0:
            assert result["monthly_payment"] == 0
            assert result["schedule"] == []
        if amount == 500000:
            assert result["allocation"]["has_private_debt"]
            assert result["allocation"]["federal_principal"] == 31000


@pytest.mark.parametrize("tuition", [None, "PrivacySuppressed", -1, float('nan'), True])
def test_missing_or_invalid_original_tuition_only_disables_cost_scenarios(tuition):
    results = scenarios(school=institution(tuition=tuition))
    assert [item["status"] for item in results] == ["unavailable", "unavailable", "ready"]


def test_zero_tuition_is_valid_without_ratio_division():
    result = scenarios(school=institution(tuition=0))[0]
    assert result["status"] == "ready"
    assert result["result"]["allocation"]["amount_borrowed"] == 120000


def test_missing_program_and_credential_matches_produce_reasons_not_proxy_earnings():
    results = scenarios(public_schools=[{"school": institution(2), "majors": [program("9999"), program(level=2)]}],
                        majors=[program()], community_college=None)
    assert all(item["status"] == "unavailable" and item["result"] is None and item["message"] for item in results)


@pytest.mark.parametrize("years,level", [(2, 3), (4, 2), (5, 3)])
def test_transfer_does_not_silently_change_duration_or_credential(years, level):
    result = scenarios(major=program(level=level), overrides={"years_in_school": years})[1]
    assert result["status"] == "unavailable"
    assert "four total years" in result["message"]


def test_every_scenario_preserves_overrides_including_zero_rates_and_grace():
    overrides = {"dependent": False, "subsidized_fraction": 1, "federal_rate": 0,
                 "private_rate": 0, "term_months": 60, "years_in_school": 4,
                 "grace_months": 0, "local_tax_rate": .01}
    for comparison in scenarios(overrides=overrides):
        result = comparison["result"]
        assert result["assumptions"]["dependent_undergraduate"] is False
        assert result["assumptions"]["subsidized_fraction_of_federal_debt"] == 1
        for key in ("federal_rate", "private_rate", "term_months", "years_in_school", "grace_months"):
            assert result["assumptions"][key] == overrides[key]
        assert result["taxes"]["local_tax_rate"] == .01
        assert len(result["schedule"]) == 60
        assert result["monthly_payment"] == pytest.approx(result["allocation"]["amount_borrowed"] / 60)


def test_low_and_zero_earnings_alternative_is_dangerous_without_negative_take_home():
    for earnings in (0, .01):
        result = scenarios(majors=[program(), program("1419", earnings)])[2]["result"]
        assert result["burden"]["verdict"] == "dangerous"
        assert result["taxes"]["monthly_take_home"] >= 0
        json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("weights", [[1, 2], [-1, 1, 1, 1], [0, 0, 0, 0], [float('nan'), 1, 1, 1]])
def test_capitalization_rejects_invalid_annual_weights(weights):
    with pytest.raises(ValueError):
        capitalize(10000, disbursement_weights=weights)


def test_weighted_subsidized_loans_remain_interest_free():
    result = capitalize(10000, subsidized_principal=10000, disbursement_weights=[0, 0, 1, 1])
    assert result["repayment_principal"] == 10000
    assert result["accrued_interest"] == 0
