# HTTP API

Install with `.venv/bin/python -m pip install -r requirements-dev.txt` and run:

```sh
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

The API always uses the committed seed cache. It does not read `.env`, require
an API key, or enable live Scorecard requests. `/openapi.json` documents the
request and response schemas without external assets. Swagger/ReDoc pages are
disabled to avoid CDN requests during offline use.

## GET /schools/{school_id}/majors

Returns Scorecard titles and CIP-4/credential identities with available **median
earnings four years after completion**, plus a clear message when none qualify.
The `credential_level` query parameter defaults to `3` (bachelor's); `2` selects
associate programs and `1` undergraduate certificates. Graduate credentials are
outside the current model and are rejected. Null/suppressed values are excluded;
a numeric zero remains valid.

Example: `/schools/210605/majors?credential_level=2` for CCAC.

## POST /analyze

```json
{
  "school_id": 215293,
  "major": {"code": "1107", "credential_level": 3},
  "loan_amount": 80000,
  "overrides": {"private_rate": 0.09, "term_months": 120}
}
```

Use a major returned by GET. The server resolves **median earnings four years
after completion** from the cache; the request cannot replace that value. The
response preserves every core result field, including the complete schedule,
capitalization, gross-income burden benchmarks, take-home share, taxes,
assumptions, and annual-limit warnings. It also includes school costs, the exact
selected major, and `data_source="seed cache"`.

The response includes the three named comparison entries, each with
`status="not_implemented"` and `result=null`. Step 6 implements the comparison
engine; this step does not invent alternative borrowing amounts or results.

`overrides` is optional. Supported fields are `subsidized_fraction`, `dependent`,
`federal_rate`, `private_rate`, `term_months`, `years_in_school`, `grace_months`,
and `local_tax_rate`. Defaults are the core defaults, including four years in
school; pass `years_in_school=2` when modeling a two-year course of study.
Rates are fractions (`0.09`, not `9`). The effective assumptions are returned.

Request JSON uses strict numeric/boolean types and rejects unknown fields,
negative amounts, and non-finite values. Operational bounds are $1 trillion
borrowed, 600 repayment months, 20 school years, 120 grace months, and rates
between 0 and 1. These bound arithmetic/work per request, not federal eligibility.
Amounts above federal limits—including $500,000—are accepted with private debt.

Zero borrowing returns the core empty state, instructional message, an empty
schedule, and `hero_monthly_payment=null`.

## Errors and tests

- `404`: school is not in the offline cache; select a seeded school.
- `422`: invalid input or unavailable school/program/credential combination.
- `503`: corrupt or incompatible seed data; restore the committed files.

Validation errors omit raw input values so rejected NaN/Infinity still produce
valid JSON. Data errors do not reveal file paths, credentials, or request URLs.

Run `.venv/bin/python -m pytest`. Endpoint tests use FastAPI's in-process client;
the suite blocks sockets and DNS, and endpoint tests also block Scorecard HTTP
calls and API-key reads. Both endpoints are exercised against all five real
seeded schools, with synthetic cached records for suppression and zero/low
median earnings four years after completion. No browser rendering or comparison
calculations are tested in this step.
