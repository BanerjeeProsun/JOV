import React from 'react'
import { LayoutDashboard, Briefcase, Layers, History, UserCheck, Settings, Activity, Moon, Sun } from 'lucide-react'
import { motion } from 'motion/react'
import { BrandLogo } from './BrandLogo'
import { useTheme } from './ThemeProvider'

export type TabId = 'overview' | 'jobs' | 'queue' | 'tracker' | 'profile' | 'settings' | 'diagnostics'
interface NavbarProps { activeTab: TabId; onSelectTab: (tab: TabId) => void; autonomyLevel?: string }

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onSelectTab }) => {
  const { resolvedTheme, setMode } = useTheme()
  const navItems: Array<{ id: TabId; label: string; icon: React.ReactNode }> = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard /> }, { id: 'jobs', label: 'Jobs', icon: <Briefcase /> },
    { id: 'queue', label: 'Application Queue', icon: <Layers /> }, { id: 'tracker', label: 'Tracker', icon: <History /> },
    { id: 'profile', label: 'Profile', icon: <UserCheck /> }, { id: 'settings', label: 'Settings', icon: <Settings /> }, { id: 'diagnostics', label: 'Diagnostics', icon: <Activity /> },
  ]
  return <header className="sticky top-3 z-50 px-3 md:top-5 md:px-6">
    <div className="glass-nav mx-auto flex h-14 max-w-[1280px] items-center gap-2 px-3 md:px-4">
      <button onClick={() => onSelectTab('overview')} className="shrink-0 rounded-full px-1.5 py-1 text-text-primary" aria-label="JOV.si overview"><BrandLogo /></button>
      <nav className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto [scrollbar-width:none]" aria-label="Primary navigation">
        {navItems.map((item) => { const active = activeTab === item.id; return <button key={item.id} onClick={() => onSelectTab(item.id)} aria-current={active ? 'page' : undefined} className={`relative inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-2 text-[12px] font-medium ${active ? 'text-text-primary' : 'text-text-secondary hover:text-text-primary'}`}>
          {active && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-full bg-[var(--nav-active)]" transition={{ type: 'spring', stiffness: 410, damping: 34 }} />}
          {React.cloneElement(item.icon as React.ReactElement<{ className?: string }>, { className: 'relative h-3.5 w-3.5' })}<span className="relative">{item.label}</span>
        </button> })}
      </nav>
      <button onClick={() => setMode(resolvedTheme === 'dark' ? 'light' : 'dark')} className="inline-flex shrink-0 items-center justify-center rounded-full p-2 text-text-secondary transition-colors hover:bg-[var(--nav-active)] hover:text-text-primary" aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`}>
        {resolvedTheme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>
    </div>
  </header>
}
