import axios, { AxiosError } from 'axios';
import type {
  ClaimSubmission,
  UploadResponse,
  AnalysisResult,
  HealthResponse,
  StatsResponse,
  SearchQuery,
  SearchResponse,
} from './types';

// Validate API URL in production - throw error to prevent misconfiguration
if (import.meta.env.PROD && !import.meta.env.VITE_API_URL) {
  throw new Error(
    'VITE_API_URL environment variable must be set in production. ' +
    'Please configure your deployment with the correct API URL.'
  );
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
});

// Response interceptor for global error handling
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Log error for monitoring
    console.error('API Error:', {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      message: error.message,
    });

    // Handle specific error types
    if (error.response?.status === 401) {
      // Handle unauthorized - could redirect to login
      console.warn('Unauthorized request');
    }

    if (error.response?.status === 503) {
      // Service unavailable
      console.warn('Service temporarily unavailable');
    }

    if (!error.response) {
      // Network error
      console.error('Network error - check backend connectivity');
    }

    return Promise.reject(error);
  }
);

// Request interceptor for adding auth headers if needed
api.interceptors.request.use(
  (config) => {
    // Add auth token if available (for future auth implementation)
    // const token = getAuthToken();
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => Promise.reject(error)
);

/** Backend error response structure */
interface ApiErrorResponse {
  message?: string;
  detail?: string;
  errors?: Array<{ loc: string[]; msg: string; type: string }>;
}

/**
 * Get user-friendly error message from API error
 * @param error - The error to extract a message from
 * @returns A user-friendly error message string
 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>;

    // Check for backend error message
    const data = axiosError.response?.data;

    // Handle FastAPI validation errors
    if (data?.errors && Array.isArray(data.errors)) {
      const errorMessages = data.errors.map(e => `${e.loc.join('.')}: ${e.msg}`);
      return errorMessages.join('; ');
    }

    const backendMessage = data?.message || data?.detail;

    switch (axiosError.response?.status) {
      case 400:
        return backendMessage || 'Invalid request. Please check your input.';
      case 401:
        return 'Authentication required. Please log in.';
      case 403:
        return 'You do not have permission to perform this action.';
      case 404:
        return 'The requested resource was not found.';
      case 422:
        return backendMessage || 'Invalid data format. Please check your input.';
      case 500:
        return 'An error occurred on the server. Please try again later.';
      case 503:
        return 'Service temporarily unavailable. Please try again later.';
      default:
        if (!axiosError.response) {
          return 'Unable to connect to the server. Please check your connection.';
        }
        return 'An unexpected error occurred. Please try again.';
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'An unexpected error occurred.';
}

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
