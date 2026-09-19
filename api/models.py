"""HTTP contracts using median earnings four years after completion."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.constants import (
    DEFAULT_GRACE_MONTHS, DEFAULT_PRIVATE_RATE, DEFAULT_SUBSIDIZED_FRACTION,
    DEFAULT_TERM_MONTHS, DEFAULT_YEARS_IN_SCHOOL, UNDERGRADUATE_RATE,
)
from core.taxes import PITTSBURGH_RESIDENT_EIT_RATE


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


Rate = Annotated[float, Field(ge=0, le=1)]
UndergraduateCredential = Annotated[int, Field(ge=1, le=3)]


class MajorSelection(RequestModel):
    code: str = Field(pattern=r"^[0-9]{4}$", description="Scorecard CIP-4 code, preserving leading zeros.")
    credential_level: UndergraduateCredential = 3


class Overrides(RequestModel):
    subsidized_fraction: Rate = DEFAULT_SUBSIDIZED_FRACTION
    dependent: bool = True
    federal_rate: Rate = UNDERGRADUATE_RATE
    private_rate: Rate = DEFAULT_PRIVATE_RATE
    # Operational limits bound computation and response size, not loan eligibility.
    term_months: int = Field(default=DEFAULT_TERM_MONTHS, ge=1, le=600)
    years_in_school: int = Field(default=DEFAULT_YEARS_IN_SCHOOL, ge=1, le=20)
    grace_months: float = Field(default=DEFAULT_GRACE_MONTHS, ge=0, le=120)
    local_tax_rate: Rate = PITTSBURGH_RESIDENT_EIT_RATE


class AnalysisRequest(RequestModel):
    school_id: int = Field(gt=0)
    major: MajorSelection
    loan_amount: float = Field(ge=0, le=1e12, description="Total face amount borrowed in dollars; not limited to federal eligibility.")
    overrides: Overrides = Field(default_factory=Overrides)


class Major(BaseModel):
    code: str
    title: str
    credential_level: int
    credential_title: str
    median_earnings_four_years_after_completion: float
    earnings_label: Literal["Median earnings four years after completion"]


class MajorsResponse(BaseModel):
    school_id: int
    school_name: str
    earnings_label: Literal["Median earnings four years after completion"]
    credential_level: int
    majors: list[Major]
    message: str | None


class ScheduleRow(BaseModel):
    month: int
    payment: float
    interest_portion: float
    principal_portion: float
    remaining_balance: float
    cumulative_interest: float


class SchoolAnalysis(BaseModel):
    school: dict[str, Any]
    major: Major
    data_source: Literal["seed cache"]
    state: Literal["empty", "ready"]
    message: str | None
    hero_monthly_payment: float | None
    earnings_label: Literal["Median earnings four years after completion"]
    median_earnings_four_years_after_completion: float
    allocation: dict[str, Any]
    capitalization: dict[str, Any]
    repayment_principal: float
    monthly_payment: float
    federal_monthly_payment: float
    private_monthly_payment: float
    total_repaid: float
    repayment_interest: float
    total_interest_including_capitalization: float
    schedule: list[ScheduleRow]
    taxes: dict[str, Any]
    burden: dict[str, Any]
    annual_limit_warnings: list[dict[str, Any]]
    assumptions: dict[str, Any]


class ComparisonScenario(BaseModel):
    kind: Literal["in_state_public", "community_college_transfer", "same_school_different_major"]
    label: str
    status: Literal["ready", "unavailable"]
    message: str
    result: SchoolAnalysis | None
    assumptions: list[str]
    annual_borrowing: list[float]
    original_annual_tuition: float | None
    annual_tuition: list[float]
    borrowing_reduction: float | None


class AnalysisResponse(SchoolAnalysis):
    comparisons: list[ComparisonScenario]
