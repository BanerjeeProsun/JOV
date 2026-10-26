import React from 'react'

interface StatusBadgeProps { state: string; className?: string }

export const StatusBadge: React.FC<StatusBadgeProps> = ({ state, className = '' }) => {
  const labels: Record<string, string> = {
    APPLIED_CONFIRMED: 'Applied (Confirmed)', SUBMISSION_UNCERTAIN: 'Sent, not confirmed',
    READY_FOR_REVIEW: 'Review required', APPROVAL_REQUESTED: 'Review required',
    APPROVED: 'Approved', APPROVED_PENDING_SUBMISSION: 'Approved', SUBMITTING: 'Submitting…',
    SHORTLISTED: 'Shortlisted', ELIGIBLE: 'Eligible', ELIGIBILITY_CHECKED: 'Eligible',
    BELOW_THRESHOLD: 'Below threshold', APPLICATION_FAILED: 'Failed', SUBMISSION_FAILED: 'Failed',
    REJECTED: 'Failed', PAUSED_AUTH: 'Action needed: sign in', DISCOVERED: 'Discovered',
  }
  const tone = state.includes('FAILED') || state === 'REJECTED' ? 'bg-danger-subtle text-danger-red' : state.includes('UNCERTAIN') || state === 'PAUSED_AUTH' ? 'bg-warning-subtle text-warning-amber' : state === 'APPLIED_CONFIRMED' ? 'bg-success-subtle text-success-green' : 'bg-ash text-text-secondary'
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[12px] font-medium ${tone} ${className}`}>{labels[state] || state.replaceAll('_', ' ')}</span>
}
