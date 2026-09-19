"""Pure comparison scenarios. Cost changes are explicit assumptions, not aid quotes."""

from math import fsum, isfinite

from .analysis import analyze
from .constants import DEFAULT_YEARS_IN_SCHOOL

EARNINGS = "median_earnings_four_years_after_completion"
LABELS = {
    "in_state_public": "Same major at an in-state public school",
    "community_college_transfer": "Two years at community college, then transfer",
    "same_school_different_major": "Different major at the same school",
}
TUITION_ASSUMPTION = (
    "Borrowing changes dollar for dollar with published in-state tuition: each year's debt is "
    "max(0, your original annual borrowing + alternative tuition - original tuition). "
    "Other spending and non-loan funding stay unchanged; unused savings are not carried to other years. "
    "In-state tuition eligibility is assumed, including CCAC's published rate. "
    "Tuition stays constant, and changes in aid, housing, fees, and time to completion are not modeled."
)


def _tuition(school: dict) -> float | None:
    value = ((school.get("latest", {}).get("cost") or {}).get("tuition") or {}).get("in_state")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if isfinite(value) and value >= 0 else None


def _unavailable(kind: str, message: str) -> dict:
    return {"kind": kind, "label": LABELS[kind], "status": "unavailable", "message": message,
            "result": None, "assumptions": [], "annual_borrowing": [], "annual_tuition": [],
            "original_annual_tuition": None, "borrowing_reduction": None}


def _ready(kind: str, school: dict, major: dict, amount: float, overrides: dict,
           annual_borrowing: list[float], assumptions: list[str], message: str,
           *, original_tuition: float | None = None, annual_tuition: list[float] | None = None) -> dict:
    borrowed = amount if kind == "same_school_different_major" else fsum(annual_borrowing)
    # An unchanged same-school plan must preserve the original equal-year calculation exactly.
    timing = {"disbursement_weights": annual_borrowing} if kind == "community_college_transfer" else {}
    result = analyze(borrowed, major[EARNINGS], **overrides, **timing)
    return {
        "kind": kind, "label": LABELS[kind], "status": "ready", "message": message,
        "result": {**result, "school": {"id": school["id"], "name": school["school"]["name"],
                                       "cost": school["latest"].get("cost")},
                   "major": major, "data_source": "seed cache"},
        "assumptions": assumptions,
        "annual_borrowing": annual_borrowing,
        "original_annual_tuition": original_tuition,
        "annual_tuition": annual_tuition or [],
        "borrowing_reduction": amount - borrowed,
    }


def compare_paths(school: dict, major: dict, majors: list[dict], amount_borrowed: float,
                  *, public_schools: list[dict], community_college: dict | None,
                  overrides: dict | None = None) -> list[dict]:
    """Use exact CIP/credential matches and the existing loan model for all metrics.

    Inputs are already validated by the primary analysis and data layer. No I/O.
    Public selection: lowest reported in-state tuition among matching, different
    curated schools, with institution ID breaking ties. Other-major selection:
    highest reported median earnings, with CIP code breaking ties.
    """
    options = dict(overrides or {})
    years = options.get("years_in_school", DEFAULT_YEARS_IN_SCHOOL)
    tuition = _tuition(school)
    annual_base = amount_borrowed / years
    comparisons = []

    kind = "in_state_public"
    candidates = []
    for item in public_schools:
        candidate = item["school"]
        cost = _tuition(candidate)
        if candidate["id"] == school["id"] or cost is None:
            continue
        matching = next((p for p in item["majors"] if p["code"] == major["code"]
                         and p["credential_level"] == major["credential_level"]), None)
        if matching is not None:
            candidates.append((cost, candidate["id"], candidate, matching))
    if tuition is None:
        comparisons.append(_unavailable(kind, "Your school's in-state tuition is unavailable in the cache; a borrowing comparison cannot be estimated."))
    elif not candidates:
        comparisons.append(_unavailable(kind, "No other cached Pennsylvania public school has both tuition and reported earnings for this exact CIP code and credential."))
    else:
        cost, _, destination, program = min(candidates, key=lambda item: (item[0], item[1]))
        borrowing = [max(0.0, annual_base + cost - tuition)] * years
        comparisons.append(_ready(kind, destination, program, amount_borrowed, options, borrowing,
            [TUITION_ASSUMPTION, "Uses the lowest in-state tuition among the other matching cached Pennsylvania public schools. All loan and tax overrides stay unchanged."],
            "Same CIP code and credential at " + destination["school"]["name"] +
            (". This school's tuition is not lower than your selection." if cost >= tuition else "."),
            original_tuition=tuition, annual_tuition=[cost] * years))

    kind = "community_college_transfer"
    cc = community_college["school"] if community_college else None
    cc_tuition = _tuition(cc) if cc else None
    if major["credential_level"] != 3 or years != 4:
        comparisons.append(_unavailable(kind, "The two-plus-two path requires a bachelor's program with four total years in school."))
    elif tuition is None or cc_tuition is None:
        comparisons.append(_unavailable(kind, "Cached tuition is missing for your school or CCAC; a transfer borrowing estimate is unavailable."))
    else:
        annual_tuition = [cc_tuition, cc_tuition, tuition, tuition]
        borrowing = [max(0.0, annual_base + value - tuition) for value in annual_tuition]
        comparisons.append(_ready(kind, school, major, amount_borrowed, options, borrowing,
            [TUITION_ASSUMPTION,
             "Assumes two years at CCAC transfer fully into your selected bachelor's program, followed by two years at your selected school. Admission, credit transfer, and completion in four years are not guaranteed.",
             "Uses the destination program's median earnings four years after completion; this is not a transfer-student-specific earnings measure.",
             "Borrowing follows each year's tuition; interest accrues from each academic year's midpoint through the same grace period. Aggregate federal/private/subsidized shares are spread proportionally across years; annual-limit conflicts are reported. All loan and tax overrides stay unchanged."],
            "Two years at " + cc["school"]["name"] + ", then two years at " + school["school"]["name"] + ".",
            original_tuition=tuition, annual_tuition=annual_tuition))

    kind = "same_school_different_major"
    other_majors = [p for p in majors if p["code"] != major["code"] and p["credential_level"] == major["credential_level"]]
    if not other_majors:
        comparisons.append(_unavailable(kind, "No other program at this school and credential has reported earnings in the cache."))
    else:
        program = min(other_majors, key=lambda p: (-p[EARNINGS], p["code"]))
        comparisons.append(_ready(kind, school, program, amount_borrowed, options, [annual_base] * years,
            ["Uses the highest reported median earnings among other programs at the same school and credential. This is a comparison, not a recommendation or a guarantee of earnings.",
             "Borrowing, school duration, loan terms, and tax assumptions stay unchanged. Program-specific tuition and aid differences are not available; no borrowing savings are assumed."],
            "Same school, different major: " + program["title"]))
    return comparisons
