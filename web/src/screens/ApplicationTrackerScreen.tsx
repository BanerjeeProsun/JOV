import React, { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../api/client'
import type { Application } from '../types'
import {
  History,
  ShieldCheck,
  FileCheck2,
  RefreshCw,
  ListTree,
  Building,
} from 'lucide-react'

export const ApplicationTrackerScreen: React.FC = () => {
  const [applications, setApplications] = useState<Application[]>([])
  const [selectedAppDetail, setSelectedAppDetail] = useState<Application | null>(null)
  const [loading, setLoading] = useState(true)
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [resolveMessage, setResolveMessage] = useState<string | null>(null)

  const loadData = async () => {
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
    loadData()
  }, [])

  const handleInspectDetail = async (appId: string) => {
    try {
      const detail = await api.getApplication(appId)
      setSelectedAppDetail(detail)
    } catch (err: any) {
      console.error(err)
    }
  }

  const handleResolveUncertain = async (appId: string, resolution: 'confirmed_with_proof' | 'not_submitted') => {
    setResolvingId(appId)
    try {
      const res = await api.resolveUncertain(appId, resolution)
      setResolveMessage(`Application #${appId.slice(0, 8)} resolved as ${res.state}`)
      await loadData()
      if (selectedAppDetail?.id === appId) {
        await handleInspectDetail(appId)
      }
    } catch (err: any) {
      setResolveMessage(`Error resolving: ${err.message}`)
    } finally {
      setResolvingId(null)
    }
  }

  return (
    <div className="screen-page space-y-8">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Proof & Audit
          </span>
          <h1 className="page-title">
            Application Tracker
          </h1>
          <p className="page-intro">
            Evidence-verified application records, confirmation numbers, and append-only audit histories.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={loadData} loading={loading}>
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Tracker</span>
          </Button>
        </div>
      </div>

      {resolveMessage && (
        <div className="p-4 rounded-apple-md bg-apple-blue-subtle border border-apple-blue/20 text-text-primary text-xs flex items-center justify-between shadow-sm">
          <span>{resolveMessage}</span>
          <button onClick={() => setResolveMessage(null)} className="text-text-tertiary hover:text-text-primary">
            ×
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-center py-16 text-text-tertiary text-sm animate-pulse">
          Querying application records and evidence logs...
        </div>
      ) : applications.length === 0 ? (
        <Card className="text-center py-16 bg-surface">
          <History className="w-12 h-12 text-text-tertiary mx-auto mb-3 opacity-40" />
          <h3 className="text-base font-semibold text-text-primary">No applications in record</h3>
          <p className="text-xs text-text-secondary mt-1 max-w-sm mx-auto">
            Once you submit an application, its submission verification, confirmation receipt, and evidence ladder will be tracked here.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Applications List */}
          <div className="lg:col-span-7 space-y-4">
            {applications.map((app) => {
              const rawState = (app as any).state || app.current_state
              const isUncertain = rawState === 'SUBMISSION_UNCERTAIN'
              const isSelected = selectedAppDetail?.id === app.id

              const roleTitle = (app as any).role_title || app.job?.role_title || 'Software Engineer'
              const companyName = (app as any).company_name || app.job?.company_name || 'Target Company'

              return (
                <Card
                  key={app.id}
                  onClick={() => handleInspectDetail(app.id)}
                  interactive
                  className={`p-5 bg-surface transition-all ${
                    isSelected ? 'ring-2 ring-apple-blue border-apple-blue/50' : ''
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-3">
                        <h3 className="text-base font-semibold text-text-primary tracking-tight">
                          {roleTitle}
                        </h3>
                        <StatusBadge state={rawState} />
                      </div>
                      <div className="flex items-center gap-2 text-xs text-text-secondary font-medium">
                        <Building className="w-3.5 h-3.5 text-text-tertiary" />
                        <span>{companyName}</span>
                      </div>
                      <div className="flex items-center gap-3 font-mono text-[11px] text-text-tertiary pt-0.5">
                        <span>ID: {app.id.slice(0, 8)}</span>
                        <span>•</span>
                        <span>
                          {new Date((app as any).updated_at || app.updated_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0 self-start sm:self-auto">
                      {isUncertain && (
                        <Button
                          variant="secondary"
                          size="sm"
                          loading={resolvingId === app.id}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleResolveUncertain(app.id, 'confirmed_with_proof')
                          }}
                        >
                          <span>Resolve as Confirmed</span>
                        </Button>
                      )}
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleInspectDetail(app.id)
                        }}
                      >
                        <span>Evidence & Audit</span>
                      </Button>
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>

          {/* Right Column: Evidence & Audit Inspector */}
          <div className="lg:col-span-5 space-y-4">
            {!selectedAppDetail ? (
              <Card className="text-center py-20 bg-surface">
                <FileCheck2 className="w-10 h-10 text-text-tertiary mx-auto mb-3 opacity-40" />
                <p className="text-xs text-text-secondary max-w-xs mx-auto">
                  Select an application to view its verified evidence artifacts and immutable event timeline.
                </p>
              </Card>
            ) : (
              <div className="space-y-5">
                {/* Evidence Artifacts */}
                <Card className="p-6 bg-surface shadow-apple-card space-y-4">
                  <div className="flex items-center justify-between border-b border-border-subtle pb-3">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-success-green" />
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-primary">
                        Evidence Record
                      </h4>
                    </div>
                    <StatusBadge state={(selectedAppDetail as any).state || selectedAppDetail.current_state} />
                  </div>

                  {selectedAppDetail.evidence && (selectedAppDetail.evidence as any).length > 0 ? (
                    <div className="space-y-3">
                      {(selectedAppDetail.evidence as any).map((ev: any, idx: number) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-apple-sm bg-canvas border border-border-subtle text-xs space-y-1.5"
                        >
                          <div className="flex items-center justify-between">
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-success-subtle text-success-green border border-success-green/20">
                              Level {ev.level}
                            </span>
                            <span className="text-[10px] text-text-tertiary font-mono">
                              {new Date(ev.created_at).toLocaleTimeString()}
                            </span>
                          </div>

                          {ev.payload?.confirmation_number && (
                            <div className="text-text-primary font-semibold text-sm">
                              Confirmation #{ev.payload.confirmation_number}
                            </div>
                          )}

                          <div className="text-[11px] text-text-secondary">
                            Kind: {ev.kind}
                          </div>

                          <div className="text-[10px] text-text-tertiary font-mono truncate">
                            SHA-256: {ev.sha256}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-text-tertiary italic">
                      No evidence artifacts logged yet.
                    </p>
                  )}
                </Card>

                {/* Event Audit Trail */}
                <Card className="p-6 bg-surface shadow-apple-card space-y-4">
                  <div className="flex items-center gap-2 border-b border-border-subtle pb-3">
                    <ListTree className="w-4 h-4 text-apple-blue" />
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-text-primary">
                      Event Audit Trail
                    </h4>
                  </div>

                  {selectedAppDetail.events && (selectedAppDetail.events as any).length > 0 ? (
                    <div className="space-y-2 text-xs">
                      {(selectedAppDetail.events as any).map((ev: any) => (
                        <div
                          key={ev.seq}
                          className="flex items-start gap-3 p-2.5 rounded-apple-sm hover:bg-canvas transition-colors"
                        >
                          <span className="font-mono text-[10px] text-text-tertiary mt-0.5 w-6">
                            #{ev.seq}
                          </span>
                          <div className="flex-1 space-y-0.5">
                            <div className="font-medium text-text-primary">
                              {ev.type}
                            </div>
                            <div className="text-[11px] text-text-secondary">
                              {ev.from_state ? `${ev.from_state} → ` : ''}
                              <strong className="text-text-primary">{ev.to_state}</strong>
                            </div>
                          </div>
                          <span className="font-mono text-[10px] text-text-tertiary">
                            {new Date(ev.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-text-tertiary italic">
                      No audit events recorded yet.
                    </p>
                  )}
                </Card>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
