import React from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { ease, spring } from '../../design/motion'
import { Wordmark } from './Wordmark'

export interface JLogoProps {
  size?: number
  animated?: boolean
  variant?: 'mark' | 'lockup'
  layoutId?: string
  className?: string
  showSweep?: boolean
}

export const JLogo: React.FC<JLogoProps> = ({
  size = 32,
  animated = false,
  variant = 'mark',
  layoutId,
  className = '',
  showSweep = false,
}) => {
  const reducedMotion = useReducedMotion()
  const isAnimated = animated && !reducedMotion

  const svgContent = (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      width={size}
      height={size}
      className="shrink-0 text-text"
      aria-label="JOV.si mark"
    >
      {/* Optional pearl highlight sweep gradient mask */}
      <defs>
        <linearGradient id="pearlSweep" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--pearl-1)" stopOpacity="0.8" />
          <stop offset="50%" stopColor="var(--pearl-2)" stopOpacity="0.5" />
          <stop offset="100%" stopColor="var(--pearl-3)" stopOpacity="0.8" />
        </linearGradient>
      </defs>

      {isAnimated ? (
        <>
          <motion.path
            d="M40 12 V37 C40 46.4 33.4 52 26 52 C19 52 14 47.5 13 41"
            stroke="currentColor"
            strokeWidth="7"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.9, ease: ease.out }}
          />
          <motion.circle
            cx="24"
            cy="12"
            r="4"
            fill="currentColor"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.7, ...spring.snappy }}
          />
          {showSweep && (
            <motion.path
              d="M40 12 V37 C40 46.4 33.4 52 26 52 C19 52 14 47.5 13 41"
              stroke="url(#pearlSweep)"
              strokeWidth="7"
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={{ pathOffset: -1, opacity: 0 }}
              animate={{ pathOffset: 1, opacity: [0, 1, 0] }}
              transition={{ delay: 0.9, duration: 0.8, ease: ease.inOut }}
            />
          )}
        </>
      ) : (
        <>
          <path
            d="M40 12 V37 C40 46.4 33.4 52 26 52 C19 52 14 47.5 13 41"
            stroke="currentColor"
            strokeWidth="7"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="24" cy="12" r="4" fill="currentColor" />
        </>
      )}
    </svg>
  )

  const markElement = layoutId ? (
    <motion.div layoutId={layoutId} className="inline-flex items-center justify-center">
      {svgContent}
    </motion.div>
  ) : (
    svgContent
  )

  if (variant === 'mark') {
    return <span className={`inline-flex items-center ${className}`}>{markElement}</span>
  }

  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      {markElement}
      <Wordmark animated={isAnimated} size={Math.round(size * 0.58)} />
    </span>
  )
}
