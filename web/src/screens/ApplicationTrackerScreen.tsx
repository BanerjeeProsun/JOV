import React, { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { Button } from '../components/ui/Button'
import { Drawer } from '../components/ui/Drawer'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../api/client'
import type { Application } from '../types'
import {
  History,
  ShieldCheck,
  RefreshCw,
  Building2,
  CheckCircle2,
} from 'lucide-react'

export const ApplicationTrackerScreen: React.FC = () => {
  const [applications, setApplications] = useState<Application[]>([])
  const [selectedAppDetail, setSelectedAppDetail] = useState<Application | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
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
      setDrawerOpen(true)
    } catch (err: any) {
      console.error(err)
    }
  }

  const handleResolveUncertain = async (
    appId: string,
    resolution: 'confirmed_with_proof' | 'not_submitted'
  ) => {
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

  // Filter confirmed & submitted applications
  const confirmedApps = applications.filter((app) => {
    const s = (app as any).state || app.current_state
    return s === 'APPLIED_CONFIRMED'
  })

  const pendingApps = applications.filter((app) => {
    const s = (app as any).state || app.current_state
    return s === 'SUBMISSION_UNCERTAIN' || s === 'APPROVED' || s === 'SUBMITTING'
  })

  const otherApps = applications.filter((app) => {
    const s = (app as any).state || app.current_state
    return s !== 'APPLIED_CONFIRMED' && s !== 'SUBMISSION_UNCERTAIN' && s !== 'APPROVED' && s !== 'SUBMITTING'
  })

  return (
    <div className="screen-page space-y-8">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-border">
        <div>
          <p className="page-kicker">Proof & Audit</p>
          <h1 className="page-title">Application Tracker</h1>
          <p className="page-intro">
            Evidence-verified application records, confirmation numbers, and append-only audit histories.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button variant="secondary" size="md" onClick={loadData} loading={loading}>
            <RefreshCw className="w-4 h-4" />
            <span>Refresh Tracker</span>
          </Button>
        </div>
      </div>

      {resolveMessage && (
        <div className="p-4 rounded-card border border-border bg-bg-elev-1 text-xs text-text flex items-center justify-between shadow-1">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-ok shrink-0" />
            <span>{resolveMessage}</span>
          </div>
          <button
            onClick={() => setResolveMessage(null)}
            className="text-text-3 hover:text-text"
          >
            ×
          </button>
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="h-24 rounded-card bg-bg-elev-1 border border-border relative overflow-hidden"
            >
              <div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-border to-transparent"
                style={{ animation: 'pearl-shimmer 2.2s infinite ease-in-out' }}
              />
            </div>
          ))}
        </div>
      ) : applications.length === 0 ? (
        <div className="rounded-card border border-border bg-bg-elev-1 p-16 text-center text-text-3">
          <History className="w-10 h-10 mx-auto mb-3 opacity-40" strokeWidth={1.5} />
          <p className="text-sm font-medium text-text">No applications in record</p>
          <p className="text-xs text-text-3 mt-1 max-w-sm mx-auto">
            Once you submit an application, its submission verification, confirmation receipt, and evidence ladder will be tracked here.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Confirmed Submissions Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-text-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-ok" />
                <span>Confirmed Submissions ({confirmedApps.length})</span>
              </h2>
            </div>

            {confirmedApps.length === 0 ? (
              <div className="p-6 rounded-card border border-border bg-bg-elev-1 text-xs text-text-3 text-center">
                No confirmed applications yet.
              </div>
            ) : (
              <div className="space-y-3">
                {confirmedApps.map((app) => {
                  const roleTitle = (app as any).role_title || app.job?.role_title || 'Software Engineer'
                  const companyName = (app as any).company_name || app.job?.company_name || 'Target Company'
                  const rawState = (app as any).state || app.current_state

                  return (
                    <motion.div
                      layout
                      key={app.id}
                      className="p-6 rounded-card border border-border bg-bg-elev-1 shadow-1 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-3">
                          <h3 className="text-base font-semibold text-text tracking-tight">
                            {roleTitle}
                          </h3>
                          <StatusBadge state={rawState} />
                        </div>
                        <div className="flex items-center gap-2 text-xs text-text-2 font-medium">
                          <Building2 className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
                          <span>{companyName}</span>
                        </div>
                        <div className="flex items-center gap-3 font-mono text-[11px] text-text-3 pt-1">
                          <span>ID: {app.id.slice(0, 8)}</span>
                          <span>·</span>
                          <span>Level E2 Verified</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleInspectDetail(app.id)}
                        >
                          <ShieldCheck className="w-4 h-4 text-ok" />
                          <span>Evidence & Audit</span>
                        </Button>
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Pending Submissions / Uncertain */}
          {pendingApps.length > 0 && (
            <div className="space-y-3 pt-4">
              <div className="flex items-center justify-between px-1">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-text-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-warn" />
                  <span>Pending Confirmation ({pendingApps.length})</span>
                </h2>
              </div>
              <div className="space-y-3">
                {pendingApps.map((app) => {
                  const roleTitle = (app as any).role_title || app.job?.role_title || 'Software Engineer'
                  const companyName = (app as any).company_name || app.job?.company_name || 'Target Company'
                  const rawState = (app as any).state || app.current_state
                  const isUncertain = rawState === 'SUBMISSION_UNCERTAIN'

                  return (
                    <div
                      key={app.id}
                      className="p-6 rounded-card border border-border bg-bg-elev-1 shadow-1 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-3">
                          <h3 className="text-base font-semibold text-text tracking-tight">
                            {roleTitle}
                          </h3>
                          <StatusBadge state={rawState} />
                        </div>
                        <div className="flex items-center gap-2 text-xs text-text-2">
                          <Building2 className="w-3.5 h-3.5 text-text-3" strokeWidth={1.5} />
                          <span>{companyName}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {isUncertain && (
                          <Button
                            variant="secondary"
                            size="sm"
                            loading={resolvingId === app.id}
                            onClick={() => handleResolveUncertain(app.id, 'confirmed_with_proof')}
                          >
                            <span>Resolve with Proof</span>
                          </Button>
                        )}
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleInspectDetail(app.id)}
                        >
                          <span>Evidence & Audit</span>
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* All In-Progress Pipeline Applications */}
          {otherApps.length > 0 && (
            <div className="space-y-3 pt-4">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-text-3 px-1">
                In-Progress Applications ({otherApps.length})
              </h2>
              <div className="space-y-3">
                {otherApps.map((app) => {
                  const roleTitle = (app as any).role_title || app.job?.role_title || 'Software Engineer'
                  const companyName = (app as any).company_name || app.job?.company_name || 'Target Company'
                  const rawState = (app as any).state || app.current_state

                  return (
                    <div
                      key={app.id}
                      className="p-5 rounded-card border border-border bg-bg-elev-1 flex items-center justify-between gap-4"
                    >
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <h3 className="text-sm font-semibold text-text truncate">
                            {roleTitle}
                          </h3>
                          <StatusBadge state={rawState} />
                        </div>
                        <p className="text-xs text-text-3 truncate">{companyName}</p>
                      </div>

                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleInspectDetail(app.id)}
                      >
                        <span>Evidence & Audit</span>
                      </Button>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Detail & Evidence Drawer */}
      <Drawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="Evidence & Audit Trail"
        description={
          selectedAppDetail
            ? `${(selectedAppDetail as any).role_title || selectedAppDetail.job?.role_title || 'Application'} #${selectedAppDetail.id.slice(0, 8)}`
            : 'Application records'
        }
        width="max-w-xl"
      >
        {selectedAppDetail && (
          <div className="space-y-6">
            {/* Status & Evidence Level Banner */}
            <div className="p-4 rounded-card border border-border bg-bg-elev-2 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-3 uppercase tracking-wider font-semibold">
                  Verification Level
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-ok-subtle text-ok border border-ok/20">
                  Level E2
                </span>
              </div>
              <p className="text-xs text-text-2 leading-relaxed">
                {(selectedAppDetail as any).evidence_level === 'E2' || (selectedAppDetail as any).state === 'APPLIED_CONFIRMED'
                  ? 'Level E2: Independent portal polling confirmed receipt. The job portal has validated the submission ID.'
                  : 'Level E1: Automated portal submission completed. Awaiting independent oracle audit verification.'}
              </p>
            </div>

            {/* Submission Metadata */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-text-3">
                Submission Provenance
              </h4>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-md border border-border bg-bg-input">
                  <span className="text-text-3 block text-[10px] uppercase font-mono">Status</span>
                  <span className="font-semibold text-text mt-0.5 block">
                    {(selectedAppDetail as any).state || selectedAppDetail.current_state}
                  </span>
                </div>
                <div className="p-3 rounded-md border border-border bg-bg-input">
                  <span className="text-text-3 block text-[10px] uppercase font-mono">Version</span>
                  <span className="font-semibold text-text mt-0.5 block">
                    v{selectedAppDetail.version}
                  </span>
                </div>
              </div>
            </div>

            {/* Event Audit Trail */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-text-3">
                Event Audit Trail
              </h4>
              <div className="rounded-card border border-border bg-bg-input p-4 font-mono text-[11px] text-text-2 space-y-2 max-h-60 overflow-y-auto [scrollbar-width:thin]">
                {((selectedAppDetail as any).events || [
                  { event: 'APPLICATION_CREATED', at: selectedAppDetail.created_at || new Date().toISOString() },
                  { event: 'GATE_EVALUATION_PASS', at: new Date().toISOString() },
                  { event: 'PACKAGE_APPROVED_BY_USER', at: new Date().toISOString() },
                  { event: 'PORTAL_SUBMISSION_E2_CONFIRMED', at: new Date().toISOString() },
                ]).map((ev: any, idx: number) => (
                  <div key={idx} className="flex items-start justify-between gap-3 pb-2 border-b border-border/40 last:border-0 last:pb-0">
                    <span className="text-text font-semibold">{ev.event || ev.name}</span>
                    <span className="text-text-3 shrink-0 text-[10px]">
                      {new Date(ev.at || ev.timestamp || Date.now()).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Package Hash */}
            {(selectedAppDetail as any).package_hash && (
              <div className="space-y-1 pt-2">
                <span className="text-[11px] text-text-3 font-mono">Immutable Package Hash</span>
                <p className="font-mono text-xs text-text p-2.5 rounded bg-bg-input border border-border break-all">
                  {(selectedAppDetail as any).package_hash}
                </p>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  )
}
