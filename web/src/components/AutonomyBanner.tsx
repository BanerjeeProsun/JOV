import React, { useState } from 'react'
import { ShieldCheck, X } from 'lucide-react'

interface AutonomyBannerProps { allowRealSubmission?: boolean; submitHostAllowlist?: string[] }

export const AutonomyBanner: React.FC<AutonomyBannerProps> = ({ allowRealSubmission = false, submitHostAllowlist = ['127.0.0.1:8765', 'localhost:8765'] }) => {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null
  return <aside aria-label="System Safety Sandbox Notice" className="mx-auto w-full max-w-[1440px] px-5 pt-5 md:px-10">
    <div className="flex items-start justify-between gap-4 rounded-apple-md bg-ash px-5 py-3 text-[13px] text-text-secondary">
      <div className="flex items-start gap-2.5"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-text-primary" /><p className="m-0"><strong className="font-semibold text-text-primary">{allowRealSubmission ? 'Live submission mode' : 'Release 1 safety sandbox active'}</strong>{allowRealSubmission ? ' — submissions require a verified approval.' : ` — automated submissions are restricted to ${submitHostAllowlist.join(', ')}.`}</p></div>
      <button onClick={() => setDismissed(true)} className="shrink-0 rounded-full p-1 text-text-tertiary hover:bg-white hover:text-text-primary" aria-label="Dismiss safety notice"><X className="h-3.5 w-3.5" /></button>
    </div>
  </aside>
}
