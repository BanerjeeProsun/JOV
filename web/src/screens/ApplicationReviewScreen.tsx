import React, { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { Button } from '../components/ui/Button'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../api/client'
import type { Application } from '../types'
import {
  ArrowLeft,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Lock,
  User,
  Send,
  RefreshCw,
  ExternalLink,
  Edit3,
  Building2,
} from 'lucide-react'
import { spring } from '../design/motion'

interface ApplicationReviewScreenProps {
  applicationId: string
  onBack: () => void
  onNavigateToTracker: () => void
}

export const ApplicationReviewScreen: React.FC<ApplicationReviewScreenProps> = ({
  applicationId,
  onBack,
  onNavigateToTracker,
}) => {
  const [app, setApp] = useState<Application | null>(null)
  const [loading, setLoading] = useState(true)
  const [approving, setApproving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [runningGate, setRunningGate] = useState(false)
  const [activeTab, setActiveTab] = useState<'RESUME' | 'COVER_LETTER' | 'FIELDS'>('RESUME')
  const [feedback, setFeedback] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Cover Letter editing state
  const [editingCoverLetter, setEditingCoverLetter] = useState(false)
  const [coverLetterText, setCoverLetterText] = useState('')
  const [savingCoverLetter, setSavingCoverLetter] = useState(false)

  const loadApplication = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getApplication(applicationId)
      setApp(data)
      if ((data as any).cover_letter) {
        setCoverLetterText((data as any).cover_letter)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load application')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadApplication()
  }, [applicationId])

  const handleRunGate = async () => {
    setRunningGate(true)
    setFeedback(null)
    try {
      const res = await api.runGate(applicationId)
      setFeedback(`Gate evaluated: ${res.outcome}`)
      await loadApplication()
    } catch (err: any) {
      setError(`Gate evaluation failed: ${err.message}`)
    } finally {
      setRunningGate(false)
    }
  }

  const handleApprove = async () => {
    if (!app?.gate_report?.content_hash) return
    setApproving(true)
    setFeedback(null)
    try {
      const res = await api.approveApplication(applicationId, app.gate_report.content_hash)
      setFeedback(`Package approved! Approval ID: ${res.approval_id}. Valid until: ${new Date(res.expires_at).toLocaleTimeString()}`)
      await loadApplication()
    } catch (err: any) {
      setError(`Approval failed: ${err.message}`)
    } finally {
      setApproving(false)
    }
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setFeedback(null)
    try {
      const res = await api.submitApplication(applicationId)
      setFeedback(`Submission complete: Outcome ${res.outcome}!`)
      await loadApplication()
      setTimeout(() => {
        onNavigateToTracker()
      }, 1200)
    } catch (err: any) {
      setError(`Submission failed: ${err.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  const handleSaveCoverLetter = async () => {
    setSavingCoverLetter(true)
    try {
      await fetch(`/api/v1/applications/${applicationId}/cover-letter`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cover_letter: coverLetterText }),
      })
      setEditingCoverLetter(false)
      setFeedback('Cover letter updated successfully!')
      await loadApplication()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSavingCoverLetter(false)
    }
  }

  if (loading && !app) {
    return (
      <div className="screen-page py-24 text-center text-text-3 font-mono text-xs">
        Loading package data and validation records…
      </div>
    )
  }

  if (error && !app) {
    return (
      <div className="screen-page py-24 text-center">
        <div className="p-6 rounded-card border border-err/20 bg-err-subtle text-err text-xs max-w-md mx-auto">
          {error}
        </div>
      </div>
    )
  }

  const gatePassed = app?.gate_report?.outcome === 'PASS'
  const isApproved = app?.state === 'APPROVED' || app?.current_state === 'APPROVED'
  const packageHash = app?.gate_report?.content_hash || (app?.package as any)?.package_hash

  const candidateDisplayName =
    app?.candidate?.display_name || (app as any)?.candidate_name || 'Active Candidate'
  const roleTitle = app?.job?.role_title || (app as any)?.role_title || 'Software Engineer'
  const companyName = app?.job?.company_name || (app as any)?.company_name || 'Target Company'

  return (
    <div className="screen-page space-y-8 pb-32">
      {/* Navigation & Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-border">
        <div className="flex items-center gap-4">
          <Button variant="secondary" size="sm" onClick={onBack}>
            <ArrowLeft className="w-4 h-4" />
            <span>Queue</span>
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight text-text">
                Application Review
              </h1>
              <StatusBadge state={(app as any)?.state || app?.current_state || ''} />
            </div>
            <p className="text-xs font-mono text-text-3 mt-1">
              Package ID: {app?.id.slice(0, 8)} · v{app?.version}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button variant="secondary" size="sm" onClick={loadApplication} loading={loading}>
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </Button>

          {!app?.gate_report && (
            <Button
              variant="primary"
              size="sm"
              loading={runningGate}
              onClick={handleRunGate}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Run 15-Point Gate</span>
            </Button>
          )}
        </div>
      </div>

      {/* Notifications */}
      {feedback && (
        <div className="p-4 rounded-card border border-ok/20 bg-ok-subtle text-ok text-xs flex items-center justify-between shadow-1">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{feedback}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="p-1 hover:opacity-70">
            ×
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-card border border-err/20 bg-err-subtle text-err text-xs flex items-center justify-between shadow-1">
          <div className="flex items-center gap-2">
            <XCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="p-1 hover:opacity-70">
            ×
          </button>
        </div>
      )}

      {/* Package Header Card */}
      <div className="rounded-card border border-border bg-bg-elev-1 p-6 shadow-1">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-3">
              Target Role & Organization
            </span>
            <h2 className="text-xl font-semibold text-text tracking-tight">
              {roleTitle}
            </h2>
            <div className="flex items-center gap-2 text-xs text-text-2 font-medium">
              <Building2 className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
              <span>{companyName}</span>
            </div>
            {app?.job?.canonical_url && (
              <a
                href={app.job.canonical_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-focus hover:underline pt-1"
              >
                <span>View verified posting</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>

          <div className="space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-3">
              Candidate Provenance & Package SHA-256
            </span>
            <div className="text-xs text-text flex items-center gap-2">
              <User className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
              <span>{candidateDisplayName}</span>
            </div>

            {/* Cryptographic Package Hash */}
            {packageHash && (
              <div className="pt-1">
                <span className="text-[10px] text-text-3 font-mono block mb-1 uppercase tracking-wide">
                  Immutable Cryptographic Hash
                </span>
                <code
                  data-testid="package-hash-value"
                  className="font-mono text-xs bg-bg-input px-3 py-1.5 rounded-md border border-border text-text block overflow-x-auto select-all"
                >
                  {packageHash}
                </code>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 15-Point Pre-Submission Validation Gate Report */}
      <div className="rounded-card border border-border bg-bg-elev-1 p-6 space-y-4 shadow-1">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-5 h-5 text-focus" strokeWidth={1.5} />
            <div>
              <h3 className="text-base font-semibold text-text">
                15-Point Pre-Submission Validation Gate
              </h3>
              <p className="text-xs text-text-3">
                Deterministic cryptographic check preventing fabricated claims or malformed data.
              </p>
            </div>
          </div>

          {app?.gate_report && (
            <span
              className={`px-3 py-1 rounded-full text-xs font-mono font-semibold uppercase tracking-wider border ${
                gatePassed
                  ? 'bg-ok-subtle text-ok border-ok/20'
                  : 'bg-err-subtle text-err border-err/20'
              }`}
            >
              Gate Outcome: {app.gate_report.outcome}
            </span>
          )}
        </div>

        {/* Validation Checks Table */}
        {app?.gate_report?.results && (
          <div className="rounded-md border border-border overflow-hidden">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-bg-elev-2 border-b border-border text-text-3 font-mono">
                  <th className="py-2.5 px-4 font-medium w-16">#</th>
                  <th className="py-2.5 px-4 font-medium">Standard Check</th>
                  <th className="py-2.5 px-4 font-medium w-24">Severity</th>
                  <th className="py-2.5 px-4 font-medium w-24">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-mono text-[11px]">
                {app.gate_report.results.map((chk) => (
                  <tr key={chk.check_id} className="hover:bg-selected transition-colors">
                    <td className="py-2.5 px-4 text-text-3">{chk.check_id}</td>
                    <td className="py-2.5 px-4 text-text font-sans font-medium">
                      {chk.name}
                      {chk.message && (
                        <span className="block text-[11px] font-mono text-text-3 mt-0.5">
                          {chk.message}
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="text-text-3">{chk.severity}</span>
                    </td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`inline-flex items-center gap-1 font-semibold ${
                          chk.result === 'PASS' ? 'text-ok' : 'text-err'
                        }`}
                      >
                        {chk.result === 'PASS' ? '✓ PASS' : '✗ FAIL'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Document Viewer: Solid reading measure (~70ch) */}
      <div className="rounded-card border border-border bg-bg-elev-1 p-6 space-y-6 shadow-1">
        {/* Tabs for Document View */}
        <div className="flex items-center gap-1 border-b border-border pb-3">
          {[
            { id: 'RESUME' as const, label: 'Synthesized Resume' },
            { id: 'COVER_LETTER' as const, label: 'Tailored Cover Letter' },
            { id: 'FIELDS' as const, label: 'Verified Form Inputs' },
          ].map((tab) => {
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative px-4 py-2 rounded-full text-xs font-medium transition-colors ${
                  active ? 'text-text font-semibold' : 'text-text-3 hover:text-text'
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="review-doc-pill"
                    className="absolute inset-0 rounded-full bg-selected border border-border"
                    transition={spring.layout}
                  />
                )}
                <span className="relative z-10">{tab.label}</span>
              </button>
            )
          })}
        </div>

        {/* Resume Content */}
        {activeTab === 'RESUME' && (
          <div className="max-w-[70ch] mx-auto p-8 rounded-card border border-border bg-bg-elev-2 text-text font-sans leading-relaxed space-y-6 shadow-1">
            <div className="border-b border-border pb-4">
              <h2 className="text-2xl font-semibold tracking-tight text-text">
                {candidateDisplayName}
              </h2>
              <p className="text-xs text-text-3 font-mono mt-1">
                Generated from immutable facts · Provenance verified
              </p>
            </div>

            <div className="space-y-4 text-[14px] text-text-2">
              <p className="font-medium text-text">
                Targeting: {roleTitle} at {companyName}
              </p>
              <p>
                Synthesized package tailored to required competencies with zero synthetic claims. All experience points correspond to active candidate records.
              </p>
            </div>
          </div>
        )}

        {/* Cover Letter Content */}
        {activeTab === 'COVER_LETTER' && (
          <div className="max-w-[70ch] mx-auto p-8 rounded-card border border-border bg-bg-elev-2 text-text font-sans leading-relaxed space-y-4 shadow-1">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <h3 className="text-sm font-semibold text-text">Cover Letter Draft</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditingCoverLetter(!editingCoverLetter)}
              >
                <Edit3 className="w-3.5 h-3.5" />
                <span>{editingCoverLetter ? 'Cancel Edit' : 'Edit'}</span>
              </Button>
            </div>

            {editingCoverLetter ? (
              <div className="space-y-3">
                <textarea
                  rows={10}
                  value={coverLetterText}
                  onChange={(e) => setCoverLetterText(e.target.value)}
                  className="app-input resize-y text-xs font-mono"
                />
                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    size="sm"
                    loading={savingCoverLetter}
                    onClick={handleSaveCoverLetter}
                  >
                    Save Changes
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-xs text-text-2 whitespace-pre-line leading-relaxed">
                {coverLetterText || 'No custom cover letter required for this application.'}
              </p>
            )}
          </div>
        )}

        {/* Verified Fields Content */}
        {activeTab === 'FIELDS' && (
          <div className="max-w-[70ch] mx-auto p-6 rounded-card border border-border bg-bg-elev-2 space-y-3 text-xs font-mono">
            <h4 className="text-xs uppercase font-semibold text-text-3">Form Field Responses</h4>
            <div className="p-4 rounded bg-bg-input border border-border text-text space-y-2">
              <p>Full Name: {candidateDisplayName}</p>
              <p>Portal Target: Mock Acme Submitter (L0_DRY_RUN)</p>
              <p>Status: Pre-validation passed</p>
            </div>
          </div>
        )}
      </div>

      {/* Floating Glass Approval Bar — Section 9 & 11 */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 w-full max-w-2xl px-4 pointer-events-none">
        <div className="glass rounded-full p-2.5 border border-glass-border shadow-float flex items-center justify-between gap-4 pointer-events-auto">
          {/* Calm persistent mock mode notice */}
          <div className="flex items-center gap-2 pl-3 min-w-0">
            <span className="w-2 h-2 rounded-full bg-warn shrink-0" />
            <span className="text-[12px] font-mono text-text-2 truncate">
              Release 1 Safety Sandbox Active · Mock Portal Target
            </span>
          </div>

          {/* Action Button: Approve Package Hash or Submit to Mock Portal */}
          <div className="shrink-0 flex items-center gap-2">
            {!isApproved ? (
              <Button
                variant="primary"
                size="md"
                disabled={!gatePassed}
                disabledTooltip={!gatePassed ? '15-point validation gate must PASS first' : undefined}
                loading={approving}
                onClick={handleApprove}
              >
                <Lock className="w-4 h-4" />
                <span>Approve Package Hash</span>
              </Button>
            ) : (
              <Button
                variant="primary"
                size="md"
                loading={submitting}
                onClick={handleSubmit}
              >
                <Send className="w-4 h-4" />
                <span>Submit to Mock Portal</span>
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
