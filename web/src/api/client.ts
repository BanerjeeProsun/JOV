import type {
  Application,
  Candidate,
  DeepLinkItem,
  DiagnosticsData,
  DiscoveredJob,
  EvaluationDetails,
  Fact,
  Job,
  JobSearchResponse,
  LocationHierarchyResponse,
  JobSource,
  MasterResumeStatus,
  MetricsSummary,
  SettingsData,
  SourceHealthTelemetry,
  User,
} from '../types'

const BASE_URL = ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const headers: Record<string, string> = {
    ...((options?.headers as Record<string, string>) || {}),
  }

  // Do not set Content-Type if body is FormData
  if (!(options?.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`
    try {
      const errJson = await response.json()
      errorDetail = errJson.detail || errJson.title || errorDetail
    } catch {
      // not JSON
    }
    throw new Error(errorDetail)
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T
  }

  return response.json()
}

async function downloadFile(path: string, fallbackFilename: string): Promise<string> {
  const url = `${BASE_URL}${path}`
  const response = await fetch(url, {
    credentials: 'include',
  })

  if (!response.ok) {
    let errorDetail = `Download failed (HTTP ${response.status})`
    try {
      const errJson = await response.json()
      errorDetail = errJson.detail || errJson.title || errorDetail
    } catch {
      // not JSON
    }
    throw new Error(errorDetail)
  }

  let filename = fallbackFilename
  const disposition = response.headers.get('Content-Disposition')
  if (disposition) {
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
    if (utf8Match && utf8Match[1]) {
      try {
        filename = decodeURIComponent(utf8Match[1].trim())
      } catch {
        // fallback
      }
    } else {
      const match = disposition.match(/filename="?([^";]+)"?/i)
      if (match && match[1]) {
        filename = match[1].trim()
      }
    }
  }

  const blob = await response.blob()
  const blobUrl = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.style.display = 'none'
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    window.URL.revokeObjectURL(blobUrl)
    document.body.removeChild(a)
  }, 200)

  return filename
}

export const api = {
  // Authentication & Account Identity
  register: (data: { email: string; password: string; display_name?: string; timezone?: string }) =>
    request<User>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  login: (data: { email: string; password: string }) =>
    request<User>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  logout: () =>
    request<{ status: string }>('/api/v1/auth/logout', {
      method: 'POST',
    }),
  getMe: () => request<User>('/api/v1/auth/me'),
  updateProfile: (data: { display_name?: string; timezone?: string }) =>
    request<User>('/api/v1/auth/profile', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  changePassword: (data: { current_password: string; new_password: string }) =>
    request<{ status: string }>('/api/v1/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  forgotPassword: (email: string) =>
    request<{ message: string; _test_token?: string }>('/api/v1/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (data: { token: string; new_password: string }) =>
    request<{ status: string }>('/api/v1/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  verifyEmail: (token: string) =>
    request<{ status: string }>('/api/v1/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),

  // System Health & Diagnostics
  getHealth: () => request<{ status: string; product: string; autonomy_level: string; allow_real_submission: boolean; timestamp: string }>('/health'),
  getDiagnostics: () => request<DiagnosticsData>('/diagnostics/health'),
  resetMockPortal: () => request<{ status: string; count: number }>('/__admin/reset', { method: 'POST' }),

  // Honest Metrics
  getMetricsSummary: () => request<MetricsSummary>('/api/v1/metrics/summary'),

  // Candidates & Facts
  getCandidates: () => request<Candidate[]>('/api/v1/candidates'),
  getCandidate: (id: string) => request<Candidate>(`/api/v1/candidates/${id}`),
  getActiveCandidate: async (): Promise<Candidate | null> => {
    const list = await request<Candidate[]>('/api/v1/candidates')
    return list.length > 0 ? list[0] : null
  },
  ensureActiveCandidate: async (): Promise<Candidate> => {
    const list = await request<Candidate[]>('/api/v1/candidates')
    if (list.length > 0) return list[0]

    let displayName = 'Candidate'
    try {
      const me = await request<User>('/api/v1/auth/me')
      if (me.display_name) displayName = me.display_name
    } catch {
      // not authenticated
    }

    return request<Candidate>('/api/v1/candidates', {
      method: 'POST',
      body: JSON.stringify({
        display_name: displayName,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata',
        is_synthetic: false,
      }),
    })
  },
  createCandidate: (data: { display_name: string; timezone: string; is_synthetic?: boolean }) =>
    request<Candidate>('/api/v1/candidates', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getCandidateFacts: (candidateId: string) => request<Fact[]>(`/api/v1/candidates/${candidateId}/facts`),
  addCandidateFact: (candidateId: string, data: { kind: string; key: string; value: Record<string, any> }) =>
    request<Fact>(`/api/v1/candidates/${candidateId}/facts`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateFact: (factId: string, data: { key?: string; value: Record<string, any> }) =>
    request<Fact>(`/api/v1/facts/${factId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteFact: (factId: string) =>
    request<void>(`/api/v1/facts/${factId}`, {
      method: 'DELETE',
    }),
  confirmFact: (factId: string) =>
    request<Fact>(`/api/v1/facts/${factId}/confirm`, {
      method: 'POST',
    }),
  confirmAllFacts: (candidateId: string) =>
    request<Fact[]>(`/api/v1/candidates/${candidateId}/confirm-all-facts`, {
      method: 'POST',
    }),
  rejectFact: (factId: string) =>
    request<Fact>(`/api/v1/facts/${factId}/reject`, {
      method: 'POST',
    }),

  // Master Resume Ingestion & Storage
  uploadMasterResume: (candidateId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<any>(`/api/v1/candidates/${candidateId}/resume/upload`, {
      method: 'POST',
      body: formData,
    })
  },
  getMasterResumeStatus: (candidateId: string) =>
    request<MasterResumeStatus>(`/api/v1/candidates/${candidateId}/master-resume`),
  deleteDocument: (documentId: string) =>
    request<void>(`/api/v1/documents/${documentId}`, {
      method: 'DELETE',
    }),

  // Jobs & Discovery
  getJobSources: () => request<JobSource[]>('/api/v1/jobs/sources'),
  getSourceHealth: () => request<SourceHealthTelemetry[]>('/api/v1/jobs/sources/health'),
  getDeepLinks: (query?: string, location?: string) => {
    const qp = new URLSearchParams()
    if (query) qp.append('query', query)
    if (location) qp.append('location', location)
    return request<DeepLinkItem[]>(`/api/v1/jobs/deep-links?${qp.toString()}`)
  },
  importJobByUrl: (url: string) =>
    request<Job>('/api/v1/jobs/import/url', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }),
  discoverJobs: (params: {
    source?: string
    query?: string
    company?: string
    location?: string
    limit?: number
    candidate_id?: string
  }) =>
    request<{ total_found: number; source_status: Record<string, string>; jobs: DiscoveredJob[] }>(
      '/api/v1/jobs/discover',
      {
        method: 'POST',
        body: JSON.stringify(params),
      }
    ),
  searchJobs: (params?: {
    q?: string
    country?: string[]
    admin1?: string[]
    city?: string[]
    work_mode?: string[]
    remote_scope?: string[]
    min_score?: number
    source?: string[]
    sort?: string
    page?: number
    page_size?: number
    candidate_id?: string
  }) => {
    const qp = new URLSearchParams()
    if (params?.q) qp.append('q', params.q)
    if (params?.country) params.country.forEach((c) => qp.append('country', c))
    if (params?.admin1) params.admin1.forEach((a) => qp.append('admin1', a))
    if (params?.city) params.city.forEach((c) => qp.append('city', c))
    if (params?.work_mode) params.work_mode.forEach((w) => qp.append('work_mode', w))
    if (params?.remote_scope) params.remote_scope.forEach((r) => qp.append('remote_scope', r))
    if (params?.min_score !== undefined && params.min_score !== null) qp.append('min_score', String(params.min_score))
    if (params?.source) params.source.forEach((s) => qp.append('source', s))
    if (params?.sort) qp.append('sort', params.sort)
    if (params?.page) qp.append('page', String(params.page))
    if (params?.page_size) qp.append('page_size', String(params.page_size))
    if (params?.candidate_id) qp.append('candidate_id', params.candidate_id)
    return request<JobSearchResponse>(`/api/v1/jobs/search?${qp.toString()}`)
  },
  getLocationFacets: (params?: { country?: string; admin1?: string; q?: string }) => {
    const qp = new URLSearchParams()
    if (params?.country) qp.append('country', params.country)
    if (params?.admin1) qp.append('admin1', params.admin1)
    if (params?.q) qp.append('q', params.q)
    return request<LocationHierarchyResponse>(`/api/v1/jobs/facets/locations?${qp.toString()}`)
  },
  getJobs: (params?: { status?: string; company?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (params?.status) q.append('status', params.status)
    if (params?.company) q.append('company', params.company)
    if (params?.limit) q.append('limit', String(params.limit))
    return request<Job[]>(`/api/v1/jobs?${q.toString()}`)
  },
  getJob: (id: string) => request<Job>(`/api/v1/jobs/${id}`),
  importJob: (data: {
    source: string
    source_url: string
    canonical_url?: string
    portal_key: string
    native_id: string
    company_name: string
    title: string
    raw_description: string
    min_degree?: string
    min_experience_months?: number
    required_skills?: string[]
    preferred_skills?: string[]
    accepted_work_modes?: string[]
    target_locations?: string[]
    work_auth_countries?: string[]
    mandatory_certifications?: string[]
    deadline_at?: string
  }) =>
    request<Job>('/api/v1/jobs/import', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Applications
  getApplications: (params?: { state?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (params?.state) q.append('state', params.state)
    if (params?.limit) q.append('limit', String(params.limit))
    return request<Application[]>(`/api/v1/applications?${q.toString()}`)
  },
  getApplication: (id: string) => request<Application>(`/api/v1/applications/${id}`),
  createApplication: (candidateId: string, jobId: string) =>
    request<{ id: string; state: string; created_at: string }>('/api/v1/applications', {
      method: 'POST',
      body: JSON.stringify({ candidate_id: candidateId, job_id: jobId }),
    }),
  evaluateApplication: (id: string) =>
    request<EvaluationDetails>(`/api/v1/applications/${id}/evaluate`, {
      method: 'POST',
    }),
  generateResume: (id: string) =>
    request<{ status: string; state: string; sha256: string }>(`/api/v1/applications/${id}/generate-resume`, {
      method: 'POST',
    }),
  downloadResumePdf: (id: string, fallbackFilename = 'resume.pdf') =>
    downloadFile(`/api/v1/applications/${id}/resume/pdf`, fallbackFilename),
  downloadResumeDocx: (id: string, fallbackFilename = 'resume.docx') =>
    downloadFile(`/api/v1/applications/${id}/resume/docx`, fallbackFilename),
  runGate: (id: string) =>
    request<{ package_hash: string; outcome: string; results: any[] }>(`/api/v1/applications/${id}/gate`, {
      method: 'POST',
    }),
  approveApplication: (id: string, packageHash: string) =>
    request<{ status: string; approval_id: string; expires_at: string }>(`/api/v1/applications/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ package_hash: packageHash, approved_by: 'user' }),
    }),
  submitApplication: (id: string) =>
    request<{ outcome: string; state: string }>(`/api/v1/applications/${id}/submit`, {
      method: 'POST',
    }),
  resolveUncertain: (id: string, resolution: 'confirmed_with_proof' | 'not_submitted', proofRef?: string) =>
    request<{ state: string; resolution: string }>(`/api/v1/applications/${id}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution, proof_ref: proofRef }),
    }),

  // Settings
  getSettings: () => request<SettingsData>('/api/v1/settings'),
  updateSettings: (data: Partial<SettingsData>) =>
    request<SettingsData>('/api/v1/settings', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
}
