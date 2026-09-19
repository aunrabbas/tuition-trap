import io
import json
from pathlib import Path
import traceback
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from data import CacheError, CacheMissError, JSONCache, ScorecardClient, ScorecardError
from data import scorecard
from data.scorecard import SCHOOL_FIELDS

ROOT = Path(__file__).resolve().parents[1]
DEMO_NAMES = (
    "University of Pittsburgh-Pittsburgh Campus",
    "Pennsylvania State University-Main Campus",
    "Carnegie Mellon University",
    "Community College of Allegheny County",
    "New York University",
)


def no_network_or_key(*args, **kwargs):
    raise AssertionError("Cache hits must not invoke HTTP or read an API key")


@pytest.mark.parametrize("name", DEMO_NAMES)
@pytest.mark.parametrize("allow_network", [False, True])
def test_committed_seed_cache_without_network(name, allow_network, monkeypatch):
    # The autouse fixture also blocks socket connections and DNS for the full suite.
    monkeypatch.setattr(scorecard, "urlopen", no_network_or_key)
    monkeypatch.setattr(scorecard, "read_api_key", no_network_or_key)
    manifest = json.loads((ROOT / "seed/manifest.json").read_text())["schools"]
    assert len(manifest) == 5
    entry = next(s for s in manifest if s["name"] == name)
    client = ScorecardClient(allow_network=allow_network, env_file=ROOT / "does-not-exist.env")
    assert entry["id"] in [s["id"] for s in client.search_schools(entry["search_name"])]
    school = client.get_school(entry["id"])
    assert school["school"]["name"] == name
    assert school["latest"]["cost"]["tuition"]["in_state"] > 0
    assert school["latest"]["cost"]["attendance"]["academic_year"] > 0
    all_programs = client.list_majors(entry["id"])
    assert len(all_programs["majors"]) == entry["programs_with_median_earnings_four_years_after_completion"]
    choices = client.list_majors(entry["id"], credential_level=entry["demo_credential_level"])
    assert len(choices["majors"]) == entry["demo_programs_with_median_earnings_four_years_after_completion"]
    assert choices["majors"]
    assert choices["message"] is None
    for choice in choices["majors"]:
        assert choice["credential_level"] == entry["demo_credential_level"]
        assert choice["median_earnings_four_years_after_completion"] >= 0
        assert choice["earnings_label"] == "Median earnings four years after completion"
    print(f"\nOffline cache verified: {name}; {len(choices['majors'])} selectable programs with median earnings four years after completion (credential {entry['demo_credential_level']}).")


def program(value, code="1107", level=3):
    return {"code": code, "title": "Scorecard's exact program title.",
            "credential": {"level": level, "title": "Credential title from Scorecard"},
            "earnings": {"4_yr": {"overall_median_earnings": value}}}


def response(programs=None):
    return {"metadata": {"total": 1}, "results": [{
        "id": 1, "school": {"name": "Test School"},
        "latest": {"programs": {"cip_4_digit": programs or []}},
    }]}


def seeded_client(tmp_path, programs):
    client = ScorecardClient(seed_dir=tmp_path)
    params = {"id": 1, "fields": SCHOOL_FIELDS, "keys_nested": "true", "all_programs_nested": "true", "per_page": 100}
    client.cache.write(params, response(programs))
    return client


def test_suppression_zero_values_and_credential_identity(tmp_path):
    rows = [program(50000), program(60000, level=5), program(50000),
            program(None, "1101"), program("PrivacySuppressed", "1102"),
            program(True, "1103"), program(0, "1104"), program(-1, "1105")]
    client = seeded_client(tmp_path, rows)
    choices = client.list_majors(1)["majors"]
    assert len(choices) == 3
    assert {(p["code"], p["credential_level"]) for p in choices} == {("1107", 3), ("1107", 5), ("1104", 3)}
    assert all(p["title"] == "Scorecard's exact program title." for p in choices)
    assert len(client.list_majors(1, credential_level=3)["majors"]) == 2


@pytest.mark.parametrize("rows", [[], [program(None)], [program("PrivacySuppressed")], [{"earnings": None}], [{"earnings": {"4_yr": None}}]])
def test_no_coverage_has_clear_message(tmp_path, rows):
    result = seeded_client(tmp_path, rows).list_majors(1)
    assert result["majors"] == []
    assert "No programs with median earnings four years after completion" in result["message"]
    assert "Choose another school or credential level" in result["message"]


def test_conflicting_program_records_are_not_silently_overwritten(tmp_path):
    client = seeded_client(tmp_path, [program(100), program(200)])
    with pytest.raises(ScorecardError, match="conflicting"):
        client.list_majors(1)


def test_malformed_program_value_has_actionable_schema_error(tmp_path):
    client = seeded_client(tmp_path, [{"earnings": {"4_yr": [123]}}])
    with pytest.raises(ScorecardError, match="Median earnings four years after completion has an unexpected schema"):
        client.list_majors(1)


