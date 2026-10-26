import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api } from '../api/client'
import type { User } from '../types'
import { AuthModal } from '../components/auth/AuthModal'

interface AuthContextType {
  user: User | null
  loading: boolean
  isAuthenticated: boolean
  isSandboxMode: boolean
  openAuthModal: () => void
  closeAuthModal: () => void
  logout: () => Promise<void>
  refreshUser: () => Promise<User | null>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [isSandboxMode, setIsSandboxMode] = useState(false)
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false)

  const refreshUser = useCallback(async (): Promise<User | null> => {
    try {
      const current = await api.getMe()
      setUser(current)
      setIsSandboxMode(false)
      return current
    } catch {
      setUser(null)
      // Check if synthetic test candidate is present in sandbox test runner
      try {
        const candidate = await api.getActiveCandidate()
        if (candidate?.is_synthetic) {
          setIsSandboxMode(true)
        } else {
          setIsSandboxMode(false)
        }
      } catch {
        setIsSandboxMode(false)
      }
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  const openAuthModal = useCallback(() => {
    setIsAuthModalOpen(true)
  }, [])

  const closeAuthModal = useCallback(() => {
    setIsAuthModalOpen(false)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setUser(null)
      setIsSandboxMode(false)
    }
  }, [])

  const handleAuthenticated = useCallback((authUser: User) => {
    setUser(authUser)
    setIsSandboxMode(false)
    setIsAuthModalOpen(false)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: Boolean(user),
        isSandboxMode,
        openAuthModal,
        closeAuthModal,
        logout,
        refreshUser,
      }}
    >
      {children}
      <AuthModal
        open={isAuthModalOpen}
        onClose={closeAuthModal}
        onSuccess={handleAuthenticated}
      />
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
