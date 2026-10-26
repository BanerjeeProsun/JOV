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

  let style = 'bg-bg-elev-2 text-text-2 border-border'
  let Icon = Clock

  if (state.includes('FAILED') || state === 'REJECTED') {
    style = 'bg-err-subtle text-err border-err/20'
    Icon = XCircle
  } else if (state.includes('UNCERTAIN') || state === 'PAUSED_AUTH') {
    style = 'bg-warn-subtle text-warn border-warn/20'
    Icon = ShieldAlert
  } else if (state === 'APPLIED_CONFIRMED') {
    style = 'bg-ok-subtle text-ok border-ok/20'
    Icon = CheckCircle2
  } else if (state.includes('REVIEW') || state.includes('APPROVED')) {
    style = 'bg-info-subtle text-info border-info/20'
    Icon = AlertCircle
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium border ${style} ${className}`}
    >
      {showIcon && <Icon className="h-3 w-3 shrink-0" strokeWidth={1.5} />}
      <span>{labels[state] || state.replaceAll('_', ' ')}</span>
    </span>
  )
}
