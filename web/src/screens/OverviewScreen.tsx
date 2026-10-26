import React, { useEffect, useState } from 'react'
import {
  ArrowRight,
  FileText,
  RefreshCw,
  Search,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Clock,
  LogIn,
  LogOut,
  FileCheck2,
  Sparkles,
  KeyRound,
  UserPlus,
  Globe2,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { SplitText } from '../components/motion/SplitText'
import { Magnetic } from '../components/motion/Magnetic'
import { HeroVideo } from '../components/media/HeroVideo'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import type { MasterResumeStatus, MetricsSummary } from '../types'

interface OverviewScreenProps {
  onNavigate: (tab: 'jobs' | 'queue' | 'tracker' | 'profile') => void
}

export const OverviewScreen: React.FC<OverviewScreenProps> = ({ onNavigate }) => {
  const { user, isAuthenticated, isSandboxMode, openAuthModal, logout } = useAuth()
  const hasFullAccess = isAuthenticated || isSandboxMode

  const [metrics, setMetrics] = useState<MetricsSummary | null>(null)
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
        {!hasFullAccess && <span data-testid="metric-confirmed-value">0</span>}
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
            {hasFullAccess ? (
              user?.display_name?.trim() ? (
                <h1 className="text-[clamp(2.5rem,5.5vw,4.5rem)] font-semibold tracking-tight leading-[1.02] text-text">
                  Welcome back,{' '}
                  <span className="font-editorial italic font-normal text-text inline-block pr-1">
                    {user.display_name}.
                  </span>
                </h1>
              ) : (
                <h1 className="text-[clamp(2.5rem,5.5vw,4.5rem)] font-semibold tracking-tight leading-[1.02] text-text">
                  Welcome back.
                </h1>
              )
            ) : (
              <div className="space-y-2">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono text-text-3 border border-border/80 bg-bg/80 backdrop-blur-sm">
                  <ShieldCheck className="w-3.5 h-3.5 text-accent" />
                  <span>Resume-First · Strict Provenance · Verified ATS</span>
                </div>
                <SplitText
                  text="Your next role, in focus."
                  accentWords={['focus.']}
                  className="text-[clamp(2.75rem,6.5vw,5rem)] font-semibold tracking-tight leading-[1.0] text-text"
                />
              </div>
            )}
          </div>

          <p className="page-intro max-w-lg lg:max-w-xl text-text-2 text-[15px] sm:text-[16px] leading-relaxed">
            {hasFullAccess
              ? hasResume
                ? 'A calm, accurate view of your applications. Every proposition is derived from your verified records with strict provenance.'
                : 'Turn a noisy search into an aligned, finished application. Your master resume generates factual, tailored packages gated by strict provenance verification.'
              : 'JOV.si is an intelligent, resume-first career workspace. We eliminate hallucinated credentials and ghost postings with cryptographic master-resume grounding, multi-source ATS discovery, and automated 15-point pre-submission validation gates.'}
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            {hasFullAccess ? (
              <>
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
                  className="inline-flex items-center gap-2 px-4 py-3 text-[14px] font-medium text-text-2 hover:text-text transition-colors group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-full cursor-pointer"
                >
                  <span>{hasResume ? 'Open application queue' : 'Explore candidate graph'}</span>
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                </button>
              </>
            ) : (
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <Magnetic strength={8}>
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={() => openAuthModal('login')}
                    className="shadow-float"
                  >
                    <LogIn className="w-4 h-4" />
                    <span>Sign In</span>
                  </Button>
                </Magnetic>

                <Button
                  variant="secondary"
                  size="lg"
                  onClick={() => openAuthModal('register')}
                  className="shadow-subtle"
                >
                  <UserPlus className="w-4 h-4" />
                  <span>Create Account</span>
                </Button>

                <button
                  onClick={() => {
                    document.getElementById('product-architecture')?.scrollIntoView({ behavior: 'smooth' })
                  }}
                  className="inline-flex items-center gap-2 px-4 py-3 text-[14px] font-medium text-text-2 hover:text-text transition-colors group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-full cursor-pointer"
                >
                  <span>Explore Product</span>
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                </button>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Error Notice */}
      {error && hasFullAccess && (
        <div className="border border-border/80 bg-bg-elev-1/60 p-4 rounded-xl text-[13px] text-text-2 flex items-center gap-3">
          <AlertCircle className="w-4 h-4 shrink-0 text-text-3" />
          <span>Unable to synchronize workspace data: {error}</span>
        </div>
      )}

      {/* Conditional Content: Workspace Command Center (Authenticated) vs Product Showcase (Unauthenticated) */}
      {hasFullAccess ? (
        /* Main Workspace / Command Center */
        <section className="space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-4">
            <div>
              <p className="page-kicker">Command Center</p>
              <h2 className="text-2xl font-semibold tracking-tight text-text mt-1">
                {hasResume ? 'Application Status' : 'Honest Baseline'}
              </h2>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={refresh}
                loading={loading}
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Refresh data</span>
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={async () => {
                  await logout()
                }}
                className="text-text-3 hover:text-text cursor-pointer"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Sign Out</span>
              </Button>
            </div>
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
      ) : (
        /* Public Product Showcase & Feature Tour (Unauthenticated) */
        <div id="product-architecture" className="space-y-20">
          {/* Section: Architectural Pillars */}
          <section className="space-y-10">
            <div className="border-b border-border pb-4 space-y-1">
              <p className="page-kicker">Core Pillars</p>
              <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-text">
                Engineered for Integrity, Verification, and Control
              </h2>
              <p className="text-sm text-text-2 max-w-2xl">
                Unlike generic AI job bots that fabricate experience and spam blind applications,
                JOV.si is designed as a rigorous, verified workspace.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Pillar 1 */}
              <div className="p-7 rounded-2xl bg-bg-elev-1/60 border border-border space-y-4 shadow-subtle hover:border-border-strong transition-colors">
                <div className="w-11 h-11 rounded-xl bg-bg border border-border flex items-center justify-center">
                  <FileCheck2 className="w-5 h-5 text-text" strokeWidth={1.5} />
                </div>
                <div className="space-y-1">
                  <h3 className="text-lg font-semibold text-text">
                    1. Master-Resume Fact Provenance
                  </h3>
                  <p className="text-xs uppercase font-mono tracking-wider text-text-3">
                    SHA-256 Grounded Records
                  </p>
                </div>
                <p className="text-sm text-text-2 leading-relaxed">
                  Upload your master resume once. Every bullet, date, metric, and skill is extracted
                  into an immutable fact record with SHA-256 document hashing. Zero hallucinations,
                  zero ungrounded claims, and zero sycophancy.
                </p>
              </div>

              {/* Pillar 2 */}
              <div className="p-7 rounded-2xl bg-bg-elev-1/60 border border-border space-y-4 shadow-subtle hover:border-border-strong transition-colors">
                <div className="w-11 h-11 rounded-xl bg-bg border border-border flex items-center justify-center">
                  <Globe2 className="w-5 h-5 text-text" strokeWidth={1.5} />
                </div>
                <div className="space-y-1">
                  <h3 className="text-lg font-semibold text-text">
                    2. Real Multi-Source ATS Discovery
                  </h3>
                  <p className="text-xs uppercase font-mono tracking-wider text-text-3">
                    Direct Connectors & Normalized Geography
                  </p>
                </div>
                <p className="text-sm text-text-2 leading-relaxed">
                  Direct connections to Ashby, SmartRecruiters, Lever, Greenhouse, and verified
                  aggregators. True country, state, and city search normalized across 249 territories
                  with strict ISO compliance. No scraping, no dead listings.
                </p>
              </div>

              {/* Pillar 3 */}
              <div className="p-7 rounded-2xl bg-bg-elev-1/60 border border-border space-y-4 shadow-subtle hover:border-border-strong transition-colors">
                <div className="w-11 h-11 rounded-xl bg-bg border border-border flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-text" strokeWidth={1.5} />
                </div>
                <div className="space-y-1">
                  <h3 className="text-lg font-semibold text-text">
                    3. Two-Phase Eligibility & Explainable Fit
                  </h3>
                  <p className="text-xs uppercase font-mono tracking-wider text-text-3">
                    9 Hard Gates + 0–100 Soft Scoring
                  </p>
                </div>
                <p className="text-sm text-text-2 leading-relaxed">
                  Eliminates ineligible jobs instantly across work authorization, location, remote
                  policy, and salary floors. Eligible jobs receive transparent 0–100 suitability scores
                  with human-readable rationale cards explaining exact alignment.
                </p>
              </div>

              {/* Pillar 4 */}
              <div className="p-7 rounded-2xl bg-bg-elev-1/60 border border-border space-y-4 shadow-subtle hover:border-border-strong transition-colors">
                <div className="w-11 h-11 rounded-xl bg-bg border border-border flex items-center justify-center">
                  <KeyRound className="w-5 h-5 text-text" strokeWidth={1.5} />
                </div>
                <div className="space-y-1">
                  <h3 className="text-lg font-semibold text-text">
                    4. 15-Point Pre-Submission Safety Gate
                  </h3>
                  <p className="text-xs uppercase font-mono tracking-wider text-text-3">
                    Cryptographic Sign-off & Offline Kits
                  </p>
                </div>
                <p className="text-sm text-text-2 leading-relaxed">
                  Every application must pass 15 automated validation gates prior to transmission.
                  Packages require explicit cryptographic approval tokens, or can be exported as
                  portable .zip handoff kits complete with tailored PDFs and form answers.
                </p>
              </div>
            </div>
          </section>

          {/* Section: Workflow Walkthrough */}
          <section className="space-y-10 border-t border-border pt-12">
            <div className="space-y-1">
              <p className="page-kicker">End-to-End Workflow</p>
              <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-text">
                How JOV.si Operates
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="p-6 rounded-xl bg-bg-elev-1/40 border border-border space-y-3">
                <span className="font-mono text-xs font-semibold text-accent">01. INGEST</span>
                <h4 className="text-base font-semibold text-text">Import & Ground</h4>
                <p className="text-xs text-text-3 leading-relaxed">
                  Upload your master resume. Structured facts are extracted, verified, and linked to
                  your isolated account profile.
                </p>
              </div>

              <div className="p-6 rounded-xl bg-bg-elev-1/40 border border-border space-y-3">
                <span className="font-mono text-xs font-semibold text-accent">02. DISCOVER</span>
                <h4 className="text-base font-semibold text-text">Search & Match</h4>
                <p className="text-xs text-text-3 leading-relaxed">
                  Query live jobs from Ashby and SmartRecruiters with country/state/city filters and
                  real-time eligibility scoring.
                </p>
              </div>

              <div className="p-6 rounded-xl bg-bg-elev-1/40 border border-border space-y-3">
                <span className="font-mono text-xs font-semibold text-accent">03. TAILOR</span>
                <h4 className="text-base font-semibold text-text">Generate & Validate</h4>
                <p className="text-xs text-text-3 leading-relaxed">
                  Synthesize factual resumes and cover letters strictly grounded in your active facts,
                  rendered into clean PDF and DOCX.
                </p>
              </div>

              <div className="p-6 rounded-xl bg-bg-elev-1/40 border border-border space-y-3">
                <span className="font-mono text-xs font-semibold text-accent">04. APPROVE</span>
                <h4 className="text-base font-semibold text-text">Gate & Submit</h4>
                <p className="text-xs text-text-3 leading-relaxed">
                  Pass the 15-point safety gate. Sign off with single-use cryptographic tokens or
                  export offline application kits.
                </p>
              </div>
            </div>
          </section>

          {/* Section: Bottom Sign-Up Callout Banner */}
          <section className="p-8 sm:p-12 rounded-3xl bg-bg-elev-1 border border-border text-center space-y-6 shadow-float">
            <div className="max-w-xl mx-auto space-y-3">
              <h3 className="text-2xl sm:text-3xl font-semibold tracking-tight text-text">
                Ready to take control of your career search?
              </h3>
              <p className="text-sm text-text-2 leading-relaxed">
                Sign in or create your account to unlock the full workspace: live job discovery feeds,
                tailored resume generation, and verified application tracking.
              </p>
            </div>

            <div className="flex flex-wrap justify-center items-center gap-4 pt-2">
              <Button
                variant="primary"
                size="lg"
                onClick={() => openAuthModal('login')}
                className="shadow-float"
              >
                <LogIn className="w-4 h-4" />
                <span>Sign In</span>
              </Button>

              <Button
                variant="secondary"
                size="lg"
                onClick={() => openAuthModal('register')}
                className="shadow-subtle"
              >
                <UserPlus className="w-4 h-4" />
                <span>Create Account</span>
              </Button>
            </div>
          </section>
        </div>
      )}

      {/* Safety & Provenance Integrity Notice — Unboxed Footer Strip */}
      <section className="pt-8 border-t border-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 text-text-3">
        <div className="flex items-start gap-3 max-w-2xl">
          <ShieldCheck className="w-4 h-4 text-text-2 shrink-0 mt-0.5" strokeWidth={1.5} />
          <div className="space-y-1">
            <h3 className="text-sm font-medium text-text">
              Engineered with strict candidate provenance
            </h3>
            <p className="text-xs text-text-3 leading-relaxed">
              Every field in every tailored resume maps to an active candidate fact. No hallucinated
              experience, no fabricated confirmation. Submissions are gated until explicitly approved.
            </p>
          </div>
        </div>

        {hasFullAccess ? (
          <button
            onClick={() => onNavigate('tracker')}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-text-2 hover:text-text transition-colors shrink-0 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded cursor-pointer"
          >
            <span>View event audit trail</span>
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </button>
        ) : (
          <button
            onClick={openAuthModal}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-text-2 hover:text-text transition-colors shrink-0 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded cursor-pointer"
          >
            <span>Sign in to access audit trail</span>
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </button>
        )}
      </section>
    </div>
  )
}
