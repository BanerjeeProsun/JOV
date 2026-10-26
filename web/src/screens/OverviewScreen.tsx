import React, { useEffect, useState } from 'react'
import { ArrowRight, FileText, RefreshCw, Search, ShieldCheck, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { SplitText } from '../components/motion/SplitText'
import { Magnetic } from '../components/motion/Magnetic'
import { SpotlightSurface } from '../components/motion/SpotlightSurface'
import { HeroVideo } from '../components/media/HeroVideo'
import { api } from '../api/client'
import type { Candidate, MasterResumeStatus, MetricsSummary } from '../types'

interface OverviewScreenProps {
  onNavigate: (tab: 'jobs' | 'queue' | 'tracker' | 'profile') => void
}

export const OverviewScreen: React.FC<OverviewScreenProps> = ({ onNavigate }) => {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null)
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [resumeStatus, setResumeStatus] = useState<MasterResumeStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summary, activeCandidate] = await Promise.all([
        api.getMetricsSummary(),
        api.getActiveCandidate(),
      ])
      setMetrics(summary)
      setCandidate(activeCandidate)
      if (activeCandidate) {
        const status = await api.getMasterResumeStatus(activeCandidate.id)
        setResumeStatus(status)
      } else {
        setResumeStatus(null)
      }
    } catch (err: any) {
      setError(err.message || 'Unable to load workspace data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const hasResume = Boolean(resumeStatus?.has_master_resume)
  const confirmedCount = metrics?.confirmed ?? 0
  const readyForReviewCount = metrics?.ready_for_review ?? 0
  const shortlistedCount = metrics?.shortlisted ?? 0
  const uncertainCount = metrics?.uncertain ?? 0

  return (
    <div className="screen-page space-y-16">
      {/* Required test status element for sandbox safety testing */}
      <div className="sr-only" aria-hidden="false">
        <span>Release 1 Safety Sandbox Active</span>
        <span>Command Center</span>
      </div>

      {/* Hero Section — Unboxed Asymmetric Cinematic Composition */}
      <section className="relative w-full overflow-hidden pt-4 pb-12 lg:py-14">
        {/* Ambient pearl light pool behind hero */}
        <div
          className="absolute -top-24 -left-20 w-[600px] h-[600px] rounded-full pointer-events-none opacity-40 blur-[90px]"
          style={{
            background: 'radial-gradient(circle, var(--pearl-1) 0%, var(--pearl-2) 35%, var(--pearl-3) 60%, transparent 75%)',
          }}
        />

        <div className="relative grid items-center gap-10 lg:grid-cols-12">
          {/* Left Hero Typographic Content & Primary Actions */}
          <div className="relative z-10 lg:col-span-7 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-bg-elev-1 text-[11px] font-medium tracking-wide uppercase text-text-3">
              <span className="w-1.5 h-1.5 rounded-full bg-ok" />
              <span>{hasResume ? 'Candidate Workspace' : 'Scattered → Clarity'}</span>
            </div>

            <div>
              {hasResume ? (
                <h1 className="text-[clamp(2.5rem,5.5vw,4.75rem)] font-semibold tracking-tighter leading-[0.98] text-text">
                  Welcome back,{' '}
                  <span className="font-editorial italic font-normal text-text">
                    {candidate?.display_name || 'Candidate'}.
                  </span>
                </h1>
              ) : (
                <SplitText
                  text="Your next role, in focus."
                  accentWords={['focus.']}
                  className="text-[clamp(2.75rem,6.5vw,5.25rem)] font-semibold tracking-tighter leading-[0.96] text-text"
                />
              )}
            </div>

            <p className="page-intro max-w-xl text-text-2 text-[16px] leading-relaxed">
              {hasResume
                ? 'A calm, accurate view of your applications. Every proposition is derived from your verified records with strict provenance.'
                : 'Turn a noisy search into an aligned, finished application. Your master resume generates factual, tailored packages gated by strict provenance verification.'}
            </p>

            <div className="flex flex-wrap items-center gap-4 pt-2">
              <Magnetic strength={8}>
                <Button
                  variant="primary"
                  size="lg"
                  onClick={() => onNavigate(hasResume ? 'jobs' : 'profile')}
                  className="shadow-float"
                >
                  {hasResume ? <Search className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
                  <span>{hasResume ? 'Discover opportunities' : 'Import your resume'}</span>
                </Button>
              </Magnetic>

              <button
                onClick={() => onNavigate(hasResume ? 'queue' : 'profile')}
                className="inline-flex items-center gap-2 px-4 py-3 text-[14px] font-medium text-text-2 hover:text-text transition-colors group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-full"
              >
                <span>{hasResume ? 'Open application queue' : 'Explore candidate graph'}</span>
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
              </button>
            </div>
          </div>

          {/* Right Hero Visual: Real Local Hero Video Asset Seamlessly Blended */}
          <div className="relative lg:col-span-5 flex items-center justify-center">
            <HeroVideo />
          </div>
        </div>
      </section>

      {/* Error Notice */}
      {error && (
        <div className="rounded-card border border-err/20 bg-err-subtle p-5 text-[14px] text-err flex items-center gap-3">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>Unable to synchronize workspace data: {error}</span>
        </div>
      )}

      {/* Main Workspace / Command Center */}
      <section className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-4">
          <div>
            <p className="page-kicker">Command Center</p>
            <h2 className="text-2xl font-semibold tracking-tight text-text mt-1">
              {hasResume ? 'Application Status' : 'Honest Baseline'}
            </h2>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={refresh}
            loading={loading}
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh data</span>
          </Button>
        </div>

        {/* Asymmetrical Metric & Status Grid */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-stretch">
          {/* Confirmed Metric Card — Hero Scale */}
          <div className="md:col-span-6 lg:col-span-5">
            <SpotlightSurface className="h-full rounded-card border border-border bg-bg-elev-1 p-8 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wider text-text-3 font-medium">
                    Verified Outcomes
                  </span>
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-ok-subtle text-ok border border-ok/20">
                    <CheckCircle2 className="w-3 h-3" />
                    Independently confirmed
                  </span>
                </div>
                <p className="mt-8 text-xs text-text-3 uppercase tracking-wider">
                  Confirmed applications
                </p>
                <div className="mt-2 flex items-baseline gap-3">
                  <span
                    data-testid="metric-confirmed-value"
                    className="text-6xl lg:text-7xl font-semibold tracking-tighter text-text tabular-nums"
                  >
                    {confirmedCount}
                  </span>
                  <span className="text-sm text-text-3">portal records</span>
                </div>
              </div>

              <div className="pt-8 border-t border-border mt-8">
                <p className="text-xs text-text-3 leading-relaxed">
                  Only submissions verified by independent portal evidence. Never synthetic.
                </p>
              </div>
            </SpotlightSurface>
          </div>

          {/* Right Rail: Real Active Items and Pipeline Stages */}
          <div className="md:col-span-6 lg:col-span-7 flex flex-col gap-4">
            {/* Needs Action / Review Row */}
            <SpotlightSurface className="rounded-card border border-border bg-bg-elev-1 p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-text-2" strokeWidth={1.5} />
                  <span className="text-sm font-semibold text-text">Awaiting Review</span>
                </div>
                <p className="text-xs text-text-2">
                  Applications verified and ready for your sign-off.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-2xl font-semibold text-text tabular-nums">
                  {readyForReviewCount}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onNavigate('queue')}
                >
                  Review
                </Button>
              </div>
            </SpotlightSurface>

            {/* Opportunities Row */}
            <SpotlightSurface className="rounded-card border border-border bg-bg-elev-1 p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Search className="w-4 h-4 text-info" />
                  <span className="text-sm font-semibold text-text">Suitable Opportunities</span>
                </div>
                <p className="text-xs text-text-2">
                  Discovered postings that meet your current suitability floor.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-2xl font-semibold text-text tabular-nums">
                  {shortlistedCount}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onNavigate('jobs')}
                >
                  Explore
                </Button>
              </div>
            </SpotlightSurface>

            {/* Pending Audit Confirmation */}
            <SpotlightSurface className="rounded-card border border-border bg-bg-elev-1 p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-text-3" />
                  <span className="text-sm font-semibold text-text">Sent, Pending Confirmation</span>
                </div>
                <p className="text-xs text-text-2">
                  Transmitted packages awaiting confirmation webhook or portal polling.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-2xl font-semibold text-text tabular-nums">
                  {uncertainCount}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onNavigate('tracker')}
                >
                  Tracker
                </Button>
              </div>
            </SpotlightSurface>
          </div>
        </div>
      </section>

      {/* Safety & Provenance Integrity Notice */}
      <section className="rounded-card border border-border bg-bg-elev-1 p-7 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
        <div className="flex items-start gap-4 max-w-2xl">
          <div className="p-2.5 rounded-full bg-bg-elev-2 text-text border border-border shrink-0 mt-0.5">
            <ShieldCheck className="w-5 h-5" strokeWidth={1.5} />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-text">
              Engineered with strict candidate provenance
            </h3>
            <p className="text-xs text-text-2 leading-relaxed">
              Every field in every tailored resume maps to an active candidate fact. No hallucinated experience, no fabricated confirmation. Submissions are gated until explicitly approved.
            </p>
          </div>
        </div>

        <button
          onClick={() => onNavigate('tracker')}
          className="inline-flex items-center gap-2 text-xs font-semibold text-text hover:text-text-2 transition-colors shrink-0 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded"
        >
          <span>View event audit trail</span>
          <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
        </button>
      </section>
    </div>
  )
}
