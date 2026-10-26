import React, { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { Button } from '../components/ui/Button'
import { api } from '../api/client'
import {
  ShieldCheck,
  Save,
  RefreshCw,
  CheckCircle2,
  Sliders,
  Moon,
  Sun,
  Monitor,
  Info,
} from 'lucide-react'
import { useTheme, type ThemeMode } from '../components/ThemeProvider'
import { spring } from '../design/motion'

type SettingsTab = 'appearance' | 'behavior' | 'integrations' | 'about'

export const SettingsScreen: React.FC = () => {
  const { mode, setMode } = useTheme()
  const [activeTab, setActiveTab] = useState<SettingsTab>('appearance')
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

  const TABS = [
    { id: 'appearance' as SettingsTab, label: 'Appearance', icon: Sun },
    { id: 'behavior' as SettingsTab, label: 'Application Behavior', icon: Sliders },
    { id: 'integrations' as SettingsTab, label: 'Application Safeguards', icon: ShieldCheck },
    { id: 'about' as SettingsTab, label: 'About JOV.si', icon: Info },
  ]

  return (
    <div className="screen-page space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-border">
        <div>
          <p className="page-kicker">Account & Workflow</p>
          <h1 className="page-title">Settings & Safeguards</h1>
          <p className="page-intro">
            Suitability floor parameters, daily volume caps, theme preferences, and verified safety controls.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button variant="secondary" size="md" onClick={loadSettings} loading={loading}>
            <RefreshCw className="w-4 h-4" />
            <span>Reload</span>
          </Button>
        </div>
      </div>

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
          <span>{error}</span>
          <button onClick={() => setError(null)} className="p-1 hover:opacity-70">
            ×
          </button>
        </div>
      )}

      {/* Main Settings Grid: Left Rail + Content */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Sticky Nav Rail */}
        <div className="lg:col-span-4 sticky top-24 space-y-1">
          {TABS.map((tab) => {
            const active = activeTab === tab.id
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-left transition-colors ${
                  active ? 'text-text font-semibold' : 'text-text-2 hover:text-text hover:bg-selected'
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="settings-tab-pill"
                    className="absolute inset-0 rounded-xl bg-selected border border-border/80"
                    transition={spring.layout}
                  />
                )}
                <Icon className="relative z-10 w-4 h-4 text-text-3" strokeWidth={1.5} />
                <span className="relative z-10 text-sm">{tab.label}</span>
              </button>
            )
          })}
        </div>

        {/* Right Settings Content */}
        <div className="lg:col-span-8">
          <form onSubmit={handleSave} className="space-y-6">
            {activeTab === 'appearance' && (
              <div className="border-t border-border/60 pt-6 space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-text">Visual Theme</h3>
                  <p className="text-xs text-text-3 mt-1">
                    Select your preferred interface theme. In system mode, JOV.si adapts automatically.
                  </p>
                </div>

                {/* 3-Segment Theme Selector with layoutId sliding indicator */}
                <div className="inline-flex items-center p-1.5 rounded-full bg-bg-elev-1/60 border border-border/80">
                  {[
                    { id: 'light' as ThemeMode, label: 'Light', icon: Sun },
                    { id: 'dark' as ThemeMode, label: 'Dark', icon: Moon },
                    { id: 'system' as ThemeMode, label: 'System', icon: Monitor },
                  ].map((opt) => {
                    const active = mode === opt.id
                    const Icon = opt.icon
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={(e) => setMode(opt.id, e)}
                        className={`relative flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium transition-colors ${
                          active ? 'text-text font-semibold' : 'text-text-3 hover:text-text'
                        }`}
                      >
                        {active && (
                          <motion.span
                            layoutId="theme-selector-pill"
                            className="absolute inset-0 rounded-full bg-bg-elev-1 border border-border shadow-1"
                            transition={spring.layout}
                          />
                        )}
                        <Icon className="relative z-10 w-3.5 h-3.5" strokeWidth={1.5} />
                        <span className="relative z-10">{opt.label}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {activeTab === 'behavior' && (
              <div className="border-t border-border/60 pt-6 space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-text">Matching & Quotas</h3>
                  <p className="text-xs text-text-3 mt-1">
                    Control suitability gating floors and anti-spam application volume limits.
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <label className="font-semibold text-text">Suitability Floor Score</label>
                      <span className="font-mono text-text font-semibold">{suitabilityFloor}/100</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={suitabilityFloor}
                      onChange={(e) => setSuitabilityFloor(Number(e.target.value))}
                      className="w-full accent-text cursor-pointer"
                    />
                    <p className="text-[11px] text-text-3">
                      Roles scoring below this threshold are automatically flagged as Below Threshold.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-border">
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-text">Daily Global Cap</label>
                      <input
                        type="number"
                        min={1}
                        max={50}
                        value={dailyCapGlobal}
                        onChange={(e) => setDailyCapGlobal(Number(e.target.value))}
                        className="app-input"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-text">Daily Per Portal</label>
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={dailyCapPortal}
                        onChange={(e) => setDailyCapPortal(Number(e.target.value))}
                        className="app-input"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-text">Daily Per Company</label>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        value={dailyCapCompany}
                        onChange={(e) => setDailyCapCompany(Number(e.target.value))}
                        className="app-input"
                      />
                    </div>
                  </div>
                </div>

                <div className="pt-2">
                  <Button type="submit" variant="primary" size="md" loading={saving}>
                    <Save className="w-4 h-4" />
                    <span>Save Application Settings</span>
                  </Button>
                </div>
              </div>
            )}

            {activeTab === 'integrations' && (
              <div className="border-t border-border/60 pt-6 space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-text">Application Safeguards</h3>
                  <p className="text-xs text-text-3 mt-1">
                    Strict security boundaries and verification controls protecting your application process.
                  </p>
                </div>

                <div className="p-5 rounded-xl border border-border/60 bg-bg-elev-1/30 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <ShieldCheck className="w-4 h-4 text-text" strokeWidth={1.5} />
                      <span className="text-sm font-semibold text-text">
                        Supervised Verification & Staging
                      </span>
                    </div>
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono border border-border/60 text-text-2">
                      Protected
                    </span>
                  </div>
                  <p className="text-xs text-text-2 leading-relaxed">
                    JOV.si operates with strict candidate provenance. Tailored resumes, cover letters, and application answers remain securely staged in your private workspace. Nothing is ever submitted to an employer portal without your explicit review and sign-off.
                  </p>
                  <div className="pt-3 border-t border-border flex items-center justify-between text-xs text-text-3">
                    <span>Provenance standard</span>
                    <span className="text-text font-medium">Cryptographic Package Verification</span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'about' && (
              <div className="border-t border-border/60 pt-6 space-y-5">
                <div>
                  <h3 className="text-sm font-semibold text-text">About JOV.si</h3>
                  <p className="text-xs text-text-3 mt-1">
                    Autonomous job application platform engineered around factual candidate provenance.
                  </p>
                </div>

                <div className="text-xs text-text-2 space-y-3 pt-3 border-t border-border">
                  <div className="flex items-center justify-between">
                    <span className="text-text-3">Platform</span>
                    <span className="text-text font-medium">JOV.si Autonomous Career Platform</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-text-3">Version</span>
                    <span className="font-mono text-text">0.2.0</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-text-3">Data Integrity</span>
                    <span className="text-text">Verified Provenance Standard</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-text-3">System Status</span>
                    <span className="font-mono text-[11px] text-text-2 border border-border/60 px-1.5 py-0.5 rounded">
                      OPERATIONAL
                    </span>
                  </div>
                </div>
              </div>
            )}
          </form>
        </div>
      </div>
    </div>
  )
}
