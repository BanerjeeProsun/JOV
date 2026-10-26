import React from 'react'
import { FloatingNav, type TabId } from './FloatingNav'

interface AppShellProps {
  activeTab: TabId
  onSelectTab: (tab: TabId) => void
  onOpenCommand?: () => void
  isModalOpen?: boolean
  children: React.ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({
  activeTab,
  onSelectTab,
  onOpenCommand,
  isModalOpen = false,
  children,
}) => {
  return (
    <div className="min-h-screen bg-bg text-text flex flex-col justify-between selection:bg-text selection:text-bg">
      {/* Skip to main content link for screen reader accessibility */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:bg-accent focus:text-accent-contrast focus:rounded-pill focus:shadow-float"
      >
        Skip to main content
      </a>

      {/* Floating Glass Navigation */}
      <FloatingNav
        activeTab={activeTab}
        onSelectTab={onSelectTab}
        onOpenCommand={onOpenCommand}
        isModalOpen={isModalOpen}
      />

      {/* Main Content Area */}
      <main id="main-content" className="flex-1 w-full pt-16 sm:pt-20 pb-24 sm:pb-16 outline-none">
        {children}
      </main>

      {/* Refined Minimalist Footer */}
      <footer className="w-full py-8 border-t border-border text-[12px] text-text-3">
        <div className="max-w-[1240px] mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-text">JOV.si</span>
            <span aria-hidden="true" className="opacity-40">·</span>
            <span>Private & Verified Career Workspace</span>
          </div>

          <div className="flex items-center gap-3">
            <span>Strict provenance</span>
            <span aria-hidden="true" className="opacity-40">·</span>
            <span>Protected submission</span>
            <span aria-hidden="true" className="opacity-40">·</span>
            <button
              onClick={() => onSelectTab('diagnostics')}
              className="hover:text-text transition-colors text-text-3 underline-offset-2 hover:underline cursor-pointer"
            >
              Diagnostics
            </button>
          </div>
        </div>
      </footer>
    </div>
  )
}
