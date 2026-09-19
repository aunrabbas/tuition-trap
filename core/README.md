# Core model

All functions are pure Python, with no I/O, network, or framework imports.
Amounts are dollars, rates are fractions (`0.0652` means 6.52%), and durations
are months unless named otherwise. Calculations retain floating-point precision;
format money only for display. The final amortization payment retires the exact
remaining balance, which is returned as `0.0`.

`analyze(amount_borrowed, median_earnings_four_years_after_completion, **overrides)`
combines amortization, capitalization, loan allocation, taxes, and burden. Every
income-dependent result carries the label **Median earnings four years after
completion**. This is the observed Scorecard measure, not a projection of income
when repayment begins. Gross-income burden thresholds use that measure as their
denominator; the headline share uses the estimated monthly take-home amount.
Debt in the debt-to-income ratio is the repayment-start balance, including
capitalized interest. Ratios with positive debt/payment and zero income return
`None` and a dangerous verdict, avoiding non-finite JSON values.

The defaults follow AGENTS.md:

- Four equal annual disbursements, at each academic year's midpoint, followed by
  six months of grace: interest accrues for 4, 3, 2, and 1 years respectively.
- 40% of federal principal subsidized, capped at $23,000. Subsidized principal
  accrues no enrollment/grace interest. Other principal accrues simple interest,
  capitalized once at repayment under the requested model.
- Federal/private allocation uses the $31,000 dependent or $57,500 independent
  aggregate cap. Annual borrowing and subsidized sub-limits are stored and
  conflicts with equal disbursements appear in `annual_limit_warnings`.
  This aggregate-cap estimate is not an annual eligibility determination.
- Each loan type uses one fixed rate for every modeled disbursement: federal
  undergraduate 6.52%, private 9%, both adjustable. Private debt is assumed to
  follow the same simple-interest enrollment/grace timing; actual contracts vary.
  Federal and private balances are amortized separately and their rows combined.
- Federal origination fees reduce cash received without reducing face debt.
  The 1.057% unrounded estimate excludes private fees; actual federal fees are
  truncated to cents at disbursement. The returned values are labeled estimates.
- 2026 single-filer federal brackets and standard deduction, employee Social
  Security and base Medicare, Pennsylvania tax, and Pittsburgh resident EIT.
  The local rate is adjustable. Tax credits, benefits deductions, PA forgiveness,
  local services tax, and the additional Medicare surtax are excluded, consistent
  with the specified simplified tax model. Assumptions accompany the result.

Zero borrowing returns `state="empty"`, an instructional message, no schedule,
and `hero_monthly_payment=None`. Rendering is left to the later web step.

## Comparison engine (step 6)

`core.comparisons.compare_paths` accepts already validated institution/program
records. It performs no I/O and uses `analyze` for every scenario, returning the
same metrics and complete amortization schedules. `data/comparisons.py` loads
the curated cached candidates; the API assembles the response.

- In-state public: match the exact CIP-4 code and credential at another cached
  Pennsylvania public institution (Pitt or Penn State). Select the lowest
  reported in-state tuition, breaking ties by institution ID. If the other
  school is more expensive, report increased debt rather than claim savings.
- Transfer: two years at CCAC, then two at the selected school, with the
  selected bachelor's program's earnings. Requires four total school years
  and a bachelor's credential; does not substitute associate earnings or
  silently override a user-selected duration. Transfer credit, admission,
  and four-year completion are assumptions, not verified articulation agreements.
- Other major: highest reported median earnings among other programs at the
  same school and credential, breaking ties by CIP code. Debt and terms remain
  unchanged; this is not a claim of lower tuition or a career recommendation.

The cost model is an explicit estimate: annual debt equals
`max(0, original_total_debt / years + alternative_tuition - original_tuition)`.
Other spending and non-loan funding stay constant. Published in-state tuition
eligibility is assumed; tuition inflation, changes in aid, housing, and fees
are not modeled. Unused annual savings are not carried forward. This avoids
inventing a financial-aid package or treating sticker cost as the user's debt.
No cost ratio or division by tuition is used. Zero tuition is valid; missing,
suppressed, negative, or non-finite tuition disables the affected scenario.

Transfer uses `disbursement_weights` on `analyze` / `capitalize` to accrue
interest against the actual borrowing distribution, including years with no
borrowing. Federal, private, and subsidized principal are spread proportionally
across years after applying the existing aggregate caps. The existing annual
limit warnings still apply; this is not an annual eligibility determination.
Default primary analyses retain their original equal-year calculations.

All loan and tax overrides carry into comparisons. Ready scenarios include
their assumptions, annual tuition, annual borrowing, and signed borrowing
reduction. Missing alternative caches or program earnings produce an explicit
unavailable reason without discarding the primary estimate. No institution-wide
earnings or major-title crosswalk is used.

## Sources and verification

Source comments sit beside the constants. Federal 2026 brackets and the standard
deduction were verified against [IRS Revenue Procedure 2025-32](https://www.irs.gov/irb/2025-45_IRB).
FICA uses [IRS Publication 15 (2026)](https://www.irs.gov/publications/p15).
State and local rates use the [Pennsylvania Department of Revenue](https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/personal-income-tax)
and [City of Pittsburgh](https://www.pittsburghpa.gov/City-Government/Finance-Budget/Taxes).

The $80,000, 6.52%, 120-month amortization reference was retrieved from
[Calculator.net](https://www.calculator.net/loan-calculator.html?cloanamount=80000&cloanterm=10&cloantermmonth=0&cinterestrate=6.52&ccompound=monthly&cpayback=month&x=Calculate&type=1)
on September 19, 2026: $909.20 monthly, $109,103.77 total payments, and $29,103.77
interest. Tests also independently solve discounted cash flows with Decimal
arithmetic and compare cumulative tax at every IRS bracket boundary.

Run `.venv/bin/python -m pytest`. The tests disable network access. They cover
acceptance items 1–4 and 9, and core behavior for items 5–6. Actual rendering,
school coverage messages, and API cache behavior belong to later build steps.
