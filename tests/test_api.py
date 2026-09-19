import json
from math import fsum

from fastapi.testclient import TestClient
import pytest

from api.main import create_app
from core import analyze
from data import JSONCache
from data import scorecard
from data.scorecard import SCHOOL_FIELDS


def payload(**changes):
    return {"school_id": 215293, "major": {"code": "1107", "credential_level": 3}, "loan_amount": 80000, **changes}


@pytest.fixture(autouse=True)
def prohibit_scorecard_network_and_credentials(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("API requests must use seed cache without network or credentials")

    monkeypatch.setattr(scorecard, "urlopen", blocked)
    monkeypatch.setattr(scorecard, "read_api_key", blocked)


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


@pytest.mark.parametrize("school_id,credential,count", [
    (215293, 3, 58), (214777, 3, 104), (211440, 3, 22),
    (210605, 2, 17), (193900, 3, 44),
])
def test_both_endpoints_use_real_seed_cache_without_network(client, school_id, credential, count):
    response = client.get(f"/schools/{school_id}/majors", params={"credential_level": credential})
    assert response.status_code == 200
    data = response.json()
    assert data["school_id"] == school_id
    assert data["credential_level"] == credential
    assert len(data["majors"]) == count
    assert data["message"] is None
    assert data["earnings_label"] == "Median earnings four years after completion"
    assert all(p["credential_level"] == credential for p in data["majors"])
    assert all(p["median_earnings_four_years_after_completion"] is not None for p in data["majors"])
    major = data["majors"][0]
    result = client.post("/analyze", json=payload(school_id=school_id, major={"code": major["code"], "credential_level": credential}))
    assert result.status_code == 200
    assert result.json()["data_source"] == "seed cache"
    assert result.json()["major"] == major


def test_post_preserves_complete_core_result_and_schedule(client):
    response = client.post("/analyze", json=payload())
    assert response.status_code == 200
    result = response.json()
    assert result["school"]["name"] == "University of Pittsburgh-Pittsburgh Campus"
    assert result["school"]["cost"]["tuition"]["in_state"] > 0
    assert result["major"]["title"] == "Computer Science."
    assert result["median_earnings_four_years_after_completion"] == 108680
    expected = json.loads(json.dumps(analyze(80000, 108680)))
    for key, value in expected.items():
        assert result[key] == value, key
    assert len(result["schedule"]) == 120
    assert result["schedule"][-1]["remaining_balance"] == 0
    assert fsum(r["principal_portion"] for r in result["schedule"]) == pytest.approx(result["repayment_principal"])
    assert {c["kind"] for c in result["comparisons"]} == {
        "in_state_public", "community_college_transfer", "same_school_different_major",
    }
    assert all(c["status"] == "ready" and c["result"] is not None for c in result["comparisons"])
    json.dumps(result, allow_nan=False)


def test_all_overrides_reach_core(client):
    overrides = {"subsidized_fraction": .8, "dependent": False, "federal_rate": .04,
                 "private_rate": .11, "term_months": 60, "years_in_school": 2,
                 "grace_months": 0, "local_tax_rate": .01}
    response = client.post("/analyze", json=payload(overrides=overrides))
    assert response.status_code == 200
    result = response.json()
    expected = json.loads(json.dumps(analyze(80000, 108680, **overrides)))
    for key, value in expected.items():
        assert result[key] == value, key


def test_zero_borrowing_is_empty_without_zero_hero(client):
    response = client.post("/analyze", json=payload(loan_amount=0))
    assert response.status_code == 200
    result = response.json()
    assert result["state"] == "empty"
    assert result["hero_monthly_payment"] is None
    assert result["schedule"] == []
    assert "Enter a loan amount" in result["message"]


def test_500000_borrowing_is_accepted_and_flagged(client):
    response = client.post("/analyze", json=payload(loan_amount=500000))
    assert response.status_code == 200
    result = response.json()
    assert result["allocation"]["has_private_debt"] is True
    assert result["allocation"]["private_principal"] == 469000
    assert result["burden"]["verdict"] == "dangerous"


@pytest.mark.parametrize("changes", [
    {"loan_amount": -1}, {"loan_amount": True}, {"loan_amount": "80000"},
    {"loan_amount": None}, {"loan_amount": 1e13}, {"school_id": True},
    {"school_id": 0}, {"school_id": "215293"},
    {"major": {"code": "11.07"}}, {"major": {"code": 1107}},
    {"major": {"code": "1107", "credential_level": True}},
    {"major": {"code": "1107", "credential_level": 5}},
    {"major": {"code": "1107", "title": "untrusted"}},
    {"median_earnings_four_years_after_completion": 999999},
    {"overrides": {"private_rate": -.01}}, {"overrides": {"private_rate": 9}},
    {"overrides": {"subsidized_fraction": 1.01}},
    {"overrides": {"dependent": "false"}},
    {"overrides": {"term_months": 0}}, {"overrides": {"term_months": 1.5}},
    {"overrides": {"term_months": 601}}, {"overrides": {"years_in_school": 0}},
    {"overrides": {"years_in_school": 21}}, {"overrides": {"grace_months": -1}},
    {"overrides": {"local_tax_rate": 2}}, {"overrides": {"unknown": 1}},
])
def test_post_validates_inputs(client, changes):
    response = client.post("/analyze", json=payload(**changes))
    assert response.status_code == 422
    assert response.json()["detail"]


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nonfinite_input_returns_valid_json_error(client, number):
    body = '{"school_id":215293,"major":{"code":"1107"},"loan_amount":' + number + '}'
    response = client.post("/analyze", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"]
    assert "input" not in response.json()["detail"][0]


@pytest.mark.parametrize("body", ["{", "null", "{}", "[]"])
def test_malformed_or_missing_request_fields(client, body):
    response = client.post("/analyze", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422


@pytest.mark.parametrize("url", [
    "/schools/0/majors", "/schools/nope/majors",
    "/schools/215293/majors?credential_level=0",
    "/schools/215293/majors?credential_level=5",
    "/schools/215293/majors?credential_level=true",
])
def test_get_validates_school_and_undergraduate_credential(client, url):
    assert client.get(url).status_code == 422


def test_unknown_school_does_not_fetch(client):
    for response in (client.get("/schools/999999/majors"), client.post("/analyze", json=payload(school_id=999999))):
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "school_not_cached"


def test_unknown_program_returns_actionable_error(client):
    response = client.post("/analyze", json=payload(major={"code": "9999"}))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "major_unavailable"
    assert "median earnings four years after completion" in response.json()["detail"]["message"]


def seed_school(directory, value):
    params = {"id": 1, "fields": SCHOOL_FIELDS, "keys_nested": "true", "all_programs_nested": "true", "per_page": 100}
    response = {"metadata": {"total": 1}, "results": [{"id": 1, "school": {"name": "Test School"},
        "latest": {"programs": {"cip_4_digit": [{"code": "1107", "title": "Exact source title.",
            "credential": {"level": 3, "title": "Bachelor's Degree"},
            "earnings": {"4_yr": {"overall_median_earnings": value}}}]}}}]}
    cache = JSONCache(directory)
    cache.write(params, response)
    return cache.path_for(params)


@pytest.mark.parametrize("value", [None, "PrivacySuppressed"])
def test_suppressed_program_not_selectable_and_no_coverage_message(tmp_path, value):
    seed_school(tmp_path, value)
    with TestClient(create_app(seed_dir=tmp_path)) as client:
        response = client.get("/schools/1/majors")
        assert response.status_code == 200
        assert response.json()["majors"] == []
        assert "No programs with median earnings four years after completion" in response.json()["message"]
        assert client.post("/analyze", json=payload(school_id=1)).status_code == 422


@pytest.mark.parametrize("value", [0, .01, 100])
def test_low_median_earnings_four_years_after_completion_is_dangerous(tmp_path, value):
    seed_school(tmp_path, value)
    with TestClient(create_app(seed_dir=tmp_path)) as client:
        response = client.post("/analyze", json=payload(school_id=1))
        assert response.status_code == 200
        result = response.json()
        assert result["burden"]["verdict"] == "dangerous"
        assert result["taxes"]["monthly_take_home"] >= 0
        json.dumps(result, allow_nan=False)


def test_corrupt_cache_returns_service_error_without_live_fallback(tmp_path):
    seed_school(tmp_path, 100).write_text("broken JSON")
    with TestClient(create_app(seed_dir=tmp_path)) as client:
        for response in (client.get("/schools/1/majors"), client.post("/analyze", json=payload(school_id=1))):
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "school_data_unavailable"


def test_openapi_documents_full_response_and_only_two_business_routes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert set(schema["paths"]) == {"/analyze", "/schools/{school_id}/majors"}
    fields = schema["components"]["schemas"]["AnalysisResponse"]["properties"]
    assert {"schedule", "comparisons", "assumptions", "median_earnings_four_years_after_completion"} <= fields.keys()


def test_real_comparisons_use_cached_costs_and_exact_earnings(client):
    result = client.post("/analyze", json=payload()).json()
    public, transfer, different = result["comparisons"]
    assert public["result"]["school"]["id"] == 214777
    assert public["result"]["allocation"]["amount_borrowed"] == 74872
    assert public["original_annual_tuition"] == 21926
    assert public["annual_tuition"] == [20644] * 4
    assert transfer["annual_borrowing"] == [2916, 2916, 20000, 20000]
    assert transfer["result"]["allocation"]["amount_borrowed"] == 45832
    assert transfer["annual_tuition"] == [4842, 4842, 21926, 21926]
    assert transfer["result"]["major"] == result["major"]
    assert different["result"]["major"]["code"] != result["major"]["code"]
    assert different["result"]["monthly_payment"] == result["monthly_payment"]
    for item in result["comparisons"]:
        scenario = item["result"]
        choices = client.get(f"/schools/{scenario['school']['id']}/majors").json()["majors"]
        assert scenario["major"] in choices
        assert scenario["data_source"] == "seed cache"
        assert len(scenario["schedule"]) == 120
        assert scenario["schedule"][-1]["remaining_balance"] == 0
        assert scenario["total_repaid"] == pytest.approx(fsum(row["payment"] for row in scenario["schedule"]))
        assert item["assumptions"]


@pytest.mark.parametrize("school_id", [211440, 193900])
def test_private_school_comparisons_have_three_real_results(client, school_id):
    public_codes = {p["code"] for p in client.get('/schools/215293/majors').json()["majors"]}
    program = next(p for p in client.get(f'/schools/{school_id}/majors').json()["majors"] if p["code"] in public_codes)
    result = client.post('/analyze', json=payload(school_id=school_id, major={"code": program["code"]})).json()
    assert all(item["status"] == "ready" for item in result["comparisons"])
    public, transfer, different = result["comparisons"]
    assert public["result"]["allocation"]["amount_borrowed"] < 80000
    assert transfer["result"]["allocation"]["amount_borrowed"] < 80000
    assert different["result"]["allocation"]["amount_borrowed"] == 80000


def test_optional_candidate_cache_error_does_not_lose_main_result(client, monkeypatch):
    from data import CacheError

    original = scorecard.ScorecardClient.get_school

    def read(self, school_id):
        if school_id == 214777:
            raise CacheError("Test missing/corrupt candidate cache")
        return original(self, school_id)

    monkeypatch.setattr(scorecard.ScorecardClient, "get_school", read)
    response = client.post('/analyze', json=payload())
    assert response.status_code == 200
    public, transfer, different = response.json()["comparisons"]
    assert public["status"] == "unavailable" and public["result"] is None
    assert transfer["status"] == different["status"] == "ready"


def test_sparse_cache_returns_explicit_unavailable_comparisons(tmp_path):
    seed_school(tmp_path, 60000)
    with TestClient(create_app(seed_dir=tmp_path)) as client:
        response = client.post('/analyze', json=payload(school_id=1))
        assert response.status_code == 200
        assert all(item["status"] == "unavailable" and item["message"] for item in response.json()["comparisons"])


def test_api_comparisons_preserve_rate_tax_and_term_overrides(client):
    options = {"private_rate": .03, "federal_rate": .01, "term_months": 72,
               "local_tax_rate": .02, "subsidized_fraction": .25, "grace_months": 3,
               "dependent": False}
    response = client.post('/analyze', json=payload(overrides=options))
    assert response.status_code == 200
    for item in response.json()["comparisons"]:
        result = item["result"]
        assert result["assumptions"]["private_rate"] == .03
        assert result["assumptions"]["federal_rate"] == .01
        assert result["assumptions"]["subsidized_fraction_of_federal_debt"] == .25
        assert result["assumptions"]["dependent_undergraduate"] is False
        assert result["assumptions"]["grace_months"] == 3
        assert result["taxes"]["local_tax_rate"] == .02
        assert len(result["schedule"]) == 72
