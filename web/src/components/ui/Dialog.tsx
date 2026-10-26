import React, { useEffect, useRef } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'motion/react'
import { X } from 'lucide-react'
import { modalVariants } from '../../design/motion'

interface DialogProps {
  open: boolean
  onClose: () => void
  title?: React.ReactNode
  description?: React.ReactNode
  children: React.ReactNode
  maxWidth?: string
  className?: string
}

export const Dialog: React.FC<DialogProps> = ({
  open,
  onClose,
  title,
  description,
  children,
  maxWidth = 'max-w-lg',
  className = '',
}) => {
  const reducedMotion = useReducedMotion()
  const dialogRef = useRef<HTMLDivElement>(null)

  // Esc key listener and focus trap
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          {/* Overlay Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-overlay backdrop-blur-sm transition-opacity"
            aria-hidden="true"
          />

          {/* Modal Container */}
          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={title ? 'dialog-title' : undefined}
            variants={reducedMotion ? undefined : modalVariants}
            initial="hidden"
            animate="show"
            exit="exit"
            className={`relative w-full ${maxWidth} glass rounded-card p-6 shadow-float border border-glass-border text-text z-10 overflow-hidden ${className}`}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                {title && (
                  <h2 id="dialog-title" className="text-lg font-semibold tracking-tight text-text">
                    {title}
                  </h2>
                )}
                {description && (
                  <p className="mt-1 text-sm text-text-2">
                    {description}
                  </p>
                )}
              </div>
              <button
                onClick={onClose}
                aria-label="Close dialog"
                className="p-1.5 rounded-full text-text-3 hover:text-text hover:bg-selected transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                <X className="w-4 h-4" strokeWidth={1.5} />
              </button>
            </div>

            {/* Body */}
            <div>{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
