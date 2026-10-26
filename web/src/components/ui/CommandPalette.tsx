import React, { useEffect, useMemo, useState, useRef } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  Search,
  X,
  LayoutDashboard,
  Briefcase,
  Layers,
  History,
  UserCheck,
  Settings,
  Activity,
  Sun,
  Moon,
  FileUp,
} from 'lucide-react'
import { modalVariants, spring } from '../../design/motion'
import { useTheme } from '../ThemeProvider'
import type { TabId } from '../layout/FloatingNav'

export interface CommandAction {
  id: string
  label: string
  hint: string
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>
  category: 'Navigation' | 'Actions' | 'Preferences'
  run: () => void
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  onNavigate: (tab: TabId) => void
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  open,
  onClose,
  onNavigate,
}) => {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const reducedMotion = useReducedMotion()
  const { resolvedTheme, toggleTheme } = useTheme()

  const allActions: CommandAction[] = useMemo(
    () => [
      {
        id: 'nav-overview',
        label: 'Go to Overview',
        hint: 'Command center and status summary',
        icon: LayoutDashboard,
        category: 'Navigation',
        run: () => onNavigate('overview'),
      },
      {
        id: 'nav-jobs',
        label: 'Discover Jobs',
        hint: 'Browse matching opportunities and feeds',
        icon: Briefcase,
        category: 'Navigation',
        run: () => onNavigate('jobs'),
      },
      {
        id: 'nav-queue',
        label: 'Application Queue',
        hint: 'Review packages and advance active applications',
        icon: Layers,
        category: 'Navigation',
        run: () => onNavigate('queue'),
      },
      {
        id: 'nav-tracker',
        label: 'Application Tracker',
        hint: 'Verified audit trail and submission history',
        icon: History,
        category: 'Navigation',
        run: () => onNavigate('tracker'),
      },
      {
        id: 'nav-profile',
        label: 'Candidate Profile',
        hint: 'Structured records, skills, and resume facts',
        icon: UserCheck,
        category: 'Navigation',
        run: () => onNavigate('profile'),
      },
      {
        id: 'action-resume',
        label: 'Import Master Resume',
        hint: 'Upload PDF to extract verified candidate facts',
        icon: FileUp,
        category: 'Actions',
        run: () => onNavigate('profile'),
      },
      {
        id: 'action-theme',
        label: `Switch to ${resolvedTheme === 'dark' ? 'Light' : 'Dark'} Mode`,
        hint: 'Toggle interface visual theme appearance',
        icon: resolvedTheme === 'dark' ? Sun : Moon,
        category: 'Preferences',
        run: () => toggleTheme(),
      },
      {
        id: 'nav-settings',
        label: 'Settings',
        hint: 'Matching thresholds and environment configuration',
        icon: Settings,
        category: 'Navigation',
        run: () => onNavigate('settings'),
      },
      {
        id: 'nav-diagnostics',
        label: 'System Diagnostics',
        hint: 'Engine health, adapter state, and mock portal oracle',
        icon: Activity,
        category: 'Navigation',
        run: () => onNavigate('diagnostics'),
      },
    ],
    [onNavigate, resolvedTheme, toggleTheme]
  )

  const filtered = useMemo(() => {
    if (!query.trim()) return allActions
    const q = query.toLowerCase()
    return allActions.filter(
      (a) => a.label.toLowerCase().includes(q) || a.hint.toLowerCase().includes(q)
    )
  }, [allActions, query])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  useEffect(() => {
    setSelectedIndex(0)
  }, [filtered.length])

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filtered.length))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % Math.max(1, filtered.length))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const target = filtered[selectedIndex]
      if (target) {
        target.run()
        onClose()
      }
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-start justify-center p-4 pt-[14vh] sm:pt-[18vh]">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-overlay backdrop-blur-sm"
            aria-hidden="true"
          />

          {/* Palette Dialog */}
          <motion.section
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            variants={reducedMotion ? undefined : modalVariants}
            initial="hidden"
            animate="show"
            exit="exit"
            className="relative w-full max-w-xl glass rounded-card border border-glass-border shadow-float text-text z-10 overflow-hidden"
          >
            {/* Input Bar */}
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
              <Search className="w-4 h-4 text-text-3 shrink-0" strokeWidth={1.5} />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a command or search…"
                className="flex-1 bg-transparent text-[15px] text-text placeholder:text-text-3 outline-none"
              />
              <kbd className="hidden sm:inline-block font-mono text-[10px] text-text-3 px-1.5 py-0.5 rounded bg-bg-input border border-border">
                ESC
              </kbd>
              <button
                onClick={onClose}
                aria-label="Close command palette"
                className="p-1 rounded-full text-text-3 hover:text-text hover:bg-selected transition-colors"
              >
                <X className="w-4 h-4" strokeWidth={1.5} />
              </button>
            </div>

            {/* Results List */}
            <div className="p-2 max-h-[340px] overflow-y-auto space-y-0.5 [scrollbar-width:thin]">
              {filtered.length === 0 ? (
                <div className="py-8 text-center text-xs text-text-3">
                  No matching commands found for "{query}".
                </div>
              ) : (
                filtered.map((action, idx) => {
                  const Icon = action.icon
                  const isSelected = idx === selectedIndex

                  return (
                    <button
                      key={action.id}
                      onClick={() => {
                        action.run()
                        onClose()
                      }}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className={`relative w-full flex items-center justify-between px-3.5 py-2.5 rounded-md text-left transition-colors ${
                        isSelected ? 'text-text' : 'text-text-2 hover:text-text'
                      }`}
                    >
                      {isSelected && (
                        <motion.span
                          layoutId="cmd-active"
                          className="absolute inset-0 rounded-md bg-selected border border-border/40 pointer-events-none"
                          transition={spring.layout}
                        />
                      )}
                      <div className="relative z-10 flex items-center gap-3 min-w-0">
                        <Icon className="w-4 h-4 text-text-3 shrink-0" strokeWidth={1.5} />
                        <div className="truncate">
                          <p className="text-[13px] font-medium leading-none text-text">
                            {action.label}
                          </p>
                          <p className="mt-1 text-[11px] text-text-3 leading-none truncate">
                            {action.hint}
                          </p>
                        </div>
                      </div>
                      <span className="relative z-10 text-[10px] text-text-3 font-mono px-2 py-0.5 rounded bg-bg-input border border-border">
                        {action.category}
                      </span>
                    </button>
                  )
                })
              )}
            </div>
          </motion.section>
        </div>
      )}
    </AnimatePresence>
  )
}
