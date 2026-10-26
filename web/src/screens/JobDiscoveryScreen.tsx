import React, { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { api } from '../api/client'
import type { Candidate, Job } from '../types'
import {
  Briefcase,
  Search,
  Plus,
  ArrowRight,
  ExternalLink,
  CheckCircle2,
  X,
  Sparkles,
  Building,
} from 'lucide-react'

interface JobDiscoveryScreenProps {
  onSelectApplication?: (appId: string) => void
  onNavigateToQueue: () => void
}

export const JobDiscoveryScreen: React.FC<JobDiscoveryScreenProps> = ({
  onNavigateToQueue,
}) => {
  const [jobs, setJobs] = useState<Job[]>([])
  const [activeCandidate, setActiveCandidate] = useState<Candidate | null>(null)
  const [loading, setLoading] = useState(true)
  const [discovering, setDiscovering] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [companyQuery, setCompanyQuery] = useState('')
  const [selectedSource, setSelectedSource] = useState('all')
  const [showImportModal, setShowImportModal] = useState(false)
  const [startingAppId, setStartingAppId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  // Import Form State (Pre-populated for instant testing & convenience)
  const [importForm, setImportForm] = useState({
    title: 'Senior Software Engineer',
    company_name: 'Mock Acme Corp',
    source_url: 'http://127.0.0.1:8765/jobs/job-123/apply',
    portal_key: 'mock_hostile',
    native_id: 'job-123',
    raw_description: 'We are looking for a Senior Software Engineer with Python and React experience. Required: 3+ years experience, Bachelor degree.',
    min_degree: 'BACHELOR',
    min_experience_months: 36,
    required_skills: 'Python, FastAPI, React, SQL',
  })
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    try {
      const [cand, jobsData] = await Promise.all([
        api.getActiveCandidate(),
        api.getJobs(),
      ])
      setActiveCandidate(cand)
      setJobs(jobsData)
    } catch (err: any) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleDiscoverLive = async () => {
    setDiscovering(true)
    setActionMessage(null)
    try {
      const resp = await api.discoverJobs({
        source: selectedSource,
        query: searchQuery,
        company: companyQuery || undefined,
        candidate_id: activeCandidate?.id,
        limit: 15,
      })
      setActionMessage(`Discovered ${resp.total_found} real opportunities across live feeds.`)
      await loadData()
    } catch (err: any) {
      setActionMessage(`Discovery failed: ${err.message}`)
    } finally {
      setDiscovering(false)
    }
  }

  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setImporting(true)
    setImportError(null)
    try {
      const skillsArray = importForm.required_skills
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)

      await api.importJob({
        source: 'manual_import',
        source_url: importForm.source_url,
        canonical_url: importForm.source_url,
        portal_key: importForm.portal_key,
        native_id: importForm.native_id,
        company_name: importForm.company_name,
        title: importForm.title,
        raw_description: importForm.raw_description,
        min_degree: importForm.min_degree,
        min_experience_months: Number(importForm.min_experience_months),
        required_skills: skillsArray,
      })

      setShowImportModal(false)
      await loadData()
      setActionMessage('Job successfully imported and sanitized!')
      setTimeout(() => setActionMessage(null), 4000)
    } catch (err: any) {
      setImportError(err.message || 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  const handleStartApplication = async (job: Job) => {
    setStartingAppId(job.id)
    try {
      const activeCand = await api.ensureActiveCandidate()
      const res = await api.createApplication(activeCand.id, job.id)
      setActionMessage(`Application #${res.id.slice(0, 8)} created in state: ${res.state}`)
      setTimeout(() => {
        onNavigateToQueue()
      }, 800)
    } catch (err: any) {
      setActionMessage(`Error starting application: ${err.message}`)
    } finally {
      setStartingAppId(null)
    }
  }

  const filteredJobs = jobs.filter((j) => {
    const q = searchQuery.toLowerCase()
    return (
      (j.title_norm && j.title_norm.toLowerCase().includes(q)) ||
      (j.company_norm && j.company_norm.toLowerCase().includes(q)) ||
      (j.description_clean && j.description_clean.toLowerCase().includes(q))
    )
  })

  return (
    <div className="screen-page">
      {/* Title & Introduction */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Real Market Sourcing
          </span>
          <h1 className="page-title">
            Job Discovery
          </h1>
          <p className="page-intro">
            Query live ATS endpoints (Greenhouse, Lever) and remote job directories, or import any job posting URL with sanitization provenance.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowImportModal(true)}
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Import Job Posting</span>
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleDiscoverLive}
            loading={discovering || loading}
          >
            <Sparkles className="w-3.5 h-3.5 text-coral-brand" />
            <span>Discover Live Jobs</span>
          </Button>
        </div>
      </div>

      {/* Notifications */}
      {actionMessage && (
        <div className="mb-6 p-4 rounded-apple-md text-sm flex items-center justify-between border bg-surface border-border-subtle shadow-sm text-text-primary">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-success-green flex-shrink-0" />
            <span>{actionMessage}</span>
          </div>
          <button onClick={() => setActionMessage(null)} className="text-text-tertiary hover:text-text-primary">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Live Search & Filter Bar */}
      <Card className="mb-8 p-5 bg-surface">
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-center">
          <div className="sm:col-span-5 relative">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="text"
              placeholder="Job title, keywords, or skills..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-full text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
            />
          </div>

          <div className="sm:col-span-4 relative">
            <Building className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="text"
              placeholder="Company (e.g. Cloudflare, Figma, Stripe)..."
              value={companyQuery}
              onChange={(e) => setCompanyQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-full text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
            />
          </div>

          <div className="sm:col-span-3 flex items-center gap-2">
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              className="w-full py-2.5 px-3 rounded-full text-xs border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
            >
              <option value="all">All Live Sources</option>
              <option value="greenhouse">Greenhouse ATS</option>
              <option value="lever">Lever ATS</option>
              <option value="jobicy">Jobicy Remote</option>
            </select>
            <Button
              variant="primary"
              size="sm"
              onClick={handleDiscoverLive}
              loading={discovering}
            >
              Search
            </Button>
          </div>
        </div>
      </Card>

      {/* Job Listings Grid */}
      {filteredJobs.length === 0 ? (
        <Card className="text-center py-16">
          <Briefcase className="w-12 h-12 text-text-tertiary mx-auto mb-4 opacity-40" />
          <h3 className="text-base font-semibold text-text-primary">
            No opportunities loaded yet
          </h3>
          <p className="text-sm text-text-secondary max-w-md mx-auto mt-1 mb-6">
            Run a live query across Greenhouse and Lever company boards, or manually import a job description using the button above.
          </p>
          <div className="flex justify-center gap-3">
            <Button variant="primary" size="sm" onClick={handleDiscoverLive} loading={discovering}>
              Search Cloudflare & Stripe Boards
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setShowImportModal(true)}>
              Import Job URL
            </Button>
          </div>
        </Card>
      ) : (
        <motion.div layout className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <AnimatePresence mode="popLayout">
          {filteredJobs.map((job) => {
            const isApplying = startingAppId === job.id
            const reqSkills = job.requirements?.required_skills || []

            return (
              <motion.div layout key={job.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: .98 }} transition={{ duration: .22 }}>
              <Card
                key={job.id}
                className="flex flex-col justify-between p-6 bg-surface"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-black/5 text-text-secondary border border-black/5 uppercase tracking-wide">
                      {job.source}
                    </span>
                    {job.requirements?.accepted_work_modes && (
                      <span className="text-xs text-text-tertiary capitalize">
                        {job.requirements.accepted_work_modes.join(', ')}
                      </span>
                    )}
                  </div>

                  <h3 className="font-semibold text-lg text-text-primary tracking-tight">
                    {job.title_norm || job.title}
                  </h3>
                  <div className="flex items-center gap-2 mt-1 text-sm text-text-secondary font-medium">
                    <Building className="w-4 h-4 text-text-tertiary" />
                    <span>{job.company_norm || job.company}</span>
                  </div>

                  <p className="text-xs text-text-tertiary mt-3 line-clamp-3 leading-relaxed">
                    {job.description_clean}
                  </p>

                  {reqSkills.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-4">
                      {reqSkills.slice(0, 5).map((skill: string) => (
                        <span
                          key={skill}
                          className="px-2 py-0.5 rounded-md bg-canvas text-text-secondary border border-border-subtle text-[11px]"
                        >
                          {skill}
                        </span>
                      ))}
                      {reqSkills.length > 5 && (
                        <span className="text-[11px] text-text-tertiary self-center">
                          +{reqSkills.length - 5} more
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between pt-5 border-t border-border-subtle mt-5">
                  <a
                    href={job.canonical_url || job.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-apple-blue hover:underline font-medium"
                  >
                    <span>View Listing</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>

                  <Button
                    variant="primary"
                    size="sm"
                    loading={isApplying}
                    onClick={() => handleStartApplication(job)}
                  >
                    <span>Apply</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </Card>
              </motion.div>
            )
          })}
          </AnimatePresence>
        </motion.div>
      )}

      {/* Import Job Modal */}
      <AnimatePresence>
      {showImportModal && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--overlay)] backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setShowImportModal(false)}>
          <motion.div initial={{ opacity: 0, y: 12, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: .98 }} transition={{ type: 'spring', stiffness: 360, damping: 30 }} onClick={(event) => event.stopPropagation()}>
          <Card className="glass-dialog w-full max-w-xl p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-text-primary text-lg">
                  Import Job Posting
                </h3>
                <p className="text-xs text-text-secondary mt-0.5">
                  Job content is sanitized, canonicalized, and hashed to prevent injection.
                </p>
              </div>
              <button
                onClick={() => setShowImportModal(false)}
                className="text-text-tertiary hover:text-text-primary"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {importError && (
              <div className="mb-4 p-3 rounded-apple-sm text-xs bg-danger-subtle text-danger-red border border-danger-red/20">
                {importError}
              </div>
            )}

            <form onSubmit={handleImportSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                    Job Title
                  </label>
                  <input
                    type="text"
                    value={importForm.title}
                    onChange={(e) => setImportForm({ ...importForm, title: e.target.value })}
                    className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                    Company Name
                  </label>
                  <input
                    type="text"
                    value={importForm.company_name}
                    onChange={(e) => setImportForm({ ...importForm, company_name: e.target.value })}
                    className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                  Source Application URL
                </label>
                <input
                  type="url"
                  value={importForm.source_url}
                  onChange={(e) => setImportForm({ ...importForm, source_url: e.target.value })}
                  className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                  Raw Description / HTML
                </label>
                <textarea
                  value={importForm.raw_description}
                  onChange={(e) => setImportForm({ ...importForm, raw_description: e.target.value })}
                  className="w-full h-28 p-2.5 rounded-apple-sm text-xs font-mono border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                    Minimum Degree
                  </label>
                  <select
                    value={importForm.min_degree}
                    onChange={(e) => setImportForm({ ...importForm, min_degree: e.target.value })}
                    className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
                  >
                    <option value="BACHELOR">Bachelor's Degree</option>
                    <option value="MASTER">Master's Degree</option>
                    <option value="DOCTORATE">Doctorate / PhD</option>
                    <option value="DIPLOMA">Diploma</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                    Min Experience (Months)
                  </label>
                  <input
                    type="number"
                    value={importForm.min_experience_months}
                    onChange={(e) => setImportForm({ ...importForm, min_experience_months: Number(e.target.value) })}
                    className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                  Required Skills (comma separated)
                </label>
                <input
                  type="text"
                  value={importForm.required_skills}
                  onChange={(e) => setImportForm({ ...importForm, required_skills: e.target.value })}
                  className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <Button variant="secondary" size="sm" type="button" onClick={() => setShowImportModal(false)}>
                  Cancel
                </Button>
                <Button variant="primary" size="sm" type="submit" loading={importing}>
                  Sanitize & Import
                </Button>
              </div>
            </form>
          </Card>
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>
    </div>
  )
}
