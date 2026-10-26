import React, { useEffect, useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { ease } from '../../design/motion'

interface FragmentConfig {
  id: number
  initX: number
  initY: number
  initRotate: number
  initScale: number
  initOpacity: number
  width: number
  targetY: number
  isMatch: boolean
}

// 32 deterministic seeds to avoid hydration/render jitter
const SEEDED_FRAGMENTS: FragmentConfig[] = Array.from({ length: 32 }, (_, i) => {
  const isMatch = i === 15
  // Deterministic pseudo-random values using sine/cosine hash
  const pseudo1 = Math.sin(i * 12.9898 + 78.233) * 43758.5453
  const r1 = pseudo1 - Math.floor(pseudo1)
  const pseudo2 = Math.cos(i * 4.898 + 34.123) * 23421.631
  const r2 = pseudo2 - Math.floor(pseudo2)

  const initX = (r1 - 0.5) * 280
  const initY = (r2 - 0.5) * 220
  const initRotate = (r1 - 0.5) * 65
  const initScale = 0.75 + r2 * 0.2
  const initOpacity = isMatch ? 0.8 : 0.2 + r1 * 0.25

  // In ordered state: stacked column centered vertically around 0
  const targetY = (i - 16) * 11
  const width = isMatch ? 240 : 160 + (i % 5) * 16

  return {
    id: i,
    initX,
    initY,
    initRotate,
    initScale,
    initOpacity,
    width,
    targetY,
    isMatch,
  }
})

export const ChaosToClarity: React.FC<{ className?: string }> = ({ className = '' }) => {
  const reducedMotion = useReducedMotion()
  const [resolved, setResolved] = useState(false)

  useEffect(() => {
    // Transition from chaotic to aligned clarity 400ms after mount
    const timer = setTimeout(() => setResolved(true), 400)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div
      className={`relative w-full h-[400px] flex items-center justify-center overflow-hidden pointer-events-none select-none ${className}`}
      aria-hidden="true"
    >
      {/* Central pearl illumination pool */}
      <motion.div
        className="absolute w-72 h-72 rounded-full opacity-40 blur-[60px]"
        style={{
          background: 'radial-gradient(circle, var(--pearl-1) 0%, var(--pearl-2) 45%, transparent 70%)',
        }}
        animate={{
          scale: resolved ? [1, 1.15, 1] : 0.8,
          opacity: resolved ? 0.6 : 0.2,
        }}
        transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Baseline guide line appearing on resolution */}
      <motion.div
        className="absolute left-1/2 -translate-x-1/2 w-[280px] h-[1px]"
        style={{
          background: 'linear-gradient(90deg, transparent, var(--border-strong), transparent)',
        }}
        initial={{ opacity: 0, scaleX: 0 }}
        animate={{ opacity: resolved ? 0.4 : 0, scaleX: resolved ? 1 : 0 }}
        transition={{ duration: 1.2, ease: ease.out }}
      />

      {/* 32 abstract document fragments */}
      {SEEDED_FRAGMENTS.map((frag) => {
        const isMatch = frag.isMatch

        return (
          <motion.div
            key={frag.id}
            className="absolute rounded-full border"
            style={{
              width: frag.width,
              height: isMatch ? '14px' : '7px',
              backgroundColor: isMatch ? 'var(--bg-elev-1)' : 'var(--bg-elev-2)',
              borderColor: isMatch ? 'var(--pearl-1)' : 'var(--border)',
              boxShadow: isMatch
                ? '0 0 20px var(--pearl-1), 0 0 40px var(--pearl-2)'
                : 'none',
              zIndex: isMatch ? 20 : 10,
            }}
            initial={
              reducedMotion
                ? { x: 0, y: frag.targetY, rotate: 0, scale: 1, opacity: frag.initOpacity }
                : {
                    x: frag.initX,
                    y: frag.initY,
                    rotate: frag.initRotate,
                    scale: frag.initScale,
                    opacity: frag.initOpacity,
                    filter: isMatch ? 'blur(0px)' : 'blur(2px)',
                  }
            }
            animate={
              resolved || reducedMotion
                ? {
                    x: 0,
                    y: frag.targetY,
                    rotate: 0,
                    scale: isMatch ? 1.06 : 0.98,
                    opacity: isMatch ? 1 : 0.45,
                    filter: 'blur(0px)',
                  }
                : undefined
            }
            transition={{
              type: 'spring',
              stiffness: isMatch ? 340 : 220 + (frag.id % 6) * 20,
              damping: 28,
              mass: 0.8,
              delay: isMatch ? 0.2 : (frag.id % 8) * 0.04,
            }}
          >
            {/* The single matched role displays an internal luminous signal dot */}
            {isMatch && (
              <div className="absolute left-2.5 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-ok animate-pulse" />
            )}
          </motion.div>
        )
      })}
    </div>
  )
}
