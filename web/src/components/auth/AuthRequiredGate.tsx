import React from 'react'
import {
  Briefcase,
  Layers,
  History,
  UserCheck,
  Settings,
  ShieldCheck,
  LogIn,
  ArrowLeft,
  Sparkles,
} from 'lucide-react'
import { Button } from '../ui/Button'
import { useAuth } from '../../context/AuthContext'
import type { TabId } from '../layout/FloatingNav'

interface AuthRequiredGateProps {
  tab: TabId
  onNavigate: (tab: TabId) => void
}

const TAB_METADATA: Record<
  TabId,
  {
    title: string
    subtitle: string
    description: string
    icon: React.ComponentType<{ className?: string; strokeWidth?: number }>
    highlights: string[]
  }
> = {
  jobs: {
    title: 'Job Discovery & Multi-Source Feeds',
    subtitle: 'Real ATS Discovery & Geographic Search',
    description:
      'Search authentic, live job postings directly from Ashby, SmartRecruiters, Lever, Greenhouse, and verified aggregators with true country, state, and city normalization.',
    icon: Briefcase,
    highlights: [
      '249-country ISO-normalized geographic location filters',
      'Direct, authorized ATS connectors with real-time health probers',
      'Two-phase eligibility gating (9 deterministic rules + 0–100 scoring)',
      '1-click application staging into your private review queue',
    ],
  },
  queue: {
    title: 'Application Pipeline & Queue',
    subtitle: 'Supervised Workflow Execution',
    description:
      'Evaluate openings, compile factual tailored resumes, and execute 15-point pre-submission safety gates prior to any portal submission.',
    icon: Layers,
    highlights: [
      'Zero-hallucination resume tailoring derived strictly from master facts',
      'Automated 15-point pre-submission safety validation gate',
      'Cryptographic single-use SHA-256 package approval tokens',
      'Interactive form field mapping preview and manual handoff kits',
    ],
  },
  tracker: {
    title: 'Application Tracker & Audit Trail',
    subtitle: 'Independent Portal Evidence',
    description:
      'Monitor application outcomes backed by independent portal records, webhook evidence, and cryptographic event audit trails.',
    icon: History,
    highlights: [
      'Level E2 confirmed submission receipts from real job portals',
      'Full cryptographic audit event log with SHA-256 integrity check',
      'Anti-tamper status inspection and retry telemetry',
      'Zero synthetic metrics: pure SQL aggregation of verified records',
    ],
  },
  profile: {
    title: 'Candidate Profile & Master Fact Graph',
    subtitle: 'Master Resume Provenance',
    description:
      'Upload and manage your master resume with strict SHA-256 provenance tracking. Your credentials, contact information, and career history are isolated to your account.',
    icon: UserCheck,
    highlights: [
      'Instant PDF master-resume ingestion and structured fact extraction',
      'Immutable provenance tagging: every claim linked to verified source',
      'Isolated multi-tenant boundaries: zero data leakage across accounts',
      'Candidate fact graph management: skills, experience, education, auth',
    ],
  },
  settings: {
    title: 'Workspace Preferences & Autonomy',
    subtitle: 'Safety & Automation Policies',
    description:
      'Configure suitability thresholds, daily application velocity caps, timezone synchronization, and submission autonomy level.',
    icon: Settings,
    highlights: [
      'Suitability floor threshold (0–100 scoring cutoff)',
      'Daily submission limits and anti-spam protection',
      'Autonomy policies: L0 Dry-Run, L1 Human-in-the-Loop, L2 Supervised',
      'Credential vault status and session encryption',
    ],
  },
  overview: {
    title: 'Workspace Command Center',
    subtitle: 'Verified Outcomes & Overview',
    description:
      'A calm, truthful summary of your active job search, confirmed applications, and review queue.',
    icon: Sparkles,
    highlights: [
      'Personalized greeting and verified application counts',
      'Real-time pipeline breakdown and status telemetry',
    ],
  },
  diagnostics: {
    title: 'System Diagnostics & Health',
    subtitle: 'Service Probers & Ground-Truth Oracle',
    description:
      'Inspect system telemetry, connector probers, database integrity, and mock portal state.',
    icon: ShieldCheck,
    highlights: [
      'Live service probers for Ashby, SmartRecruiters, Jobicy, Adzuna',
      'Database health, table row counts, and migration status',
    ],
  },
}

export const AuthRequiredGate: React.FC<AuthRequiredGateProps> = ({ tab, onNavigate }) => {
  const { openAuthModal } = useAuth()
  const meta = TAB_METADATA[tab] || TAB_METADATA.jobs
  const Icon = meta.icon

  return (
    <div className="screen-page max-w-4xl mx-auto py-8 sm:py-12 space-y-10">
      {/* Back button */}
      <button
        onClick={() => onNavigate('overview')}
        className="inline-flex items-center gap-2 text-xs font-medium text-text-3 hover:text-text transition-colors group cursor-pointer"
      >
        <ArrowLeft className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-0.5" />
        <span>Return to Product Overview</span>
      </button>

      {/* Main Feature Gate Card */}
      <div className="p-8 sm:p-12 rounded-2xl bg-bg-elev-1/70 border border-border space-y-8 shadow-float">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
          <div className="w-14 h-14 rounded-2xl bg-bg border border-border flex items-center justify-center shrink-0 shadow-1">
            <Icon className="w-7 h-7 text-text" strokeWidth={1.5} />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase font-mono tracking-wider text-text-3 font-semibold">
                Private Account Workspace
              </span>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono text-text-3 border border-border bg-bg">
                <ShieldCheck className="w-3 h-3 text-emerald-500" />
                Protected
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-text">
              {meta.title}
            </h1>
            <p className="text-sm text-text-2">{meta.subtitle}</p>
          </div>
        </div>

        <p className="text-sm sm:text-[15px] leading-relaxed text-text-2 max-w-2xl">
          {meta.description}{' '}
          <strong className="text-text font-medium">
            Sign in or create an account to unlock this workspace.
          </strong>{' '}
          All candidate records, tailored resumes, and active application pipelines are strictly
          isolated to authenticated accounts.
        </p>

        {/* Feature Highlights Preview */}
        <div className="space-y-3 pt-2 border-t border-border/60">
          <p className="text-xs font-mono uppercase tracking-wider text-text-3">
            What you unlock with an account
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {meta.highlights.map((highlight, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2.5 p-3 rounded-xl bg-bg/60 border border-border/80 text-xs text-text-2"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0 mt-1.5" />
                <span>{highlight}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-4 pt-4 border-t border-border/60">
          <Button variant="primary" size="lg" onClick={openAuthModal} className="shadow-float">
            <LogIn className="w-4 h-4" />
            <span>Sign In or Create Account</span>
          </Button>

          <Button variant="secondary" size="lg" onClick={() => onNavigate('overview')}>
            <span>Explore Product Features</span>
          </Button>
        </div>
      </div>
    </div>
  )
}
