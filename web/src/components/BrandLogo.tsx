import React from 'react'
import { motion, useReducedMotion } from 'motion/react'

interface BrandLogoProps { compact?: boolean; dark?: boolean; className?: string }

/** Original JOV.si monogram: the open orbit represents a focused opportunity path. */
export const BrandLogo: React.FC<BrandLogoProps> = ({ compact = false, dark = false, className = '' }) => {
  const reduceMotion = useReducedMotion()
  const ink = dark ? '#ffffff' : '#1d1d1f'
  return <span className={`inline-flex items-center gap-2 ${className}`} aria-label="JOV.si">
    <motion.svg width="28" height="28" viewBox="0 0 32 32" fill="none" aria-hidden="true" initial={reduceMotion ? false : { opacity: 0, scale: .85 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: 'spring', stiffness: 380, damping: 24 }}>
      <motion.path d="M23.8 6.3v11.3c0 5.2-3.1 8.1-7.8 8.1-3.4 0-6-1.5-7.8-4.2" stroke={ink} strokeWidth="3.1" strokeLinecap="round" initial={reduceMotion ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: .7, ease: [.22, 1, .36, 1] }} />
      <motion.path d="M8.2 21.5c1.4 2.4 3.7 3.8 6.6 3.8" stroke={ink} strokeWidth="3.1" strokeLinecap="round" initial={reduceMotion ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: .45, delay: .42 }} />
      <circle cx="23.8" cy="6.3" r="2.15" fill={ink} />
    </motion.svg>
    {!compact && <motion.span initial={reduceMotion ? false : { opacity: 0, x: -5 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: .18, duration: .35 }} className="text-[15px] font-semibold tracking-[-.03em]">JOV.si</motion.span>}
  </span>
}
