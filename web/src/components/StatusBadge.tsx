import React from 'react'
import { CheckCircle2, AlertCircle, XCircle, Clock, ShieldAlert } from 'lucide-react'

interface StatusBadgeProps {
  state: string
  className?: string
  showIcon?: boolean
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ state, className = '', showIcon = true }) => {
  const labels: Record<string, string> = {
    APPLIED_CONFIRMED: 'Applied (Confirmed)',
    SUBMISSION_UNCERTAIN: 'Sent, not confirmed',
    READY_FOR_REVIEW: 'Review required',
    APPROVAL_REQUESTED: 'Review required',
    APPROVED: 'Approved',
    APPROVED_PENDING_SUBMISSION: 'Approved',
    SUBMITTING: 'Submitting…',
    SHORTLISTED: 'Shortlisted',
    ELIGIBLE: 'Eligible',
    ELIGIBILITY_CHECKED: 'Eligible',
    BELOW_THRESHOLD: 'Below threshold',
    APPLICATION_FAILED: 'Failed',
    SUBMISSION_FAILED: 'Failed',
    REJECTED: 'Failed',
    PAUSED_AUTH: 'Action needed: sign in',
    DISCOVERED: 'Discovered',
  }

  let style = 'bg-bg-input text-text-3 border-border/60'
  let Icon = Clock

  if (state.includes('FAILED') || state === 'REJECTED') {
    style = 'bg-transparent text-text-2 border-border-strong'
    Icon = XCircle
  } else if (state.includes('UNCERTAIN') || state === 'PAUSED_AUTH') {
    style = 'bg-transparent text-text-2 border-border'
    Icon = ShieldAlert
  } else if (state === 'APPLIED_CONFIRMED') {
    style = 'bg-transparent text-text border-border-strong font-medium'
    Icon = CheckCircle2
  } else if (state.includes('REVIEW') || state.includes('APPROVED')) {
    style = 'bg-transparent text-text-2 border-border'
    Icon = AlertCircle
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-mono border ${style} ${className}`}
    >
      {showIcon && <Icon className="h-3 w-3 shrink-0 opacity-70" strokeWidth={1.5} />}
      <span>{labels[state] || state.replaceAll('_', ' ')}</span>
    </span>
  )
}
