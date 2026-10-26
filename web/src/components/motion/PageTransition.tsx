import React, { useEffect, useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { pageVariants, dur, ease } from '../../design/motion'

interface PageTransitionProps {
  children: React.ReactNode
  pageKey: string
  className?: string
}

export const PageTransition: React.FC<PageTransitionProps> = ({ children, pageKey, className = '' }) => {
  const reducedMotion = useReducedMotion()
  const [navigating, setNavigating] = useState(false)

  useEffect(() => {
    setNavigating(true)
    window.scrollTo({ top: 0, behavior: 'instant' })
    const timer = setTimeout(() => setNavigating(false), dur.slow * 1000)
    return () => clearTimeout(timer)
  }, [pageKey])

  return (
    <div className={`relative w-full ${className}`}>
      {/* 1px pearl sweep indicator line across top during navigation */}
      {!reducedMotion && navigating && (
        <motion.div
          key={`sweep-${pageKey}`}
          className="fixed top-0 left-0 right-0 h-[2px] z-[90] pointer-events-none"
          style={{
            background: 'linear-gradient(90deg, transparent 0%, var(--pearl-1) 50%, var(--pearl-2) 80%, transparent 100%)',
          }}
          initial={{ x: '-100%', opacity: 1 }}
          animate={{ x: '100%', opacity: 0 }}
          transition={{ duration: dur.slow, ease: ease.out }}
        />
      )}

      <motion.div
        key={pageKey}
        variants={reducedMotion ? undefined : pageVariants}
        initial="initial"
        animate="enter"
        exit="exit"
        className="w-full"
      >
        {children}
      </motion.div>
    </div>
  )
}
