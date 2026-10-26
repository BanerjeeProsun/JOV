import React, { useEffect, useState, useRef } from 'react'
import { AnimatePresence, motion, LayoutGroup } from 'motion/react'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { api } from '../api/client'
import type { Candidate, DeepLinkItem, JobSource, JobSearchItem, JobSearchResponse, LocationHierarchyResponse } from '../types'
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
  MapPin,
  SlidersHorizontal,
  Globe,
  ChevronDown,
  RotateCcw,
  Check,
  Link as LinkIcon,
  FileText,
  AlertCircle,
  Compass,
} from 'lucide-react'
import { spring, fadeUp } from '../design/motion'

interface JobDiscoveryScreenProps {
  onSelectApplication?: (appId: string) => void
  onNavigateToQueue: () => void
}

interface SearchFilters {
  q: string
  countries: string[]
  admin1: string[]
  cities: string[]
  workModes: string[]
  minScore: number | null
  sources: string[]
  page: number
  sort: string
}

const readUrlFilters = (): SearchFilters => {
  if (typeof window === 'undefined') {
    return { q: '', countries: [], admin1: [], cities: [], workModes: [], minScore: null, sources: [], page: 1, sort: 'date' }
  }
  const params = new URLSearchParams(window.location.search)
  const q = params.get('q') || ''
  const countries = params.get('country') ? params.get('country')!.split(',').filter(Boolean) : []
  const admin1 = params.get('admin1') ? params.get('admin1')!.split(',').filter(Boolean) : []
  const cities = params.get('city') ? params.get('city')!.split(',').filter(Boolean) : []
  const workModes = params.get('work_mode') ? params.get('work_mode')!.split(',').filter(Boolean) : []
  const sources = params.get('source') ? params.get('source')!.split(',').filter(Boolean) : []
  const scoreRaw = params.get('min_score')
  const minScore = scoreRaw !== null && scoreRaw !== '' ? Number(scoreRaw) : null
  const page = Number(params.get('page')) || 1
  const sort = params.get('sort') || 'date'

  return { q, countries, admin1, cities, workModes, minScore, sources, page, sort }
}

const writeUrlFilters = (f: SearchFilters) => {
  if (typeof window === 'undefined') return
  const params = new URLSearchParams()
  if (f.q.trim()) params.set('q', f.q.trim())
  if (f.countries.length > 0) params.set('country', f.countries.join(','))
  if (f.admin1.length > 0) params.set('admin1', f.admin1.join(','))
  if (f.cities.length > 0) params.set('city', f.cities.join(','))
  if (f.workModes.length > 0) params.set('work_mode', f.workModes.join(','))
  if (f.sources.length > 0) params.set('source', f.sources.join(','))
  if (f.minScore !== null && f.minScore > 0) params.set('min_score', String(f.minScore))
  if (f.page > 1) params.set('page', String(f.page))
  if (f.sort && f.sort !== 'date') params.set('sort', f.sort)

  const newSearch = params.toString()
  const newUrl = newSearch ? `${window.location.pathname}?${newSearch}` : window.location.pathname
  if (window.location.search !== `?${newSearch}` && (window.location.search || newSearch)) {
    window.history.pushState({}, '', newUrl)
  }
}

