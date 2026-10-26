import React from 'react'
import { FloatingNav, type TabId } from './layout/FloatingNav'

export type { TabId }

interface NavbarProps {
  activeTab: TabId
  onSelectTab: (tab: TabId) => void
  autonomyLevel?: string
  onOpenCommand?: () => void
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onSelectTab,
  onOpenCommand,
}) => {
  return (
    <FloatingNav
      activeTab={activeTab}
      onSelectTab={onSelectTab}
      onOpenCommand={onOpenCommand}
    />
  )
}
