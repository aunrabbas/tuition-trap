#!/usr/bin/env python3
"""Step 1: inspect real CIP-4 earnings coverage; cache the API response."""

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
# Verified against CollegeScorecardDataDictionary.xlsx, FieldOfStudy sheet,
# EARN_MDN_4YR (consumer-site measure), CREDLEV, CIPCODE, and CIPDESC:
# https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx
EARNINGS_FIELD = "latest.programs.cip_4_digit.earnings.4_yr.overall_median_earnings"


def read_key():
    """Read .env without executing it or revealing its contents."""
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, sep, value = line.partition("=")
        if sep and name.strip() == "SCORECARD_API_KEY":
            parts = shlex.split(value, comments=True)
            if len(parts) == 1 and parts[0]:
                return parts[0]
    raise ValueError("Set SCORECARD_API_KEY in .env.")


def fetch(school):
    params = {
        "school.name": school,
        "fields": "id,school.name,latest.programs.cip_4_digit",
        "keys_nested": "true",
        "all_programs_nested": "true",
        "per_page": 100,
    }
    cache_id = hashlib.sha256(urlencode(params).encode()).hexdigest()[:16]
    cache = ROOT / "seed" / f"coverage-{cache_id}.json"
    if cache.exists():
        return json.loads(cache.read_text()), "seed cache"
    # Header authentication keeps the secret out of request URLs.
    request = Request(
        "https://api.data.gov/ed/collegescorecard/v1/schools?" + urlencode(params),
        headers={"X-Api-Key": read_key(), "Accept": "application/json"},
    )
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if "results" not in payload:
        raise ValueError("Scorecard returned no results array.")
    if payload["metadata"]["total"] > len(payload["results"]):
        raise ValueError("Too many schools matched; use a more specific school name.")
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(payload, indent=2) + "\n")
    return payload, "live API (saved to seed cache)"


def earnings(program):
    value = program.get("earnings", {}).get("4_yr", {}).get("overall_median_earnings")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--school", default="University of Pittsburgh-Pittsburgh Campus")
    parser.add_argument("--program", default="Computer Science")
    args = parser.parse_args()
    payload, source = fetch(args.school)
    matches = [s for s in payload["results"] if s["school"]["name"].casefold() == args.school.casefold()]
    if len(matches) != 1:
        names = ", ".join(s["school"]["name"] for s in payload["results"])
        raise ValueError("Use an exact school name. Matches: " + (names or "none"))
    school = matches[0]
    programs = school["latest"]["programs"]["cip_4_digit"] or []
    # A program is a CIP code plus credential level, not just a CIP code.
    programs = list({(p["code"], p["credential"]["level"]): p for p in programs}.values())
    covered = [p for p in programs if earnings(p) is not None]
    bachelors = [p for p in programs if p["credential"]["level"] == 3]
    print(f"School: {school['school']['name']} (ID {school['id']})")
    print(f"Source: {source}")
    print(f"Earnings field: {EARNINGS_FIELD}")
    print("Measure: median annual earnings 4 years after completion")
    print(f"CIP-4 programs with non-null median earnings (all credentials): {len(covered)} / {len(programs)}")
    print(f"Bachelor's programs with non-null median earnings: {sum(earnings(p) is not None for p in bachelors)} / {len(bachelors)}")
    if not covered:
        print("No field-of-study earnings are available for this school.")
        return
    named = [p for p in bachelors if p["title"].rstrip(".").casefold() == args.program.rstrip(".").casefold()]
    if len(named) != 1:
        raise ValueError("Named bachelor's program not found uniquely; use --program with its Scorecard title.")
    p = named[0]
    amount = earnings(p)
    print(f"Program: {p['title']} (CIP {p['code']}, {p['credential']['title']})")
    print(f"Median annual earnings: ${amount:,.0f}" if amount is not None else "Median annual earnings: unavailable (null/suppressed)")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as exc:
        sys.exit(f"Scorecard HTTP {exc.code}; check API access and retry.")
    except (URLError, TimeoutError):
        sys.exit("Scorecard connection failed; check network access and retry.")
    except (OSError, ValueError, KeyError, TypeError):
        # Do not print exceptions that might contain credentials or request URLs.
        sys.exit("Coverage check failed; check .env, exact school/program names, and response schema.")
