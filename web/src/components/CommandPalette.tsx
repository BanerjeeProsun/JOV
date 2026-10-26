import React, { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Command, Search, X } from 'lucide-react'
import type { TabId } from './Navbar'

const destinations: Array<{ id: TabId; label: string; hint: string }> = [
  { id: 'overview', label: 'Overview', hint: 'Welcome and next actions' }, { id: 'jobs', label: 'Jobs', hint: 'Discover opportunities' },
  { id: 'queue', label: 'Application Queue', hint: 'Advance active work' }, { id: 'tracker', label: 'Application Tracker', hint: 'History and evidence' },
  { id: 'profile', label: 'Candidate Profile', hint: 'Resume and facts' }, { id: 'settings', label: 'Settings', hint: 'Preferences and limits' }, { id: 'diagnostics', label: 'Diagnostics', hint: 'Technical workspace' },
]

interface CommandPaletteProps { open: boolean; onClose: () => void; onNavigate: (tab: TabId) => void }
export const CommandPalette: React.FC<CommandPaletteProps> = ({ open, onClose, onNavigate }) => {
  const [query, setQuery] = useState('')
  useEffect(() => { if (!open) setQuery('') }, [open])
  const matches = useMemo(() => destinations.filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(query.toLowerCase())), [query])
  return <AnimatePresence>{open && <motion.div className="fixed inset-0 z-[60] flex items-start justify-center bg-[var(--overlay)] p-4 pt-[18vh] backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={onClose}>
    <motion.section className="glass-dialog w-full max-w-xl rounded-card p-3" initial={{ opacity: 0, y: 14, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: .98 }} transition={{ type: 'spring', stiffness: 380, damping: 30 }} onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="flex items-center gap-3 px-3 py-2"><Search className="h-4 w-4 text-text-tertiary" /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') onClose(); if (event.key === 'Enter' && matches[0]) { onNavigate(matches[0].id); onClose() } }} placeholder="Jump to…" className="min-w-0 flex-1 bg-transparent text-[17px] text-text-primary outline-none placeholder:text-text-tertiary" /><button onClick={onClose} className="rounded-full p-1 text-text-tertiary hover:bg-ash" aria-label="Close command palette"><X className="h-4 w-4" /></button></div>
      <div className="mt-2 space-y-1">{matches.map((item) => <button key={item.id} onClick={() => { onNavigate(item.id); onClose() }} className="flex w-full items-center justify-between rounded-apple-sm px-4 py-3 text-left hover:bg-[var(--nav-active)]"><span><span className="block text-[15px] font-medium text-text-primary">{item.label}</span><span className="block text-[12px] text-text-secondary">{item.hint}</span></span><Command className="h-3.5 w-3.5 text-text-tertiary" /></button>)}</div>
    </motion.section>
  </motion.div>}</AnimatePresence>
}
