import React, { createContext, useContext, useEffect, useState } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'
interface ThemeContextValue { mode: ThemeMode; resolvedTheme: 'light' | 'dark'; setMode: (mode: ThemeMode) => void }
const ThemeContext = createContext<ThemeContextValue | null>(null)

const resolve = (mode: ThemeMode) => mode === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : mode

export const ThemeProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [mode, setStoredMode] = useState<ThemeMode>(() => (localStorage.getItem('jovsi-theme') as ThemeMode) || 'system')
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>(() => resolve(mode))
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => setResolvedTheme(resolve(mode))
    update(); media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [mode])
  useEffect(() => { document.documentElement.dataset.theme = resolvedTheme; document.documentElement.style.colorScheme = resolvedTheme }, [resolvedTheme])
  const setMode = (next: ThemeMode) => { localStorage.setItem('jovsi-theme', next); setStoredMode(next) }
  return <ThemeContext.Provider value={{ mode, resolvedTheme, setMode }}>{children}</ThemeContext.Provider>
}
export const useTheme = () => { const context = useContext(ThemeContext); if (!context) throw new Error('useTheme must be used within ThemeProvider'); return context }
