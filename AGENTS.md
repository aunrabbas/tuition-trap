# AGENTS.md — Tuition Trap

Build this end to end. It is a weekend hackathon project for SteelHacks XII at the University of Pittsburgh and speed matters, but correctness of the financial math matters more than feature count, because the numbers are what we are judged on.

## What it does

A user enters a school, an intended major, and an expected total loan amount. The app shows them what life looks like after graduation:

1. Their real monthly loan payment
2. Median earnings for that specific major at that specific school
3. What share of their monthly take-home pay the payment consumes
4. Total repaid vs. amount borrowed
5. A single verdict: manageable, tight, or dangerous
6. A side-by-side comparison against cheaper alternative paths

## Architecture

```
core/          pure functions, no I/O, no network, no framework imports
data/          Scorecard API client + local JSON cache
api/           thin FastAPI layer, validates input, calls core, returns JSON
web/           React + Vite + Tailwind
seed/          pre-fetched Scorecard responses, committed to the repo
scripts/       one-off utilities
tests/         pytest
```

`core/` must stay free of I/O and framework imports. This is what lets us swap the front end late if we have to.

## The math — implement exactly this

### Monthly payment

Standard amortization, closed form:

```
r = annual_rate / 12
n = term_months
M = P * r * (1 + r)**n / ((1 + r)**n - 1)
```

Edge case: if `r == 0`, then `M = P / n`. Do not let a zero rate produce a division by zero.

Round only at display time. Keep full precision through the schedule, or use `Decimal`.

### Amortization schedule

Month by month, for the full term:

```
interest_portion  = balance * r
principal_portion = M - interest_portion
balance           = balance - principal_portion
```

The final payment must be adjusted so the ending balance is exactly zero rather than a fraction of a cent either way. Return a list of rows with month index, payment, interest portion, principal portion, remaining balance, and cumulative interest.

### Capitalization — this is the differentiator, get it right

Subsidized loans accrue no interest while the borrower is enrolled at least half time, and none during the six-month grace period after leaving school. The government covers it.

Unsubsidized loans accrue interest from disbursement, through enrollment and through the grace period. That accrued interest capitalizes onto the principal when repayment begins, so the borrower enters repayment owing more than they borrowed.

Accrual is simple daily interest, not compounding:

```
accrued = principal * annual_rate * years_accruing
```

Model disbursement per academic year, not as a lump sum, because the timing changes the answer materially. For a four-year borrower whose loans are split evenly across four years, with a six-month grace period:

```
year 1 disbursement accrues 3.5 years + 0.5 grace = 4.0 years
year 2                      2.5           + 0.5   = 3.0
year 3                      1.5           + 0.5   = 2.0
year 4                      0.5           + 0.5   = 1.0
```

Repayment principal = total borrowed + sum of accrued interest on the unsubsidized portion only.

Default assumption when the user does not specify a split: 40% subsidized / 60% unsubsidized for a dependent undergraduate, capped at the subsidized aggregate limit below. Expose it as an adjustable input but do not block on the user setting it.

### Origination fee

Federal Direct loans carry a 1.057% origination fee for loans first disbursed on or after October 1, 2020 and before October 1, 2027. The borrower receives less than the face amount but owes the full amount. Show the disbursed-vs-owed gap somewhere in the detail view; it is a small number but it is the kind of thing that reads as rigor.

### Take-home pay

Convert median gross earnings to monthly net:

- Federal income tax, single filer, standard deduction, current-year brackets. Hardcode the brackets from the IRS published tables in `core/taxes.py` with a comment citing the tax year. Do not invent bracket thresholds — look them up and if you cannot verify them, stop and ask.
- FICA: 6.2% Social Security up to the wage base, 1.45% Medicare, no cap.
- Pennsylvania flat state income tax.
- Local earned income tax: default to the Pittsburgh resident rate, make it a named constant, and label it in the UI as an assumption.

Divide annual net by 12. Every rate in this module gets a source comment.

### Burden verdict

Two benchmarks, and the verdict is the worse of the two:

**Payment as a share of gross monthly income**
- under 8% → manageable
- 8% to 15% → tight
- over 15% → dangerous

**Total debt vs. first-year salary**
- ratio under 1.0 → manageable
- 1.0 to 1.5 → tight
- over 1.5 → dangerous

