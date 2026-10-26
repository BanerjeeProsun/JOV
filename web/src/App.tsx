import React, { useEffect, useState } from 'react'
import { AnimatePresence, MotionConfig, motion, useReducedMotion } from 'motion/react'
import { Navbar, type TabId } from './components/Navbar'
import { CommandPalette } from './components/CommandPalette'
import { OverviewScreen } from './screens/OverviewScreen'
import { JobDiscoveryScreen } from './screens/JobDiscoveryScreen'
import { ApplicationQueueScreen } from './screens/ApplicationQueueScreen'
import { ApplicationReviewScreen } from './screens/ApplicationReviewScreen'
import { ApplicationTrackerScreen } from './screens/ApplicationTrackerScreen'
import { CandidateProfileScreen } from './screens/CandidateProfileScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { DiagnosticsScreen } from './screens/DiagnosticsScreen'

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [reviewAppId, setReviewAppId] = useState<string | null>(null)
  const [commandOpen, setCommandOpen] = useState(false)
  const reducedMotion = useReducedMotion()

  const handleOpenReview = (appId: string) => {
    setReviewAppId(appId)
  }

  const handleBackFromReview = () => {
    setReviewAppId(null)
  }

  const handleNavigateToTracker = () => {
    setReviewAppId(null)
    setActiveTab('tracker')
  }

  const handleNavigateFromOverview = (tab: 'jobs' | 'queue' | 'tracker' | 'profile') => {
    setReviewAppId(null)
    setActiveTab(tab)
  }
  const navigate = (tab: TabId) => { setReviewAppId(null); setActiveTab(tab) }
  useEffect(() => {
    const listener = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setCommandOpen(true) } }
    window.addEventListener('keydown', listener); return () => window.removeEventListener('keydown', listener)
  }, [])

  const pageKey = reviewAppId ? `review-${reviewAppId}` : activeTab
  return (
    <MotionConfig reducedMotion="user">
    <div className="min-h-screen bg-canvas text-text-primary flex flex-col justify-between">
      <div>
        <Navbar
          activeTab={reviewAppId ? 'queue' : activeTab}
          onSelectTab={navigate}
          autonomyLevel="L0_DRY_RUN"
        />
      </div>

      <main className="flex-1 w-full">
        <AnimatePresence mode="wait" initial={false}>
        <motion.div key={pageKey} initial={reducedMotion ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={reducedMotion ? {} : { opacity: 0, y: -7 }} transition={{ duration: .28, ease: [.22, 1, .36, 1] }}>
        {reviewAppId ? (
          <ApplicationReviewScreen
            applicationId={reviewAppId}
            onBack={handleBackFromReview}
            onNavigateToTracker={handleNavigateToTracker}
          />
        ) : (
          <>
            {activeTab === 'overview' && (
              <OverviewScreen onNavigate={handleNavigateFromOverview} />
            )}
            {activeTab === 'jobs' && (
              <JobDiscoveryScreen
                onSelectApplication={handleOpenReview}
                onNavigateToQueue={() => setActiveTab('queue')}
              />
            )}
            {activeTab === 'queue' && (
              <ApplicationQueueScreen onSelectApplication={handleOpenReview} />
            )}
            {activeTab === 'tracker' && <ApplicationTrackerScreen />}
            {activeTab === 'profile' && <CandidateProfileScreen />}
            {activeTab === 'settings' && <SettingsScreen />}
            {activeTab === 'diagnostics' && <DiagnosticsScreen />}
          </>
        )}
        </motion.div>
        </AnimatePresence>
      </main>
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} onNavigate={navigate} />

      <footer className="w-full py-8 text-center text-xs text-text-tertiary">
        <div className="max-w-[1440px] mx-auto px-10 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-text-primary">JOV.si</span>
            <span aria-hidden="true">·</span>
            <span>v0.1.0-alpha</span>
            <span aria-hidden="true">·</span>
            <span>Architecture Blueprint v2.0</span>
          </div>

          <div className="text-[12px]">
            Strict provenance · 15-point gate · zero synthetic metrics
          </div>
        </div>
      </footer>
    </div>
    </MotionConfig>
  )
}

export default App
