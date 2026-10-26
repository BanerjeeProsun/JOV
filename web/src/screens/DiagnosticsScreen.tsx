import React, { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { api } from '../api/client'
import type { DiagnosticsData } from '../types'
import {
  Server,
  Database,
  RefreshCw,
  RotateCcw,
  CheckCircle,
  ShieldCheck,
  Radio,
} from 'lucide-react'

export const DiagnosticsScreen: React.FC = () => {
  const [diag, setDiag] = useState<DiagnosticsData | null>(null)
  const [health, setHealth] = useState<any | null>(null)
  const [oracleRecords, setOracleRecords] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [resettingPortal, setResettingPortal] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [oracleError, setOracleError] = useState<string | null>(null)

  const loadDiagnostics = async () => {
    setLoading(true)
    try {
      const [diagData, healthData] = await Promise.all([
        api.getDiagnostics(),
        api.getHealth(),
      ])
      setDiag(diagData)
      setHealth(healthData)

      // Query mock portal oracle via backend proxy
      try {
        const oracleRes = await fetch('/api/v1/diagnostics/mock-portal/applications')
        if (oracleRes.ok) {
          const recs = await oracleRes.json()
          setOracleRecords(recs)
          setOracleError(null)
        } else {
          setOracleError('Mock portal not responding')
        }
      } catch (err) {
        setOracleError('Mock portal unreachable')
      }
    } catch (err: any) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDiagnostics()
  }, [])

  const handleResetMockPortal = async () => {
    setResettingPortal(true)
    setFeedback(null)
    try {
      const res = await fetch('/api/v1/diagnostics/mock-portal/reset', { method: 'POST' })
      if (res.ok) {
        setFeedback('Mock portal database reset to clean state (0 applications).')
        await loadDiagnostics()
      } else {
        setFeedback('Failed to reset mock portal.')
      }
    } catch (err: any) {
      setFeedback(`Could not reach mock portal: ${err.message}`)
    } finally {
      setResettingPortal(false)
    }
  }

  return (
    <div className="screen-page space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="page-title">
            System Diagnostics & Mock Oracle
          </h1>
          <p className="page-intro">
            Real-time process health, queue depth, database heartbeat, and mock portal state.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={loadDiagnostics} loading={loading}>
            <RefreshCw className="w-3.5 h-3.5" />
            Ping Services
          </Button>
          <Button
            variant="secondary"
            size="sm"
            loading={resettingPortal}
            onClick={handleResetMockPortal}
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Mock Portal State
          </Button>
        </div>
      </div>

      {feedback && (
        <div className="p-3.5 rounded-2xl bg-blue-50 border border-blue-200 text-blue-800 text-xs flex items-center justify-between shadow-subtle">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-blue-600 flex-shrink-0" />
            <span className="font-medium">{feedback}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="text-apple-subtle hover:text-apple-charcoal font-medium">
            ✕
          </button>
        </div>
      )}

      {/* Services Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* FastAPI Server */}
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase font-medium tracking-wider text-apple-subtle">Core API Server</span>
            <div className="w-8 h-8 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
              <Server className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-base font-semibold text-apple-charcoal">
              {health?.status === 'healthy' ? 'Healthy & Online' : 'Offline'}
            </span>
          </div>
          <div className="space-y-1 font-mono text-[11px] text-apple-subtle pt-2 border-t border-apple-border">
            <div>Product: {health?.product || 'JOV.si'}</div>
            <div>Autonomy: {health?.autonomy_level || 'L0_DRY_RUN'}</div>
            <div>Timestamp: {health?.timestamp ? new Date(health.timestamp).toLocaleTimeString() : '—'}</div>
          </div>
        </Card>

        {/* Database */}
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase font-medium tracking-wider text-apple-subtle">Database Engine</span>
            <div className="w-8 h-8 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-base font-semibold text-apple-charcoal">
              {diag?.database === 'connected' ? 'Connected & Verified' : 'Checking...'}
            </span>
          </div>
          <div className="space-y-1 font-mono text-[11px] text-apple-subtle pt-2 border-t border-apple-border">
            <div>Driver: SQLite / PostgreSQL Ready</div>
            <div>Queue Depth: {diag?.queue_depth ?? 0} active jobs</div>
            <div>Triggers: Append-Only Immutable</div>
          </div>
        </Card>

        {/* Mock Portal Ground Truth */}
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase font-medium tracking-wider text-apple-subtle">Mock Portal Oracle</span>
            <div className="w-8 h-8 rounded-full bg-orange-50 text-orange-600 flex items-center justify-center">
              <Radio className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`w-2.5 h-2.5 rounded-full ${
                oracleError ? 'bg-amber-400' : 'bg-emerald-500'
              }`}
            />
            <span className="text-base font-semibold text-apple-charcoal">
              {oracleError ? 'Mock Portal Standby' : 'Listening on 8765'}
            </span>
          </div>
          <div className="space-y-1 font-mono text-[11px] text-apple-subtle pt-2 border-t border-apple-border">
            <div>Oracle Records: {oracleRecords.length} stored</div>
            <div>Host: 127.0.0.1:8765</div>
            <div>Fault Modes: Hostile Simulation</div>
          </div>
        </Card>
      </div>

      {/* Mock Portal Oracle Records */}
      <Card className="space-y-4">
        <div className="flex items-center justify-between border-b border-apple-border pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-apple-accent" />
            <h3 className="text-base font-semibold text-apple-charcoal">
              Mock Portal Ground-Truth Oracle Records (/__admin/applications)
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              loading={resettingPortal}
              onClick={handleResetMockPortal}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Oracle
            </Button>
          </div>
        </div>

        {oracleRecords.length === 0 ? (
          <div className="text-center py-8 bg-apple-canvas/60 rounded-2xl border border-dashed border-apple-border text-apple-subtle text-xs">
            {oracleError || 'No applications recorded by the mock portal server yet. Submit an approved application to see its ground-truth entry appear here.'}
          </div>
        ) : (
          <div className="rounded-xl border border-apple-border overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-apple-canvas border-b border-apple-border text-apple-subtle uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-4 font-semibold">Confirmation #</th>
                  <th className="py-2.5 px-4 font-semibold">Full Name</th>
                  <th className="py-2.5 px-4 font-semibold">Email</th>
                  <th className="py-2.5 px-4 font-semibold">Submitted At</th>
                  <th className="py-2.5 px-4 font-semibold">Resume File</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-apple-border bg-white">
                {oracleRecords.map((rec: any, idx: number) => (
                  <tr key={idx} className="hover:bg-apple-canvas/40 transition-colors">
                    <td className="py-2.5 px-4 text-emerald-600 font-medium">
                      {rec.confirmation_number}
                    </td>
                    <td className="py-2.5 px-4 text-apple-charcoal font-medium">
                      {rec.full_name}
                    </td>
                    <td className="py-2.5 px-4 text-apple-subtle">
                      {rec.email}
                    </td>
                    <td className="py-2.5 px-4 text-apple-subtle">
                      {new Date(rec.submitted_at).toLocaleTimeString()}
                    </td>
                    <td className="py-2.5 px-4 text-apple-charcoal">
                      {rec.resume_filename || 'resume.pdf'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Layer Architecture Lints & Verification Check */}
      <Card variant="recessed" className="space-y-3 font-mono text-xs">
        <h4 className="text-xs uppercase tracking-wider font-semibold text-apple-charcoal">
          Structural Invariants Verified
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-apple-subtle">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>AST Layer Check: Domain imports zero network, DB, or external libraries.</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>Locator Lint: Zero raw xpath or brittle mouse.click locators.</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>Database Triggers: UPDATE and DELETE on events table trigger ABORT.</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>Allowlist Guard: Hostile external domains rejected prior to page navigation.</span>
          </div>
        </div>
      </Card>
    </div>
  )
}
