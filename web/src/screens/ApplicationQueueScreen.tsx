import React, { useEffect, useState } from 'react'
import { motion, LayoutGroup } from 'motion/react'
import { Button } from '../components/ui/Button'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../api/client'
import type { Application } from '../types'
import {
  Layers,
  RefreshCw,
  Eye,
  Play,
  FileText,
  ShieldCheck,
  Send,
  CheckCircle2,
  Building2,
  User,
  X,
  AlertCircle,
  Check,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { spring } from '../design/motion'

interface ApplicationQueueScreenProps {
  onSelectApplication: (appId: string) => void
}

export const ApplicationQueueScreen: React.FC<ApplicationQueueScreenProps> = ({
  onSelectApplication,
}) => {
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [filterState, setFilterState] = useState<string>('ALL')
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [expandedScores, setExpandedScores] = useState<Record<string, boolean>>({})

  const loadApplications = async () => {
    setLoading(true)
    try {
      const data = await api.getApplications()
      setApplications(data)
    } catch (err: any) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadApplications()
  }, [])

  const handleRunEvaluation = async (appId: string) => {
    setActionLoadingId(appId)
    try {
      const res = await api.evaluateApplication(appId)
      setFeedback(`Evaluation complete: Score ${res.score_total}/100, transitioned to ${res.new_state}`)
      await loadApplications()
    } catch (err: any) {
      setFeedback(`Evaluation failed: ${err.message}`)
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleGenerateResume = async (appId: string) => {
    setActionLoadingId(appId)
    try {
      const res = await api.generateResume(appId)
      setFeedback(`Resume generated & validated. PDF SHA: ${res.sha256.slice(0, 12)}... State: ${res.state}`)
      await loadApplications()
    } catch (err: any) {
      setFeedback(`Resume generation failed: ${err.message}`)
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleRunGate = async (appId: string) => {
    setActionLoadingId(appId)
    try {
      const res = await api.runGate(appId)
      setFeedback(`Gate outcome: ${res.outcome}. Package Hash: ${res.package_hash.slice(0, 12)}...`)
      await loadApplications()
    } catch (err: any) {
      setFeedback(`Gate run failed: ${err.message}`)
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleSubmit = async (appId: string) => {
    setActionLoadingId(appId)
    try {
      const res = await api.submitApplication(appId)
      setFeedback(`Submission outcome: ${res.outcome}. Transitioned to ${res.state}`)
      await loadApplications()
    } catch (err: any) {
      setFeedback(`Submission failed: ${err.message}`)
    } finally {
      setActionLoadingId(null)
    }
  }

  const filteredApps = applications.filter((app) => {
    if (filterState === 'ALL') return true
    const rawState = (app as any).state || app.current_state
    if (filterState === 'ACTION') {
      return (
        rawState === 'DISCOVERED' ||
        rawState === 'SHORTLISTED' ||
        rawState === 'RESUME_GENERATED' ||
        rawState === 'READY_FOR_REVIEW' ||
        rawState === 'APPROVAL_REQUESTED'
      )
    }
    if (filterState === 'REVIEW') {
      return rawState === 'READY_FOR_REVIEW' || rawState === 'APPROVAL_REQUESTED'
    }
    if (filterState === 'APPROVED') {
      return rawState === 'APPROVED' || rawState === 'APPROVED_PENDING_SUBMISSION'
    }
    if (filterState === 'COMPLETED') {
      return rawState === 'APPLIED_CONFIRMED' || rawState === 'SUBMISSION_UNCERTAIN'
    }
    return true
  })

  // Group applications by urgency
  const needsAction = filteredApps.filter((app) => {
    const s = (app as any).state || app.current_state
    return s === 'READY_FOR_REVIEW' || s === 'APPROVAL_REQUESTED' || s === 'DISCOVERED' || s === 'SHORTLISTED' || s === 'RESUME_GENERATED'
  })

  const inProgress = filteredApps.filter((app) => {
    const s = (app as any).state || app.current_state
    return s === 'APPROVED' || s === 'SUBMITTING' || s === 'APPROVED_PENDING_SUBMISSION' || s === 'EVALUATING_ELIGIBILITY'
  })

  const waiting = filteredApps.filter((app) => {
    const s = (app as any).state || app.current_state
    return s === 'APPLIED_CONFIRMED' || s === 'SUBMISSION_UNCERTAIN' || s === 'REJECTED' || s === 'APPLICATION_FAILED'
  })

  const renderAppCard = (app: Application) => {
    const rawState = (app as any).state || app.current_state || 'DISCOVERED'
    const isActing = actionLoadingId === app.id

    const canEvaluate = rawState === 'DISCOVERED'
    const canGenerateResume = rawState === 'SHORTLISTED'
    const canRunGate = rawState === 'RESUME_GENERATED'
    const canReview = rawState === 'READY_FOR_REVIEW' || rawState === 'APPROVAL_REQUESTED'
    const canSubmit = rawState === 'APPROVED'

    const candidateName =
      (app as any).candidate_name || app.candidate?.display_name || 'Active Candidate'
    const roleTitle =
      (app as any).role_title || app.job?.role_title || (app as any).title || 'Senior Software Engineer'
    const companyName =
      (app as any).company_name || app.job?.company_name || (app as any).company || 'Mock Acme Corp'

    // Determine blocking reason
    let blockingLabel = ''
    if (canEvaluate) blockingLabel = 'Requires eligibility scoring against job requirements'
    else if (canGenerateResume) blockingLabel = 'Tailored resume draft ready for factual synthesis'
    else if (canRunGate) blockingLabel = 'Synthesized document awaits verification checklist'
    else if (canReview) blockingLabel = 'Verification passed. Candidate review and sign-off required'
    else if (canSubmit) blockingLabel = 'Approved by candidate. Ready for portal submission'
    else if (rawState === 'APPLIED_CONFIRMED') blockingLabel = 'Submission independently confirmed by employer portal'
    else if (rawState === 'SUBMISSION_UNCERTAIN') blockingLabel = 'Sent. Awaiting confirmation receipt'

    const evaluation = app.evaluation
    const rulesResult = evaluation?.rules_result || (app as any).rules_result
    const scoreVal = evaluation?.score_total ?? (app as any).score
    const isExpanded = !!expandedScores[app.id]

    const toggleExpanded = () => {
      setExpandedScores(prev => ({ ...prev, [app.id]: !prev[app.id] }))
    }

    const matchedSkills = evaluation?.matched_skills || evaluation?.breakdown?.matched_skills || []
    const missingSkills = evaluation?.missing_skills || evaluation?.breakdown?.missing_skills || []
    const uncertainReasons = evaluation?.uncertain_reasons || evaluation?.breakdown?.eligibility?.uncertain_reasons || []
    const disqualifyingReasons = evaluation?.disqualifying_reasons || evaluation?.breakdown?.eligibility?.disqualifying_reasons || []
    const summaryExplanation = evaluation?.summary_explanation || evaluation?.breakdown?.summary_explanation
    const categories = evaluation?.breakdown?.categories

    return (
      <motion.div
        layout
        key={app.id}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.98 }}
        transition={spring.smooth}
        className="py-5 hover:bg-bg-elev-1/30 px-3 -mx-3 transition-colors border-b border-border/40 last:border-0"
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2.5 min-w-0 flex-1">
            <div className="flex items-center gap-3 flex-wrap">
              <h3 className="text-base font-semibold text-text tracking-tight">
                {roleTitle}
              </h3>
              <StatusBadge state={rawState} />

              {/* Hard Eligibility Gate Badge */}
              {rulesResult && (
                rulesResult === 'PASS' ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <Check className="w-3 h-3" /> Gate: PASS
                  </span>
                ) : rulesResult === 'UNCERTAIN' || rulesResult === 'NEEDS_REVIEW' ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    <AlertCircle className="w-3 h-3" /> Gate: Needs Review
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                    <X className="w-3 h-3" /> Gate: Disqualified
                  </span>
                )
              )}
            </div>

            <div className="flex items-center gap-3 text-xs text-text-2">
              <span className="flex items-center gap-1.5 font-medium text-text">
                <Building2 className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
                {companyName}
              </span>
              <span className="opacity-30">·</span>
              <span className="flex items-center gap-1.5 text-text-3">
                <User className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
                {candidateName}
              </span>
            </div>

            {/* Block reason notice */}
            {blockingLabel && (
              <p className="text-xs text-text-3 font-mono pt-1">
                {blockingLabel}
              </p>
            )}

            {/* Disqualifying Alert */}
            {disqualifyingReasons.length > 0 && (
              <div className="mt-2 p-2.5 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-300 font-sans space-y-1">
                <div className="font-semibold flex items-center gap-1.5">
                  <X className="w-3.5 h-3.5 text-red-400" /> Disqualification Reason:
                </div>
                <ul className="list-disc pl-5 space-y-0.5">
                  {disqualifyingReasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Uncertain / Needs Review Alert */}
            {uncertainReasons.length > 0 && (
              <div className="mt-2 p-2.5 rounded bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 font-sans space-y-1">
                <div className="font-semibold flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" /> Candidate Verification Required:
                </div>
                <ul className="list-disc pl-5 space-y-0.5">
                  {uncertainReasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Matched & Missing Skills Chips */}
            {(matchedSkills.length > 0 || missingSkills.length > 0) && (
              <div className="flex items-center gap-2 flex-wrap pt-1 text-xs">
                {matchedSkills.slice(0, 4).map((s, i) => (
                  <span
                    key={`m-${i}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                  >
                    ✓ {s}
                  </span>
                ))}
                {missingSkills.slice(0, 3).map((s, i) => (
                  <span
                    key={`miss-${i}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-bg-elev-2 text-text-3 border border-border/60"
                  >
                    – {s}
                  </span>
                ))}
              </div>
            )}

            <div className="flex items-center gap-3 pt-1 text-[11px] font-mono text-text-3 flex-wrap">
              <span>ID: {app.id.slice(0, 8)}</span>
              <span>·</span>
              <span>v{app.version}</span>
              {scoreVal !== undefined && scoreVal !== null && (
                <>
                  <span>·</span>
                  <button
                    onClick={toggleExpanded}
                    className="inline-flex items-center gap-1 text-text font-medium hover:text-accent-primary transition-colors cursor-pointer"
                  >
                    <span>Suitability: {Math.round(scoreVal)}/100</span>
                    {categories && (
                      isExpanded ? <ChevronUp className="w-3 h-3 text-text-3" /> : <ChevronDown className="w-3 h-3 text-text-3" />
                    )}
                  </button>
                </>
              )}
            </div>

            {/* Expandable Category Score Breakdown & Provenance Summary */}
            {isExpanded && categories && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 p-3 rounded bg-bg-elev-1 border border-border/60 text-xs space-y-2.5 font-sans"
              >
                <div className="font-medium text-text text-xs flex items-center justify-between">
                  <span>Category Points Breakdown (100-Point Model)</span>
                  <span className="font-mono text-text-2">{scoreVal}/100 total</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 font-mono text-[11px]">
                  {Object.entries(categories).map(([k, c]) => (
                    <div key={k} className="p-2 rounded bg-bg-elev-2/80 border border-border/40 space-y-0.5">
                      <div className="text-text-3 uppercase tracking-wider text-[10px]">{k}</div>
                      <div className="text-text font-semibold">{c.earned_points} / {c.available_points}</div>
                    </div>
                  ))}
                </div>
                {summaryExplanation && (
                  <p className="text-[11px] text-text-2 font-sans pt-1 border-t border-border/30">
                    {summaryExplanation}
                  </p>
                )}
              </motion.div>
            )}
          </div>

          {/* Single Clear Primary Action */}
          <div className="flex items-center gap-3 shrink-0">
            {canEvaluate && (
              <Button
                variant="primary"
                size="md"
                loading={isActing}
                onClick={() => handleRunEvaluation(app.id)}
              >
                <Play className="w-4 h-4" />
                <span>Run Evaluation</span>
              </Button>
            )}

            {canGenerateResume && (
              <Button
                variant="primary"
                size="md"
                loading={isActing}
                onClick={() => handleGenerateResume(app.id)}
              >
                <FileText className="w-4 h-4" />
                <span>Generate Resume</span>
              </Button>
            )}

            {canRunGate && (
              <Button
                variant="primary"
                size="md"
                loading={isActing}
                onClick={() => handleRunGate(app.id)}
              >
                <ShieldCheck className="w-4 h-4" />
                <span>Execute Gate</span>
              </Button>
            )}

            {canReview && (
              <Button
                variant="primary"
                size="md"
                onClick={() => onSelectApplication(app.id)}
              >
                <Eye className="w-4 h-4" />
                <span>Review Package</span>
              </Button>
            )}

            {canSubmit && (
              <Button
                variant="primary"
                size="md"
                loading={isActing}
                onClick={() => handleSubmit(app.id)}
              >
                <Send className="w-4 h-4" />
                <span>Submit to Portal</span>
              </Button>
            )}
          </div>
        </div>
      </motion.div>
    )
  }

  return (
    <div className="screen-page space-y-8">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-border">
        <div>
          <p className="page-kicker">Progressive Pipeline</p>
          <h1 className="page-title">Application Queue</h1>
          <p className="page-intro">
            Active applications moving step-by-step through eligibility scoring, tailored document synthesis, and verification checks.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button variant="secondary" size="md" onClick={loadApplications} loading={loading}>
            <RefreshCw className="w-4 h-4" />
            <span>Refresh Queue</span>
          </Button>
        </div>
      </div>

      {/* Feedback Alert */}
      {feedback && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 border border-border/80 rounded-xl bg-bg-elev-1/60 text-xs text-text flex items-center justify-between shadow-1"
        >
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-text-2 shrink-0" />
            <span className="font-medium">{feedback}</span>
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="p-1 rounded-full text-text-3 hover:text-text"
          >
            <X className="w-4 h-4" />
          </button>
        </motion.div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 border-b border-border pb-3 overflow-x-auto [scrollbar-width:none]">
        {[
          { id: 'ALL', label: `All (${applications.length})` },
          { id: 'ACTION', label: `Needs Action (${needsAction.length})` },
          { id: 'REVIEW', label: `Review Required` },
          { id: 'APPROVED', label: `Approved` },
          { id: 'COMPLETED', label: `Completed` },
        ].map((tab) => {
          const active = filterState === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setFilterState(tab.id)}
              className={`relative px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors ${
                active ? 'text-text' : 'text-text-3 hover:text-text'
              }`}
            >
              {active && (
                <motion.span
                  layoutId="queue-filter-pill"
                  className="absolute inset-0 rounded-full bg-selected border border-border"
                  transition={spring.layout}
                />
              )}
              <span className="relative z-10">{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* Queue Content Grouped by Urgency */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="h-28 rounded-xl bg-bg-elev-1/40 border border-border/60 relative overflow-hidden"
            >
              <div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-border to-transparent"
                style={{ animation: 'pearl-shimmer 2.2s infinite ease-in-out' }}
              />
            </div>
          ))}
        </div>
      ) : filteredApps.length === 0 ? (
        <div className="border border-border/60 rounded-xl bg-bg-elev-1/20 py-16 text-center text-text-3">
          <Layers className="w-10 h-10 mx-auto mb-3 opacity-40" strokeWidth={1.5} />
          <p className="text-sm font-medium text-text">Queue is currently clear</p>
          <p className="text-xs text-text-3 mt-1">
            No active applications in this stage. Browse Job Discovery to select an opportunity.
          </p>
        </div>
      ) : (
        <LayoutGroup>
          <div className="space-y-10">
            {/* Needs Action Group */}
            {needsAction.length > 0 && (
              <div className="space-y-2">
                <div className="px-1 border-b border-border/40 pb-2">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-text-3">
                    Needs Your Action ({needsAction.length})
                  </h2>
                </div>
                <div className="divide-y divide-border/40">
                  {needsAction.map(renderAppCard)}
                </div>
              </div>
            )}

            {/* In Progress Group */}
            {inProgress.length > 0 && (
              <div className="space-y-2">
                <div className="px-1 border-b border-border/40 pb-2">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-text-3">
                    In Progress ({inProgress.length})
                  </h2>
                </div>
                <div className="divide-y divide-border/40">
                  {inProgress.map(renderAppCard)}
                </div>
              </div>
            )}

            {/* Waiting / Completed Group */}
            {waiting.length > 0 && (
              <div className="space-y-2">
                <div className="px-1 border-b border-border/40 pb-2">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-text-3">
                    Completed & Waiting ({waiting.length})
                  </h2>
                </div>
                <div className="divide-y divide-border/40">
                  {waiting.map(renderAppCard)}
                </div>
              </div>
            )}
          </div>
        </LayoutGroup>
      )}
    </div>
  )
}
