import React, { useState, useEffect } from 'react'
import {
  LayoutDashboard,
  Briefcase,
  Layers,
  History,
  UserCheck,
  Settings,
  Activity,
  Moon,
  Sun,
  Command,
} from 'lucide-react'
import { motion, useScroll, useMotionValueEvent, useReducedMotion } from 'motion/react'
import { JLogo } from '../brand/JLogo'
import { useTheme } from '../ThemeProvider'
import { spring } from '../../design/motion'

export type TabId = 'overview' | 'jobs' | 'queue' | 'tracker' | 'profile' | 'settings' | 'diagnostics'

interface FloatingNavProps {
  activeTab: TabId
  onSelectTab: (tab: TabId) => void
  onOpenCommand?: () => void
  isModalOpen?: boolean
  className?: string
}

interface NavItem {
  id: TabId
  label: string
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'jobs', label: 'Jobs', icon: Briefcase },
  { id: 'queue', label: 'Queue', icon: Layers },
  { id: 'tracker', label: 'Tracker', icon: History },
  { id: 'profile', label: 'Profile', icon: UserCheck },
  { id: 'settings', label: 'Settings', icon: Settings },
  { id: 'diagnostics', label: 'Diagnostics', icon: Activity },
]

export const FloatingNav: React.FC<FloatingNavProps> = ({
  activeTab,
  onSelectTab,
  onOpenCommand,
  isModalOpen = false,
  className = '',
}) => {
  const { resolvedTheme, toggleTheme } = useTheme()
  const reducedMotion = useReducedMotion()
  const [navVisible, setNavVisible] = useState(true)

  const { scrollY } = useScroll()

  // Reset visibility when tab changes
  useEffect(() => {
    setNavVisible(true)
  }, [activeTab])

  // Reveal when moving cursor towards top of window
  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (e.clientY < 96) {
        setNavVisible(true)
      }
    }
    window.addEventListener('mousemove', onMouseMove)
    return () => window.removeEventListener('mousemove', onMouseMove)
  }, [])

  // Auto-reveal if idle after scrolling
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null
    const onScroll = () => {
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => {
        setNavVisible(true)
      }, 1200)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      if (timer) clearTimeout(timer)
    }
  }, [])

  // Hide nav on deep scroll down, show on scroll up (never hide when modal is open or near top)
  useMotionValueEvent(scrollY, 'change', (latest) => {
    if (isModalOpen || reducedMotion) {
      setNavVisible(true)
      return
    }
    const prev = scrollY.getPrevious() ?? 0
    const diff = latest - prev
    if (latest < 60) {
      setNavVisible(true)
    } else if (diff > 10 && latest > 200) {
      setNavVisible(false)
    } else if (diff < -6) {
      setNavVisible(true)
    }
  })

  return (
    <>
      {/* Decorative pearl ambient glow positioned behind the nav */}
      <div
        className="fixed top-0 inset-x-0 mx-auto w-[600px] h-24 pointer-events-none z-40 opacity-50 blur-[48px]"
        style={{
          background: 'radial-gradient(ellipse at 50% 0%, var(--pearl-1) 0%, var(--pearl-2) 35%, transparent 70%)',
        }}
      />

      {/* Desktop & Tablet Floating Nav */}
      <motion.header
        initial={{ y: -80, opacity: 0 }}
        animate={{
          y: navVisible || isModalOpen ? 0 : -84,
          opacity: navVisible || isModalOpen ? 1 : 0,
        }}
        transition={spring.smooth}
        onFocusCapture={() => setNavVisible(true)}
        className={`fixed top-4 inset-x-0 mx-auto w-fit z-50 hidden sm:block ${className}`}
        aria-label="Main navigation"
      >
        <div className="glass flex items-center h-14 rounded-full p-1.5 gap-1 shadow-float">
          {/* Logo with shared layoutId */}
          <button
            onClick={() => onSelectTab('overview')}
            className="flex items-center gap-2 pl-3 pr-2.5 py-1 text-text rounded-full hover:opacity-85 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            aria-label="JOV.si home"
          >
            <JLogo size={26} layoutId="brand-j" variant="mark" />
            <span className="font-semibold text-[14px] tracking-tight text-text">JOV<span className="text-text-3">.si</span></span>
          </button>

          <div className="h-4 w-[1px] bg-border mx-1" />

          {/* Nav Items */}
          <nav className="flex items-center gap-0.5">
            {NAV_ITEMS.map((item) => {
              const active = activeTab === item.id
              const Icon = item.icon

              return (
                <button
                  key={item.id}
                  onClick={() => onSelectTab(item.id)}
                  aria-current={active ? 'page' : undefined}
                  className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-medium transition-colors ${
                    active ? 'text-text' : 'text-text-2 hover:text-text hover:bg-selected/40'
                  } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus`}
                >
                  {active && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 rounded-full bg-selected border border-border pointer-events-none"
                      transition={spring.layout}
                    />
                  )}
                  <Icon className="relative z-10 w-4 h-4 shrink-0" strokeWidth={1.5} />
                  <span className="relative z-10 hidden sm:inline">{item.label}</span>
                </button>
              )
            })}
          </nav>

          <div className="h-4 w-[1px] bg-border mx-1" />

          {/* Quick Actions: Command Palette & Theme Switch */}
          <div className="flex items-center gap-1 pr-1">
            {onOpenCommand && (
              <button
                onClick={onOpenCommand}
                aria-label="Open command palette (Ctrl+K or Cmd+K)"
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-full text-text-3 hover:text-text hover:bg-selected transition-colors text-[12px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                <Command className="w-3.5 h-3.5" strokeWidth={1.5} />
                <kbd className="hidden md:inline font-mono text-[10px] bg-bg-input px-1.5 py-0.5 rounded border border-border">
                  ⌘K
                </kbd>
              </button>
            )}

            <button
              onClick={(e) => toggleTheme(e)}
              aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`}
              className="p-2 rounded-full text-text-2 hover:text-text hover:bg-selected transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {resolvedTheme === 'dark' ? (
                <Sun className="w-4 h-4" strokeWidth={1.5} />
              ) : (
                <Moon className="w-4 h-4" strokeWidth={1.5} />
              )}
            </button>
          </div>
        </div>
      </motion.header>

      {/* Mobile Bottom Tab Bar (<640px) */}
      <nav
        className="fixed bottom-3 left-3 right-3 z-50 sm:hidden"
        aria-label="Mobile navigation"
      >
        <div className="glass flex items-center justify-around h-14 rounded-full px-2 shadow-float border border-border">
          {NAV_ITEMS.map((item) => {
            const active = activeTab === item.id
            const Icon = item.icon
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                aria-current={active ? 'page' : undefined}
                className={`relative flex flex-col items-center justify-center p-2 rounded-full text-xs ${
                  active ? 'text-text' : 'text-text-3'
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="mobile-nav-pill"
                    className="absolute inset-0 rounded-full bg-selected border border-border pointer-events-none"
                    transition={spring.layout}
                  />
                )}
                <Icon className="relative z-10 w-4 h-4" strokeWidth={1.5} />
                <span className="sr-only">{item.label}</span>
              </button>
            )
          })}
          <button
            onClick={(e) => toggleTheme(e)}
            aria-label="Toggle theme"
            className="p-2 text-text-3 hover:text-text"
          >
            {resolvedTheme === 'dark' ? <Sun className="w-4 h-4" strokeWidth={1.5} /> : <Moon className="w-4 h-4" strokeWidth={1.5} />}
          </button>
        </div>
      </nav>
    </>
  )
}
