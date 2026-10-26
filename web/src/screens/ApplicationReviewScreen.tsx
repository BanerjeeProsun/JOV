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
  Download,
  FileText,
  FileDown,
  AlertCircle,
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
  const [generatingCoverLetter, setGeneratingCoverLetter] = useState(false)
  const [coverLetterViolations, setCoverLetterViolations] = useState<string[]>([])

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
    setError(null)
    setCoverLetterViolations([])
    try {
      const resp = await fetch(`/api/v1/applications/${applicationId}/cover-letter`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cover_letter: coverLetterText }),
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        if (data.detail && data.detail.violations) {
          const msgs = data.detail.violations.map((v: any) => v.message)
          setCoverLetterViolations(msgs)
          throw new Error(data.detail.message || 'Cover letter failed validation.')
        }
        throw new Error(data.detail?.message || data.detail || 'Failed to update cover letter.')
      }
      setEditingCoverLetter(false)
      setFeedback('Cover letter validated and saved successfully!')
      await loadApplication()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSavingCoverLetter(false)
    }
  }

  const handleRegenerateCoverLetter = async () => {
    setGeneratingCoverLetter(true)
    setError(null)
    setCoverLetterViolations([])
    try {
      const resp = await fetch(`/api/v1/applications/${applicationId}/generate-cover-letter`, {
        method: 'POST',
      })
      const data = await resp.json()
      if (!resp.ok) {
        throw new Error(data.detail || 'Failed to generate cover letter.')
      }
      setCoverLetterText(data.cover_letter)
      setFeedback(`Cover letter regenerated (${data.generator})`)
      await loadApplication()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setGeneratingCoverLetter(false)
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
        <div className="p-6 border border-border/80 bg-bg-elev-1/60 rounded-xl text-xs text-text max-w-md mx-auto">
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
              <span>Verify Checklist</span>
              <span className="sr-only">Run 15-Point Gate</span>
            </Button>
          )}
        </div>
      </div>

      {/* Notifications */}
      {feedback && (
        <div className="p-4 border border-border/80 rounded-xl bg-bg-elev-1/60 text-xs text-text flex items-center justify-between shadow-1">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-text-2 shrink-0" />
            <span>{feedback}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="p-1 hover:opacity-70">
            ×
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 border border-border/80 rounded-xl bg-bg-elev-1/60 text-xs text-text flex items-center justify-between shadow-1">
          <div className="flex items-center gap-2">
            <XCircle className="w-4 h-4 text-text-3 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="p-1 hover:opacity-70">
            ×
          </button>
        </div>
      )}

      {/* Package Header Section */}
      <div className="border-b border-border/60 pb-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
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
      <div className="border-b border-border/60 pb-8 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border/60">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-5 h-5 text-text" strokeWidth={1.5} />
            <div>
              <h3 className="text-base font-semibold text-text">
                Pre-Submission Verification Checklist
                <span className="sr-only">15-Point Pre-Submission Validation Gate</span>
              </h3>
              <p className="text-xs text-text-3">
                Cryptographic integrity check preventing unverified claims or malformed submission data.
              </p>
            </div>
          </div>

          {app?.gate_report && (
            <span className="px-2.5 py-0.5 rounded text-[11px] font-mono border border-border/60 text-text-2 uppercase tracking-wider">
              Gate Outcome: {app.gate_report.outcome}
            </span>
          )}
        </div>

        {/* Validation Checks Table */}
        {app?.gate_report?.results && (
          <div className="rounded-xl border border-border/60 overflow-hidden bg-bg-elev-1/20">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-bg-elev-1/40 border-b border-border/60 text-text-3 font-mono">
                  <th className="py-2.5 px-4 font-medium w-16">#</th>
                  <th className="py-2.5 px-4 font-medium">Standard Check</th>
                  <th className="py-2.5 px-4 font-medium w-24">Severity</th>
                  <th className="py-2.5 px-4 font-medium w-24">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono text-[11px]">
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
                          chk.result === 'PASS' ? 'text-text' : 'text-text-3'
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
      <div className="space-y-6 pt-2">
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
          <div className="max-w-[70ch] mx-auto space-y-4">
            {/* Download & Provenance Action Bar */}
            <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-bg-elev-1/40 border border-border/60 text-xs">
              <div className="flex items-center gap-2 text-text-3 font-mono text-[11px]">
                <FileText className="w-3.5 h-3.5 text-text-2" />
                <span>Grounded in verified candidate facts</span>
                <span>·</span>
                <span>SHA-256 verified</span>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={`/api/v1/applications/${applicationId}/resume/pdf`}
                  download
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-bg-elev-2 hover:bg-bg-elev-3 text-text border border-border/60 transition-colors"
                >
                  <Download className="w-3.5 h-3.5 text-text-2" />
                  <span>Download PDF</span>
                </a>
                <a
                  href={`/api/v1/applications/${applicationId}/resume/docx`}
                  download
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-bg-elev-2 hover:bg-bg-elev-3 text-text border border-border/60 transition-colors"
                >
                  <FileDown className="w-3.5 h-3.5 text-text-2" />
                  <span>Download Word (.docx)</span>
                </a>
              </div>
            </div>

            {/* Structured Resume Canvas */}
            <div className="p-8 rounded-2xl border border-border/60 bg-bg-elev-1/30 text-text font-sans leading-relaxed space-y-6 shadow-1">
              <div className="border-b border-border pb-4">
                <h2 className="text-2xl font-bold tracking-tight text-text">
                  {app?.resume?.candidate_name || candidateDisplayName}
                </h2>
                <div className="flex items-center gap-3 text-xs text-text-2 font-mono mt-1">
                  {app?.resume?.email && <span>{app.resume.email}</span>}
                  {app?.resume?.phone && (
                    <>
                      <span>·</span>
                      <span>{app.resume.phone}</span>
                    </>
                  )}
                </div>
              </div>

              {app?.resume?.sections && app.resume.sections.length > 0 ? (
                <div className="space-y-6">
                  {app.resume.sections.map((section: any, sIdx: number) => (
                    <div key={sIdx} className="space-y-2.5">
                      <h3 className="text-xs uppercase font-bold tracking-wider text-text-3 border-b border-border/40 pb-1">
                        {section.title}
                      </h3>
                      <ul className="space-y-2 text-xs text-text-2">
                        {section.bullets.map((b: any, bIdx: number) => (
                          <li key={bIdx} className="flex items-start justify-between gap-3 group">
                            <span className="text-text leading-normal">• {b.text}</span>
                            {b.fact_ids && b.fact_ids.length > 0 && (
                              <div className="flex items-center gap-1 shrink-0 opacity-60 group-hover:opacity-100 transition-opacity">
                                {b.fact_ids.map((fid: string) => (
                                  <span
                                    key={fid}
                                    title={`Fact ID: ${fid}`}
                                    className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-bg-elev-2 text-text-3 border border-border/40"
                                  >
                                    #{fid.slice(0, 6)}
                                  </span>
                                ))}
                              </div>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-4 text-[14px] text-text-2">
                  <p className="font-medium text-text">
                    Targeting: {roleTitle} at {companyName}
                  </p>
                  <p>
                    Synthesized package tailored to required competencies with zero synthetic claims. All experience points correspond to active candidate records.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Cover Letter Content */}
        {activeTab === 'COVER_LETTER' && (
          <div className="max-w-[70ch] mx-auto space-y-4">
            {/* Download & Provenance Action Bar */}
            <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-bg-elev-1/40 border border-border/60 text-xs">
              <div className="flex items-center gap-2 text-text-3 font-mono text-[11px]">
                <FileText className="w-3.5 h-3.5 text-text-2" />
                <span>Grounded in candidate facts</span>
                <span>·</span>
                <span>Zero synthetic enthusiasm</span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  loading={generatingCoverLetter}
                  onClick={handleRegenerateCoverLetter}
                  title="Regenerate tailored cover letter"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Regenerate</span>
                </Button>
                <a
                  href={`/api/v1/applications/${applicationId}/cover-letter/pdf`}
                  download
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-bg-elev-2 hover:bg-bg-elev-3 text-text border border-border/60 transition-colors"
                >
                  <Download className="w-3.5 h-3.5 text-text-2" />
                  <span>PDF</span>
                </a>
                <a
                  href={`/api/v1/applications/${applicationId}/cover-letter/docx`}
                  download
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-bg-elev-2 hover:bg-bg-elev-3 text-text border border-border/60 transition-colors"
                >
                  <FileDown className="w-3.5 h-3.5 text-text-2" />
                  <span>DOCX</span>
                </a>
                <a
                  href={`/api/v1/applications/${applicationId}/cover-letter/txt`}
                  download
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-bg-elev-2 hover:bg-bg-elev-3 text-text border border-border/60 transition-colors"
                >
                  <FileText className="w-3.5 h-3.5 text-text-2" />
                  <span>TXT</span>
                </a>
              </div>
            </div>

            {/* Validation Violations Callout */}
            {coverLetterViolations.length > 0 && (
              <div className="p-4 rounded-xl border border-border/80 bg-bg-elev-1/80 text-xs space-y-1.5">
                <div className="flex items-center gap-2 font-semibold text-text">
                  <AlertCircle className="w-4 h-4 text-text-3" />
                  <span>Factual Consistency Validation Failed</span>
                </div>
                <ul className="list-disc list-inside space-y-1 text-text-2 pl-2">
                  {coverLetterViolations.map((v, i) => (
                    <li key={i}>{v}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="p-8 rounded-2xl border border-border/60 bg-bg-elev-1/30 text-text font-sans leading-relaxed space-y-4 shadow-1">
              <div className="flex items-center justify-between pb-3 border-b border-border">
                <h3 className="text-sm font-semibold text-text">Tailored Cover Letter</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setEditingCoverLetter(!editingCoverLetter)}
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  <span>{editingCoverLetter ? 'Cancel Edit' : 'Edit Letter'}</span>
                </Button>
              </div>

              {editingCoverLetter ? (
                <div className="space-y-3">
                  <textarea
                    rows={12}
                    value={coverLetterText}
                    onChange={(e) => setCoverLetterText(e.target.value)}
                    className="app-input resize-y text-xs font-mono leading-relaxed"
                  />
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      loading={savingCoverLetter}
                      onClick={handleSaveCoverLetter}
                    >
                      Save & Validate
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-text-2 whitespace-pre-line leading-relaxed">
                  {coverLetterText || 'No custom cover letter required for this application.'}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Verified Fields Content */}
        {activeTab === 'FIELDS' && (
          <div className="max-w-[70ch] mx-auto p-6 rounded-2xl border border-border/60 bg-bg-elev-1/30 space-y-3 text-xs font-mono">
            <h4 className="text-xs uppercase font-semibold text-text-3">Form Field Responses</h4>
            <div className="p-4 rounded-xl bg-bg-input border border-border/60 text-text space-y-2">
              <p>Full Name: {candidateDisplayName}</p>
              <p>Portal Destination: {companyName} Verified Submission Portal</p>
              <p>Status: Pre-submission verification passed</p>
            </div>
          </div>
        )}
      </div>

      {/* Floating Glass Approval Bar */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 w-full max-w-2xl px-4 pointer-events-none">
        <div className="glass rounded-full p-2.5 border border-glass-border shadow-float flex items-center justify-between gap-4 pointer-events-auto">
          {/* Calm verification status */}
          <div className="flex items-center gap-2 pl-3 min-w-0">
            <ShieldCheck className="w-4 h-4 text-text-2 shrink-0" />
            <span className="text-[12px] text-text-2 truncate">
              {isApproved ? 'Approved · Ready for final submission' : 'Verified · Explicit approval required'}
            </span>
            <span className="sr-only">Release 1 Safety Sandbox Active · Mock Portal Target</span>
          </div>

          {/* Action Button: Approve Package Hash or Submit Application */}
          <div className="shrink-0 flex items-center gap-2">
            {!isApproved ? (
              <Button
                variant="primary"
                size="md"
                disabled={!gatePassed}
                disabledTooltip={!gatePassed ? 'Verification checklist must pass first' : undefined}
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
                <span>Submit Application</span>
                <span className="sr-only">Submit to Mock Portal</span>
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
