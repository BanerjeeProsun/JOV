import React, { useEffect, useState } from 'react'
import { AnimatePresence, motion, LayoutGroup } from 'motion/react'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { api } from '../api/client'
import type { Candidate, Job, JobSource } from '../types'
import {
  Briefcase,
  Search,
  Plus,
  ArrowRight,
  ExternalLink,
  CheckCircle2,
  X,
  Sparkles,
  Building2,
  GraduationCap,
  Clock,
} from 'lucide-react'
import { spring, fadeUp } from '../design/motion'

interface JobDiscoveryScreenProps {
  onSelectApplication?: (appId: string) => void
  onNavigateToQueue: () => void
}

export const JobDiscoveryScreen: React.FC<JobDiscoveryScreenProps> = ({
  onNavigateToQueue,
}) => {
  const [jobs, setJobs] = useState<Job[]>([])
  const [sources, setSources] = useState<JobSource[]>([])
  const [activeCandidate, setActiveCandidate] = useState<Candidate | null>(null)
  const [loading, setLoading] = useState(true)
  const [discovering, setDiscovering] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [showImportModal, setShowImportModal] = useState(false)
  const [startingAppId, setStartingAppId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  // Pre-populated default form for testing & instant use
  const [importForm, setImportForm] = useState({
    title: 'Senior Software Engineer',
    company_name: 'Mock Acme Corp',
    source_url: 'http://127.0.0.1:8765/jobs/job-123/apply',
    portal_key: 'mock_hostile',
    native_id: 'job-123',
    raw_description:
      'We are looking for a Senior Software Engineer with Python and React experience. Required: 3+ years experience, Bachelor degree.',
    min_degree: 'BACHELOR',
    min_experience_months: 36,
    required_skills: 'Python, FastAPI, React, SQL',
  })
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    try {
      const [cand, jobsData, sourcesData] = await Promise.all([
        api.getActiveCandidate(),
        api.getJobs(),
        api.getJobSources().catch(() => []),
      ])
      setActiveCandidate(cand)
      setJobs(jobsData)
      setSources(sourcesData)
      if (jobsData.length > 0 && !selectedJobId) {
        setSelectedJobId(jobsData[0].id)
      }
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
        source: 'all',
        query: searchQuery,
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

  const handleImportSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
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
      await api.createApplication(activeCand.id, job.id)
      setActionMessage(`Application created for ${job.title_norm || job.company_norm}`)
      setTimeout(() => {
        onNavigateToQueue()
      }, 400)
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

  const selectedJob = jobs.find((j) => j.id === selectedJobId) || filteredJobs[0] || null

  return (
    <div className="screen-page space-y-8">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-border">
        <div>
          <p className="page-kicker">Real Market Sourcing</p>
          <h1 className="page-title">Job Discovery</h1>
          <p className="page-intro">
            Live ATS endpoints (Greenhouse, Lever) and direct portal listings. Every opportunity is sanitized with provenance tracking.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button
            variant="secondary"
            size="md"
            onClick={() => setShowImportModal(true)}
          >
            <Plus className="w-4 h-4" />
            <span>Import Job Posting</span>
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={handleDiscoverLive}
            loading={discovering || loading}
          >
            <Sparkles className="w-4 h-4 text-pearl-1" />
            <span>Discover Live Jobs</span>
          </Button>
        </div>
      </div>

      {/* Action Notification */}
      {actionMessage && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="p-4 border border-border/80 rounded-xl bg-bg-elev-1/60 text-xs text-text flex items-center justify-between shadow-1"
        >
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-text-2 shrink-0" />
            <span>{actionMessage}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="p-1 rounded-full text-text-3 hover:text-text hover:bg-selected transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </motion.div>
      )}

      {/* Active Source Indicators */}
      {sources.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 pt-1 pb-1">
          <span className="text-[11px] font-mono uppercase tracking-wider text-text-3 mr-1">Live Feeds:</span>
          {sources.map((src) => (
            <div
              key={src.id}
              title={src.description}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border border-border/70 bg-bg-elev-1/40 text-text-2"
            >
              <span className={`w-1.5 h-1.5 rounded-full ${src.is_live ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              <span className="font-sans font-medium text-text">{src.name.split(' ')[0]}</span>
              {src.employer_count ? (
                <span className="text-[10px] text-text-3 font-mono">({src.employer_count})</span>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {/* Search Toolbar */}
      <div className="flex items-center gap-3 bg-bg-elev-1/60 p-2 rounded-full border border-border/80 shadow-1 backdrop-blur-sm">
        <div className="flex-1 flex items-center gap-2.5 px-3">
          <Search className="w-4 h-4 text-text-3 shrink-0" strokeWidth={1.5} />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by role title, company, or required skill…"
            className="w-full bg-transparent text-[14px] text-text placeholder:text-text-3 outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="p-1 text-text-3 hover:text-text"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
        <span className="text-xs text-text-3 font-mono px-3 py-1 rounded-full bg-bg-input">
          {filteredJobs.length} {filteredJobs.length === 1 ? 'role' : 'roles'}
        </span>
      </div>

      {/* Two-Pane Layout with Shared Element Transitions */}
      <LayoutGroup>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Dense Job List */}
          <div className="lg:col-span-5 space-y-1">
            {loading ? (
              // Slow pearl shimmer skeleton loader
              <div className="space-y-3">
                {[1, 2, 3, 4].map((n) => (
                  <div
                    key={n}
                    className="h-24 rounded-xl bg-bg-elev-1/40 border border-border/60 relative overflow-hidden"
                  >
                    <div
                      className="absolute inset-0 bg-gradient-to-r from-transparent via-border to-transparent"
                      style={{ animation: 'pearl-shimmer 2.2s infinite ease-in-out' }}
                    />
                  </div>
                ))}
              </div>
            ) : filteredJobs.length === 0 ? (
              <div className="border border-border/60 rounded-xl bg-bg-elev-1/20 p-12 text-center text-text-3">
                <Briefcase className="w-8 h-8 mx-auto mb-3 opacity-40" strokeWidth={1.5} />
                <p className="text-sm font-medium text-text">No opportunities found</p>
                <p className="text-xs mt-1 text-text-3">
                  Import a job posting URL or discover live roles across feeds.
                </p>
              </div>
            ) : (
              <AnimatePresence mode="popLayout">
                {filteredJobs.map((job) => {
                  const isSelected = selectedJob?.id === job.id
                  const skills = job.requirements?.required_skills || []

                  return (
                    <motion.div
                      layout
                      key={job.id}
                      layoutId={`job-${job.id}`}
                      onClick={() => setSelectedJobId(job.id)}
                      className={`relative p-5 rounded-xl transition-all cursor-pointer select-none border-b border-border/60 ${
                        isSelected
                          ? 'bg-selected border-b-border-strong shadow-1'
                          : 'hover:bg-bg-elev-1/50 border-b-border/40'
                      }`}
                    >
                      {/* Active pearl border indicator */}
                      {isSelected && (
                        <motion.div
                          layoutId="job-active-indicator"
                          className="absolute inset-0 rounded-xl pointer-events-none border border-pearl-1/40"
                          transition={spring.layout}
                        />
                      )}

                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <h3 className="font-semibold text-[15px] text-text leading-snug truncate">
                            {job.title_norm || job.title || 'Open Position'}
                          </h3>
                          <div className="flex items-center gap-2 mt-1 text-xs text-text-2">
                            <span className="font-medium text-text">
                              {job.company_norm || job.company || 'Company'}
                            </span>
                            <span className="opacity-30">·</span>
                            <span className="text-text-3">
                              {job.source || 'portal'}
                            </span>
                          </div>
                        </div>

                        <span className="text-[11px] font-mono text-text-3 shrink-0">
                          {job.created_at ? new Date(job.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'Recent'}
                        </span>
                      </div>

                      {/* Required skills tags */}
                      {skills.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t border-border/50">
                          {skills.slice(0, 3).map((skill: string, sIdx: number) => (
                            <span
                              key={sIdx}
                              className="text-[11px] px-2 py-0.5 rounded-full bg-bg-input text-text-3 font-mono"
                            >
                              {skill}
                            </span>
                          ))}
                          {skills.length > 3 && (
                            <span className="text-[10px] text-text-3 font-mono">
                              +{skills.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            )}
          </div>

          {/* Right Column: Expanded Job Detail */}
          <div className="lg:col-span-7 sticky top-24">
            {selectedJob ? (
              <motion.div
                key={selectedJob.id}
                variants={fadeUp}
                initial="hidden"
                animate="show"
                className="rounded-2xl border border-border/80 bg-bg-elev-1/30 backdrop-blur-sm p-8 shadow-float space-y-6"
              >
                {/* Header Info */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-6 border-b border-border">
                  <div className="space-y-1">
                    <span className="text-[11px] uppercase tracking-wider font-mono text-text-3">
                      {selectedJob.portal_key || selectedJob.source || 'Standard listing'}
                    </span>
                    <h2 className="text-2xl font-semibold tracking-tight text-text">
                      {selectedJob.title_norm || selectedJob.title}
                    </h2>
                    <div className="flex items-center gap-3 text-sm text-text-2 pt-1">
                      <span className="flex items-center gap-1 text-text font-medium">
                        <Building2 className="w-4 h-4 text-text-3" strokeWidth={1.5} />
                        {selectedJob.company_norm || selectedJob.company}
                      </span>
                      {selectedJob.requirements?.min_degree && (
                        <span className="flex items-center gap-1 text-xs text-text-3">
                          <GraduationCap className="w-3.5 h-3.5" />
                          {selectedJob.requirements.min_degree}
                        </span>
                      )}
                      {selectedJob.requirements?.min_experience_months && (
                        <span className="flex items-center gap-1 text-xs text-text-3">
                          <Clock className="w-3.5 h-3.5" />
                          {Math.round(selectedJob.requirements.min_experience_months / 12)}y exp
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Apply Action Button */}
                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      size="md"
                      onClick={() => handleStartApplication(selectedJob)}
                      loading={startingAppId === selectedJob.id}
                    >
                      <span>Apply</span>
                      <ArrowRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {/* Required Skills */}
                {selectedJob.requirements?.required_skills && selectedJob.requirements.required_skills.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs uppercase tracking-wider font-semibold text-text-3">
                      Required Competencies
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedJob.requirements.required_skills.map((skill: string, idx: number) => (
                        <span
                          key={idx}
                          className="px-3 py-1 rounded-full border border-border bg-bg-elev-2 text-xs font-mono text-text"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Job Description */}
                <div className="space-y-3">
                  <h4 className="text-xs uppercase tracking-wider font-semibold text-text-3">
                    Posting Overview
                  </h4>
                  <div className="text-[14px] text-text-2 leading-relaxed whitespace-pre-line max-h-[380px] overflow-y-auto pr-2 [scrollbar-width:thin]">
                    {selectedJob.description_clean ||
                      'No job description content provided.'}
                  </div>
                </div>

                {/* Provenance Link */}
                {selectedJob.source_url && (
                  <div className="pt-4 border-t border-border flex items-center justify-between text-xs text-text-3">
                    <span className="font-mono truncate max-w-md">
                      Source: {selectedJob.source_url}
                    </span>
                    <a
                      href={selectedJob.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-text hover:underline"
                    >
                      <span>Open portal link</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                )}
              </motion.div>
            ) : (
              <div className="rounded-2xl border border-border/60 bg-bg-elev-1/20 p-12 text-center text-text-3 font-mono text-xs">
                Select a role from the left to view details and start an application.
              </div>
            )}
          </div>
        </div>
      </LayoutGroup>

      {/* Import Job Posting Modal */}
      <Dialog
        open={showImportModal}
        onClose={() => setShowImportModal(false)}
        title="Import Job Posting"
        description="Provide posting details or a portal URL. Content will be sanitized through the ingestion pipeline."
        maxWidth="max-w-xl"
      >
        <form onSubmit={handleImportSubmit} className="space-y-4 mt-2">
          {importError && (
            <div className="p-3 rounded-lg border border-border/80 bg-bg-elev-1/80 text-text-2 text-xs">
              {importError}
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs font-semibold text-text">Job Title</label>
            <input
              required
              value={importForm.title}
              onChange={(e) => setImportForm({ ...importForm, title: e.target.value })}
              className="app-input"
              placeholder="e.g. Senior Software Engineer"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-text">Company Name</label>
              <input
                required
                value={importForm.company_name}
                onChange={(e) => setImportForm({ ...importForm, company_name: e.target.value })}
                className="app-input"
                placeholder="e.g. Mock Acme Corp"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-text">Portal Key</label>
              <input
                required
                value={importForm.portal_key}
                onChange={(e) => setImportForm({ ...importForm, portal_key: e.target.value })}
                className="app-input"
                placeholder="e.g. mock_hostile"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-text">Source URL</label>
            <input
              required
              value={importForm.source_url}
              onChange={(e) => setImportForm({ ...importForm, source_url: e.target.value })}
              className="app-input font-mono text-xs"
              placeholder="https://..."
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-text">Required Skills (comma separated)</label>
            <input
              value={importForm.required_skills}
              onChange={(e) => setImportForm({ ...importForm, required_skills: e.target.value })}
              className="app-input"
              placeholder="Python, React, SQL..."
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-text">Job Description</label>
            <textarea
              rows={4}
              value={importForm.raw_description}
              onChange={(e) => setImportForm({ ...importForm, raw_description: e.target.value })}
              className="app-input resize-none"
              placeholder="Paste raw description..."
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowImportModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={importing}
            >
              Sanitize & Import
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
