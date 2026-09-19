<div align="center">

# Tuition Trap

**See what your student loans actually cost — before you sign.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Tests](https://img.shields.io/badge/tests-199%20passing-success)](#validation)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Enter a school, a major, and how much you plan to borrow.
Get the monthly payment, what it costs you in take-home pay, and whether it's survivable.

Built for **SteelHacks XII** at the University of Pittsburgh.

</div>


<img width="1414" height="810" alt="Screenshot 2026-09-19 at 4 35 45 PM" src="https://github.com/user-attachments/assets/93f2f22d-fe61-4a3c-a616-9108ab245ed7" />

---

## The problem

An eighteen-year-old choosing between a $60,000-a-year private school and an in-state option gets handed a tuition number, a vague awareness that loans exist, and a financial aid letter written to obscure rather than clarify.

What they don't get: the monthly payment, what graduates of that specific program actually earn, whether that payment is survivable on that salary, or what the loan costs in total once interest is counted.

All of it is public data. It's just scattered across federal databases nobody reads and buried in amortization math nobody does by hand.

## What it does

Three inputs. One uncomfortable answer.

| Output | What it means |
|:--|:--|
| **Monthly payment** | From a real amortization schedule, not a rule of thumb |
| **Share of take-home pay** | After federal, FICA, Pennsylvania, and Pittsburgh local tax |
| **Total repaid vs. borrowed** | The number that changes how people think about the decision |
| **Burden verdict** | Manageable, tight, or dangerous — against debt-to-income benchmarks |
| **Alternative paths** | Same major in-state, community college transfer, different major same school |


## Why the numbers are real

Most loan calculators are a payment formula with a chart attached. Three things here aren't.

<table>
<tr><td width="33%" valign="top">

### Capitalization is modeled

Unsubsidized loans accrue interest from disbursement — through four years of enrollment and a six-month grace period — and that interest capitalizes onto the principal at repayment.

**You start repayment owing more than you borrowed.**

Disbursements are modeled year by year, because a freshman loan accrues for four years and a senior loan for one.

</td><td width="33%" valign="top">

### Earnings are program-specific

College Scorecard publishes median earnings by four-digit CIP code and credential level at each institution.

**Not "CS majors earn $X nationally."**

What graduates of *that program* at *that school* reported to the IRS.

</td><td width="33%" valign="top">

### Suppressed data is excluded

Scorecard only covers graduates who took federal loans, and programs with too few completers return null.

**122 of 422 Pitt programs have usable data.** 58 of 102 at bachelor's level.

The major selector only offers programs where real data exists. Nothing is estimated to fill a gap.

</td></tr>
</table>

## An honest caveat, stated up front

> Scorecard earnings are measured **four years after completion**, not at graduation.
>
> A Pitt computer science graduate's median is **$108,680** four years out — considerably more than a first-year salary.
>
> **Every burden figure here is the optimistic case.** The first years of repayment are harder than what this tool shows. The measure is labeled everywhere it appears and never called a starting salary.

## Quick start

Requires **Python 3.11+** and **Node 20+**.

```bash
git clone https://github.com/aunrabbas/tuition-trap.git
cd tuition-trap

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm --prefix web install
```

Run the API and the front end in two terminals:

```bash
# Terminal 1 — API
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

```bash
# Terminal 2 — web
npm --prefix web run dev
```

Open **http://127.0.0.1:5173**

> **No API key needed to run.** Seed data is committed and the app reads from disk by default. A free [api.data.gov](https://api.data.gov/signup/) key is only required to fetch additional schools:
> ```bash
> echo 'SCORECARD_API_KEY=your_key_here' > .env
> ```

### Tests

```bash
.venv/bin/python -m pytest      # 199 Python tests
npm --prefix web test           # 9 browser tests
```

## Architecture

```
core/       pure financial modeling — no I/O, no network, no framework imports
data/       College Scorecard client, atomic JSON cache, offline by default
api/        FastAPI — POST /analyze, GET /schools/{id}/majors
web/        React 19 + Vite + Tailwind 4 + TypeScript
seed/       pre-fetched Scorecard responses, committed
scripts/    coverage and seed-fetch utilities
tests/      199 Python tests, 9 browser tests
```

`core/` is deliberately free of I/O, so the modeling can be verified in isolation and the front end swapped without touching it. `core/` also has **zero third-party dependencies** — standard library only. Every API response is cached to `seed/` and read from disk by default, which means the app runs with networking fully disabled. That's also why it works on conference wifi.

<details>
<summary><b>Module breakdown</b></summary>

<br>

| Module | Responsibility |
|:--|:--|
| `core/amortization.py` | Monthly payment, full amortization schedule |
| `core/capitalization.py` | Year-by-year disbursement, accrual through enrollment and grace |
| `core/taxes.py` | Federal brackets, FICA, PA flat rate, Pittsburgh EIT |
| `core/burden.py` | Debt-to-income assessment against benchmarks |
| `core/comparisons.py` | Alternative path scenarios |
| `core/analysis.py` | Orchestration — combines all of the above |
| `core/validation.py` | Input guards |
| `core/constants.py` | Rates, limits, labels, all source-commented |
| `data/scorecard.py` | Scorecard API client |
| `data/cache.py` | Atomic JSON cache with integrity checks |

</details>

## Data sources

| Source | What it provides |
|:--|:--|
| [College Scorecard API](https://collegescorecard.ed.gov/data/api-documentation/) | Median earnings by institution and field of study, net price, cost of attendance |
| [Federal Student Aid](https://studentaid.gov) | Direct Loan rates, origination fee, annual and aggregate borrowing limits |
| IRS | Federal brackets, standard deduction, FICA rates and wage base |
| PA Dept. of Revenue | State flat rate, Pittsburgh resident earned income tax |

Loans disbursed **July 1, 2026 – June 30, 2027** carry a fixed **6.52%** rate for undergraduate Direct Subsidized and Unsubsidized loans, set by the May 2026 ten-year Treasury auction.

## Assumptions

Every one of these is visible in the interface, not buried in code.

**Modeled**
- Standard 10-year repayment
- Single filer, standard deduction, Pittsburgh resident
- Default 40% subsidized / 60% unsubsidized split for a dependent undergraduate, adjustable
- Four years of enrollment, six-month grace period
- Borrowing above the federal aggregate limit modeled as private debt at an adjustable rate

**Deliberately not modeled**
- Income-driven repayment, PSLF, refinancing, graduate deferment, other states' tax codes

## Validation

- Monthly payment verified against independent loan calculators **to the cent**
- Principal portions across the full schedule sum to the original principal; final balance is exactly zero
- A fully subsidized loan enters repayment owing exactly what was borrowed; an unsubsidized one owes more
- Tax brackets carry source comments and cite their tax year
- Edge cases covered: zero borrowing, $500,000 borrowing, programs with very low median earnings, schools with no field-of-study coverage
- Cache tests run with **networking blocked**

## Roadmap

- Income-driven repayment comparison
- PSLF eligibility
- Refinancing scenarios
- Parent PLUS modeling
- Multi-state tax support
- Cost-of-living adjustment by metro, so a $108,680 median in Pittsburgh and San Francisco stop looking like the same number

## License

MIT
