import React, { useEffect, useState, useRef } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { api } from '../api/client'
import type { Candidate, Fact, MasterResumeStatus } from '../types'
import {
  FileText,
  Upload,
  CheckCircle2,
  Clock,
  AlertCircle,
  Download,
  Trash2,
  Plus,
  RefreshCw,
  Edit2,
  X,
  User,
} from 'lucide-react'

export const CandidateProfileScreen: React.FC = () => {
  const [activeCandidate, setActiveCandidate] = useState<Candidate | null>(null)
  const [resumeStatus, setResumeStatus] = useState<MasterResumeStatus | null>(null)
  const [facts, setFacts] = useState<Fact[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [actingFactId, setActingFactId] = useState<string | null>(null)

  // Edit / Add Fact Modal
  const [editingFact, setEditingFact] = useState<Fact | null>(null)
  const [editValueText, setEditValueText] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [newFactKind, setNewFactKind] = useState('SKILL')
  const [newFactKey, setNewFactKey] = useState('')
  const [newFactValue, setNewFactValue] = useState('')

  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadData = async () => {
    setLoading(true)
    try {
      const cand = await api.ensureActiveCandidate()
      setActiveCandidate(cand)

      const [status, factList] = await Promise.all([
        api.getMasterResumeStatus(cand.id),
        api.getCandidateFacts(cand.id),
      ])
      setResumeStatus(status)
      setFacts(factList)
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to load profile data.' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const uploadFile = async (file: File | undefined) => {
    if (!file || !activeCandidate) return

    setUploading(true)
    setMessage(null)
    try {
      const result = await api.uploadMasterResume(activeCandidate.id, file)
      setMessage({
        type: 'success',
        text: `Master resume successfully parsed! Extracted ${result.total_facts_extracted} proposed facts. Please review and confirm below.`,
      })
      await loadData()
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to parse resume.' })
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    await uploadFile(e.target.files?.[0])
  }

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    await uploadFile(e.dataTransfer.files?.[0])
  }

  const handleConfirmFact = async (factId: string) => {
    setActingFactId(factId)
    try {
      await api.confirmFact(factId)
      if (activeCandidate) {
        const updated = await api.getCandidateFacts(activeCandidate.id)
        setFacts(updated)
        const status = await api.getMasterResumeStatus(activeCandidate.id)
        setResumeStatus(status)
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setActingFactId(null)
    }
  }

  const handleRejectFact = async (factId: string) => {
    setActingFactId(factId)
    try {
      await api.rejectFact(factId)
      if (activeCandidate) {
        const updated = await api.getCandidateFacts(activeCandidate.id)
        setFacts(updated)
        const status = await api.getMasterResumeStatus(activeCandidate.id)
        setResumeStatus(status)
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setActingFactId(null)
    }
  }

  const handleConfirmAll = async () => {
    if (!activeCandidate) return
    setLoading(true)
    try {
      await api.confirmAllFacts(activeCandidate.id)
      setMessage({ type: 'success', text: 'All proposed facts have been verified and set to ACTIVE.' })
      await loadData()
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteDocument = async () => {
    if (!resumeStatus?.document_id) return
    if (!confirm('Are you sure you want to delete the active master resume document?')) return

    try {
      await api.deleteDocument(resumeStatus.document_id)
      setMessage({ type: 'success', text: 'Master resume document deleted.' })
      await loadData()
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    }
  }

  const handleSaveEditFact = async () => {
    if (!editingFact) return
    try {
      let parsedValue: any
      try {
        parsedValue = JSON.parse(editValueText)
      } catch {
        parsedValue = { name: editValueText }
      }
      await api.updateFact(editingFact.id, { value: parsedValue })
      setEditingFact(null)
      if (activeCandidate) {
        const updated = await api.getCandidateFacts(activeCandidate.id)
        setFacts(updated)
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    }
  }

  const handleAddFactSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeCandidate) return
    try {
      let parsedValue: any
      try {
        parsedValue = JSON.parse(newFactValue)
      } catch {
        parsedValue = { name: newFactValue }
      }
      await api.addCandidateFact(activeCandidate.id, {
        kind: newFactKind,
        key: newFactKey || newFactKind.toLowerCase(),
        value: typeof parsedValue === 'object' ? parsedValue : { text: parsedValue },
      })
      setShowAddModal(false)
      setNewFactKey('')
      setNewFactValue('')
      const updated = await api.getCandidateFacts(activeCandidate.id)
      setFacts(updated)
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    }
  }

  const proposedCount = facts.filter((f) => f.status === 'PROPOSED').length
  const activeCount = facts.filter((f) => f.status === 'ACTIVE').length

  const filteredFacts = facts.filter((f) => {
    if (selectedCategory === 'ALL') return true
    return f.kind === selectedCategory
  })

  return (
    <div className="screen-page">
      {/* Title & Introduction */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Identity & Provenance
          </span>
          <h1 className="page-title">
            Candidate Profile & Fact Graph
          </h1>
          <p className="page-intro">
            The factual source of truth for all job-specific resumes. Upload your master resume to extract and verify your qualifications.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            loading={uploading}
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Import Master Resume</span>
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt,.md"
            onChange={handleFileUpload}
            className="hidden"
          />
          <Button variant="primary" size="sm" onClick={() => setShowAddModal(true)}>
            <Plus className="w-3.5 h-3.5" />
            <span>Add Fact Manually</span>
          </Button>
        </div>
      </div>

      {/* Notifications */}
      {message && (
        <div
          className={`mb-6 p-4 rounded-apple-md text-sm flex items-start justify-between border ${
            message.type === 'success'
              ? 'bg-success-subtle border-success-green/20 text-success-green'
              : 'bg-danger-subtle border-danger-red/20 text-danger-red'
          }`}
        >
          <div className="flex items-center gap-2">
            {message.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
            )}
            <span>{message.text}</span>
          </div>
          <button onClick={() => setMessage(null)} className="opacity-70 hover:opacity-100">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Master Resume Card */}
      <div className="mb-10">
        {resumeStatus?.has_master_resume ? (
          <Card className="bg-surface p-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-2xl bg-apple-blue/10 text-apple-blue flex items-center justify-center flex-shrink-0">
                  <FileText className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-text-primary text-base">
                      {resumeStatus.filename || 'Master_Resume.pdf'}
                    </h3>
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-success-subtle text-success-green border border-success-green/20">
                      Active Master Resume
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-xs text-text-tertiary">
                    <span>
                      SHA-256:{' '}
                      <code className="font-mono bg-black/5 px-1 py-0.5 rounded">
                        {resumeStatus.sha256?.slice(0, 16)}...
                      </code>
                    </span>
                    <span>•</span>
                    <span>{resumeStatus.total_facts} extracted facts</span>
                    <span>•</span>
                    <span>
                      Uploaded {resumeStatus.uploaded_at ? new Date(resumeStatus.uploaded_at).toLocaleDateString() : 'Recently'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 self-start md:self-auto">
                <a
                  href={`/api/v1/documents/${resumeStatus.document_id}/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-surface text-text-primary border border-border-subtle hover:bg-surface-hover transition-all shadow-apple-button"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Document</span>
                </a>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-black/5 transition-all"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Replace</span>
                </button>
                <button
                  onClick={handleDeleteDocument}
                  className="p-1.5 rounded-full text-text-tertiary hover:text-danger-red hover:bg-danger-subtle transition-all"
                  title="Delete Document"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </Card>
        ) : (
          <Card
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click() }}
            className="border-2 border-dashed border-border-strong hover:border-text-primary p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-all bg-surface/50 hover:bg-surface"
          >
            <div className="w-14 h-14 rounded-full bg-black/5 text-text-primary flex items-center justify-center mb-4">
              <Upload className="w-6 h-6" />
            </div>
            <h3 className="font-semibold text-text-primary text-lg">
              Import Master Resume
            </h3>
            <p className="text-text-secondary text-sm max-w-md mt-1 mb-4">
              Upload your actual master resume (PDF, DOCX, or TXT). JOV.si extracts education, experience, projects, skills, and contact facts with strict provenance.
            </p>
            <Button variant="primary" size="sm" loading={uploading}>
              Choose Resume File
            </Button>
            <span className="text-xs text-text-tertiary mt-3">
              Drop a searchable PDF, DOCX, or TXT here, or choose a file · up to 10MB
            </span>
          </Card>
        )}
      </div>

      {/* Proposed Facts Action Bar */}
      {proposedCount > 0 && (
        <div className="mb-6 p-4 rounded-card-lg bg-warning-subtle/80 border border-warning-amber/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-warning-amber flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-text-primary">
                {proposedCount} Proposed Facts Awaiting Verification
              </p>
              <p className="text-xs text-text-secondary">
                Extracted information requires human confirmation before it can be used in job applications.
              </p>
            </div>
          </div>
          <Button variant="primary" size="sm" onClick={handleConfirmAll} loading={loading}>
            <CheckCircle2 className="w-3.5 h-3.5 text-success-green" />
            <span>Confirm All Proposed Facts</span>
          </Button>
        </div>
      )}

      {/* Facts Filter Navigation */}
      <div className="flex items-center justify-between gap-4 mb-4 border-b border-border-subtle pb-3">
        <div className="flex items-center gap-1 overflow-x-auto">
          {[
            { id: 'ALL', label: `All Facts (${facts.length})` },
            { id: 'SKILL', label: 'Skills' },
            { id: 'EXPERIENCE', label: 'Experience' },
            { id: 'EDUCATION', label: 'Education' },
            { id: 'PROJECT', label: 'Projects' },
            { id: 'CONTACT', label: 'Contact & Auth' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSelectedCategory(tab.id)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                selectedCategory === tab.id
                  ? 'bg-text-primary text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-black/5'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="text-xs text-text-tertiary flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-success-green" />
            {activeCount} Active
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-warning-amber" />
            {proposedCount} Proposed
          </span>
        </div>
      </div>

      {/* Fact List */}
      {filteredFacts.length === 0 ? (
        <Card className="text-center py-12">
          <User className="w-10 h-10 text-text-tertiary mx-auto mb-3 opacity-40" />
          <h4 className="text-sm font-semibold text-text-primary">No facts in this category</h4>
          <p className="text-xs text-text-secondary mt-1">
            Import your master resume or add a fact manually to expand your qualification graph.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredFacts.map((fact) => {
            const isProposed = fact.status === 'PROPOSED'
            const isActionable = actingFactId === fact.id

            // Format human readable value
            let displayTitle = fact.key
            let displayContent = JSON.stringify(fact.value)

            if (fact.kind === 'SKILL') {
              displayTitle = fact.value.name || fact.key
              displayContent = 'Technical Skill'
            } else if (fact.kind === 'CONTACT') {
              displayTitle = fact.value.display_name || fact.key
              displayContent = `${fact.value.email || ''} • ${fact.value.phone || ''} • ${fact.value.location || ''}`
            } else if (fact.kind === 'EDUCATION') {
              displayTitle = `${fact.value.degree_level || 'Degree'} in ${fact.value.field || 'Study'}`
              displayContent = `Graduation Year: ${fact.value.graduation_year || 'N/A'}`
            } else if (fact.kind === 'EXPERIENCE') {
              displayTitle = fact.value.title || fact.key
              displayContent = fact.value.description || JSON.stringify(fact.value)
            } else if (fact.kind === 'PROJECT') {
              displayTitle = fact.value.name || fact.key
              displayContent = fact.value.description || ''
            }

            return (
              <Card
                key={fact.id}
                className={`flex flex-col justify-between p-4 ${
                  isProposed ? 'border-warning-amber/30 bg-warning-subtle/20' : 'bg-surface'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary">
                      {fact.kind}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        isProposed
                          ? 'bg-warning-subtle text-warning-amber border border-warning-amber/30'
                          : 'bg-success-subtle text-success-green border border-success-green/20'
                      }`}
                    >
                      {isProposed ? 'Proposed' : 'Active (Verified)'}
                    </span>
                  </div>

                  <h4 className="font-semibold text-text-primary text-sm mb-1">{displayTitle}</h4>
                  <p className="text-xs text-text-secondary line-clamp-3 mb-3 leading-relaxed">
                    {displayContent}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-border-subtle mt-2 text-xs">
                  <span className="text-[11px] text-text-tertiary font-mono">
                    {fact.provenance}
                  </span>

                  <div className="flex items-center gap-1.5">
                    {isProposed ? (
                      <>
                        <button
                          onClick={() => handleConfirmFact(fact.id)}
                          disabled={isActionable}
                          className="px-2.5 py-1 rounded-full text-xs font-medium bg-success-green text-white hover:opacity-90 transition-opacity"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => handleRejectFact(fact.id)}
                          disabled={isActionable}
                          className="px-2.5 py-1 rounded-full text-xs font-medium text-danger-red hover:bg-danger-subtle transition-colors"
                        >
                          Reject
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => {
                            setEditingFact(fact)
                            setEditValueText(JSON.stringify(fact.value, null, 2))
                          }}
                          className="p-1 rounded-full text-text-tertiary hover:text-text-primary transition-colors"
                          title="Edit Fact"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={async () => {
                            if (confirm('Delete this verified fact?')) {
                              await api.deleteFact(fact.id)
                              if (activeCandidate) {
                                const updated = await api.getCandidateFacts(activeCandidate.id)
                                setFacts(updated)
                              }
                            }
                          }}
                          className="p-1 rounded-full text-text-tertiary hover:text-danger-red transition-colors"
                          title="Delete Fact"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Edit Fact Modal */}
      {editingFact && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <Card className="w-full max-w-lg p-6 bg-surface shadow-apple-floating">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-text-primary text-base">
                Edit Fact: {editingFact.key}
              </h3>
              <button onClick={() => setEditingFact(null)} className="text-text-tertiary hover:text-text-primary">
                <X className="w-4 h-4" />
              </button>
            </div>
            <textarea
              value={editValueText}
              onChange={(e) => setEditValueText(e.target.value)}
              className="w-full h-40 p-3 rounded-apple-sm font-mono text-xs border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue mb-4"
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setEditingFact(null)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" onClick={handleSaveEditFact}>
                Save Changes
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Add Fact Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <Card className="w-full max-w-lg p-6 bg-surface shadow-apple-floating">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-text-primary text-base">Add New Candidate Fact</h3>
              <button onClick={() => setShowAddModal(false)} className="text-text-tertiary hover:text-text-primary">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleAddFactSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                  Fact Kind
                </label>
                <select
                  value={newFactKind}
                  onChange={(e) => setNewFactKind(e.target.value)}
                  className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
                >
                  <option value="SKILL">Skill</option>
                  <option value="EXPERIENCE">Experience</option>
                  <option value="EDUCATION">Education</option>
                  <option value="PROJECT">Project</option>
                  <option value="WORK_AUTH">Work Authorization</option>
                  <option value="CONTACT">Contact</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                  Key / Identifier
                </label>
                <input
                  type="text"
                  placeholder="e.g. skill_python or degree"
                  value={newFactKey}
                  onChange={(e) => setNewFactKey(e.target.value)}
                  className="w-full p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase mb-1">
                  Value (JSON or plain text)
                </label>
                <textarea
                  placeholder='e.g. {"name": "Python"} or Python'
                  value={newFactValue}
                  onChange={(e) => setNewFactValue(e.target.value)}
                  className="w-full h-24 p-2.5 rounded-apple-sm text-sm border border-border-subtle bg-canvas text-text-primary focus:outline-none focus:border-apple-blue font-mono text-xs"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" size="sm" type="button" onClick={() => setShowAddModal(false)}>
                  Cancel
                </Button>
                <Button variant="primary" size="sm" type="submit">
                  Save Fact
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  )
}
