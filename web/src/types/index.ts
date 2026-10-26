export type ApplicationState =
  | 'DISCOVERED'
  | 'EVALUATING_ELIGIBILITY'
  | 'ELIGIBILITY_CHECKED'
  | 'ELIGIBLE'
  | 'INELIGIBLE'
  | 'SCORING'
  | 'SCORED'
  | 'SHORTLISTED'
  | 'BELOW_THRESHOLD'
  | 'SELECTING_EVIDENCE'
  | 'EVIDENCE_SELECTED'
  | 'PREPARING_PACKAGE'
  | 'PACKAGE_READY'
  | 'RESUME_GENERATED'
  | 'READY_FOR_REVIEW'
  | 'VALIDATING_PACKAGE'
  | 'PACKAGE_VALID'
  | 'APPROVAL_REQUESTED'
  | 'APPROVED'
  | 'APPROVED_PENDING_SUBMISSION'
  | 'REJECTED_BY_USER'
  | 'SUBMITTING'
  | 'SUBMISSION_UNCERTAIN'
  | 'APPLIED_CONFIRMED'
  | 'APPLICATION_FAILED'
  | 'SUBMISSION_FAILED'
  | 'REJECTED'
  | 'PAUSED_AUTH'

export type FactKind = 'EDUCATION' | 'EXPERIENCE' | 'SKILL' | 'CERTIFICATION' | 'WORK_AUTH' | 'CONTACT' | 'PROJECT'
export type FactProvenance = 'USER_SUPPLIED' | 'USER_VERIFIED' | 'EXTRACTED_RESUME' | 'INFERRED'
export type FactStatus = 'ACTIVE' | 'PROPOSED' | 'SUPERSEDED' | 'REJECTED'

export interface Fact {
  id: string
  candidate_id: string
  kind: FactKind
  key: string
  predicate?: string
  value: Record<string, any>
  provenance: FactProvenance
  status: FactStatus
  source_document_id?: string | null
  confidence_score?: number
  verified_at?: string | null
  is_usable?: boolean
  created_at?: string
}

export interface Candidate {
  id: string
  display_name: string
  timezone: string
  is_synthetic?: boolean
  created_at?: string
}

export interface JobRequirements {
  min_degree?: string
  allowed_graduation_years?: number[]
  min_experience_months?: number
  work_auth_countries?: string[]
  mandatory_certifications?: string[]
  required_skills?: string[]
  preferred_skills?: string[]
  responsibilities?: string[]
  accepted_work_modes?: string[]
  target_locations?: string[]
  deadline?: string
}

export interface Job {
  id: string
  source: string
  source_url?: string
  canonical_url?: string
  canonical_job_key?: string
  company_norm?: string
  title_norm?: string
  title?: string
  company?: string
  portal_key?: string
  description_clean?: string
  raw_sha256?: string
  requirements?: JobRequirements
  deadline_at?: string
  status?: string
  created_at?: string
}

export interface GateCheck {
  check_id: number
  name: string
  severity: 'FATAL' | 'BLOCKING' | 'WARN'
  result: 'PASS' | 'FAIL' | 'NEEDS_USER' | 'WAIVED'
  message: string
  details?: Record<string, any>
}

export interface GateReport {
  content_hash: string
  outcome: string
  results: GateCheck[]
  package_hash?: string
  is_pass?: boolean
}

export interface Application {
  id: string
  candidate_id?: string
  job_id?: string
  state?: ApplicationState | string
  current_state?: ApplicationState | string
  version: number
  role_title?: string
  company_name?: string
  candidate_name?: string
  score?: number | null
  job?: {
    id: string
    company_name?: string
    role_title?: string
    canonical_url?: string
    description?: string
    requirements?: any
  }
  candidate?: {
    id: string
    display_name?: string
    timezone?: string
  }
  evaluation?: {
    rules_result: string
    score_total: number
    breakdown: any
  }
  resume?: any
  gate_report?: GateReport
  attempts?: Array<{
    id: string
    outcome: string
    clicked_at?: string | null
    error?: string | null
  }>
  evidence?: Array<{
    level: string
    kind: string
    payload: any
    sha256: string
    created_at: string
  }>
  events?: Array<{
    seq: number
    type: string
    from_state?: string | null
    to_state: string
    actor: string
    reason?: string
    created_at: string
  }>
  package?: {
    package_hash: string
  }
  created_at: string
  updated_at: string
}

export interface MetricsSummary {
  discovered: number
  shortlisted: number
  ready_for_review: number
  prepared: number
  confirmed: number
  uncertain: number
  failed: number
  quota_used_today: number
  confirmation_rate: number
  autonomy_level: string
}

export interface SettingsData {
  suitability_floor: number
  daily_cap_global: number
  daily_cap_per_portal: number
  daily_cap_per_company: number
  timezone: string
  autonomy_level: string
  allow_real_submission: boolean
  submit_host_allowlist: string[]
  min_evidence_level: string
  llm_enabled: boolean
}

export interface MasterResumeStatus {
  has_master_resume: boolean
  document_id?: string
  filename?: string
  sha256?: string
  uploaded_at?: string
  total_facts: number
  active_facts: number
  proposed_facts: number
}

export interface JobSource {
  id: string
  name: string
  status: string
  is_live: boolean
  description: string
  employer_count?: number
  provider?: string
}

export interface DiscoveredJob {
  id: string
  source: string
  source_url: string
  canonical_url: string
  company_name: string
  title: string
  location: string
  description: string
  required_skills: string[]
  match_score?: number
  rules_result?: string
  rules_reason?: string
  matched_skills: string[]
  missing_skills: string[]
}

export interface DiagnosticsData {
  status: string
  api_alive: boolean
  worker_heartbeat: string
  database: string
  submit_host_allowlist: string[]
  queue_depth: number
}

export interface User {
  id: string
  email: string
  display_name: string
  is_verified: boolean
  is_active: boolean
  role: string
  created_at: string
}
