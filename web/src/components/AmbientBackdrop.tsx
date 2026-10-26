import React from 'react'
import { motion, useReducedMotion } from 'motion/react'

/** Motion/SVG fallback for the requested cinematic welcome film. It is local, silent, and motion-safe. */
export const AmbientBackdrop: React.FC = () => {
  const reduced = useReducedMotion()
  return <div className="ambient-backdrop" aria-hidden="true">
    <svg viewBox="0 0 760 460" preserveAspectRatio="xMidYMid slice">
      <defs><filter id="soft"><feGaussianBlur stdDeviation="24" /></filter><linearGradient id="beam" x1="0" x2="1"><stop stopColor="currentColor" stopOpacity=".25" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></linearGradient></defs>
      <motion.path d="M40 340C184 87 407 71 726 105" stroke="url(#beam)" strokeWidth="110" fill="none" filter="url(#soft)" initial={false} animate={reduced ? {} : { pathLength: [0.68, 1, .68], opacity: [.25, .65, .25] }} transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }} />
      <motion.circle cx="520" cy="145" r="82" fill="currentColor" opacity=".08" filter="url(#soft)" animate={reduced ? {} : { x: [-26, 24, -26], y: [-8, 16, -8], scale: [.85, 1.15, .85] }} transition={{ duration: 14, repeat: Infinity, ease: 'easeInOut' }} />
      <motion.circle cx="265" cy="320" r="54" fill="currentColor" opacity=".12" filter="url(#soft)" animate={reduced ? {} : { x: [22, -18, 22], y: [12, -16, 12] }} transition={{ duration: 11, repeat: Infinity, ease: 'easeInOut' }} />
    </svg>
  </div>
}
