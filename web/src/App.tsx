import React, { useEffect, useState } from 'react'
import { MotionConfig } from 'motion/react'
import { AuthProvider, useAuth } from './context/AuthContext'
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
import { AuthRequiredGate } from './components/auth/AuthRequiredGate'
import { spring } from './design/motion'

const MainApp: React.FC = () => {
  const { isAuthenticated, isSandboxMode, openAuthModal } = useAuth()
  const hasFullAccess = isAuthenticated || isSandboxMode

  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [reviewAppId, setReviewAppId] = useState<string | null>(null)
  const [commandOpen, setCommandOpen] = useState(false)
  const [, setIntroComplete] = useState(false)

  const handleOpenReview = (appId: string) => {
    if (!hasFullAccess) {
      openAuthModal()
      return
    }
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
    if (!hasFullAccess) {
      openAuthModal()
    }
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
            hasFullAccess ? (
              <ApplicationReviewScreen
                applicationId={reviewAppId}
                onBack={handleBackFromReview}
                onNavigateToTracker={handleNavigateToTracker}
              />
            ) : (
              <AuthRequiredGate tab="queue" onNavigate={navigate} />
            )
          ) : (
            <>
              {activeTab === 'overview' && (
                <OverviewScreen onNavigate={handleNavigateFromOverview} />
              )}
              {activeTab === 'jobs' &&
                (hasFullAccess ? (
                  <JobDiscoveryScreen
                    onSelectApplication={handleOpenReview}
                    onNavigateToQueue={() => setActiveTab('queue')}
                  />
                ) : (
                  <AuthRequiredGate tab="jobs" onNavigate={navigate} />
                ))}
              {activeTab === 'queue' &&
                (hasFullAccess ? (
                  <ApplicationQueueScreen onSelectApplication={handleOpenReview} />
                ) : (
                  <AuthRequiredGate tab="queue" onNavigate={navigate} />
                ))}
              {activeTab === 'tracker' &&
                (hasFullAccess ? (
                  <ApplicationTrackerScreen />
                ) : (
                  <AuthRequiredGate tab="tracker" onNavigate={navigate} />
                ))}
              {activeTab === 'profile' &&
                (hasFullAccess ? (
                  <CandidateProfileScreen />
                ) : (
                  <AuthRequiredGate tab="profile" onNavigate={navigate} />
                ))}
              {activeTab === 'settings' &&
                (hasFullAccess ? (
                  <SettingsScreen />
                ) : (
                  <AuthRequiredGate tab="settings" onNavigate={navigate} />
                ))}
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
  )
}

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  )
}

export default App
