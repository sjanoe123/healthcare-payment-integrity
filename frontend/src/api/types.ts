// Claim submission types
export interface ClaimItem {
  procedure_code: string;
  diagnosis_code?: string;
  quantity: number;
  line_amount: number;
  modifier?: string;
}

export interface ClaimSubmission {
  claim_id: string;
  patient_id?: string;
  provider_npi?: string;
  date_of_service?: string;
  claim_type?: 'professional' | 'institutional';
  billed_amount?: number;
  total_amount?: number;
  diagnosis_codes?: string[];
  items: ClaimItem[];
  provider?: {
    npi: string;
    specialty?: string;
  };
  member?: {
    age: number;
    gender: 'M' | 'F';
  };
}

// Rule hit types
export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type RuleType = 'ncci' | 'coverage' | 'provider' | 'financial' | 'modifier';

export interface RuleHit {
  rule_id: string;
  rule_type: RuleType;
  description: string;
  weight: number;
  severity: Severity;
  flag: string;
  affected_codes?: string[];
  citation?: string;
  metadata?: Record<string, unknown>;
}

// Kirk structured JSON response types (matches kirk_config.py format)
export type KirkSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type KirkCategory = 'ncci' | 'coverage' | 'provider' | 'financial' | 'format' | 'modifier' | 'eligibility';

export interface KirkFinding {
  category: KirkCategory;
  issue: string;
  evidence: string;
  regulation: string;
  severity: KirkSeverity;
}

export interface KirkRecommendation {
  priority: number;
  action: string;
  rationale: string;
}

export interface KirkStructuredResponse {
  risk_summary: string;
  severity: KirkSeverity;
  chain_of_thought: string;
  findings: KirkFinding[];
  recommendations: KirkRecommendation[];
  confidence: number;
}

// Claude/Kirk analysis types
export interface ClaudeAnalysis {
  summary?: string;
  explanation: string;
  risk_factors: string[];
  recommendations: string[];
  model: string;
  tokens_used: number;
  agent: 'Kirk';
  // Optional structured response when JSON parsing succeeds
  structured_response?: KirkStructuredResponse;
}

// Decision modes
export type DecisionMode =
  | 'informational'
  | 'recommendation'
  | 'soft_hold'
  | 'auto_approve'
  | 'auto_approve_fast';

// Analysis result
export interface AnalysisResult {
  job_id: string;
  claim_id: string;
  fraud_score: number;
  decision_mode: DecisionMode;
  rule_hits: RuleHit[];
  ncci_flags: string[];
  coverage_flags: string[];
  provider_flags: string[];
  roi_estimate: number | null;
  claude_analysis: ClaudeAnalysis;
}

// Upload response
export interface UploadResponse {
  job_id: string;
  claim_id: string;
  status: 'pending';
  message: string;
}

// Health check response
export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  rag_documents: number;
  ncci_rules?: number;
  uptime?: string;
}

// Stats response
export interface StatsResponse {
  total_jobs: number;
  completed_jobs: number;
  avg_fraud_score: number;
  rag_documents: number;
  claims_analyzed?: number;
  flags_detected?: number;
  auto_approved?: number;
  potential_savings?: number;
}

// Job summary for listing
export interface JobSummary {
  job_id: string;
  claim_id: string;
  fraud_score: number;
  decision_mode: DecisionMode;
  rule_hits: RuleHit[];
  ncci_flags: string[];
  coverage_flags: string[];
  provider_flags: string[];
  roi_estimate: number | null;
  created_at: string;
  status: string;
  flags_count: number;
}

export interface JobsResponse {
  jobs: JobSummary[];
  total: number;
}

// Search types
export interface SearchQuery {
  query: string;
  n_results?: number;
  top_k?: number;
}

export interface SearchResult {
  content: string;
  source?: string;
  score?: number;
  metadata: {
    source?: string;
    chapter?: string;
    section?: string;
    url?: string;
  };
  distance: number;
  id: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total_documents: number;
}

// Utility types
export type RiskLevel = 'safe' | 'caution' | 'alert' | 'critical';

export function getRiskLevel(score: number): RiskLevel {
  if (score < 0.6) return 'safe';
  if (score < 0.8) return 'caution';
  if (score < 0.9) return 'alert';
  return 'critical';
}

export function getRiskColor(score: number): string {
  const level = getRiskLevel(score);
  const colors = {
    safe: '#10B981',
    caution: '#F59E0B',
    alert: '#F97316',
    critical: '#EF4444',
  };
  return colors[level];
}

export function getSeverityColor(severity: Severity): string {
  const colors = {
    low: '#10B981',
    medium: '#F59E0B',
    high: '#F97316',
    critical: '#EF4444',
  };
  return colors[severity];
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

export function formatScore(score: number): string {
  return (score * 100).toFixed(0) + '%';
}

// Kirk structured response utilities
export function parseKirkResponse(explanation: string): KirkStructuredResponse | null {
  try {
    // Try to extract JSON from the explanation
    const jsonMatch = explanation.match(/\{[\s\S]*\}/);
    if (!jsonMatch) return null;

    const parsed = JSON.parse(jsonMatch[0]) as KirkStructuredResponse;

    // Validate required fields
    if (
      typeof parsed.risk_summary !== 'string' ||
      !['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(parsed.severity) ||
      !Array.isArray(parsed.findings) ||
      !Array.isArray(parsed.recommendations) ||
      typeof parsed.confidence !== 'number'
    ) {
      return null;
    }

    return parsed;
  } catch {
    return null;
  }
}

export function getKirkSeverityColor(severity: KirkSeverity): string {
  const colors: Record<KirkSeverity, string> = {
    CRITICAL: '#EF4444',
    HIGH: '#F97316',
    MEDIUM: '#F59E0B',
    LOW: '#10B981',
  };
  return colors[severity];
}

export function getKirkCategoryLabel(category: KirkCategory): string {
  const labels: Record<KirkCategory, string> = {
    ncci: 'NCCI Edits',
    coverage: 'Coverage',
    provider: 'Provider',
    financial: 'Financial',
    format: 'Format',
    modifier: 'Modifier',
    eligibility: 'Eligibility',
  };
  return labels[category];
}
