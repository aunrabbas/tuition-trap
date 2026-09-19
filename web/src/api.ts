export interface Major {
  code: string
  title: string
  credential_level: number
  credential_title: string
  median_earnings_four_years_after_completion: number
}

export interface MajorsResponse {
  school_id: number
  school_name: string
  majors: Major[]
  message: string | null
}

export interface ScheduleRow {
  month: number
  payment: number
  interest_portion: number
  principal_portion: number
  remaining_balance: number
  cumulative_interest: number
}

export interface SchoolAnalysis {
  school: { id: number; name: string }
  major: Major
  state: 'empty' | 'ready'
  message: string | null
  monthly_payment: number
  repayment_principal: number
  total_repaid: number
  repayment_interest: number
  total_interest_including_capitalization: number
  median_earnings_four_years_after_completion: number
  allocation: {
    amount_borrowed: number; federal_principal: number; private_principal: number
    subsidized_principal: number; unsubsidized_principal: number; has_private_debt: boolean
    aggregate_federal_limit: number; effective_subsidized_fraction: number
    origination_fee_estimate: number; net_disbursed_estimate: number
  }
  capitalization: { federal: { accrued_interest: number }; private: { accrued_interest: number } }
  taxes: {
    monthly_take_home: number; annual_take_home: number; tax_year: number; standard_deduction: number
    federal_income_tax: number; social_security_tax: number; medicare_tax: number
    pennsylvania_income_tax: number; local_earned_income_tax: number
    local_tax_rate: number; local_tax_assumption: string; assumptions: string[]
  }
  burden: {
    verdict: 'manageable' | 'tight' | 'dangerous'
    payment_share_of_take_home: number | null
    payment_share_of_gross_median_earnings_four_years_after_completion: number | null
    debt_to_median_earnings_four_years_after_completion: number | null
  }
  assumptions: {
    dependent_undergraduate: boolean; subsidized_fraction_of_federal_debt: number
    federal_rate: number; private_rate: number; term_months: number; years_in_school: number
    grace_months: number; disbursement_timing: string; interest_rates: string
    private_accrual: string; federal_limits: string; origination_fee: string
  }
  annual_limit_warnings: { academic_year: number; modeled_federal_principal: number; federal_annual_limit: number; modeled_subsidized_principal: number; subsidized_annual_limit: number }[]
  schedule: ScheduleRow[]
}

export interface ComparisonScenario {
  kind: 'in_state_public' | 'community_college_transfer' | 'same_school_different_major'
  label: string
  status: 'ready' | 'unavailable'
  message: string
  result: SchoolAnalysis | null
  assumptions: string[]
  annual_borrowing: number[]
  annual_tuition: number[]
  original_annual_tuition: number | null
  borrowing_reduction: number | null
}

export interface Analysis extends SchoolAnalysis {
  comparisons: ComparisonScenario[]
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(`/api${path}`, init) }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new Error('The estimate service could not be reached. Start the API server and try again.')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    throw new Error(typeof detail?.message === 'string' ? detail.message :
      response.status === 422 ? 'Some inputs are outside the supported range. Check your amounts and assumptions, then try again.' :
      'The estimate service could not return a result. Check that the API server is running and try again.')
  }
  if (!body) throw new Error('The estimate service returned an unreadable response. Restart the API server and try again.')
  return body as T
}
