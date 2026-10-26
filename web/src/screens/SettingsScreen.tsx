import React, { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { api } from '../api/client'
import {
  ShieldCheck,
  Globe,
  Save,
  RefreshCw,
  CheckCircle,
  Sliders,
  Moon,
  Sun,
  Monitor,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useTheme, type ThemeMode } from '../components/ThemeProvider'

export const SettingsScreen: React.FC = () => {
  const { mode, setMode } = useTheme()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Form Fields
  const [suitabilityFloor, setSuitabilityFloor] = useState(70)
  const [dailyCapGlobal, setDailyCapGlobal] = useState(10)
  const [dailyCapPortal, setDailyCapPortal] = useState(5)
  const [dailyCapCompany, setDailyCapCompany] = useState(2)
  const [timezone, setTimezone] = useState('Asia/Kolkata')
  const [allowRealSubmission, setAllowRealSubmission] = useState(false)

  const loadSettings = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getSettings()
      setSuitabilityFloor((data as any).suitability_floor ?? 70)
      setDailyCapGlobal((data as any).daily_cap_global ?? 10)
      setDailyCapPortal((data as any).daily_cap_per_portal ?? 5)
      setDailyCapCompany((data as any).daily_cap_per_company ?? 2)
      setTimezone((data as any).timezone ?? 'Asia/Kolkata')
      setAllowRealSubmission((data as any).allow_real_submission ?? false)
    } catch (err: any) {
      setError(err.message || 'Failed to fetch settings')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setFeedback(null)
    setError(null)
    try {
      await api.updateSettings({
        suitability_floor: Number(suitabilityFloor),
        daily_cap_global: Number(dailyCapGlobal),
        daily_cap_per_portal: Number(dailyCapPortal),
        daily_cap_per_company: Number(dailyCapCompany),
        timezone,
        allow_real_submission: allowRealSubmission,
        submit_host_allowlist: allowRealSubmission
          ? ['*']
          : ['127.0.0.1:8765', 'localhost:8765'],
      } as any)
      setFeedback('Settings updated and persisted successfully!')
      setTimeout(() => setFeedback(null), 4000)
    } catch (err: any) {
      setError(err.message || 'Failed to update settings')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="screen-page space-y-8">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Platform Configuration
          </span>
          <h1 className="page-title">
            System Settings & Submission Modes
          </h1>
          <p className="page-intro">
            Configure matching suitability floors, rate-limiting quotas, and toggle between Safe Sandbox testing and Supervised Live submission.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={loadSettings} loading={loading}>
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Reload</span>
          </Button>
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
          <span>{error}</span>
        </div>
      )}

      <Card className="p-6 space-y-5">
        <div><p className="page-kicker">Appearance</p><h2 className="mt-1 text-[22px] font-semibold tracking-[-.02em] text-text-primary">Made for your environment.</h2><p className="mt-1 text-[14px] text-text-secondary">Your choice is saved locally and System follows your device preference.</p></div>
        <div className="inline-flex rounded-full bg-ash p-1" role="radiogroup" aria-label="Appearance preference">
          {([{ id: 'light', label: 'Light', icon: <Sun /> }, { id: 'dark', label: 'Dark', icon: <Moon /> }, { id: 'system', label: 'System', icon: <Monitor /> }] as Array<{ id: ThemeMode; label: string; icon: React.ReactNode }>).map((option) => <button key={option.id} role="radio" aria-checked={mode === option.id} onClick={() => setMode(option.id)} className={`relative inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-medium ${mode === option.id ? 'text-text-primary' : 'text-text-secondary'}`}>
            {mode === option.id && <motion.span layoutId="theme-choice" className="absolute inset-0 rounded-full bg-surface" transition={{ type: 'spring', stiffness: 430, damping: 32 }} />}
            {React.cloneElement(option.icon as React.ReactElement<{ className?: string }>, { className: 'relative h-3.5 w-3.5' })}<span className="relative">{option.label}</span>
          </button>)}
        </div>
      </Card>

      {/* Submission Mode Selector Card */}
      <Card className="p-6 bg-surface shadow-apple-card space-y-6">
        <div className="flex items-center justify-between border-b border-border-subtle pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-ash text-text-primary flex items-center justify-center">{allowRealSubmission ? <Globe className="w-5 h-5" /> : <ShieldCheck className="w-5 h-5" />}</div>
            <div>
              <h3 className="text-base font-semibold text-text-primary">
                {allowRealSubmission ? 'Supervised Live Mode (Real Portals Enabled)' : 'Safety Sandbox Mode (Mock Testing Only)'}
              </h3>
              <p className="text-xs text-text-secondary">
                {allowRealSubmission
                  ? 'Browser automation submits to external company portals under strict single-use approval verification.'
                  : 'All automated submissions are strictly constrained to the local hostile testing harness (127.0.0.1:8765).'}
              </p>
            </div>
          </div>

          <label className="relative inline-flex items-center cursor-pointer select-none">
            <input
              type="checkbox"
              checked={allowRealSubmission}
              onChange={(e) => setAllowRealSubmission(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-12 h-7 bg-black/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-200 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-success-green shadow-sm"></div>
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-apple-md bg-canvas border border-border-subtle space-y-1">
            <span className="font-semibold text-text-primary uppercase text-[11px] block">
              Safety Sandbox (Mock Portal)
            </span>
            <p className="text-text-secondary leading-relaxed">
              Automated browser interactions are strictly restricted to <code className="font-mono bg-white px-1 py-0.5 rounded border border-border-subtle text-text-primary">127.0.0.1:8765</code>.
              Safely test resume tailoring, validation gates, and rate limits without sending applications to real employers.
            </p>
          </div>

          <div className="p-4 rounded-apple-md bg-canvas border border-border-subtle space-y-1">
            <span className="font-semibold text-text-primary uppercase text-[11px] block">
              Supervised Live Submission Mode
            </span>
            <p className="text-text-secondary leading-relaxed">
              Permits submission to external career portals (Greenhouse, Lever, etc.). Submissions still require passing all 15 validation checks and explicit user approval bound to the SHA-256 package hash.
            </p>
          </div>
        </div>
      </Card>

      {/* Thresholds & Limit Configuration */}
      <form onSubmit={handleSave}>
        <Card className="p-6 bg-surface shadow-apple-card space-y-6">
          <div className="flex items-center gap-2 border-b border-border-subtle pb-3">
            <Sliders className="w-4 h-4 text-text-tertiary" />
            <h3 className="text-base font-semibold text-text-primary">
              Operational Thresholds & Rate Quotas
            </h3>
          </div>

          {/* Suitability Score Floor */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <label className="text-text-primary font-medium">
                Suitability Match Score Floor: <span className="font-mono text-text-primary font-semibold">{suitabilityFloor}/100</span>
              </label>
              <span className="text-text-tertiary text-[11px]">
                Jobs scored below this floor transition to BELOW_THRESHOLD
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={suitabilityFloor}
              onChange={(e) => setSuitabilityFloor(Number(e.target.value))}
              className="w-full accent-text-primary cursor-pointer"
            />
          </div>

          {/* Rate Limit Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            <div>
              <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                Global Daily Cap
              </label>
              <input
                type="number"
                min="1"
                max="100"
                value={dailyCapGlobal}
                onChange={(e) => setDailyCapGlobal(Number(e.target.value))}
                className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue font-mono"
              />
              <span className="text-[11px] text-text-tertiary mt-1 block">Max total submits/day</span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                Per-Portal Daily Cap
              </label>
              <input
                type="number"
                min="1"
                max="50"
                value={dailyCapPortal}
                onChange={(e) => setDailyCapPortal(Number(e.target.value))}
                className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue font-mono"
              />
              <span className="text-[11px] text-text-tertiary mt-1 block">Max per ATS domain</span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                Per-Company Daily Cap
              </label>
              <input
                type="number"
                min="1"
                max="20"
                value={dailyCapCompany}
                onChange={(e) => setDailyCapCompany(Number(e.target.value))}
                className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue font-mono"
              />
              <span className="text-[11px] text-text-tertiary mt-1 block">Max per employer</span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
              Candidate System Timezone
            </label>
            <input
              type="text"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full max-w-sm p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue font-mono"
            />
          </div>

          <div className="flex justify-end pt-4 border-t border-border-subtle">
            <Button variant="primary" size="md" type="submit" loading={saving}>
              <Save className="w-4 h-4" />
              <span>Save & Persist Configuration</span>
            </Button>
          </div>
        </Card>
      </form>
    </div>
  )
}
