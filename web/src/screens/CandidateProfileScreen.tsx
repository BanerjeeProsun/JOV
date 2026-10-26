import React, { useEffect, useState, useRef } from 'react'
import { motion } from 'motion/react'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { api } from '../api/client'
import type { Candidate, Fact, MasterResumeStatus } from '../types'
import {
  FileText,
  Upload,
  CheckCircle2,
  Trash2,
  Plus,
  RefreshCw,
  User,
  GraduationCap,
  Briefcase,
  Code2,
  ShieldCheck,
  X,
} from 'lucide-react'
import { spring } from '../design/motion'

type ProfileSection = 'basics' | 'experience' | 'education' | 'skills' | 'work_auth' | 'advanced'

export const CandidateProfileScreen: React.FC = () => {
  const [activeCandidate, setActiveCandidate] = useState<Candidate | null>(null)
  const [resumeStatus, setResumeStatus] = useState<MasterResumeStatus | null>(null)
  const [facts, setFacts] = useState<Fact[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [activeSection, setActiveSection] = useState<ProfileSection>('basics')
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [actingFactId, setActingFactId] = useState<string | null>(null)

  // Add Fact Modal
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
        text: `Master resume parsed: ${result.total_facts_extracted} facts extracted with provenance.`,
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

  const handleDeleteFact = async (factId: string) => {
    setActingFactId(factId)
    try {
      await api.deleteFact(factId)
      setMessage({ type: 'success', text: 'Fact successfully deleted.' })
      await loadData()
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Delete failed.' })
    } finally {
      setActingFactId(null)
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
        value: parsedValue,
      })
      setShowAddModal(false)
      setNewFactKey('')
      setNewFactValue('')
      setMessage({ type: 'success', text: 'New candidate fact added.' })
      await loadData()
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to add fact.' })
    }
  }

  // Categorize facts
  const contactFacts = facts.filter((f) => f.kind === 'CONTACT')
  const experienceFacts = facts.filter((f) => f.kind === 'EXPERIENCE')
  const educationFacts = facts.filter((f) => f.kind === 'EDUCATION')
  const skillFacts = facts.filter((f) => f.kind === 'SKILL')
  const authFacts = facts.filter((f) => f.kind === 'WORK_AUTH')

  const SECTIONS = [
    { id: 'basics' as ProfileSection, label: 'Basics & Identity', icon: User, count: contactFacts.length },
    { id: 'experience' as ProfileSection, label: 'Experience', icon: Briefcase, count: experienceFacts.length },
    { id: 'education' as ProfileSection, label: 'Education', icon: GraduationCap, count: educationFacts.length },
    { id: 'skills' as ProfileSection, label: 'Skills & Competencies', icon: Code2, count: skillFacts.length },
    { id: 'work_auth' as ProfileSection, label: 'Work Authorization', icon: ShieldCheck, count: authFacts.length },
    { id: 'advanced' as ProfileSection, label: 'Advanced Data', icon: FileText, count: facts.length },
  ]

  return (
    <div className="screen-page space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-border">
        <div>
          <p className="page-kicker">Strict Provenance</p>
          <h1 className="page-title">Candidate Profile & Fact Graph</h1>
          <p className="page-intro">
            Structured candidate records extracted from your verified master resume. Every fact is audited and immutable during application packaging.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button variant="secondary" size="md" onClick={loadData} loading={loading}>
            <RefreshCw className="w-4 h-4" />
            <span>Sync Graph</span>
          </Button>
          <Button variant="primary" size="md" onClick={() => setShowAddModal(true)}>
            <Plus className="w-4 h-4" />
            <span>Add Custom Fact</span>
          </Button>
        </div>
      </div>

      {/* Message Banner */}
      {message && (
        <div
          className={`p-4 rounded-card border text-sm flex items-center justify-between ${
            message.type === 'success'
              ? 'bg-ok-subtle border-ok/20 text-ok'
              : 'bg-err-subtle border-err/20 text-err'
          }`}
        >
          <div className="flex items-center gap-2.5">
            {message.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 shrink-0" />
            ) : (
              <X className="w-4 h-4 shrink-0" />
            )}
            <span>{message.text}</span>
          </div>
          <button onClick={() => setMessage(null)} className="p-1 hover:opacity-70">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Master Resume Upload Area */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="rounded-card border-2 border-dashed border-border bg-bg-elev-1 p-8 text-center hover:border-border-strong transition-colors relative overflow-hidden"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt"
          onChange={handleFileUpload}
          className="hidden"
          id="resume-file-input"
        />

        <div className="max-w-md mx-auto space-y-3">
          <div className="w-12 h-12 rounded-full bg-bg-elev-2 flex items-center justify-center mx-auto text-text">
            <Upload className="w-5 h-5" strokeWidth={1.5} />
          </div>
          <h3 className="text-base font-semibold text-text">
            {resumeStatus?.has_master_resume ? 'Replace Master Resume' : 'Upload Master Resume'}
          </h3>
          <p className="text-xs text-text-2 leading-relaxed">
            Drag and drop your PDF CV here, or browse files. The extractor parses verifiable claims without modifying facts.
          </p>
          <div className="pt-2">
            <Button
              variant="secondary"
              size="sm"
              loading={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>{uploading ? 'Extracting claims…' : 'Select PDF document'}</span>
            </Button>
          </div>
          {resumeStatus?.has_master_resume && (
            <p className="text-[11px] font-mono text-ok pt-2">
              ✓ Master resume active ({resumeStatus.filename || 'PDF on disk'})
            </p>
          )}
        </div>
      </div>

      {/* Two Column Layout: Sticky Section Nav & Content */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Sticky Rail */}
        <div className="lg:col-span-4 sticky top-24 space-y-1">
          {SECTIONS.map((sec) => {
            const active = activeSection === sec.id
            const Icon = sec.icon
            return (
              <button
                key={sec.id}
                onClick={() => setActiveSection(sec.id)}
                className={`relative w-full flex items-center justify-between px-4 py-3 rounded-card text-left transition-colors ${
                  active ? 'text-text font-semibold' : 'text-text-2 hover:text-text hover:bg-selected'
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="profile-section-pill"
                    className="absolute inset-0 rounded-card bg-selected border border-border"
                    transition={spring.layout}
                  />
                )}
                <div className="relative z-10 flex items-center gap-3">
                  <Icon className="w-4 h-4 text-text-3" strokeWidth={1.5} />
                  <span className="text-sm">{sec.label}</span>
                </div>
                <span className="relative z-10 text-xs font-mono text-text-3 px-2 py-0.5 rounded-full bg-bg-input">
                  {sec.count}
                </span>
              </button>
            )
          })}
        </div>

        {/* Right Section Content */}
        <div className="lg:col-span-8 space-y-4">
          {activeSection === 'basics' && (
            <div className="rounded-card border border-border bg-bg-elev-1 p-6 space-y-5">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-text-3">
                Candidate Identity
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-text-3">Display Name</label>
                  <p className="p-3 rounded-md border border-border bg-bg-input text-sm font-semibold text-text">
                    {activeCandidate?.display_name || 'Ada Lovelace'}
                  </p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-text-3">Timezone</label>
                  <p className="p-3 rounded-md border border-border bg-bg-input text-sm font-mono text-text">
                    {activeCandidate?.timezone || 'UTC'}
                  </p>
                </div>
              </div>

              {contactFacts.length > 0 && (
                <div className="pt-4 border-t border-border space-y-3">
                  <h4 className="text-xs font-semibold text-text-3 uppercase">Verified Contacts</h4>
                  {contactFacts.map((cf) => (
                    <div key={cf.id} className="p-4 rounded-md border border-border bg-bg-elev-2 flex items-center justify-between text-xs">
                      <div>
                        <p className="font-semibold text-text">{cf.value?.full_name || 'Contact Info'}</p>
                        <p className="text-text-2 font-mono mt-0.5">{cf.value?.email} · {cf.value?.phone}</p>
                      </div>
                      <span className="font-mono text-[10px] text-ok px-2 py-0.5 rounded bg-ok-subtle">
                        {cf.provenance}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeSection === 'experience' && (
            <div className="space-y-3">
              {experienceFacts.length === 0 ? (
                <div className="p-12 rounded-card border border-border bg-bg-elev-1 text-center text-xs text-text-3">
                  No experience records parsed yet. Upload your master resume above.
                </div>
              ) : (
                experienceFacts.map((ef) => (
                  <div key={ef.id} className="rounded-card border border-border bg-bg-elev-1 p-6 space-y-3 shadow-1">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h4 className="text-base font-semibold text-text">{ef.value?.title || ef.key}</h4>
                        <p className="text-xs text-text-3 font-mono mt-0.5">
                          {ef.value?.duration_months ? `${Math.round(ef.value.duration_months / 12)} years experience` : 'Professional Role'}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleDeleteFact(ef.id)}
                          disabled={actingFactId === ef.id}
                          className="p-1.5 rounded-full text-text-3 hover:text-err transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    {ef.value?.description && (
                      <p className="text-xs text-text-2 leading-relaxed">{ef.value.description}</p>
                    )}
                    {ef.value?.skills && Array.isArray(ef.value.skills) && (
                      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-border/50">
                        {ef.value.skills.map((s: string, idx: number) => (
                          <span key={idx} className="text-[11px] font-mono px-2 py-0.5 rounded bg-bg-input text-text-3">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {activeSection === 'education' && (
            <div className="space-y-3">
              {educationFacts.length === 0 ? (
                <div className="p-12 rounded-card border border-border bg-bg-elev-1 text-center text-xs text-text-3">
                  No education records parsed yet.
                </div>
              ) : (
                educationFacts.map((ef) => (
                  <div key={ef.id} className="rounded-card border border-border bg-bg-elev-1 p-6 flex items-start justify-between shadow-1">
                    <div className="space-y-1">
                      <h4 className="text-base font-semibold text-text">
                        {ef.value?.degree_level} in {ef.value?.field || ef.key}
                      </h4>
                      <p className="text-xs text-text-3 font-mono">
                        Graduation: {ef.value?.graduation_year || 'Verified'} · Provenance: {ef.provenance}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDeleteFact(ef.id)}
                      className="p-1.5 rounded-full text-text-3 hover:text-err transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

          {activeSection === 'skills' && (
            <div className="rounded-card border border-border bg-bg-elev-1 p-6 space-y-4 shadow-1">
              <div className="flex items-center justify-between pb-3 border-b border-border">
                <h3 className="text-sm font-semibold text-text">Verified Skills ({skillFacts.length})</h3>
                <span className="text-xs text-text-3 font-mono">Immutable Graph Records</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {skillFacts.map((sf) => (
                  <span
                    key={sf.id}
                    className="group inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-bg-elev-2 text-xs font-mono text-text hover:border-border-strong transition-colors"
                  >
                    <span>{sf.value?.name || sf.key}</span>
                    <button
                      onClick={() => handleDeleteFact(sf.id)}
                      className="opacity-0 group-hover:opacity-100 hover:text-err transition-opacity"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          {activeSection === 'work_auth' && (
            <div className="rounded-card border border-border bg-bg-elev-1 p-6 space-y-4 shadow-1">
              <h3 className="text-sm font-semibold text-text">Work Authorization Countries</h3>
              {authFacts.length === 0 ? (
                <p className="text-xs text-text-3">No work authorization facts registered.</p>
              ) : (
                authFacts.map((af) => (
                  <div key={af.id} className="flex items-center gap-2">
                    {(af.value?.authorized_countries || []).map((c: string) => (
                      <span key={c} className="px-3 py-1 rounded-full bg-ok-subtle border border-ok/20 text-ok text-xs font-mono font-semibold">
                        {c}
                      </span>
                    ))}
                  </div>
                ))
              )}
            </div>
          )}

          {activeSection === 'advanced' && (
            <div className="rounded-card border border-border bg-bg-elev-1 p-6 space-y-3">
              <h3 className="text-xs uppercase tracking-wider font-semibold text-text-3">
                Advanced: Raw Fact Graph JSON
              </h3>
              <pre className="p-4 rounded-md bg-bg-input border border-border text-[11px] font-mono text-text-2 overflow-x-auto max-h-[400px]">
                {JSON.stringify(facts, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>

      {/* Add Fact Modal */}
      <Dialog
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        title="Add Custom Candidate Fact"
        description="Insert a factual assertion into your provenance graph."
      >
        <form onSubmit={handleAddFactSubmit} className="space-y-4 mt-2">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-text">Fact Kind</label>
            <select
              value={newFactKind}
              onChange={(e) => setNewFactKind(e.target.value)}
              className="app-input"
            >
              <option value="SKILL">SKILL</option>
              <option value="EDUCATION">EDUCATION</option>
              <option value="EXPERIENCE">EXPERIENCE</option>
              <option value="CERTIFICATION">CERTIFICATION</option>
              <option value="WORK_AUTH">WORK_AUTH</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-text">Key Identifier</label>
            <input
              required
              value={newFactKey}
              onChange={(e) => setNewFactKey(e.target.value)}
              className="app-input font-mono text-xs"
              placeholder="e.g. typescript"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-text">Value (String or JSON)</label>
            <input
              required
              value={newFactValue}
              onChange={(e) => setNewFactValue(e.target.value)}
              className="app-input font-mono text-xs"
              placeholder="TypeScript or {&quot;name&quot;: &quot;TypeScript&quot;}"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Button type="button" variant="secondary" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              Save Fact
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