def test_offline_cache_miss_never_fetches_or_reads_key(tmp_path, monkeypatch):
    monkeypatch.setattr(scorecard, "urlopen", no_network_or_key)
    monkeypatch.setattr(scorecard, "read_api_key", no_network_or_key)
    with pytest.raises(CacheMissError, match="--fetch before the demo"):
        ScorecardClient(seed_dir=tmp_path).get_school(1)


def test_first_fetch_caches_response_and_second_call_is_offline(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('export SCORECARD_API_KEY="unit-test-key" # comment\n')
    requests = []

    def fake_open(request, timeout):
        requests.append(request)
        assert timeout == 30
        assert request.get_header("X-api-key") == "unit-test-key"
        params = parse_qs(urlsplit(request.full_url).query)
        assert params["keys_nested"] == ["true"]
        assert params["all_programs_nested"] == ["true"]
        assert "unit-test-key" not in request.full_url
        return io.StringIO(json.dumps(response([program(50000)])))

    monkeypatch.setattr(scorecard, "urlopen", fake_open)
    client = ScorecardClient(seed_dir=tmp_path / "seed", env_file=env_file, allow_network=True)
    first = client.get_school(1)
    assert len(requests) == 1
    saved = next((tmp_path / "seed").glob("*.json")).read_text()
    assert "unit-test-key" not in saved
    assert "api_key" not in saved
    assert "retrieved_at_utc" in saved
    assert not list((tmp_path / "seed").glob("*.tmp"))
    monkeypatch.setattr(scorecard, "urlopen", no_network_or_key)
    monkeypatch.setattr(scorecard, "read_api_key", no_network_or_key)
    assert client.get_school(1) == first
    assert ScorecardClient(seed_dir=tmp_path / "seed").get_school(1) == first


def test_paginated_search_caches_each_page(tmp_path, monkeypatch):
    monkeypatch.setattr(scorecard, "read_api_key", lambda _: "test-only")
    calls = []

    def fake_open(request, timeout):
        page = int(parse_qs(urlsplit(request.full_url).query)["page"][0])
        calls.append(page)
        return io.StringIO(json.dumps({"metadata": {"total": 2}, "results": [{"id": page + 1, "school": {"name": f"School {page}"}}]}))

    monkeypatch.setattr(scorecard, "urlopen", fake_open)
    client = ScorecardClient(seed_dir=tmp_path, allow_network=True)
    schools = client.search_schools("School")
    assert calls == [0, 1]
    assert len(list(tmp_path.glob("*.json"))) == 2
    monkeypatch.setattr(scorecard, "urlopen", no_network_or_key)
    assert ScorecardClient(seed_dir=tmp_path).search_schools("School") == schools


@pytest.mark.parametrize("error", [
    HTTPError("https://example.test/?secret", 401, "unit-test-secret", {}, None),
    HTTPError("https://example.test/?secret", 429, "unit-test-secret", {}, None),
    HTTPError("https://example.test/?secret", 500, "unit-test-secret", {}, None),
    URLError("https://example.test/?unit-test-secret"),
])
def test_errors_never_expose_secrets_or_request_urls(tmp_path, monkeypatch, error):
    monkeypatch.setattr(scorecard, "read_api_key", lambda _: "unit-test-secret")

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(scorecard, "urlopen", fail)
    with pytest.raises(ScorecardError) as caught:
        ScorecardClient(seed_dir=tmp_path, allow_network=True).get_school(1)
    rendered = "".join(traceback.format_exception(caught.value))
    assert "unit-test-secret" not in rendered
    assert "https://example.test" not in rendered
    assert not list(tmp_path.glob("*.json"))


def test_cache_fingerprint_ignores_parameter_order_and_rejects_credentials(tmp_path):
    cache = JSONCache(tmp_path)
    assert cache.path_for({"id": 1, "fields": "id"}) == cache.path_for({"fields": "id", "id": 1})
    assert cache.path_for({"id": 1}) != cache.path_for({"id": 2})
    with pytest.raises(CacheError, match="Credentials"):
        cache.path_for({"api_key": "test-only"})


def test_corrupt_cache_is_reported_without_network_fallback(tmp_path, monkeypatch):
    client = seeded_client(tmp_path, [program(100)])
    next(tmp_path.glob("*.json")).write_text("not json")
    client.allow_network = True
    monkeypatch.setattr(scorecard, "urlopen", no_network_or_key)
    with pytest.raises(CacheError, match="restore the committed seed"):
        client.get_school(1)


def test_invalid_live_response_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(scorecard, "read_api_key", lambda _: "test-only")
    monkeypatch.setattr(scorecard, "urlopen", lambda *a, **kw: io.StringIO('{"unexpected": true}'))
    with pytest.raises(ScorecardError, match="schema"):
        ScorecardClient(seed_dir=tmp_path, allow_network=True).get_school(1)
    assert not list(tmp_path.glob("*.json"))
