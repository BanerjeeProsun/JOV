import React, { useEffect } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'motion/react'
import { X } from 'lucide-react'
import { drawerVariants } from '../../design/motion'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title?: React.ReactNode
  description?: React.ReactNode
  children: React.ReactNode
  width?: string
  className?: string
}

export const Drawer: React.FC<DrawerProps> = ({
  open,
  onClose,
  title,
  description,
  children,
  width = 'max-w-md',
  className = '',
}) => {
  const reducedMotion = useReducedMotion()

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
        <div className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-overlay backdrop-blur-sm transition-opacity"
            aria-hidden="true"
          />

          {/* Drawer Panel */}
          <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
            <motion.div
              role="dialog"
              aria-modal="true"
              variants={reducedMotion ? undefined : drawerVariants}
              initial="hidden"
              animate="show"
              exit="exit"
              className={`w-screen ${width} bg-bg-elev-1 border-l border-border shadow-float text-text flex flex-col ${className}`}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-border">
                <div>
                  {title && (
                    <h2 className="text-base font-semibold tracking-tight text-text">
                      {title}
                    </h2>
                  )}
                  {description && (
                    <p className="mt-1 text-xs text-text-3">
                      {description}
                    </p>
                  )}
                </div>
                <button
                  onClick={onClose}
                  aria-label="Close drawer"
                  className="p-1.5 rounded-full text-text-3 hover:text-text hover:bg-selected transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  <X className="w-4 h-4" strokeWidth={1.5} />
                </button>
              </div>

              {/* Body */}
              <div className="flex-1 overflow-y-auto p-6">{children}</div>
            </motion.div>
          </div>
        </div>
      )}
    </AnimatePresence>
  )
}
