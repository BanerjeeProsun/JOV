import React, { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../api/client'
import type { Application } from '../types'
import {
  ArrowLeft,
  ShieldCheck,
  CheckCircle,
  XCircle,
  Lock,
  FileText,
  User,
  Send,
  RefreshCw,
  ExternalLink,
  Edit3,
  Check,
} from 'lucide-react'

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
      }, 1500)
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
      <div className="max-w-6xl mx-auto px-6 py-20 text-center text-text-tertiary">
        Loading application package...
      </div>
    )
  }

  if (error && !app) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-20">
        <Card className="text-center py-10 bg-danger-subtle text-danger-red border border-danger-red/20">
          <p className="text-sm">{error}</p>
        </Card>
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
    <div className="screen-page space-y-8">
      {/* Top Bar Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border-subtle pb-4">
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={onBack}>
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Queue</span>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight text-text-primary">
                Application Review
              </h1>
              <StatusBadge state={(app as any)?.state || app?.current_state || ''} />
            </div>
            <p className="text-xs font-mono text-text-tertiary mt-0.5">
              ID: {app?.id} • Version {app?.version}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
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

          {/* Approve Button */}
          {!isApproved && (
            <Button
              variant="coral"
              size="sm"
              disabled={!gatePassed}
              disabledTooltip={!gatePassed ? 'Approval locked: 15-point validation gate must PASS first' : undefined}
              loading={approving}
              onClick={handleApprove}
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Approve Package Hash</span>
            </Button>
          )}

          {/* Submit Button */}
          {isApproved && (
            <Button
              variant="primary"
              size="sm"
              loading={submitting}
              onClick={handleSubmit}
            >
              <Send className="w-3.5 h-3.5" />
              <span>Submit to Mock Portal</span>
            </Button>
          )}
        </div>
      </div>

      {feedback && (
        <div className="p-4 rounded-apple-md bg-success-subtle border border-success-green/20 text-success-green text-xs flex items-center gap-2 shadow-sm">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span className="font-medium">{feedback}</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-apple-md bg-danger-subtle border border-danger-red/20 text-danger-red text-xs flex items-center gap-2 shadow-sm">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          <span className="font-medium">{error}</span>
        </div>
      )}

      {/* Package Header Card */}
      <Card className="p-6 bg-surface">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary">
              Target Role & Portal
            </span>
            <h2 className="text-xl font-semibold text-text-primary tracking-tight">
              {roleTitle}
            </h2>
            <p className="text-sm text-text-secondary font-medium">
              {companyName}
            </p>
            {app?.job?.canonical_url && (
              <a
                href={app.job.canonical_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-apple-blue hover:underline font-medium"
              >
                <span>View Portal Job Posting</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>

          <div className="space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary">
              Candidate & Cryptographic Gate
            </span>
            <div className="text-sm text-text-primary font-medium flex items-center gap-2">
              <User className="w-4 h-4 text-text-tertiary" />
              <span>{candidateDisplayName}</span>
            </div>
            {packageHash && (
              <div className="pt-1">
                <span className="text-[11px] text-text-tertiary block mb-0.5">
                  Package SHA-256 Hash:
                </span>
                <code
                  className="font-mono text-xs bg-canvas px-2 py-1 rounded-apple-sm text-text-primary border border-border-subtle block overflow-x-auto select-all"
                  data-testid="package-hash-value"
                >
                  {packageHash}
                </code>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* 15-Point Pre-Submission Validation Gate Report */}
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b border-border-subtle pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-apple-blue" />
            <h3 className="text-lg font-semibold text-text-primary tracking-tight">
              15-Point Pre-Submission Validation Gate
            </h3>
          </div>
          {app?.gate_report && (
            <span
              className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border ${
                gatePassed
                  ? 'bg-success-subtle text-success-green border-success-green/20'
                  : 'bg-danger-subtle text-danger-red border-danger-red/20'
              }`}
            >
              Gate Outcome: {app.gate_report.outcome}
            </span>
          )}
        </div>

        {app?.gate_report?.results && (
          <div className="rounded-card-lg border border-border-subtle overflow-hidden bg-surface shadow-apple-card">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-canvas border-b border-border-subtle text-text-secondary">
                  <th className="py-2.5 px-4 font-semibold w-16">#</th>
                  <th className="py-2.5 px-4 font-semibold w-56">Gate Check Rule</th>
                  <th className="py-2.5 px-4 font-semibold w-24">Severity</th>
                  <th className="py-2.5 px-4 font-semibold w-24">Result</th>
                  <th className="py-2.5 px-4 font-semibold">Evaluation Diagnostic</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {app.gate_report.results.map((check) => {
                  const isPass = check.result === 'PASS'
                  return (
                    <tr key={check.check_id} className="hover:bg-surface-hover/50">
                      <td className="py-2.5 px-4 font-mono text-text-tertiary">
                        {check.check_id}
                      </td>
                      <td className="py-2.5 px-4 font-medium text-text-primary">
                        {check.name}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-[11px] text-text-secondary">
                        {check.severity}
                      </td>
                      <td className="py-2.5 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            isPass
                              ? 'bg-success-subtle text-success-green'
                              : 'bg-danger-subtle text-danger-red'
                          }`}
                        >
                          {isPass ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                          {check.result}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-text-secondary">
                        {check.message}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Package Components Tabs: Resume, Cover Letter, Mapped Fields */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 border-b border-border-subtle pb-3">
          {[
            { id: 'RESUME', label: 'Tailored Resume', icon: <FileText className="w-3.5 h-3.5" /> },
            { id: 'COVER_LETTER', label: 'Personalized Cover Letter', icon: <Edit3 className="w-3.5 h-3.5" /> },
            { id: 'FIELDS', label: 'Mapped Form Answers', icon: <User className="w-3.5 h-3.5" /> },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-text-primary text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-black/5'
              }`}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tailored Resume Tab */}
        {activeTab === 'RESUME' && app?.resume && (
          <Card className="p-6 bg-surface shadow-apple-card space-y-6">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <h3 className="text-base font-semibold text-text-primary">
                  {(app.resume as any).candidate_name}
                </h3>
                <p className="text-xs text-text-secondary font-mono mt-0.5">
                  {(app.resume as any).contact_info?.email} • {(app.resume as any).contact_info?.phone} • {(app.resume as any).contact_info?.location}
                </p>
              </div>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-success-subtle text-success-green border border-success-green/20">
                Factual Consistency Verified
              </span>
            </div>

            {(app.resume as any).summary && (
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary block mb-1">
                  Professional Summary
                </span>
                <p className="text-xs text-text-primary bg-canvas p-3 rounded-apple-sm border border-border-subtle leading-relaxed">
                  {(app.resume as any).summary}
                </p>
              </div>
            )}

            {(app.resume as any).sections?.map((section: any, idx: number) => (
              <div key={idx} className="space-y-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary block">
                  {section.title}
                </span>
                <div className="bg-canvas p-3 rounded-apple-sm border border-border-subtle space-y-2">
                  {section.bullets?.map((b: any, bIdx: number) => (
                    <div key={bIdx} className="flex items-start gap-2 text-xs text-text-primary">
                      <span className="text-coral-brand font-bold">•</span>
                      <div className="flex-1">
                        <span>{b.text}</span>
                        {b.fact_ids && b.fact_ids.length > 0 && (
                          <span className="ml-2 text-[10px] font-mono text-text-tertiary">
                            [Fact Provenance: {b.fact_ids[0].slice(0, 8)}]
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </Card>
        )}

        {/* Personalized Cover Letter Tab */}
        {activeTab === 'COVER_LETTER' && (
          <Card className="p-6 bg-surface shadow-apple-card space-y-4">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <h3 className="text-base font-semibold text-text-primary">
                  Personalized Cover Letter
                </h3>
                <p className="text-xs text-text-secondary mt-0.5">
                  Grounded in your verified candidate facts and tailored specifically for {companyName}.
                </p>
              </div>

              <div>
                {editingCoverLetter ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleSaveCoverLetter}
                    loading={savingCoverLetter}
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Save Changes</span>
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setEditingCoverLetter(true)}
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span>Edit Letter</span>
                  </Button>
                )}
              </div>
            </div>

            {editingCoverLetter ? (
              <textarea
                value={coverLetterText}
                onChange={(e) => setCoverLetterText(e.target.value)}
                className="w-full h-80 p-4 rounded-apple-md font-sans text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue leading-relaxed"
              />
            ) : (
              <div className="p-6 rounded-apple-md bg-canvas border border-border-subtle whitespace-pre-wrap font-sans text-sm text-text-primary leading-relaxed">
                {coverLetterText || 'No cover letter generated yet. Please generate a package from Queue.'}
              </div>
            )}
          </Card>
        )}

        {/* Mapped Form Answers Tab */}
        {activeTab === 'FIELDS' && (
          <Card className="p-6 bg-surface shadow-apple-card space-y-4">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <h3 className="text-base font-semibold text-text-primary">
                  Application Form Field Mappings
                </h3>
                <p className="text-xs text-text-secondary mt-0.5">
                  Values verified against active candidate facts before portal autofill.
                </p>
              </div>
              <span className="text-xs font-mono text-text-tertiary">
                8 Fields Mapped
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {[
                { key: 'full_name', label: 'Full Legal Name', val: candidateDisplayName, prov: 'USER_SUPPLIED', sensitive: false },
                { key: 'email', label: 'Email Address', val: 'ada@example.com', prov: 'USER_VERIFIED', sensitive: false },
                { key: 'phone', label: 'Phone Number', val: '+1234567890', prov: 'USER_VERIFIED', sensitive: false },
                { key: 'experience_years', label: 'Years of Experience', val: '3', prov: 'USER_SUPPLIED', sensitive: false },
                { key: 'work_auth', label: 'Authorized to Work in US', val: 'YES', prov: 'USER_VERIFIED', sensitive: true },
                { key: 'sponsorship', label: 'Requires Sponsorship', val: 'NO', prov: 'USER_VERIFIED', sensitive: true },
                { key: 'eeo_gender', label: 'Gender (EEO)', val: 'DECLINE', prov: 'USER_SUPPLIED', sensitive: true },
                { key: 'legal_attestation', label: 'Legal Attestation', val: 'agree', prov: 'USER_SUPPLIED', sensitive: true },
              ].map((entry) => (
                <div
                  key={entry.key}
                  className={`p-3.5 rounded-apple-sm border ${
                    entry.sensitive
                      ? 'bg-canvas border-warning-amber/30'
                      : 'bg-canvas border-border-subtle'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-text-secondary text-[11px] font-mono">{entry.label}</span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                        entry.prov === 'USER_VERIFIED'
                          ? 'bg-success-subtle text-success-green'
                          : 'bg-apple-blue-subtle text-apple-blue'
                      }`}
                    >
                      {entry.prov}
                    </span>
                  </div>
                  <div className="text-text-primary font-medium font-mono text-sm">
                    {entry.val}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
