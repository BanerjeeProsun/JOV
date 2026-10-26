import React, { useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { api } from '../../api/client'
import type { User } from '../../types'
import { LogIn, UserPlus, KeyRound, CheckCircle2, AlertCircle } from 'lucide-react'

interface AuthModalProps {
  open: boolean
  initialTab?: 'login' | 'register'
  onClose: () => void
  onSuccess: (user: User) => void
}

type TabType = 'login' | 'register' | 'forgot'

export const AuthModal: React.FC<AuthModalProps> = ({ open, initialTab, onClose, onSuccess }) => {
  const [tab, setTab] = useState<TabType>(initialTab || 'login')

  React.useEffect(() => {
    if (open && initialTab) {
      setTab(initialTab)
      setError(null)
      setSuccessMessage(null)
    }
  }, [open, initialTab])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const resetForm = () => {
    setError(null)
    setSuccessMessage(null)
    setPassword('')
  }

  const handleTabSwitch = (newTab: TabType) => {
    setTab(newTab)
    resetForm()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSuccessMessage(null)

    try {
      if (tab === 'login') {
        const user = await api.login({ email, password })
        onSuccess(user)
        onClose()
      } else if (tab === 'register') {
        const user = await api.register({
          email,
          password,
          display_name: displayName,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata',
        })
        onSuccess(user)
        onClose()
      } else if (tab === 'forgot') {
        const res = await api.forgotPassword(email)
        setSuccessMessage(res.message || 'Password reset instructions have been sent.')
      }
    } catch (err: any) {
      setError(err.message || 'Authentication request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Account Access" maxWidth="max-w-md">
      <div className="space-y-6">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 p-1 bg-bg-elev-1/60 rounded-xl border border-border">
          <button
            type="button"
            onClick={() => handleTabSwitch('login')}
            className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5 ${
              tab === 'login' ? 'bg-bg text-text shadow-1 font-semibold' : 'text-text-3 hover:text-text'
            }`}
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Sign In</span>
          </button>
          <button
            type="button"
            onClick={() => handleTabSwitch('register')}
            className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5 ${
              tab === 'register' ? 'bg-bg text-text shadow-1 font-semibold' : 'text-text-3 hover:text-text'
            }`}
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>Create Account</span>
          </button>
          <button
            type="button"
            onClick={() => handleTabSwitch('forgot')}
            className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5 ${
              tab === 'forgot' ? 'bg-bg text-text shadow-1 font-semibold' : 'text-text-3 hover:text-text'
            }`}
          >
            <KeyRound className="w-3.5 h-3.5" />
            <span>Recovery</span>
          </button>
        </div>

        {/* Status Messages */}
        {error && (
          <div className="p-3 bg-bg-elev-1 border border-border/80 rounded-xl text-xs text-text flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-text-3 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="p-3 bg-bg-elev-1 border border-border/80 rounded-xl text-xs text-text flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-text-2 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {tab === 'register' && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text">Preferred Display Name</label>
              <input
                type="text"
                placeholder="e.g. Alex Vance"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="app-input"
                autoFocus
              />
              <p className="text-[11px] text-text-3">
                This is your authenticated greeting name on the dashboard.
              </p>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-text">Account Email</label>
            <input
              type="email"
              required
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="app-input"
              autoFocus={tab !== 'register'}
            />
          </div>

          {tab !== 'forgot' && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text">Password</label>
              <input
                type="password"
                required
                minLength={8}
                placeholder="Minimum 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="app-input"
              />
            </div>
          )}

          <div className="pt-2 flex items-center justify-end gap-3 border-t border-border">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="md" loading={loading}>
              {tab === 'login' ? 'Sign In' : tab === 'register' ? 'Create Account' : 'Send Reset Link'}
            </Button>
          </div>
        </form>
      </div>
    </Dialog>
  )
}
