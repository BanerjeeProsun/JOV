import React, { useEffect, useState } from 'react'
import { ArrowRight, FileText, RefreshCw, Search, ShieldCheck } from 'lucide-react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { AmbientBackdrop } from '../components/AmbientBackdrop'
import { motion, useReducedMotion } from 'motion/react'
import { api } from '../api/client'
import type { Candidate, MasterResumeStatus, MetricsSummary } from '../types'

interface OverviewScreenProps { onNavigate: (tab: 'jobs' | 'queue' | 'tracker' | 'profile') => void }

export const OverviewScreen: React.FC<OverviewScreenProps> = ({ onNavigate }) => {
  const reducedMotion = useReducedMotion()
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null)
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [resumeStatus, setResumeStatus] = useState<MasterResumeStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true); setError(null)
    try {
      const [summary, activeCandidate] = await Promise.all([api.getMetricsSummary(), api.getActiveCandidate()])
      setMetrics(summary); setCandidate(activeCandidate)
      setResumeStatus(activeCandidate ? await api.getMasterResumeStatus(activeCandidate.id) : null)
    } catch (err: any) { setError(err.message || 'Unable to load workspace data.') }
    finally { setLoading(false) }
  }
  useEffect(() => { refresh() }, [])
  const hasResume = Boolean(resumeStatus?.has_master_resume)
  const cards = [
    ['Suitable opportunities', metrics?.shortlisted ?? 0, 'Roles that meet your current suitability floor.'],
    ['Awaiting review', metrics?.ready_for_review ?? 0, 'Prepared packages that need your decision.'],
    ['Confirmed applications', metrics?.confirmed ?? 0, 'Only submissions verified with portal evidence.'],
    ['Sent, not confirmed', metrics?.uncertain ?? 0, 'Submissions waiting for independent confirmation.'],
  ]

  return <div className="screen-page space-y-12">
    <section className="relative grid min-h-[440px] items-end gap-12 overflow-hidden rounded-card lg:grid-cols-[1fr_.8fr]">
      {!hasResume && <AmbientBackdrop />}
      <motion.div initial={reducedMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, ease: [.22, 1, .36, 1] }} className="relative pb-4 pl-2 md:pl-6">
        <p className="page-kicker">{hasResume ? 'Candidate workspace' : 'A considered application process'}</p>
        <h1 className="page-title max-w-3xl">{hasResume ? `Welcome back${candidate?.display_name ? `, ${candidate.display_name}` : ''}.` : 'Your next opportunity starts here.'}</h1>
        <p className="page-intro">{hasResume ? 'A quiet, accurate view of the work that needs your attention. Every result is derived from your saved records.' : 'Import your master resume. Discover relevant opportunities. Create an application tailored to every role.'}</p>
        <div className="mt-7 flex flex-wrap items-center gap-3">
          <Button variant="primary" size="lg" onClick={() => onNavigate(hasResume ? 'jobs' : 'profile')}>{hasResume ? <Search className="h-4 w-4" /> : <FileText className="h-4 w-4" />}{hasResume ? 'Discover opportunities' : 'Import master resume'}</Button>
          <button onClick={() => onNavigate(hasResume ? 'queue' : 'profile')} className="inline-flex items-center gap-1.5 px-2 py-3 text-[15px] text-link-blue">{hasResume ? 'Open application queue' : 'Explore how it works'}<ArrowRight className="h-3.5 w-3.5" /></button>
        </div>
      </motion.div>
      <motion.div initial={reducedMotion ? false : { opacity: 0, scale: .94 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: .7, delay: .12, ease: [.22, 1, .36, 1] }} className="relative hidden min-h-[360px] items-center justify-center lg:flex" aria-hidden="true">
        <div className="absolute h-64 w-64 rounded-full border-[18px] border-white" />
        <div className="absolute h-44 w-44 rounded-full border border-[#d6d6d6]" />
        <div className="relative flex h-28 w-28 items-center justify-center rounded-card bg-white"><span className="font-display text-[44px] font-semibold tracking-[-.04em]">J</span></div>
      </motion.div>
    </section>

    {error && <div className="rounded-apple-md bg-danger-subtle px-5 py-4 text-[14px] text-danger-red">Unable to load workspace: {error}</div>}

    {hasResume ? <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="page-kicker">Command Center</p><h2 className="font-display text-[32px] font-semibold leading-[1.19] tracking-[-.005em]">What matters now.</h2></div><Button variant="secondary" size="sm" onClick={refresh} loading={loading}><RefreshCw className="h-3.5 w-3.5" />Refresh</Button></div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([label, value, description], index) => <Card key={String(label)} className="min-h-[180px] p-7" style={{ animationDelay: `${index * 55}ms` }}><p className="text-[13px] text-text-secondary">{label}</p><p data-testid={label === 'Confirmed applications' ? 'metric-confirmed-value' : undefined} className="mt-7 font-display text-[44px] font-semibold leading-none tracking-[-.03em]">{value}</p><p className="mt-5 text-[13px] leading-5 text-text-tertiary">{description}</p></Card>)}</div>
    </section> : <><section className="grid gap-4 md:grid-cols-3">
      <Card><p className="page-kicker">01</p><h2 className="mt-6 font-display text-[28px] font-semibold leading-[1.14]">Import with provenance.</h2><p className="mt-3 text-[15px] text-text-secondary">Your document is parsed into facts that remain visible and reviewable.</p></Card>
      <Card><p className="page-kicker">02</p><h2 className="mt-6 font-display text-[28px] font-semibold leading-[1.14]">Choose real roles.</h2><p className="mt-3 text-[15px] text-text-secondary">Search live feeds or import a posting you have found yourself.</p></Card>
      <Card><p className="page-kicker">03</p><h2 className="mt-6 font-display text-[28px] font-semibold leading-[1.14]">Approve exactly what is sent.</h2><p className="mt-3 text-[15px] text-text-secondary">Every tailored package passes a 15-point gate before review.</p></Card>
    </section><div className="flex items-center justify-between rounded-card bg-white px-7 py-5"><div><p className="page-kicker">Command Center</p><p className="mt-1 text-[14px] text-text-secondary">Your activity will appear here once you begin.</p></div><div className="text-right"><p className="text-[12px] text-text-tertiary">Confirmed applications</p><p data-testid="metric-confirmed-value" className="font-display text-[28px] font-semibold leading-none">{metrics?.confirmed ?? 0}</p></div></div></>}

    <section className="flex flex-col gap-5 rounded-card bg-ash p-7 md:flex-row md:items-center md:justify-between"><div className="flex max-w-2xl gap-3"><ShieldCheck className="mt-1 h-5 w-5 shrink-0" /><div><h2 className="font-semibold">Designed to keep the candidate in control.</h2><p className="mt-1 text-[14px] text-text-secondary">No activity is invented; confirmed is reserved for independently verified submissions.</p></div></div><button onClick={() => onNavigate('tracker')} className="shrink-0 text-[15px] text-link-blue">View application history <ArrowRight className="ml-1 inline h-3.5 w-3.5" /></button></section>
  </div>
}
