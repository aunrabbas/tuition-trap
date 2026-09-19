# Scorecard data and demo cache

`ScorecardClient()` is offline by default. Reads use committed `seed/` responses
and do not need `.env` or an API key. A cache miss raises an actionable error;
it never silently enables a network request. Even `allow_network=True` reads
an existing response from cache first. No framework or third-party dependency
is required.

```python
from data import ScorecardClient

client = ScorecardClient()
pitt = client.get_school(215293)
choices = client.list_majors(215293, credential_level=3)
```

`list_majors` uses the API's program `title`, four-digit `code`, and credential
level. Credential 3 means bachelor's; 2 means associate. Omitting the credential
filter returns all credential levels. Only finite, nonnegative numeric **median
earnings four years after completion** values produce selectable majors; zero
is retained, while null and suppressed values are excluded. An empty result
includes a message telling the user to choose another school or credential.
There is no major-name crosswalk and no substitute institution-wide income.

The measure is `latest.programs.cip_4_digit.earnings.4_yr.overall_median_earnings`
(`EARN_MDN_4YR`), labeled **Median earnings four years after completion** in
returned choices. These data cover federally aided borrowers who completed
programs and are subject to suppression. They are not representative of every
graduate. Program identity includes credential level; conflicting duplicate
records raise an error rather than choosing a value silently.

Institution snapshots include `latest.cost.tuition.in_state`,
`latest.cost.tuition.out_of_state`, `latest.cost.attendance.academic_year`, and
the complete program array. Exact leaves were verified against the official
[Scorecard Data Dictionary](https://collegescorecard.ed.gov/files/CollegeScorecardDataDictionary.xlsx).
Requests set `keys_nested=true` and `all_programs_nested=true`, as documented
in the [API guide](https://collegescorecard.ed.gov/data/api-documentation/).
`latest` can describe different measurement years for different fields.

## Fetching and verifying the five schools

```sh
# Live requests only for cache misses; reads SCORECARD_API_KEY from .env.
.venv/bin/python scripts/fetch_seed.py --fetch

# Entirely offline; no key required.
.venv/bin/python scripts/fetch_seed.py

# Sockets, DNS, HTTP entry point, and API-key reads are blocked in this test.
.venv/bin/python -m pytest tests/test_data.py -k committed_seed_cache_without_network -v
```

This machine's Python installation needs `SSL_CERT_FILE=/etc/ssl/cert.pem`
before the live-fetch command to use its system CA bundle. HTTPS verification
remains enabled. Other installations can use their default trusted CA bundle.

The five institutions are Pitt's Pittsburgh campus, Penn State's Main Campus
(University Park), Carnegie Mellon, CCAC, and NYU as the high-cost private
option. `seed/manifest.json` records their API-resolved IDs, exact names, and
coverage counts. Penn State is stored under the API name
`Pennsylvania State University-Main Campus`. CCAC uses associate programs for
its demo coverage count; the other schools use bachelor's programs.

Each successful search page and institution response is saved to a separate
`scorecard-<sha256>.json` file. The fingerprint includes canonical query
parameters, never the key. The JSON envelope includes the request parameters,
UTC retrieval time, source, schema version, and unmodified response. Writes
use a temporary file and atomic replacement to prevent partial JSON caches.
Corrupt or incompatible cache files raise an error without a live fallback.
There is no automatic expiry or refresh during the demo. The earlier step-1
coverage snapshot is retained separately as historical evidence.

The key is sent in the `X-Api-Key` header. Neither full request URLs nor HTTP
error bodies are logged. `.env` remains ignored. Fetching is sequential, and
HTTP 429 stops with a rate-limit message instead of retrying (the service limit
is 1,000 requests per IP per hour).

Step 3 verifies the client/cache contract with networking disabled. FastAPI
endpoints and browser behavior remain outside this step.
