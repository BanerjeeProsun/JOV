import React, { useState } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'motion/react'
import { dur, ease } from '../../design/motion'

interface TooltipProps {
  content: React.ReactNode
  children: React.ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  className?: string
}

export const Tooltip: React.FC<TooltipProps> = ({
  content,
  children,
  position = 'top',
  className = '',
}) => {
  const [open, setOpen] = useState(false)
  const reducedMotion = useReducedMotion()

  const positions = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  }

  return (
    <div
      className={`relative inline-flex ${className}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      <AnimatePresence>
        {open && content && (
          <motion.div
            initial={reducedMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95, y: position === 'top' ? 4 : -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: dur.fast, ease: ease.out }}
            className={`absolute z-50 pointer-events-none whitespace-nowrap rounded-md glass px-2.5 py-1 text-[11px] font-medium text-text border border-glass-border shadow-1 ${positions[position]}`}
          >
            {content}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
