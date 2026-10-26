import React, { useEffect, useState } from 'react'
import { MotionConfig } from 'motion/react'
import { AuthProvider } from './context/AuthContext'
import { AppShell } from './components/layout/AppShell'
import type { TabId } from './components/layout/FloatingNav'
import { CommandPalette } from './components/ui/CommandPalette'
import { IntroSequence } from './components/brand/IntroSequence'
import { PageTransition } from './components/motion/PageTransition'
import { OverviewScreen } from './screens/OverviewScreen'
import { JobDiscoveryScreen } from './screens/JobDiscoveryScreen'
import { ApplicationQueueScreen } from './screens/ApplicationQueueScreen'
import { ApplicationReviewScreen } from './screens/ApplicationReviewScreen'
import { ApplicationTrackerScreen } from './screens/ApplicationTrackerScreen'
import { CandidateProfileScreen } from './screens/CandidateProfileScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { DiagnosticsScreen } from './screens/DiagnosticsScreen'
import { spring } from './design/motion'

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [reviewAppId, setReviewAppId] = useState<string | null>(null)
  const [commandOpen, setCommandOpen] = useState(false)
  const [, setIntroComplete] = useState(false)

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

  const navigate = (tab: TabId) => {
    setReviewAppId(null)
    setActiveTab(tab)
  }

  // Scroll to top upon navigating to any screen
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [activeTab, reviewAppId])

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen(true)
      }
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [])

  const pageKey = reviewAppId ? `review-${reviewAppId}` : activeTab

  return (
    <AuthProvider>
      <MotionConfig reducedMotion="user" transition={spring.smooth}>
        {/* Intro sequence with shared layoutId="brand-j" handoff */}
        <IntroSequence onComplete={() => setIntroComplete(true)} />

        <AppShell
          activeTab={reviewAppId ? 'queue' : activeTab}
          onSelectTab={navigate}
          onOpenCommand={() => setCommandOpen(true)}
          isModalOpen={commandOpen}
        >
          <PageTransition pageKey={pageKey}>
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
          </PageTransition>
        </AppShell>

        {/* Global ⌘K Command Palette */}
        <CommandPalette
          open={commandOpen}
          onClose={() => setCommandOpen(false)}
          onNavigate={navigate}
        />
      </MotionConfig>
    </AuthProvider>
  )
}

export default App