The headline metric shown to the user is payment as a share of *take-home* pay, because that is the number they feel. The verdict thresholds above are against gross, which is the convention the rules of thumb use. Keep the two straight and label them correctly in the UI.

## Constants — `core/constants.py`

Current federal Direct Loan rates, fixed for the life of the loan, for loans first disbursed July 1 2026 through June 30 2027:

- Undergraduate subsidized and unsubsidized: 6.52%
- Graduate unsubsidized: 8.07%
- PLUS: 9.07%

Prior year, disbursed July 1 2025 through June 30 2026, undergraduate: 6.39%.

Annual borrowing limits for dependent undergraduates: $5,500 first year, $6,500 second year, $7,500 third year and beyond, with subsidized sub-limits inside each.

Aggregate limits: $31,000 for dependent undergraduates including no more than $23,000 subsidized; $57,500 for independent undergraduates, same $23,000 subsidized cap.

If a user enters a loan amount above the aggregate federal limit, do not reject it. Show the federal portion at the federal rate and flag the excess as private debt at a user-adjustable rate defaulting to 9%. Flagging this is a demo moment, not an error state.

Note for scope: the RISE final rule published May 1 2026 changed repayment plan eligibility for loans disbursed after July 1 2026. We are not modeling income-driven repayment at all, so this does not affect us, but do not add IDR without asking.

## Data layer

Source: U.S. Department of Education College Scorecard API.

- Base URL: `https://api.data.gov/ed/collegescorecard/v1/schools`
- Key from `SCORECARD_API_KEY` in `.env`. Never hardcode, never log, never print a full request URL. Add `.env` to `.gitignore` in your first commit.
- Institution fields under `latest.*`, e.g. `latest.cost.tuition.in_state`, `latest.cost.attendance.academic_year`, `latest.earnings.10_yrs_after_entry.median`.
- Field-of-study data is an array nested under `latest.programs.cip_4_digit`, keyed by 4-digit CIP code plus credential level. Pass `keys_nested=true` for real JSON objects and `all_programs_nested=true` to get the whole array rather than only matching items.
- Verify exact leaf field names against the Data Dictionary (.xlsx) linked from `https://collegescorecard.ed.gov/data/api-documentation/`. The earnings sub-objects have been reorganized between releases. Do not guess from memory.
- Rate limit: 1,000 requests per IP per hour.

**Suppression is the central data problem.** Field-of-study earnings cover only graduates who took federal student loans, and programs with too few such completers return null. A school may have usable earnings for twenty programs and nothing for the rest.

Handling:

1. Never offer a major the user can select that has no earnings data. On school selection, fetch the program array, filter to non-null median earnings, and populate the selector from the `title` field of survivors. Do not build a major-name-to-CIP crosswalk.
2. Cache every response to `seed/` as JSON on first fetch, read from cache when present, and commit the seed files. Nothing may make a live network call during the demo.
3. Pre-fetch and commit seed data for: University of Pittsburgh, Penn State University Park, Carnegie Mellon, Community College of Allegheny County, and one high-cost private school. These are our demo path.

## Build order

Work in this sequence. Do not start a step before the prior one runs.

1. **Coverage check.** `scripts/coverage.py` prints, for a named school, the count of CIP-4 programs with non-null median earnings plus the earnings figure for one named program. Run it against Pitt and paste the real output. Stop and report before continuing.
2. **`core/` with tests.** Amortization, capitalization, taxes, burden. All acceptance tests below green. Paste real pytest output.
3. **`data/` and seed fetch.** Client, cache, the five schools committed to `seed/`.
4. **`api/`.** One POST endpoint taking school, major, loan amount, and optional overrides; returning the full result object including the schedule and the comparison scenarios. One GET endpoint listing majors with data for a school.
5. **`web/`.** Full UI per the design section.
6. **Comparison engine.** Same major at the in-state public, community college transfer for two years then transfer, and same school different major. Three alternatives, same metrics, side by side.
7. **Deploy.** Whatever is fastest and free.

## Design direction

Judged by people with personal history with student debt. It should read like an official financial disclosure rewritten to be honest — institutional credibility, not fintech optimism. Cold, precise, unsparing. No celebration, no confetti, no growth-app gradients.

### Tokens

