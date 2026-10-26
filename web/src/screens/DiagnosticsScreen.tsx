import React, { useEffect, useState } from 'react'
import { Button } from '../components/ui/Button'
import { api } from '../api/client'
import type { DiagnosticsData } from '../types'
import {
  RefreshCw,
  RotateCcw,
  CheckCircle2,
  Copy,
  AlertCircle,
} from 'lucide-react'

export const DiagnosticsScreen: React.FC = () => {
  const [diag, setDiag] = useState<DiagnosticsData | null>(null)
  const [health, setHealth] = useState<any | null>(null)
  const [oracleRecords, setOracleRecords] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [resettingPortal, setResettingPortal] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [oracleError, setOracleError] = useState<string | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

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
      } catch {
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

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(null), 2000)
  }

  return (
    <div className="screen-page space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-border">
        <div>
          <p className="page-kicker">Runtime Health</p>
          <h1 className="page-title">System Diagnostics & Mock Oracle</h1>
          <p className="page-intro">
            Live system telemetry, database health, safety sandbox status, and ground-truth oracle submission verification.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button variant="secondary" size="md" onClick={loadDiagnostics} loading={loading}>
            <RefreshCw className="w-4 h-4" />
            <span>Refresh Diagnostics</span>
          </Button>
          <Button
            variant="secondary"
            size="md"
            onClick={handleResetMockPortal}
            loading={resettingPortal}
          >
            <RotateCcw className="w-4 h-4" />
            <span>Reset Mock Portal</span>
          </Button>
        </div>
      </div>

      {feedback && (
        <div className="p-4 rounded-card border border-border bg-bg-elev-1 text-xs text-text flex items-center justify-between shadow-1">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-ok shrink-0" />
            <span>{feedback}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="text-text-3 hover:text-text">
            ×
          </button>
        </div>
      )}

      {/* Telemetry Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <div className="p-6 rounded-card border border-border bg-bg-elev-1 shadow-1 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-text-3 uppercase tracking-wider">FastAPI Core</span>
            <span className="w-2 h-2 rounded-full bg-ok" />
          </div>
          <div className="text-xl font-semibold text-text">
            {health?.status || 'HEALTHY'}
          </div>
          <p className="text-xs text-text-3 font-mono">
            Product: {health?.product || 'JOV.si Engine'}
          </p>
        </div>

        <div className="p-6 rounded-card border border-border bg-bg-elev-1 shadow-1 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-text-3 uppercase tracking-wider">Database Status</span>
            <span className="w-2 h-2 rounded-full bg-ok" />
          </div>
          <div className="text-xl font-semibold text-text">
            {diag?.database ? 'CONNECTED' : 'STANDBY'}
          </div>
          <p className="text-xs text-text-3 font-mono truncate">
            {diag?.database || 'SQLite (WAL)'}
          </p>
        </div>

        <div className="p-6 rounded-card border border-border bg-bg-elev-1 shadow-1 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-text-3 uppercase tracking-wider">Autonomy Guard</span>
            <span className="w-2 h-2 rounded-full bg-info" />
          </div>
          <div className="text-xl font-semibold text-text">
            {health?.autonomy_level || 'L0_DRY_RUN'}
          </div>
          <p className="text-xs text-text-3 font-mono">
            External submissions blocked
          </p>
        </div>
      </div>

      {/* Mock Portal Ground-Truth Oracle Records Section */}
      <div className="rounded-card border border-border bg-bg-elev-1 p-6 space-y-5 shadow-1">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border">
          <div>
            <h2 className="text-base font-semibold text-text">
              Mock Portal Ground-Truth Oracle Records
            </h2>
            <p className="text-xs text-text-3 mt-0.5">
              Independent ground-truth records stored directly inside the mock portal database.
            </p>
          </div>

          <span className="text-xs font-mono px-3 py-1 rounded-full bg-bg-input text-text-2 border border-border">
            {oracleRecords.length} recorded submissions
          </span>
        </div>

        {oracleError && (
          <div className="p-3 rounded-md bg-warn-subtle border border-warn/20 text-warn text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{oracleError}</span>
          </div>
        )}

        {oracleRecords.length === 0 ? (
          <div className="p-8 rounded-md bg-bg-input border border-border text-center text-xs text-text-3 font-mono">
            Zero submissions recorded in mock portal. Submit a package to see verification records.
          </div>
        ) : (
          <div className="space-y-3 font-mono text-xs">
            {oracleRecords.map((rec: any, idx: number) => {
              const candName = rec.candidate_name || rec.payload?.name || rec.name || 'Ada Lovelace'
              const roleTitle = rec.role_title || rec.payload?.role || 'Senior Software Engineer'
              const confId = rec.confirmation_id || rec.id || `MOCK-${idx}`

              return (
                <div
                  key={idx}
                  className="p-4 rounded-md border border-border bg-bg-input space-y-2 text-text"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-text">{candName}</span>
                    <span className="text-ok font-mono">{confId}</span>
                  </div>
                  <div className="flex items-center justify-between text-text-3 text-[11px]">
                    <span>Role: {roleTitle}</span>
                    <span>Received: {new Date(rec.submitted_at || Date.now()).toLocaleTimeString()}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Raw Diagnostic Payload */}
      {diag && (
        <div className="rounded-card border border-border bg-bg-elev-1 p-6 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-3">
              Full System Telemetry Payload
            </h3>
            <button
              onClick={() => copyToClipboard(JSON.stringify(diag, null, 2), 'diag')}
              className="inline-flex items-center gap-1.5 text-xs text-text-3 hover:text-text"
            >
              <Copy className="w-3.5 h-3.5" />
              <span>{copiedKey === 'diag' ? 'Copied' : 'Copy JSON'}</span>
            </button>
          </div>
          <pre className="p-4 rounded-md bg-bg-input border border-border text-[11px] font-mono text-text-2 overflow-x-auto max-h-[300px]">
            {JSON.stringify(diag, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
