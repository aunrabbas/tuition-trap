#!/usr/bin/env python3
"""Fetch or verify the five demo schools; offline unless --fetch is supplied."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data import CacheError, ScorecardClient, ScorecardError

# Search by name and resolve exact API names, rather than assuming institution IDs.
DEMO_SCHOOLS = (
    ("University of Pittsburgh", ("University of Pittsburgh-Pittsburgh Campus",), 3),
    ("Pennsylvania State University", ("Pennsylvania State University-Main Campus", "Pennsylvania State University-University Park"), 3),
    ("Carnegie Mellon University", ("Carnegie Mellon University",), 3),
    ("Community College of Allegheny County", ("Community College of Allegheny County",), 2),
    ("New York University", ("New York University",), 3),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Allow live API requests on cache misses; read the key from .env.")
    args = parser.parse_args()
    client = ScorecardClient(allow_network=args.fetch)
    manifest = []
    for search_name, exact_names, credential_level in DEMO_SCHOOLS:
        candidates = client.search_schools(search_name)
        matches = [s for s in candidates if s["school"]["name"] in exact_names]
        if len(matches) != 1:
            names = ", ".join(s["school"]["name"] for s in candidates)
            raise ScorecardError(f"Could not resolve {search_name} uniquely. API matches: {names or 'none'}")
        school_id = matches[0]["id"]
        school = client.get_school(school_id)
        all_majors = client.list_majors(school_id)
        primary_majors = client.list_majors(school_id, credential_level=credential_level)
        count = len(primary_majors["majors"])
        record = {
            "id": school_id,
            "name": school["school"]["name"],
            "search_name": search_name,
            "demo_credential_level": credential_level,
            "programs_with_median_earnings_four_years_after_completion": len(all_majors["majors"]),
            "demo_programs_with_median_earnings_four_years_after_completion": count,
        }
        manifest.append(record)
        print(f"{record['name']} (ID {school_id}): {len(all_majors['majors'])} programs with median earnings four years after completion; {count} at credential level {credential_level}.")
        if primary_majors["message"]:
            print(primary_majors["message"])
    if args.fetch:
        (ROOT / "seed" / "manifest.json").write_text(json.dumps({"schools": manifest}, indent=2) + "\n")
    print(f"Verified {len(manifest)} demo schools. Mode: {'cache-first with live fetch allowed' if args.fetch else 'offline cache only'}.")


if __name__ == "__main__":
    try:
        main()
    except (CacheError, ScorecardError) as exc:
        sys.exit(str(exc))
    except OSError:
        sys.exit("Could not write seed metadata; check directory permissions.")