export const JobDiscoveryScreen: React.FC<JobDiscoveryScreenProps> = ({
  onNavigateToQueue,
}) => {
  const [filters, setFilters] = useState<SearchFilters>(readUrlFilters)
  const [searchResponse, setSearchResponse] = useState<JobSearchResponse | null>(null)
  const [availableLocations, setAvailableLocations] = useState<LocationHierarchyResponse | null>(null)
  const [sources, setSources] = useState<JobSource[]>([])
  const [activeCandidate, setActiveCandidate] = useState<Candidate | null>(null)
  const [loading, setLoading] = useState(true)
  const [discovering, setDiscovering] = useState(false)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [showImportModal, setShowImportModal] = useState(false)
  const [startingAppId, setStartingAppId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  // Filter dropdown toggles
  const [countryDropdownOpen, setCountryDropdownOpen] = useState(false)
  const [cityDropdownOpen, setCityDropdownOpen] = useState(false)
  const [countrySearchText, setCountrySearchText] = useState('')
  const [citySearchText, setCitySearchText] = useState('')
  const [showScoreSlider, setShowScoreSlider] = useState(false)

  const countryMenuRef = useRef<HTMLDivElement>(null)
  const cityMenuRef = useRef<HTMLDivElement>(null)

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
  const [importMode, setImportMode] = useState<'url' | 'manual'>('manual')
  const [importUrl, setImportUrl] = useState('')
  const [showDeepLinksModal, setShowDeepLinksModal] = useState(false)
  const [deepLinks, setDeepLinks] = useState<DeepLinkItem[]>([])
  const [loadingDeepLinks, setLoadingDeepLinks] = useState(false)

  // Listen to browser Back/Forward navigation
  useEffect(() => {
    const handlePopState = () => {
      setFilters(readUrlFilters())
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  // Close popovers on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (countryMenuRef.current && !countryMenuRef.current.contains(e.target as Node)) {
        setCountryDropdownOpen(false)
      }
      if (cityMenuRef.current && !cityMenuRef.current.contains(e.target as Node)) {
        setCityDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Initial reference load
  useEffect(() => {
    const initData = async () => {
      try {
        const [cand, sourcesData, locs] = await Promise.all([
          api.getActiveCandidate(),
          api.getJobSources().catch(() => []),
          api.getLocationFacets().catch(() => ({ countries: [], admin1: [], cities: [] })),
        ])
        setActiveCandidate(cand)
        setSources(sourcesData)
        setAvailableLocations(locs)
      } catch (err) {
        console.error(err)
      }
    }
    initData()
  }, [])

  // Execute faceted search whenever filters change
  const executeSearch = async (curFilters: SearchFilters) => {
    setLoading(true)
    try {
      writeUrlFilters(curFilters)
      const resp = await api.searchJobs({
        q: curFilters.q,
        country: curFilters.countries,
        admin1: curFilters.admin1,
        city: curFilters.cities,
        work_mode: curFilters.workModes,
        min_score: curFilters.minScore ?? undefined,
        source: curFilters.sources,
        sort: curFilters.sort,
        page: curFilters.page,
        page_size: 20,
        candidate_id: activeCandidate?.id,
      })
      setSearchResponse(resp)
      if (resp.items.length > 0) {
        if (!selectedJobId || !resp.items.some((i) => i.id === selectedJobId)) {
          setSelectedJobId(resp.items[0].id)
        }
      }
    } catch (err: any) {
      console.error('Job search failed:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    executeSearch(filters)
  }, [
    filters.q,
    filters.countries.join(','),
    filters.admin1.join(','),
    filters.cities.join(','),
    filters.workModes.join(','),
    filters.sources.join(','),
    filters.minScore,
    filters.page,
    filters.sort,
  ])

  // Filter mutation helpers
  const updateFilter = (updates: Partial<SearchFilters>) => {
    setFilters((prev) => ({
      ...prev,
      ...updates,
      page: updates.page !== undefined ? updates.page : 1, // Reset page on filter changes unless explicit
    }))
  }

  const toggleCountry = (code: string) => {
    const exists = filters.countries.includes(code)
    const next = exists ? filters.countries.filter((c) => c !== code) : [...filters.countries, code]
    updateFilter({ countries: next, cities: [] }) // Reset cities if country changes
  }

  const toggleCity = (cityId: string) => {
    const exists = filters.cities.includes(cityId)
    const next = exists ? filters.cities.filter((c) => c !== cityId) : [...filters.cities, cityId]
    updateFilter({ cities: next })
  }

  const toggleWorkMode = (mode: string) => {
    const exists = filters.workModes.includes(mode)
    const next = exists ? filters.workModes.filter((m) => m !== mode) : [...filters.workModes, mode]
    updateFilter({ workModes: next })
  }

  const clearAllFilters = () => {
    setFilters({
      q: '',
      countries: [],
      admin1: [],
      cities: [],
      workModes: [],
      minScore: null,
      sources: [],
      page: 1,
      sort: 'date',
    })
  }

  const hasActiveFilters = Boolean(
    filters.q ||
    filters.countries.length > 0 ||
    filters.cities.length > 0 ||
    filters.workModes.length > 0 ||
    filters.sources.length > 0 ||
    (filters.minScore !== null && filters.minScore > 0)
  )

  const handleDiscoverLive = async () => {
    setDiscovering(true)
    setActionMessage(null)
    try {
      const resp = await api.discoverJobs({
        source: 'all',
        query: filters.q,
        candidate_id: activeCandidate?.id,
        limit: 15,
      })
      setActionMessage(`Discovered ${resp.total_found} real opportunities across live feeds.`)
      executeSearch(filters)
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
      executeSearch(filters)
      setActionMessage('Job successfully imported and sanitized!')
      setTimeout(() => setActionMessage(null), 4000)
    } catch (err: any) {
      setImportError(err.message || 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  const handleUrlImport = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!importUrl.trim()) return
    setImporting(true)
    setImportError(null)
    try {
      const imported = await api.importJobByUrl(importUrl.trim())
      setShowImportModal(false)
      setImportUrl('')
      executeSearch(filters)
      setSelectedJobId(imported.id)
      setActionMessage(`Imported ${imported.title_norm} at ${imported.company_norm}`)
      setTimeout(() => setActionMessage(null), 4000)
    } catch (err: any) {
      setImportError(err.message || 'Failed to extract posting from URL')
    } finally {
      setImporting(false)
    }
  }

  const handleOpenDeepLinks = async () => {
    setShowDeepLinksModal(true)
    setLoadingDeepLinks(true)
    try {
      const locStr = filters.cities[0] || filters.countries[0] || ''
      const links = await api.getDeepLinks(filters.q, locStr)
      setDeepLinks(links)
    } catch (err) {
      console.error(err)
    } finally {
      setLoadingDeepLinks(false)
    }
  }

  const handleStartApplication = async (item: JobSearchItem) => {
    setStartingAppId(item.id)
    try {
      const activeCand = await api.ensureActiveCandidate()
      await api.createApplication(activeCand.id, item.id)
      setActionMessage(`Application created for ${item.title} at ${item.company_name}`)
      setTimeout(() => {
        onNavigateToQueue()
      }, 400)
    } catch (err: any) {
      setActionMessage(`Error starting application: ${err.message}`)
    } finally {
      setStartingAppId(null)
    }
  }

  const items = searchResponse?.items || []
  const selectedJob = items.find((j) => j.id === selectedJobId) || items[0] || null

  // Facet options
  const countryFacetOptions =
    searchResponse?.facets?.countries && searchResponse.facets.countries.length > 0
      ? searchResponse.facets.countries
      : availableLocations?.countries || []
  const cityFacetOptions =
    searchResponse?.facets?.cities && searchResponse.facets.cities.length > 0
      ? searchResponse.facets.cities
      : availableLocations?.cities || []
  const workModeFacets = searchResponse?.facets?.work_modes || []

  const getWorkModeCount = (mode: string) => {
    const f = workModeFacets.find((wm) => wm.key.toLowerCase() === mode.toLowerCase())
    return f ? f.count : 0
  }

  return (
    <div className="screen-page space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-border">
        <div>
          <p className="page-kicker">Real Market Sourcing</p>
          <h1 className="page-title">Job Discovery</h1>
          <p className="page-intro">
            Multi-dimensional job discovery with real geographic resolution, country/city facets, and provenance tracking.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button
            variant="secondary"
            size="md"
            onClick={handleOpenDeepLinks}
          >
            <Compass className="w-4 h-4" />
            <span>Deep Search</span>
          </Button>
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

      {/* Search & Filter Toolbar */}
      <div className="space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
          {/* Main Keyword Search Box */}
          <div className="flex-1 flex items-center gap-2.5 px-3 py-2 bg-bg-elev-1/60 rounded-xl border border-border/80 shadow-1 backdrop-blur-sm">
            <Search className="w-4 h-4 text-text-3 shrink-0" strokeWidth={1.5} />
            <input
              value={filters.q}
              onChange={(e) => updateFilter({ q: e.target.value })}
              placeholder="Search by role title, company, or skills…"
              className="w-full bg-transparent text-[14px] text-text placeholder:text-text-3 outline-none"
            />
            {filters.q && (
              <button
                onClick={() => updateFilter({ q: '' })}
                className="p-1 text-text-3 hover:text-text"
                title="Clear query"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Work Mode Toggle Pills */}
          <div className="flex items-center gap-1.5 p-1 bg-bg-elev-1/60 rounded-xl border border-border/80 shadow-1 shrink-0">
            {(['remote', 'hybrid', 'onsite'] as const).map((mode) => {
              const active = filters.workModes.includes(mode)
              const count = getWorkModeCount(mode)
              const label = mode === 'remote' ? 'Remote' : mode === 'hybrid' ? 'Hybrid' : 'On-site'
              return (
                <button
                  key={mode}
                  onClick={() => toggleWorkMode(mode)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                    active
                      ? 'bg-selected text-text border border-pearl-1/40 shadow-1'
                      : 'text-text-3 hover:text-text hover:bg-bg-input'
                  }`}
                >
                  <span>{label}</span>
                  {count > 0 && (
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-bg-elev-2 text-text-3">
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Filter Popover Buttons */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Country Filter Popover */}
            <div ref={countryMenuRef} className="relative">
              <button
                onClick={() => setCountryDropdownOpen(!countryDropdownOpen)}
                className={`px-3 py-2 rounded-xl text-xs font-medium border flex items-center gap-2 transition-colors ${
                  filters.countries.length > 0
                    ? 'bg-selected text-text border-pearl-1/40'
                    : 'bg-bg-elev-1/60 text-text-2 border-border/80 hover:text-text'
                }`}
              >
                <Globe className="w-3.5 h-3.5 text-text-3" />
                <span>
                  {filters.countries.length === 0
                    ? 'Country'
                    : filters.countries.length === 1
                    ? filters.countries[0]
                    : `${filters.countries.length} Countries`}
                </span>
                <ChevronDown className="w-3.5 h-3.5 opacity-60" />
              </button>

              <AnimatePresence>
                {countryDropdownOpen && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: -6 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: -4 }}
                    className="absolute left-0 md:right-0 md:left-auto top-full mt-2 w-64 p-3 bg-bg-elev-1 rounded-xl border border-border shadow-float z-50 space-y-2"
                  >
                    <div className="flex items-center gap-2 px-2 py-1.5 bg-bg-input rounded-lg text-xs border border-border">
                      <Search className="w-3 h-3 text-text-3" />
                      <input
                        value={countrySearchText}
                        onChange={(e) => setCountrySearchText(e.target.value)}
                        placeholder="Search countries…"
                        className="w-full bg-transparent outline-none text-text text-xs"
                      />
                    </div>
                    <div className="max-h-56 overflow-y-auto space-y-0.5 [scrollbar-width:thin]">
                      {countryFacetOptions
                        .filter(
                          (c) =>
                            !countrySearchText ||
                            c.name.toLowerCase().includes(countrySearchText.toLowerCase()) ||
                            c.code.toLowerCase().includes(countrySearchText.toLowerCase())
                        )
                        .map((c) => {
                          const selected = filters.countries.includes(c.code)
                          return (
                            <button
                              key={c.code}
                              onClick={() => toggleCountry(c.code)}
                              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                                selected ? 'bg-selected text-text font-medium' : 'text-text-2 hover:bg-bg-input hover:text-text'
                              }`}
                            >
                              <div className="flex items-center gap-2 truncate">
                                <span className={`w-3.5 h-3.5 rounded flex items-center justify-center border text-[9px] ${selected ? 'border-pearl-1 bg-pearl-1 text-void' : 'border-border'}`}>
                                  {selected && <Check className="w-3 h-3 text-bg-page" />}
                                </span>
                                <span className="truncate">{c.name}</span>
                              </div>
                              <span className="font-mono text-[10px] text-text-3">{c.count}</span>
                            </button>
                          )
                        })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* City Filter Popover */}
            <div ref={cityMenuRef} className="relative">
              <button
                onClick={() => setCityDropdownOpen(!cityDropdownOpen)}
                className={`px-3 py-2 rounded-xl text-xs font-medium border flex items-center gap-2 transition-colors ${
                  filters.cities.length > 0
                    ? 'bg-selected text-text border-pearl-1/40'
                    : 'bg-bg-elev-1/60 text-text-2 border-border/80 hover:text-text'
                }`}
              >
                <MapPin className="w-3.5 h-3.5 text-text-3" />
                <span>
                  {filters.cities.length === 0
                    ? 'City'
                    : filters.cities.length === 1
                    ? '1 City'
                    : `${filters.cities.length} Cities`}
                </span>
                <ChevronDown className="w-3.5 h-3.5 opacity-60" />
              </button>

              <AnimatePresence>
                {cityDropdownOpen && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: -6 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: -4 }}
                    className="absolute right-0 top-full mt-2 w-64 p-3 bg-bg-elev-1 rounded-xl border border-border shadow-float z-50 space-y-2"
                  >
                    <div className="flex items-center gap-2 px-2 py-1.5 bg-bg-input rounded-lg text-xs border border-border">
                      <Search className="w-3 h-3 text-text-3" />
                      <input
                        value={citySearchText}
                        onChange={(e) => setCitySearchText(e.target.value)}
                        placeholder="Search cities…"
                        className="w-full bg-transparent outline-none text-text text-xs"
                      />
                    </div>
                    <div className="max-h-56 overflow-y-auto space-y-0.5 [scrollbar-width:thin]">
                      {cityFacetOptions
                        .filter(
                          (c) =>
                            !citySearchText ||
                            c.name.toLowerCase().includes(citySearchText.toLowerCase())
                        )
                        .map((c) => {
                          const selected = filters.cities.includes(c.id)
                          return (
                            <button
                              key={c.id}
                              onClick={() => toggleCity(c.id)}
                              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                                selected ? 'bg-selected text-text font-medium' : 'text-text-2 hover:bg-bg-input hover:text-text'
                              }`}
                            >
                              <div className="flex items-center gap-2 truncate">
                                <span className={`w-3.5 h-3.5 rounded flex items-center justify-center border text-[9px] ${selected ? 'border-pearl-1 bg-pearl-1 text-void' : 'border-border'}`}>
                                  {selected && <Check className="w-3 h-3 text-bg-page" />}
                                </span>
                                <span className="truncate">{c.name}</span>
                              </div>
                              <span className="font-mono text-[10px] text-text-3">{c.count}</span>
                            </button>
                          )
                        })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Suitability Score Floor Toggle */}
            <button
              onClick={() => setShowScoreSlider(!showScoreSlider)}
              className={`px-3 py-2 rounded-xl text-xs font-medium border flex items-center gap-2 transition-colors ${
                filters.minScore !== null && filters.minScore > 0
                  ? 'bg-selected text-text border-pearl-1/40'
                  : 'bg-bg-elev-1/60 text-text-2 border-border/80 hover:text-text'
              }`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5 text-text-3" />
              <span>
                {filters.minScore !== null && filters.minScore > 0
                  ? `Score ≥ ${filters.minScore}`
                  : 'Score'}
              </span>
            </button>
          </div>
        </div>

        {/* Score Slider Sub-Bar */}
        {showScoreSlider && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="p-3 bg-bg-elev-1/60 rounded-xl border border-border flex items-center gap-4 text-xs"
          >
            <span className="text-text-3 font-mono shrink-0">Suitability Floor:</span>
            <input
              type="range"
              min="0"
              max="95"
              step="5"
              value={filters.minScore ?? 0}
              onChange={(e) => updateFilter({ minScore: Number(e.target.value) || null })}
              className="flex-1 accent-pearl-1 cursor-pointer"
            />
            <span className="font-mono font-medium text-text min-w-[3rem]">
              {filters.minScore ? `≥ ${filters.minScore}` : 'Off'}
            </span>
            {filters.minScore !== null && filters.minScore > 0 && (
              <button
                onClick={() => updateFilter({ minScore: null })}
                className="text-[11px] text-text-3 hover:text-text underline"
              >
                Reset
              </button>
            )}
          </motion.div>
        )}

        {/* Active Filter Chips & Clear All */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-2 pt-1 pb-1">
            <span className="text-[11px] font-mono text-text-3 uppercase tracking-wider">Active:</span>

            {filters.q && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-bg-elev-1 border border-border text-text">
                <span>"{filters.q}"</span>
                <button onClick={() => updateFilter({ q: '' })} className="text-text-3 hover:text-text">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {filters.countries.map((c) => (
              <span key={c} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-bg-elev-1 border border-border text-text">
                <span>{c}</span>
                <button onClick={() => toggleCountry(c)} className="text-text-3 hover:text-text">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}

            {filters.cities.map((cityId) => {
              const cObj = cityFacetOptions.find((c) => c.id === cityId)
              return (
                <span key={cityId} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-bg-elev-1 border border-border text-text">
                  <span>{cObj ? cObj.name : cityId}</span>
                  <button onClick={() => toggleCity(cityId)} className="text-text-3 hover:text-text">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )
            })}

            {filters.workModes.map((m) => (
              <span key={m} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-bg-elev-1 border border-border text-text capitalize">
                <span>{m}</span>
                <button onClick={() => toggleWorkMode(m)} className="text-text-3 hover:text-text">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}

            {filters.minScore !== null && filters.minScore > 0 && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-bg-elev-1 border border-border text-text">
                <span>Score ≥ {filters.minScore}</span>
                <button onClick={() => updateFilter({ minScore: null })} className="text-text-3 hover:text-text">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            <button
              onClick={clearAllFilters}
              className="inline-flex items-center gap-1 text-[11px] font-mono text-text-3 hover:text-text underline ml-1"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Clear all</span>
            </button>
          </div>
        )}
      </div>

      {/* Two-Pane Layout */}
      <LayoutGroup>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Dense Filtered Job List */}
          <div className="lg:col-span-5 space-y-3">
            <div className="flex items-center justify-between text-xs text-text-3 font-mono px-1">
              <span>{searchResponse?.total ?? 0} matching {searchResponse?.total === 1 ? 'position' : 'positions'}</span>
              {searchResponse && searchResponse.total_pages > 1 && (
                <span>Page {searchResponse.page} of {searchResponse.total_pages}</span>
              )}
            </div>

            {loading ? (
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
            ) : items.length === 0 ? (
              /* Empty State with Actionable Guidance */
              <div className="border border-border/60 rounded-xl bg-bg-elev-1/20 p-12 text-center text-text-3 space-y-4">
                <Briefcase className="w-8 h-8 mx-auto opacity-40" strokeWidth={1.5} />
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-text">No matching opportunities</p>
                  <p className="text-xs text-text-3 max-w-sm mx-auto leading-relaxed">
                    No roles match your exact criteria. Try broadening location filters, lowering your suitability score floor, or discovering new live roles.
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                  {hasActiveFilters && (
                    <Button variant="secondary" size="sm" onClick={clearAllFilters}>
                      <span>Clear all filters</span>
                    </Button>
                  )}
                  <Button variant="secondary" size="sm" onClick={handleOpenDeepLinks}>
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Search external boards</span>
                  </Button>
                  <Button variant="primary" size="sm" onClick={handleDiscoverLive} loading={discovering}>
                    <Sparkles className="w-3.5 h-3.5 text-pearl-1" />
                    <span>Discover live roles</span>
                  </Button>
                </div>
              </div>
            ) : (
              <AnimatePresence mode="popLayout">
                {items.map((job) => {
                  const isSelected = selectedJob?.id === job.id
                  const skills = job.required_skills || []

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
                            {job.title}
                          </h3>
                          <div className="flex items-center gap-2 mt-1 text-xs text-text-2">
                            <span className="font-medium text-text">
                              {job.company_name}
                            </span>
                            <span className="opacity-30">·</span>
                            <span className="text-text-3 font-mono text-[11px]">
                              {job.primary_location}
                            </span>
                          </div>
                        </div>

                        <div className="flex flex-col items-end gap-1 shrink-0">
                          {job.match_score !== null && job.match_score !== undefined && (
                            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-pearl-1/10 text-pearl-1 border border-pearl-1/20">
                              {Math.round(job.match_score)}%
                            </span>
                          )}
                          <span className="text-[10px] font-mono text-text-3">
                            {job.created_at ? new Date(job.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'Recent'}
                          </span>
                        </div>
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

            {/* Pagination Controls */}
            {searchResponse && searchResponse.total_pages > 1 && (
              <div className="flex items-center justify-between pt-3 border-t border-border/60 text-xs">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={filters.page <= 1}
                  onClick={() => updateFilter({ page: filters.page - 1 })}
                >
                  Previous
                </Button>
                <span className="text-text-3 font-mono text-xs">
                  {filters.page} / {searchResponse.total_pages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={filters.page >= searchResponse.total_pages}
                  onClick={() => updateFilter({ page: filters.page + 1 })}
                >
                  Next
                </Button>
              </div>
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
                      {selectedJob.source || 'Standard listing'}
                    </span>
                    <h2 className="text-2xl font-semibold tracking-tight text-text">
                      {selectedJob.title}
                    </h2>
                    <div className="flex flex-wrap items-center gap-3 text-sm text-text-2 pt-1">
                      <span className="flex items-center gap-1 text-text font-medium">
                        <Building2 className="w-4 h-4 text-text-3" strokeWidth={1.5} />
                        {selectedJob.company_name}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-text-3">
                        <MapPin className="w-3.5 h-3.5" />
                        {selectedJob.primary_location}
                      </span>
                      {selectedJob.match_score !== null && selectedJob.match_score !== undefined && (
                        <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-pearl-1/10 text-pearl-1 border border-pearl-1/20">
                          {Math.round(selectedJob.match_score)}% Suitability
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

                {/* Resolved Locations if multi */}
                {selectedJob.locations.length > 1 && (
                  <div className="space-y-2">
                    <h4 className="text-xs uppercase tracking-wider font-semibold text-text-3">
                      Available Locations
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedJob.locations.map((loc, lIdx) => (
                        <span
                          key={lIdx}
                          className="px-2.5 py-1 rounded-full border border-border bg-bg-elev-2 text-xs font-mono text-text"
                        >
                          {loc.raw_location} ({loc.work_mode})
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Required Skills */}
                {selectedJob.required_skills && selectedJob.required_skills.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs uppercase tracking-wider font-semibold text-text-3">
                      Required Competencies
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedJob.required_skills.map((skill: string, idx: number) => (
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
                    {selectedJob.description || 'No job description content provided.'}
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
        description="Extract posting details directly from a supported URL or paste raw job specifications."
        maxWidth="max-w-xl"
      >
        {/* Mode Selector Tabs */}
        <div className="flex border-b border-border mb-4">
          <button
            type="button"
            onClick={() => { setImportMode('url'); setImportError(null); }}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors ${
              importMode === 'url'
                ? 'border-pearl-1 text-text'
                : 'border-transparent text-text-3 hover:text-text'
            }`}
          >
            <LinkIcon className="w-3.5 h-3.5" />
            <span>Import by URL</span>
          </button>
          <button
            type="button"
            onClick={() => { setImportMode('manual'); setImportError(null); }}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 -mb-px transition-colors ${
              importMode === 'manual'
                ? 'border-pearl-1 text-text'
                : 'border-transparent text-text-3 hover:text-text'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Paste Description</span>
          </button>
        </div>

        {importError && (
          <div className="p-3 mb-4 rounded-lg border border-border/80 bg-bg-elev-1/80 text-text-2 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-text-3 shrink-0 mt-0.5" />
            <div className="space-y-2">
              <span>{importError}</span>
              {importError.includes('restricted by') && (
                <div>
                  <button
                    type="button"
                    onClick={() => setImportMode('manual')}
                    className="text-pearl-1 hover:underline font-medium text-xs inline-flex items-center gap-1"
                  >
                    <span>Switch to Paste Description</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {importMode === 'url' ? (
          <form onSubmit={handleUrlImport} className="space-y-4">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-text">Job Posting URL</label>
              <input
                required
                type="url"
                value={importUrl}
                onChange={(e) => setImportUrl(e.target.value)}
                className="app-input font-mono text-xs"
                placeholder="https://boards.greenhouse.io/... or https://jobs.lever.co/..."
              />
              <p className="text-[11px] text-text-3 mt-1">
                Supports Greenhouse, Lever, Ashby, SmartRecruiters, and standard Schema.org JobPosting web pages. Enforces strict SSRF defense.
              </p>
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
                disabled={!importUrl.trim()}
              >
                Fetch & Import
              </Button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleImportSubmit} className="space-y-4">
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
                  placeholder="e.g. Acme Corp"
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
        )}
      </Dialog>

      {/* Deep Links Search Modal */}
      <Dialog
        open={showDeepLinksModal}
        onClose={() => setShowDeepLinksModal(false)}
        title="Deep Search on External Boards"
        description="Search restricted recruitment platforms directly in your browser without scraping."
        maxWidth="max-w-2xl"
      >
        <div className="space-y-4 mt-2">
          <p className="text-xs text-text-3 leading-relaxed">
            These major recruitment platforms prohibit automated bot scraping. JOV.si constructs pre-filtered search links that open their official search directly with your current query and location:
          </p>

          {loadingDeepLinks ? (
            <div className="py-8 text-center text-xs text-text-3">Loading external search links…</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {deepLinks.map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 rounded-xl border border-border/70 bg-bg-elev-1/40 space-y-2 flex flex-col justify-between"
                >
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-text">{item.name}</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border border-border/60 text-text-3">
                        {item.policy_status}
                      </span>
                    </div>
                    <p className="text-[11px] text-text-3 leading-snug">
                      {item.policy_reason}
                    </p>
                  </div>

                  <div className="pt-2">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-bg-elev-1 border border-border hover:bg-selected text-text transition-colors w-full justify-center"
                    >
                      <span>Search on {item.name}</span>
                      <ExternalLink className="w-3 h-3 text-text-3" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between pt-4 border-t border-border">
            <span className="text-[11px] text-text-3">
              Found a role you like? Copy the posting and use <strong>Import Job Posting</strong>.
            </span>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowDeepLinksModal(false)}
            >
              Close
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
