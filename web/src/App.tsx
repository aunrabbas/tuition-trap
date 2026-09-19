import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from 'react'
import manifest from '../../seed/manifest.json'
import { apiRequest, type Analysis, type Major, type MajorsResponse } from './api'

export const money = (value: number, cents = false) => new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0,
}).format(value)
const rate = (value: number) => new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 3 }).format(value)
const percent = (value: number | null) => value === null ? 'Unavailable' : `${(value * 100).toFixed(1)}%`
const schools = manifest.schools
// Input defaults mirror core/constants.py and core/taxes.py; calculations stay on the server.
const defaults = { subsidized: '40', privateRate: '9', federalRate: '6.52', years: '4', term: '120', grace: '6', localRate: '3', dependent: true }

function AnimatedPayment({ value }: { value: number }) {
  const [shown, setShown] = useState(value)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setShown(value); return }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min((now - start) / 550, 1)
      setShown(value * (1 - (1 - progress) ** 3))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value])
  return <div className={`hero-number ${money(value).length > 8 ? 'hero-number-long' : ''}`} aria-label={`${money(value, true)} per month`}>
    <span aria-hidden="true">{money(shown)}</span>
  </div>
}

function BalanceChart({ result }: { result: Analysis }) {
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 700px)').matches)
  useEffect(() => {
    const media = window.matchMedia('(max-width: 700px)')
    const update = () => setNarrow(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  const width = narrow ? 440 : 880
  const right = width - 20
  const rows = [{ month: 0, remaining_balance: result.repayment_principal, cumulative_interest: 0 }, ...result.schedule]
  const max = Math.max(result.repayment_principal, result.repayment_interest, 1)
  const x = (month: number) => 70 + month / result.assumptions.term_months * (right - 70)
  const y = (value: number) => 216 - value / max * 180
  const path = (key: 'remaining_balance' | 'cumulative_interest') => rows.map((row, i) => `${i ? 'L' : 'M'}${x(row.month)},${y(row[key])}`).join(' ')
  return <figure className="balance-chart">
    <figcaption className="chart-legend flex flex-wrap gap-x-6 gap-y-2"><span><i className="legend-balance" />Remaining balance</span><span><i className="legend-interest" />Interest paid during repayment</span></figcaption>
    <svg viewBox={`0 0 ${width} 264`} role="img" aria-labelledby="chart-title chart-description">
      <title id="chart-title">Your balance and interest over repayment</title>
      <desc id="chart-description">Your balance starts at {money(result.repayment_principal)} and reaches zero after {result.assumptions.term_months} months. Cumulative interest paid during repayment reaches {money(result.repayment_interest)}. Exact monthly amounts are in the repayment details.</desc>
      {[0, 0.5, 1].map(fraction => <g key={fraction}><line x1="70" x2={right} y1={y(max * fraction)} y2={y(max * fraction)} className="chart-rule" /><text x="58" y={y(max * fraction) + 5} textAnchor="end">{new Intl.NumberFormat('en-US', { notation: 'compact', style: 'currency', currency: 'USD', maximumFractionDigits: 1 }).format(max * fraction)}</text></g>)}
      <path d={path('remaining_balance')} className="balance-line" />
      <path d={path('cumulative_interest')} className="interest-line" />
      <text x="70" y="249">Repayment begins</text><text x={right} y="249" textAnchor="end">Month {result.assumptions.term_months}</text>
    </svg>
  </figure>
}

function Results({ result }: { result: Analysis }) {
  const { allocation: a, assumptions: s, taxes: t, burden: b } = result
  const share = b.payment_share_of_take_home
  const fill = share === null ? 100 : Math.max(0, Math.min(100, share * 100))
  const verdictCopy = {
    manageable: 'Your payment and total debt fall within both lower burden benchmarks.',
    tight: 'Your payment or total debt reaches a caution range for your income.',
    dangerous: 'Your payment or total debt exceeds a high-burden benchmark for your income.',
  }
  return <article className={`results verdict-${b.verdict}`} aria-label="Your loan estimate">
    <section className="payment-section" aria-labelledby="payment-heading">
      <h2 id="payment-heading" className="sr-only">Your monthly payment</h2>
      <AnimatedPayment value={result.monthly_payment} />
      <p className="payment-duration">every month for {s.term_months === 120 ? 'ten years' : `${s.term_months} months`}</p>
      <p className="result-context">{result.school.name}<br />{result.major.title}</p>
      <div className="take-home-bar" style={{ '--fill': `${fill}%` } as CSSProperties} role="img" aria-label={`${money(result.monthly_payment, true)} payment out of ${money(t.monthly_take_home, true)} monthly take-home pay. ${share === null ? 'No take-home income is available.' : `${percent(share)} of take-home pay.`}`}>
        <div className="bar-track"><div className="bar-fill" /></div>
        <div className="bar-boundary"><span className={`bar-label ${fill < 15 ? 'near-start' : fill > 85 ? 'near-end' : ''}`}>{money(result.monthly_payment)}</span></div>
      </div>
      <p className="take-home-line"><strong className="take-home-percent">{percent(share)}</strong><span>of your take-home pay<br /><span className="figure">{money(result.monthly_payment)}</span> of an estimated <span className="figure">{money(t.monthly_take_home)}</span> each month</span></p>
      {share === null && <p className="notice">This program reports no earnings. A share of take-home pay cannot be calculated.</p>}
      {share !== null && share > 1 && <p className="notice">Your payment exceeds your estimated take-home pay. The bar represents one full month of income.</p>}
      <p className="earnings-note"><span className="figure">{money(result.median_earnings_four_years_after_completion)}</span> median annual earnings, four years after completion.<br />This is the income used for your estimate, not a starting-salary figure.</p>
    </section>

    <section className="repayment-section" aria-labelledby="verdict-heading">
      <h2 id="verdict-heading" className="verdict"><span className="capitalize">{b.verdict}</span> — {verdictCopy[b.verdict]}</h2>
      <p className="repayment-totals">Borrowed <span className="figure">{money(a.amount_borrowed)}</span><span className="totals-divider"> / </span>Total repaid <span className="figure">{money(result.total_repaid)}</span></p>
      <BalanceChart result={result} />
      <p>You enter repayment owing <span className="figure">{money(result.repayment_principal)}</span>, including <span className="figure">{money(result.capitalization.federal.accrued_interest + result.capitalization.private.accrued_interest)}</span> in interest accrued during school and grace. Over the full term, interest adds <span className="figure">{money(result.total_interest_including_capitalization)}</span> to what you borrowed.</p>
      {a.has_private_debt && <aside className="notice private-debt" aria-label="Private debt warning"><strong>Part of your borrowing is private debt.</strong><p>Your <span className="figure">{money(a.amount_borrowed)}</span> total exceeds the <span className="figure">{money(a.aggregate_federal_limit)}</span> federal aggregate limit. This estimate uses <span className="figure">{money(a.federal_principal)}</span> in federal loans at <span className="figure">{rate(s.federal_rate)}</span> and <span className="figure">{money(a.private_principal)}</span> in private loans at <span className="figure">{rate(s.private_rate)}</span>. You can adjust the private rate above.</p></aside>}
      {result.annual_limit_warnings.length > 0 && <aside className="notice"><strong>The annual federal limits also apply.</strong><p>The equal-year borrowing estimate exceeds an annual federal or subsidized limit in {result.annual_limit_warnings.length === 1 ? 'year' : 'years'} {result.annual_limit_warnings.map(w => w.academic_year).join(', ')}. Your actual private borrowing may be higher.</p></aside>}
      <details className="repayment-details">
        <summary>Repayment details and monthly schedule</summary>
        <div className="disclosure-content">
          <h3>What you receive, what you owe</h3>
          <dl className="detail-list"><div><dt>Amount borrowed</dt><dd>{money(a.amount_borrowed, true)}</dd></div><div><dt>Estimated federal origination fee</dt><dd>{money(a.origination_fee_estimate, true)}</dd></div><div><dt>Estimated amount disbursed to you</dt><dd>{money(a.net_disbursed_estimate, true)}</dd></div><div><dt>Balance when repayment begins</dt><dd>{money(result.repayment_principal, true)}</dd></div></dl>
          <p>The federal fee is <span className="figure">{rate(a.federal_principal ? a.origination_fee_estimate / a.federal_principal : 0)}</span> of federal borrowing and is deducted before disbursement; you still owe the full face amount. {s.origination_fee}</p>
          {result.annual_limit_warnings.map(w => <p key={w.academic_year}>Year {w.academic_year}: federal borrowing {money(w.modeled_federal_principal)} against a {money(w.federal_annual_limit)} annual limit; subsidized borrowing {money(w.modeled_subsidized_principal)} against a {money(w.subsidized_annual_limit)} sub-limit.</p>)}
          <div className="table-scroll" tabIndex={0} role="region" aria-label="Monthly repayment schedule, scroll horizontally to view all columns">
            <table className="schedule-table"><caption>Monthly repayment schedule. Figures rounded to cents for display.</caption><thead><tr><th scope="col">Month</th><th scope="col">Payment</th><th scope="col">Interest</th><th scope="col">Principal</th><th scope="col">Balance</th><th scope="col">Interest to date</th></tr></thead><tbody>{result.schedule.map(row => <tr key={row.month}><th scope="row">{row.month}</th><td>{money(row.payment, true)}</td><td>{money(row.interest_portion, true)}</td><td>{money(row.principal_portion, true)}</td><td>{money(row.remaining_balance, true)}</td><td>{money(row.cumulative_interest, true)}</td></tr>)}</tbody></table>
          </div>
        </div>
      </details>
    </section>

    <section className="section" aria-labelledby="alternatives-heading">
      <h2 id="alternatives-heading">Compare your paths</h2>
      <p>Alternative estimates are not available yet. No savings are assumed.</p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Path comparison, scroll horizontally to view all columns"><table className="comparison-table"><caption className="sr-only">Your estimate and availability of alternative paths</caption><thead><tr><th scope="col">Path</th><th scope="col">Monthly payment</th><th scope="col">Take-home share</th><th scope="col">Total repaid</th><th scope="col">Verdict</th></tr></thead><tbody><tr><th scope="row">Your selection</th><td>{money(result.monthly_payment)}</td><td>{percent(share)}</td><td>{money(result.total_repaid)}</td><td className="capitalize">{b.verdict}</td></tr>{result.comparisons.map(item => <tr key={item.kind}><th scope="row">{item.label}</th><td colSpan={4} className="unavailable">Estimate unavailable</td></tr>)}</tbody></table></div>
    </section>

    <section className="section assumptions" aria-labelledby="assumptions-heading">
      <h2 id="assumptions-heading">What this estimate assumes</h2>
      <h3>Your income and take-home pay</h3>
      <p>College Scorecard reports median earnings for graduates who took federal student loans. These figures are four years after completion; your earnings may differ. Programs without reported earnings are excluded from the selector.</p>
      <p>{t.tax_year} taxes, single filer, <span className="figure">{money(t.standard_deduction)}</span> standard deduction. Pennsylvania income tax and <span className="figure">{rate(t.local_tax_rate)}</span> local earned income tax ({t.local_tax_assumption}).</p>
      <dl className="detail-list tax-list"><div><dt>Annual gross earnings</dt><dd>{money(result.median_earnings_four_years_after_completion, true)}</dd></div><div><dt>Federal income tax</dt><dd>{money(t.federal_income_tax, true)}</dd></div><div><dt>Social Security and Medicare</dt><dd>{money(t.social_security_tax + t.medicare_tax, true)}</dd></div><div><dt>Pennsylvania income tax</dt><dd>{money(t.pennsylvania_income_tax, true)}</dd></div><div><dt>Local earned income tax</dt><dd>{money(t.local_earned_income_tax, true)}</dd></div><div><dt>Estimated monthly take-home</dt><dd>{money(t.monthly_take_home, true)}</dd></div></dl>
      <p>No tax credits or benefit deductions. Base FICA only; additional Medicare surtax, Pennsylvania tax forgiveness, and local services tax are excluded.</p>
      <h3>Your borrowing</h3>
      <p>{s.dependent_undergraduate ? 'Dependent' : 'Independent'} undergraduate; {s.years_in_school} years in school; {s.grace_months} months of grace; {s.term_months} monthly payments. Fixed federal rate <span className="figure">{rate(s.federal_rate)}</span>; private rate <span className="figure">{rate(s.private_rate)}</span>.</p>
      <p>Requested subsidized share: <span className="figure">{percent(s.subsidized_fraction_of_federal_debt)}</span> of federal borrowing. Effective share after the cap: <span className="figure">{percent(a.effective_subsidized_fraction)}</span> (<span className="figure">{money(a.subsidized_principal)}</span> subsidized, <span className="figure">{money(a.unsubsidized_principal)}</span> unsubsidized).</p>
      <p>{s.disbursement_timing} {s.interest_rates} Subsidized loans accrue no interest during enrollment or grace in this model. Unsubsidized interest accrues simply and capitalizes at repayment.</p>
      <p>Private loans: {s.private_accrual}</p>
      <h3>How the verdict is decided</h3>
      <p>Your payment is <span className="figure">{percent(b.payment_share_of_gross_median_earnings_four_years_after_completion)}</span> of gross monthly income. Your repayment-start debt is <span className="figure">{b.debt_to_median_earnings_four_years_after_completion === null ? 'unavailable as a multiple of' : `${b.debt_to_median_earnings_four_years_after_completion.toFixed(2)} times`}</span> annual median earnings.</p>
      <p>Payment below 8% of gross income is manageable; 8–15% is tight; above 15% is dangerous. Debt below 1 times annual earnings is manageable; 1–1.5 times is tight; above 1.5 times is dangerous. The worse benchmark sets your verdict. The headline percentage uses take-home pay.</p>
      <p>These benchmarks conventionally use starting income. This estimate uses the available four-year earnings instead, which may understate the burden at graduation.</p>
    </section>
  </article>
}

export default function App() {
  const [schoolId, setSchoolId] = useState(String(schools[0].id))
  const [majors, setMajors] = useState<Major[]>([])
  const [majorCode, setMajorCode] = useState('')
  const [amount, setAmount] = useState('80000')
  const [options, setOptions] = useState(defaults)
  const [loadingMajors, setLoadingMajors] = useState(true)
  const [majorsError, setMajorsError] = useState('')
  const [coverageMessage, setCoverageMessage] = useState('')
  const [reload, setReload] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<Analysis | null>(null)
  const [resultId, setResultId] = useState(0)
  const requestRef = useRef<AbortController | null>(null)
  const school = schools.find(item => String(item.id) === schoolId)!

  function invalidate() { requestRef.current?.abort(); setBusy(false); setResult(null); setError('') }

  useEffect(() => {
    const controller = new AbortController()
    setLoadingMajors(true); setMajors([]); setMajorCode(''); setMajorsError(''); setCoverageMessage('')
    apiRequest<MajorsResponse>(`/schools/${schoolId}/majors?credential_level=${school.demo_credential_level}`, { signal: controller.signal })
      .then(data => {
        if (controller.signal.aborted) return
        const available = data.majors.filter(major => Number.isFinite(major.median_earnings_four_years_after_completion))
        setMajors(available); setCoverageMessage(data.message || 'No programs with reported earnings are available at this school. Choose another school.')
      })
      .catch(error => { if (!controller.signal.aborted) setMajorsError(error.message) })
      .finally(() => { if (!controller.signal.aborted) setLoadingMajors(false) })
    return () => controller.abort()
  }, [schoolId, school.demo_credential_level, reload])
  useEffect(() => () => requestRef.current?.abort(), [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!majorCode || loadingMajors) return
    requestRef.current?.abort()
    const controller = new AbortController(); requestRef.current = controller
    setBusy(true); setError(''); setResult(null)
    try {
      const data = await apiRequest<Analysis>('/analyze', {
        method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ school_id: Number(schoolId), major: { code: majorCode, credential_level: school.demo_credential_level }, loan_amount: Number(amount), overrides: {
          subsidized_fraction: Number(options.subsidized) / 100, private_rate: Number(options.privateRate) / 100,
          federal_rate: Number(options.federalRate) / 100, dependent: options.dependent, term_months: Number(options.term),
          years_in_school: Number(options.years), grace_months: Number(options.grace), local_tax_rate: Number(options.localRate) / 100,
        } }),
      })
      if (!controller.signal.aborted) { setResult(data); setResultId(id => id + 1) }
    } catch (error) { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'Your estimate failed. Try again.') }
    finally { if (!controller.signal.aborted) setBusy(false) }
  }

  const optionFields = [
    { key: 'subsidized', label: 'Subsidized share of federal loans (%)', min: 0, max: 100, step: 'any' },
    { key: 'privateRate', label: 'Private interest rate (%)', min: 0, max: 100, step: 'any' },
    { key: 'federalRate', label: 'Federal interest rate (%)', min: 0, max: 100, step: 'any' },
    { key: 'years', label: 'Years in school', min: 1, max: 20, step: '1' },
    { key: 'term', label: 'Repayment term (months)', min: 1, max: 600, step: '1' },
    { key: 'grace', label: 'Grace period (months)', min: 0, max: 120, step: 'any' },
    { key: 'localRate', label: 'Local earned income tax (%)', min: 0, max: 100, step: 'any' },
  ] as const

  return <>
    <a className="skip-link" href="#main">Skip to estimate</a>
    <header className="site-header flex flex-wrap items-baseline justify-between gap-2"><h1>Tuition Trap</h1><p>The cost after college.</p></header>
    <main id="main">
      <form onSubmit={submit} className="estimate-form" aria-label="Loan estimate inputs">
        <div className="primary-inputs">
          <label>School<select value={schoolId} onChange={event => { invalidate(); setSchoolId(event.target.value); const selected = schools.find(s => String(s.id) === event.target.value)!; setOptions(old => ({ ...old, years: selected.demo_credential_level === 2 ? '2' : '4' })) }}>{schools.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>Intended major<select value={majorCode} onChange={event => { invalidate(); setMajorCode(event.target.value) }} disabled={loadingMajors || !majors.length} required aria-describedby="major-status"><option value="">{loadingMajors ? 'Loading available majors…' : majors.length ? 'Choose a major' : 'No majors available'}</option>{majors.map(major => <option key={major.code} value={major.code}>{major.title}</option>)}</select></label>
          <label>Total loan amount ($)<input type="number" inputMode="decimal" min="0" max="1000000000000" step="0.01" required value={amount} onChange={event => { invalidate(); setAmount(event.target.value) }} /></label>
        </div>
        <div id="major-status" className="form-status" aria-live="polite">{loadingMajors ? 'Loading programs with reported earnings.' : majorsError ? <span role="alert">{majorsError} <button type="button" className="text-button" onClick={() => setReload(value => value + 1)}>Retry loading majors</button></span> : !majors.length ? coverageMessage : `${majors.length} ${school.demo_credential_level === 2 ? 'associate' : "bachelor’s"} programs with reported earnings. Select the program you plan to complete.`}</div>
        <details className="input-assumptions"><summary>Adjust borrowing and tax assumptions</summary><div className="options-grid">{optionFields.map(field => <label key={field.key}>{field.label}<input type="number" required inputMode="decimal" min={field.min} max={field.max} step={field.step} value={options[field.key]} onChange={event => { invalidate(); setOptions(old => ({ ...old, [field.key]: event.target.value })) }} /></label>)}<label>Undergraduate status<select value={options.dependent ? 'dependent' : 'independent'} onChange={event => { invalidate(); setOptions(old => ({ ...old, dependent: event.target.value === 'dependent' })) }}><option value="dependent">Dependent</option><option value="independent">Independent</option></select></label></div></details>
        <div className="form-action flex flex-wrap items-center gap-4"><button className="submit-button" type="submit" disabled={busy || loadingMajors || !majorCode}>{busy ? 'Calculating…' : 'See your payment'}</button><p>{options.years} years in school. {options.term} monthly payments. Single filer in Pennsylvania.</p></div>
      </form>
      <div aria-live="polite" className="sr-only">{busy ? 'Calculating your estimate.' : result?.state === 'ready' ? `Estimate ready. Monthly payment ${money(result.monthly_payment, true)}. Verdict: ${result.burden.verdict}.` : ''}</div>
      {error && <p role="alert" className="notice error-message">{error}</p>}
      {result?.state === 'ready' ? <Results key={resultId} result={result} /> : <section className="empty-state" aria-live="polite"><h2>{busy ? 'Calculating your payment.' : result?.state === 'empty' ? 'Start with the amount you expect to borrow.' : 'See what your loan asks of you.'}</h2><p>{result?.message || (busy ? 'Your estimate uses the school’s locally stored earnings data.' : 'Choose your school and major, enter your total borrowing, then select “See your payment.”')}</p></section>}
    </main>
    <footer className="site-footer"><p>Source: U.S. Department of Education College Scorecard. School and program data are stored locally for this estimate.</p><p>Estimates use the stated assumptions. They are not a loan offer or a guarantee of earnings.</p></footer>
  </>
}
