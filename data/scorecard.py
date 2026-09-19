"""Scorecard client for median earnings four years after completion and costs."""

import json
from math import isfinite
from pathlib import Path
import shlex
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.constants import EARNINGS_LABEL
from .cache import CacheMissError, JSONCache

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://api.data.gov/ed/collegescorecard/v1/schools"
# Verified against the official dictionary (institution and FieldOfStudy sheets):
# https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx
SCHOOL_FIELDS = (
    "id,school.name,latest.cost.tuition.in_state,latest.cost.tuition.out_of_state,"
    "latest.cost.attendance.academic_year,latest.programs.cip_4_digit"
)
PROGRAM_VALUE_FIELD = "latest.programs.cip_4_digit.earnings.4_yr.overall_median_earnings"


class ScorecardError(RuntimeError):
    """Safe, actionable Scorecard error without credentials or request URLs."""


def read_api_key(env_file: Path) -> str:
    """Read the API key from .env without executing shell expressions."""
    try:
        for line in Path(env_file).read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            name, separator, value = line.partition("=")
            if separator and name.strip() == "SCORECARD_API_KEY":
                parts = shlex.split(value, comments=True)
                if len(parts) == 1 and parts[0]:
                    return parts[0]
                break
    except (OSError, ValueError):
        pass
    raise ScorecardError("Set a valid SCORECARD_API_KEY in .env before fetching seed data.")


def _validate_page(payload: dict) -> None:
    try:
        if not isinstance(payload, dict) or not isinstance(payload["results"], list):
            raise ValueError
        total = payload["metadata"]["total"]
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise ValueError
        for school in payload["results"]:
            if not isinstance(school["id"], int) or not isinstance(school["school"]["name"], str):
                raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ScorecardError("Scorecard returned an unexpected response schema; verify the data dictionary.") from None


def _programs(school: dict) -> list:
    try:
        rows = school["latest"]["programs"]["cip_4_digit"]
        if rows is None:
            return []
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError
        return rows
    except (KeyError, TypeError, ValueError):
        raise ScorecardError("Scorecard program data has an unexpected schema; verify the data dictionary.") from None


def _median_four_years(program: dict) -> float | None:
    try:
        value = ((program.get("earnings") or {}).get("4_yr") or {}).get("overall_median_earnings")
    except (AttributeError, TypeError):
        raise ScorecardError("Median earnings four years after completion has an unexpected schema; verify the data dictionary.") from None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if isfinite(value) and value >= 0 else None


class ScorecardClient:
    """Read cache first, even when live fetching is explicitly enabled."""

    def __init__(self, *, seed_dir: Path = ROOT / "seed", env_file: Path = ROOT / ".env", allow_network: bool = False):
        self.cache = JSONCache(seed_dir)
        self.env_file = Path(env_file)
        self.allow_network = allow_network

    def _request(self, query: dict) -> dict:
        params = {**query, "keys_nested": "true", "all_programs_nested": "true", "per_page": 100}
        cached = self.cache.read(params)
        if cached is not None:
            _validate_page(cached)
            return cached
        if not self.allow_network:
            raise CacheMissError("School data is not cached. Run scripts/fetch_seed.py --fetch before the demo.")
        request = Request(
            BASE_URL + "?" + urlencode(params),
            headers={"X-Api-Key": read_api_key(self.env_file), "Accept": "application/json"},
        )
        # Never log the request, response error body, key, or full URL.
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code == 429:
                raise ScorecardError("Scorecard rate limit reached (1,000 requests per IP per hour); retry later.") from None
            raise ScorecardError(f"Scorecard HTTP {exc.code}; check API access and retry the seed fetch.") from None
        except (URLError, OSError):
            raise ScorecardError("Scorecard connection failed; check network access and trusted CA certificates.") from None
        except (ValueError, TypeError):
            raise ScorecardError("Scorecard returned invalid JSON; retry the seed fetch.") from None
        _validate_page(payload)
        self.cache.write(params, payload)
        return payload

    def search_schools(self, name: str) -> list[dict]:
        """Return all matching institution IDs and names; cache each result page."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Enter a school name.")
        schools = []
        page = 0
        while True:
            payload = self._request({"school.name": name.strip(), "fields": "id,school.name", "page": page})
            schools.extend(payload["results"])
            if len(schools) >= payload["metadata"]["total"]:
                return schools
            if not payload["results"]:
                raise ScorecardError("Scorecard returned an incomplete search page; retry later.")
            page += 1

    def get_school(self, school_id: int) -> dict:
        """Return a nested institution record with costs and the entire CIP-4 array."""
        if isinstance(school_id, bool) or not isinstance(school_id, int) or school_id <= 0:
            raise ValueError("School ID must be a positive integer.")
        payload = self._request({"id": school_id, "fields": SCHOOL_FIELDS})
        if payload["metadata"]["total"] != 1 or len(payload["results"]) != 1:
            raise ScorecardError("School was not found uniquely; choose a valid Scorecard institution ID.")
        school = payload["results"][0]
        if school["id"] != school_id:
            raise ScorecardError("Scorecard returned the wrong institution; verify the cached response.")
        _programs(school)
        return school

    def list_majors(self, school_id: int, *, credential_level: int | None = None) -> dict:
        """List only programs with median earnings four years after completion.

        Titles come directly from Scorecard. Identity is CIP-4 plus credential
        level. None includes all credentials; use 3 for bachelor's or 2 for
        associate degrees. Missing/suppressed values never become selectable.
        """
        if credential_level is not None and (isinstance(credential_level, bool) or not isinstance(credential_level, int) or not 1 <= credential_level <= 8):
            raise ValueError("Credential level must be an integer from 1 to 8.")
        school = self.get_school(school_id)
        majors = {}
        for program in _programs(school):
            value = _median_four_years(program)
            if value is None:
                continue
            try:
                code, title = program["code"], program["title"]
                level = program["credential"]["level"]
                credential_title = program["credential"]["title"]
                if not isinstance(code, str) or len(code) != 4 or not code.isdigit() or not isinstance(title, str) or not title:
                    raise ValueError
                if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 8 or not isinstance(credential_title, str):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise ScorecardError("Scorecard program identity is invalid; verify the data dictionary.") from None
            if credential_level is not None and level != credential_level:
                continue
            item = {
                "code": code, "title": title,
                "credential_level": level, "credential_title": credential_title,
                "median_earnings_four_years_after_completion": value,
                "earnings_label": EARNINGS_LABEL,
            }
            identity = (code, level)
            if identity in majors and majors[identity] != item:
                raise ScorecardError("Scorecard contains conflicting records for one program; verify the source data.")
            majors[identity] = item
        choices = sorted(majors.values(), key=lambda p: (p["title"], p["credential_level"], p["code"]))
        return {
            "school_id": school_id, "school_name": school["school"]["name"],
            "earnings_label": EARNINGS_LABEL, "credential_level": credential_level,
            "majors": choices,
            "message": None if choices else "No programs with median earnings four years after completion are available for this school and credential level. Choose another school or credential level.",
        }
