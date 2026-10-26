import React, { useEffect, useState } from 'react'
import { ArrowRight, FileText, RefreshCw, Search, ShieldCheck, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { SplitText } from '../components/motion/SplitText'
import { Magnetic } from '../components/motion/Magnetic'
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
      <section className="relative w-full overflow-hidden pt-2 sm:pt-4 pb-12 sm:pb-16 min-h-[440px] lg:min-h-[480px] flex items-center">
        {/* Absolute Composited Hero Video Layer */}
        <div
          className="hero-video-layer absolute inset-y-0 right-0 w-full sm:w-[85%] md:w-[74%] lg:w-[65%] max-w-[1100px] h-full pointer-events-none select-none z-0"
          aria-hidden="true"
        >
          <HeroVideo className="w-full h-full opacity-40 sm:opacity-80 lg:opacity-100 transition-opacity duration-500" />
        </div>

        {/* Left Hero Typographic Content & Primary Actions */}
        <div className="relative z-10 max-w-xl lg:max-w-2xl space-y-6">
          <div className="overflow-visible pr-2">
            {hasResume ? (
              <h1 className="text-[clamp(2.5rem,5.5vw,4.5rem)] font-semibold tracking-tight leading-[1.02] text-text">
                Welcome back,{' '}
                <span className="font-editorial italic font-normal text-text inline-block pr-1">
                  {candidate?.display_name || 'Candidate'}.
                </span>
              </h1>
            ) : (
              <SplitText
                text="Your next role, in focus."
                accentWords={['focus.']}
                className="text-[clamp(2.75rem,6.5vw,5rem)] font-semibold tracking-tight leading-[1.0] text-text"
              />
            )}
          </div>

          <p className="page-intro max-w-lg lg:max-w-xl text-text-2 text-[15px] sm:text-[16px] leading-relaxed">
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
      </section>

      {/* Error Notice */}
      {error && (
        <div className="border border-border/80 bg-bg-elev-1/60 p-4 rounded-xl text-[13px] text-text-2 flex items-center gap-3">
          <AlertCircle className="w-4 h-4 shrink-0 text-text-3" />
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

        {/* Unboxed Architectural Layout: Metric Showcase + Row Pipeline */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
          {/* Left: Confirmed Metric Showcase — Open Typographic Presentation */}
          <div className="lg:col-span-5 space-y-6">
            <div className="flex items-center justify-between border-b border-border/40 pb-3">
              <span className="text-xs uppercase tracking-wider text-text-3 font-medium">
                Verified Outcomes
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono text-text-3 border border-border/60">
                <CheckCircle2 className="w-3 h-3 opacity-70" />
                Independently confirmed
              </span>
            </div>

            <div className="pt-2">
              <p className="text-xs text-text-3 uppercase tracking-wider font-mono">
                Confirmed applications
              </p>
              <div className="mt-2 flex items-baseline gap-3">
                <span
                  data-testid="metric-confirmed-value"
                  className="text-6xl lg:text-7xl font-semibold tracking-tighter text-text tabular-nums"
                >
                  {confirmedCount}
                </span>
                <span className="text-sm text-text-3 font-mono">portal records</span>
              </div>
            </div>

            <p className="text-xs text-text-3 leading-relaxed pt-4 border-t border-border/40">
              Only submissions verified by independent portal evidence. Never synthetic.
            </p>
          </div>

          {/* Right Rail: Sleek Row-Based Pipeline with Hairline Dividers */}
          <div className="lg:col-span-7 divide-y divide-border/60 border-y border-border/60">
            {/* Needs Action / Review Row */}
            <div className="py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 group transition-colors">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-text-3" strokeWidth={1.5} />
                  <span className="text-sm font-semibold text-text">Awaiting Review</span>
                </div>
                <p className="text-xs text-text-3">
                  Applications verified and ready for your sign-off.
                </p>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <span className="text-2xl font-semibold text-text tabular-nums font-mono">
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
            </div>

            {/* Opportunities Row */}
            <div className="py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 group transition-colors">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Search className="w-4 h-4 text-text-3" strokeWidth={1.5} />
                  <span className="text-sm font-semibold text-text">Suitable Opportunities</span>
                </div>
                <p className="text-xs text-text-3">
                  Discovered postings that meet your current suitability floor.
                </p>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <span className="text-2xl font-semibold text-text tabular-nums font-mono">
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
            </div>

            {/* Pending Audit Confirmation */}
            <div className="py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 group transition-colors">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-text-3" strokeWidth={1.5} />
                  <span className="text-sm font-semibold text-text">Sent, Pending Confirmation</span>
                </div>
                <p className="text-xs text-text-3">
                  Transmitted packages awaiting confirmation webhook or portal polling.
                </p>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <span className="text-2xl font-semibold text-text tabular-nums font-mono">
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
            </div>
          </div>
        </div>
      </section>

      {/* Safety & Provenance Integrity Notice — Unboxed Footer Strip */}
      <section className="pt-8 border-t border-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 text-text-3">
        <div className="flex items-start gap-3 max-w-2xl">
          <ShieldCheck className="w-4 h-4 text-text-2 shrink-0 mt-0.5" strokeWidth={1.5} />
          <div className="space-y-1">
            <h3 className="text-sm font-medium text-text">
              Engineered with strict candidate provenance
            </h3>
            <p className="text-xs text-text-3 leading-relaxed">
              Every field in every tailored resume maps to an active candidate fact. No hallucinated experience, no fabricated confirmation. Submissions are gated until explicitly approved.
            </p>
          </div>
        </div>

        <button
          onClick={() => onNavigate('tracker')}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-text-2 hover:text-text transition-colors shrink-0 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded"
        >
          <span>View event audit trail</span>
          <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
        </button>
      </section>
    </div>
  )
}
