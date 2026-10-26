import React, { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
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
  Building,
  User,
} from 'lucide-react'

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
    if (filterState === 'REVIEW') {
      return rawState === 'READY_FOR_REVIEW' || rawState === 'APPROVAL_REQUESTED'
    }
    if (filterState === 'APPROVED') {
      return rawState === 'APPROVED' || rawState === 'APPROVED_PENDING_SUBMISSION'
    }
    if (filterState === 'APPLIED') {
      return rawState === 'APPLIED_CONFIRMED'
    }
    if (filterState === 'UNCERTAIN') {
      return rawState === 'SUBMISSION_UNCERTAIN'
    }
    return true
  })

  return (
    <div className="screen-page space-y-8">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Progressive Pipeline
          </span>
          <h1 className="page-title">
            Application Queue
          </h1>
          <p className="page-intro">
            Active applications moving step-by-step through deterministic eligibility, tailored document synthesis, and 15-point validation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={loadApplications} loading={loading}>
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Queue</span>
          </Button>
        </div>
      </div>

      {feedback && (
        <div className="p-4 rounded-apple-md bg-apple-blue-subtle border border-apple-blue/20 text-text-primary text-xs flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-apple-blue flex-shrink-0" />
            <span className="font-medium">{feedback}</span>
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="text-text-tertiary hover:text-text-primary"
          >
            ×
          </button>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 border-b border-border-subtle pb-3 overflow-x-auto">
        {[
          { id: 'ALL', label: `All Applications (${applications.length})` },
          { id: 'REVIEW', label: 'Review Required' },
          { id: 'APPROVED', label: 'Approved' },
          { id: 'APPLIED', label: 'Confirmed Applied' },
          { id: 'UNCERTAIN', label: 'Uncertain' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilterState(tab.id)}
            className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
              filterState === tab.id
                ? 'bg-text-primary text-white shadow-sm'
                : 'text-text-secondary hover:text-text-primary hover:bg-black/5'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Queue List */}
      {loading ? (
        <div className="text-center py-16 text-text-tertiary text-sm animate-pulse">
          Loading applications...
        </div>
      ) : filteredApps.length === 0 ? (
        <Card className="text-center py-16 bg-surface">
          <Layers className="w-12 h-12 text-text-tertiary mx-auto mb-3 opacity-40" />
          <h3 className="text-base font-semibold text-text-primary">Queue is empty</h3>
          <p className="text-xs text-text-secondary mt-1 max-w-sm mx-auto">
            No active applications in this stage. Go to Job Discovery to select an opportunity.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredApps.map((app) => {
            const rawState = (app as any).state || app.current_state
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

            return (
              <Card
                key={app.id}
                className="p-6 bg-surface hover:shadow-apple-floating transition-all"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold text-text-primary tracking-tight">
                        {roleTitle}
                      </h3>
                      <StatusBadge state={rawState} />
                    </div>

                    <div className="flex items-center gap-4 text-xs text-text-secondary">
                      <span className="flex items-center gap-1 font-medium">
                        <Building className="w-3.5 h-3.5 text-text-tertiary" />
                        {companyName}
                      </span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <User className="w-3.5 h-3.5 text-text-tertiary" />
                        {candidateName}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 pt-1 text-[11px] font-mono text-text-tertiary">
                      <span>ID: {app.id.slice(0, 8)}</span>
                      <span>•</span>
                      <span>Version: {app.version}</span>
                      {(app as any).score !== undefined && (app as any).score !== null && (
                        <>
                          <span>•</span>
                          <span className="text-success-green font-medium">
                            Score: {(app as any).score}/100
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Progressive Actions */}
                  <div className="flex items-center gap-2.5 flex-wrap self-start md:self-auto">
                    {canEvaluate && (
                      <Button
                        variant="primary"
                        size="sm"
                        loading={isActing}
                        onClick={() => handleRunEvaluation(app.id)}
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>Run Evaluation</span>
                      </Button>
                    )}

                    {canGenerateResume && (
                      <Button
                        variant="primary"
                        size="sm"
                        loading={isActing}
                        onClick={() => handleGenerateResume(app.id)}
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>Generate Resume</span>
                      </Button>
                    )}

                    {canRunGate && (
                      <Button
                        variant="primary"
                        size="sm"
                        loading={isActing}
                        onClick={() => handleRunGate(app.id)}
                      >
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Execute Gate</span>
                      </Button>
                    )}

                    {canReview && (
                      <Button
                        variant="coral"
                        size="sm"
                        onClick={() => onSelectApplication(app.id)}
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Review Package</span>
                      </Button>
                    )}

                    {canSubmit && (
                      <Button
                        variant="primary"
                        size="sm"
                        loading={isActing}
                        onClick={() => handleSubmit(app.id)}
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>Submit to Portal</span>
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
