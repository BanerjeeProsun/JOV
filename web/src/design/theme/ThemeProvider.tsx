import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'

export type ThemeMode = 'system' | 'light' | 'dark'
export type ResolvedTheme = 'light' | 'dark'

interface ThemeContextValue {
  mode: ThemeMode
  resolved: ResolvedTheme
  resolvedTheme: ResolvedTheme
  setMode: (mode: ThemeMode, event?: React.MouseEvent | MouseEvent) => void
  toggleTheme: (event?: React.MouseEvent | MouseEvent) => void
}

const STORAGE_KEY = 'jov-theme'

const ThemeContext = createContext<ThemeContextValue | null>(null)

function getStoredMode(): ThemeMode {
  try {
    const val = localStorage.getItem(STORAGE_KEY)
    if (val === 'light' || val === 'dark' || val === 'system') return val
  } catch {
    // LocalStorage inaccessible
  }
  return 'system'
}

function resolveSystem(): ResolvedTheme {
  if (typeof window === 'undefined') return 'dark'
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch {
    return 'dark'
  }
}

function applyThemeToDOM(resolved: ResolvedTheme) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', resolved)
  document.documentElement.style.colorScheme = resolved
  if (resolved === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

export const ThemeProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [mode, setModeState] = useState<ThemeMode>(getStoredMode)
  const [resolved, setResolved] = useState<ResolvedTheme>(() => {
    const m = getStoredMode()
    return m === 'system' ? resolveSystem() : m
  })

  // Synchronize on system preference changes
  useEffect(() => {
    if (mode !== 'system') return

    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const listener = (e: MediaQueryListEvent) => {
      const next: ResolvedTheme = e.matches ? 'dark' : 'light'
      setResolved(next)
      applyThemeToDOM(next)
    }

    media.addEventListener('change', listener)
    return () => media.removeEventListener('change', listener)
  }, [mode])

  // Apply theme to DOM whenever resolved changes
  useEffect(() => {
    applyThemeToDOM(resolved)
  }, [resolved])

  const setMode = useCallback((nextMode: ThemeMode, event?: React.MouseEvent | MouseEvent) => {
    try {
      localStorage.setItem(STORAGE_KEY, nextMode)
    } catch {
      // Storage unavailable
    }
    setModeState(nextMode)

    const nextResolved: ResolvedTheme = nextMode === 'system' ? resolveSystem() : nextMode

    // Check for reduced motion
    const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

    // View Transitions API with circular clip-path reveal
    if (!prefersReducedMotion && typeof document !== 'undefined' && 'startViewTransition' in document) {
      const x = event?.clientX ?? window.innerWidth / 2
      const y = event?.clientY ?? 0
      const endRadius = Math.hypot(
        Math.max(x, window.innerWidth - x),
        Math.max(y, window.innerHeight - y)
      )

      const transition = (document as any).startViewTransition(() => {
        setResolved(nextResolved)
        applyThemeToDOM(nextResolved)
      })

      transition.ready?.then(() => {
        document.documentElement.animate(
          {
            clipPath: [
              `circle(0px at ${x}px ${y}px)`,
              `circle(${endRadius}px at ${x}px ${y}px)`
            ]
          },
          {
            duration: 400,
            easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
            pseudoElement: '::view-transition-new(root)'
          }
        )
      }).catch(() => {
        setResolved(nextResolved)
        applyThemeToDOM(nextResolved)
      })
    } else {
      setResolved(nextResolved)
      applyThemeToDOM(nextResolved)
    }
  }, [])

  const toggleTheme = useCallback((event?: React.MouseEvent | MouseEvent) => {
    const nextMode = resolved === 'dark' ? 'light' : 'dark'
    setMode(nextMode, event)
  }, [resolved, setMode])

  return (
    <ThemeContext.Provider value={{ mode, resolved, resolvedTheme: resolved, setMode, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
