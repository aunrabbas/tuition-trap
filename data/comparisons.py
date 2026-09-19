"""Load only cached inputs for the curated demo alternatives; no calculations."""

from .cache import CacheError
from .scorecard import ScorecardClient, ScorecardError

# Curated Pennsylvania demo institutions named in AGENTS.md; IDs in seed/manifest.json.
PUBLIC_SCHOOL_IDS = (215293, 214777)
COMMUNITY_COLLEGE_ID = 210605


def comparison_catalog(client: ScorecardClient, school: dict, majors: list[dict], credential_level: int) -> dict:
    """A missing alternative must not discard an otherwise valid main estimate."""
    current = {"school": school, "majors": majors}
    catalog = {school["id"]: current}
    for school_id in (*PUBLIC_SCHOOL_IDS, COMMUNITY_COLLEGE_ID):
        if school_id in catalog:
            continue
        try:
            candidate = client.get_school(school_id)
            # Transfer earnings come from the destination, not the CCAC associate degree.
            programs = [] if school_id == COMMUNITY_COLLEGE_ID else client.list_majors(
                school_id, credential_level=credential_level,
            )["majors"]
            catalog[school_id] = {"school": candidate, "majors": programs}
        except (CacheError, ScorecardError):
            catalog[school_id] = None
    return {
        "public_schools": [catalog[school_id] for school_id in PUBLIC_SCHOOL_IDS if catalog[school_id] is not None],
        "community_college": catalog[COMMUNITY_COLLEGE_ID],
    }
