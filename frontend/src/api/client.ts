import axios from 'axios';
import type {
  ClaimSubmission,
  UploadResponse,
  AnalysisResult,
  HealthResponse,
  StatsResponse,
  SearchQuery,
  SearchResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health check
export async function getHealth(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>('/health');
  return response.data;
}

// Upload claim
export async function uploadClaim(claim: ClaimSubmission): Promise<UploadResponse> {
  const response = await api.post<UploadResponse>('/api/upload', claim);
  return response.data;
}

// Analyze claim
export async function analyzeClaim(
  jobId: string,
  claim: ClaimSubmission
): Promise<AnalysisResult> {
  const response = await api.post<AnalysisResult>(`/api/analyze/${jobId}`, claim);
  return response.data;
}

// Get results
export async function getResults(jobId: string): Promise<AnalysisResult> {
  const response = await api.get<AnalysisResult>(`/api/results/${jobId}`);
  return response.data;
}

// Search policies
export async function searchPolicies(query: SearchQuery): Promise<SearchResponse> {
  const response = await api.post<SearchResponse>('/api/search', query);
  return response.data;
}

// Get stats
export async function getStats(): Promise<StatsResponse> {
  const response = await api.get<StatsResponse>('/api/stats');
  return response.data;
}

// Combined upload and analyze
export async function uploadAndAnalyze(claim: ClaimSubmission): Promise<AnalysisResult> {
  const uploadResponse = await uploadClaim(claim);
  const analysisResult = await analyzeClaim(uploadResponse.job_id, claim);
  return analysisResult;
}