```
--paper     #EDEFF1   cool grey page ground
--ink       #16202B   deep navy-slate, primary text
--ink-soft  #5A6B7A   secondary text, axis labels
--rule      #C9D1D7   hairlines, table borders
--steel     #4A6A8A   chart lines, neutral data
--verdict-ok    #2F6B4F
--verdict-tight #B5852A
--verdict-bad   #A62B1F
```

Verdict colors are desaturated printed-ink tones, not signal-light neon. Only one appears on screen at a time.

### Type

- **Archivo** (Google Fonts) for all figures and headings. Hero number in Archivo Expanded 700. `font-variant-numeric: tabular-nums` everywhere a number appears.
- **Newsreader** (Google Fonts) for body and explanatory copy. Measure under 75 characters, line-height 1.6.

### Layout

One column, left-aligned, scrolling downward as a sequence of consequences. No card grid. No identical rounded boxes. Sections separated by hairline rules and whitespace, not containers.

```
+------------------------------------------+
|  school / major / loan amount  (compact) |
+------------------------------------------+
|                                          |
|   $ 8 4 7                                |  <- hero, enormous
|   every month for ten years              |
|                                          |
|   [============|---------------------]   |  <- one month of take-home,
|   $847 of your $3,190 take-home pay      |     payment portion filled
+------------------------------------------+
|  VERDICT — one sentence, one color       |
+------------------------------------------+
|  borrowed $80,000 -> repaid $112,400     |
|  amortization curve: balance + interest  |
+------------------------------------------+
|  alternatives: dense comparison table    |
+------------------------------------------+
```

The hero is the payment figure and the single bar beneath it showing that payment as a filled portion of one month's take-home pay. That bar is the memorable element of the app. Spend the design budget there; keep everything below it quiet and tabular.

### Do not

These read as machine-generated and will cost us with judges who have seen forty demos:

- tracked-out ALL-CAPS eyebrow labels above every heading
- content chopped into identically rounded cards with the same soft grey shadow
- gradient washes as decoration
- fade-and-slide-up entrances on every section, hover transitions on every element
- `→` appended to button text
- meta strings joined with middle dots
- accenting one word of a headline in a different color
- numbered markers (01 / 02 / 03) on content that is not a sequence

Motion only in response to user action — the bar filling and the number counting once when results arrive. Respect `prefers-reduced-motion`.

### Quality floor

Responsive to 375px. Visible keyboard focus. Hero number stays legible at mobile width — reduce size, never wrap. Color is never the sole carrier of the verdict; always pair with words.

### Copy

Plain, active, second person. State the number and what it means. Do not apologize for it, do not editorialize. Every assumption the model makes — tax filing status, subsidized split, local tax rate — is visible and labeled somewhere, not buried. Empty state is an instruction. Errors say what happened and what to do.

## Acceptance tests

Write these, keep them green, and paste real output:

1. Monthly payment for $80,000 at 6.52% over 120 months matches an independent loan calculator to the cent.
2. Sum of all principal portions in the schedule equals the original principal within one cent.
3. Final row of the schedule has a remaining balance of exactly zero.
4. An unsubsidized loan disbursed across four years with a six-month grace produces a repayment-start balance greater than the amount borrowed; a fully subsidized loan produces one exactly equal to it.
5. Zero loan amount renders a sensible empty state, no division by zero, no $0 hero.
6. $500,000 loan renders without layout breakage and triggers the private-debt flag.
7. A school with no field-of-study earnings coverage produces a clear message, not a blank dropdown.
8. Every API response is served from `seed/` cache when present — verified by a test run with networking disabled.
9. A major with very low median earnings produces a `dangerous` verdict rather than a crash or a negative take-home figure.

## Working rules

- Work on a branch. Small, reviewable commits.
- Run the tests and paste real output. Never describe results you did not produce.
- Do not add dependencies without saying why.
- Do not refactor code you were not asked to touch.
- If you are about to guess at a field name, a tax bracket, an interest rate, or a borrowing limit, stop and ask instead. A wrong constant invalidates every number in the demo and is worse than a missing feature.
- After each build-order step: report what you changed, what you verified, and what you could not verify.

## Out of scope this weekend

Income-driven repayment, PSLF, refinancing, grad school deferment, other states' tax codes, private loan shopping, user accounts, persistence, auth. If you find yourself building any of these, stop and flag it.
