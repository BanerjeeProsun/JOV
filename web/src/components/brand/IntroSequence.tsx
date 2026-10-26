import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'motion/react'
import { JLogo } from './JLogo'
import { dur, ease } from '../../design/motion'

interface IntroSequenceProps {
  onComplete: () => void
}

const STORAGE_KEY = 'jov-intro-played'

export const IntroSequence: React.FC<IntroSequenceProps> = ({ onComplete }) => {
  const reducedMotion = useReducedMotion()
  const [visible, setVisible] = useState<boolean>(() => {
    if (reducedMotion) return false
    try {
      return sessionStorage.getItem(STORAGE_KEY) !== 'true'
    } catch {
      return false
    }
  })

  const finishIntro = () => {
    try {
      sessionStorage.setItem(STORAGE_KEY, 'true')
    } catch {}
    setVisible(false)
    setTimeout(onComplete, 350)
  }

  useEffect(() => {
    if (!visible) {
      onComplete()
      return
    }

    // Auto-finish after 2.1s max
    const timer = setTimeout(finishIntro, 2100)

    // Skip on key press or click anywhere
    const handleKey = () => finishIntro()
    window.addEventListener('keydown', handleKey)
    window.addEventListener('click', handleKey)

    return () => {
      clearTimeout(timer)
      window.removeEventListener('keydown', handleKey)
      window.removeEventListener('click', handleKey)
    }
  }, [visible])

  if (!visible) return null

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-bg text-text select-none cursor-pointer"
          initial={{ opacity: 1 }}
          exit={{
            opacity: 0,
            scale: 0.92,
            transition: { duration: dur.base, ease: ease.out },
          }}
          aria-label="Skip introduction"
        >
          {/* Ambient pearl light pool behind mark */}
          <div
            className="absolute w-[360px] h-[360px] rounded-full pointer-events-none opacity-40 blur-[70px]"
            style={{
              background: 'radial-gradient(circle, var(--pearl-1) 0%, var(--pearl-2) 40%, transparent 70%)',
            }}
          />

          <div className="relative z-10 flex flex-col items-center">
            <JLogo
              size={96}
              animated={true}
              variant="lockup"
              layoutId="brand-j"
              showSweep={true}
            />

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.4 }}
              transition={{ delay: 1.2, duration: 0.4 }}
              className="mt-6 text-[11px] tracking-widest uppercase text-text-3 font-mono"
            >
              Click or press any key to skip
            </motion.p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
