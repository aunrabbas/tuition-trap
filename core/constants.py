"""Verified loan constants and explicit project modeling defaults; rates are fractions."""

# Direct loans first disbursed July 1, 2026 through June 30, 2027, fixed for life.
# https://fsapartners.ed.gov/fsa-print/publication/1007224
UNDERGRADUATE_RATE = 0.0652
GRADUATE_UNSUBSIDIZED_RATE = 0.0807
PLUS_RATE = 0.0907
# July 1, 2025 through June 30, 2026:
# https://edfinancial.studentaid.gov/Interest-Rates-for-Federal-Student-Loans
PRIOR_YEAR_UNDERGRADUATE_RATE = 0.0639

# https://studentaid.gov/articles/subsidized-vs-unsubsidized-loans/
# Tuples: first year, second year, third year and beyond.
DEPENDENT_ANNUAL_LIMITS = (5500.0, 6500.0, 7500.0)
INDEPENDENT_ANNUAL_LIMITS = (9500.0, 10500.0, 12500.0)
SUBSIDIZED_ANNUAL_LIMITS = (3500.0, 4500.0, 5500.0)
DEPENDENT_AGGREGATE_LIMIT = 31000.0
INDEPENDENT_AGGREGATE_LIMIT = 57500.0
SUBSIDIZED_AGGREGATE_LIMIT = 23000.0

# Direct subsidized/unsubsidized only; first disbursed Oct 1, 2020–Sep 30, 2027.
# https://fsapartners.ed.gov/fsa-print/publication/1007164
ORIGINATION_FEE_RATE = 0.01057

# Project assumptions specified in AGENTS.md, not federal requirements.
DEFAULT_PRIVATE_RATE = 0.09
DEFAULT_SUBSIDIZED_FRACTION = 0.40
DEFAULT_TERM_MONTHS = 120
DEFAULT_YEARS_IN_SCHOOL = 4
DEFAULT_GRACE_MONTHS = 6
EARNINGS_LABEL = "Median earnings four years after completion"
