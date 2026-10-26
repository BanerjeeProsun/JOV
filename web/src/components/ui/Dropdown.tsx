import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'motion/react'
import { dur, ease } from '../../design/motion'

export interface DropdownItem {
  id: string
  label: string
  icon?: React.ComponentType<{ className?: string }>
  onClick: () => void
  disabled?: boolean
  destructive?: boolean
}

interface DropdownProps {
  trigger: React.ReactNode
  items: DropdownItem[]
  align?: 'left' | 'right'
  className?: string
}

export const Dropdown: React.FC<DropdownProps> = ({
  trigger,
  items,
  align = 'right',
  className = '',
}) => {
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const reducedMotion = useReducedMotion()

  useEffect(() => {
    if (!open) return
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  return (
    <div ref={menuRef} className={`relative inline-block ${className}`}>
      <div onClick={() => setOpen(!open)} role="button" tabIndex={0}>
        {trigger}
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={reducedMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95, y: -6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: dur.fast, ease: ease.out }}
            className={`absolute top-full mt-2 z-50 min-w-[180px] rounded-card glass p-1.5 shadow-float border border-glass-border ${
              align === 'right' ? 'right-0' : 'left-0'
            }`}
          >
            {items.map((item) => {
              const Icon = item.icon
              return (
                <button
                  key={item.id}
                  disabled={item.disabled}
                  onClick={() => {
                    item.onClick()
                    setOpen(false)
                  }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors text-left ${
                    item.destructive
                      ? 'text-err hover:bg-err-subtle'
                      : 'text-text-2 hover:text-text hover:bg-selected'
                  } ${item.disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
                >
                  {Icon && <Icon className="w-4 h-4 shrink-0" />}
                  <span>{item.label}</span>
                </button>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
