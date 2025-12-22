import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';

export interface MappingCandidate {
  field: string;
  score: number;
}

export interface MappingReviewItem {
  source_field: string;
  status: string;
  best_match: {
    target_field: string;
    confidence: number;
    reasoning: string;
    needs_review: boolean;
  } | null;
  embedding_candidates?: MappingCandidate[];
}

export interface SmartMappingResponse {
  results: MappingReviewItem[];
  high_confidence: MappingReviewItem[];
  needs_review: MappingReviewItem[];
}

export interface RerankResponse {
  source_field: string;
  best_match: {
    target_field: string;
    confidence: number;
    reasoning: string;
    needs_review: boolean;
  };
  all_rankings: Array<{
    target_field: string;
    confidence: number;
    reasoning: string;
  }>;
}

export function useSmartMapping() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (fields: string[]) => {
      const response = await api.post<SmartMappingResponse>('/api/mappings/smart', {
        source_fields: fields,
        top_k: 5,
        min_similarity: 0.3,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mappings'] });
    },
  });
}

export function useRerank() {
  return useMutation({
    mutationFn: async (data: {
      source_field: string;
      candidates: { field: string; score: number }[];
      sample_values?: string[];
    }) => {
      const response = await api.post<RerankResponse>('/api/mappings/rerank', data);
      return response.data;
    },
  });
}

export interface StoredMapping {
  id: string;
  source_schema_id: string;
  source_schema_version: number;
  target_schema: string;
  field_mappings: Array<{
    source_field: string;
    target_field: string;
    confidence: number;
    method: string;
    reasoning?: string;
  }>;
  status: 'pending' | 'approved' | 'rejected' | 'archived';
  created_at: string;
  created_by?: string;
  approved_at?: string;
  approved_by?: string;
}

export function useMappingQueue(status: 'pending' | 'approved' | 'rejected' | 'archived' = 'pending') {
  return useQuery<StoredMapping[]>({
    queryKey: ['mappings', 'stored', status],
    queryFn: async () => {
      const response = await api.get<{ mappings: StoredMapping[] }>('/api/mappings/stored', {
        params: { status, limit: 50 },
      });
      return response.data.mappings;
    },
    staleTime: 30000,
  });
}

export interface SaveMappingRequest {
  source_schema_id: string;
  field_mappings: Array<{
    source_field: string;
    target_field: string;
    confidence: number;
    method: string;
    reasoning?: string;
  }>;
  created_by?: string;
}

export function useSaveMapping() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: SaveMappingRequest) => {
      const response = await api.post<StoredMapping>('/api/mappings/save', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mappings', 'stored'] });
    },
  });
}

export function useApproveMapping() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ mappingId, approvedBy }: { mappingId: string; approvedBy: string }) => {
      const response = await api.post<StoredMapping>(`/api/mappings/stored/${mappingId}/approve`, {
        approved_by: approvedBy,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mappings', 'stored'] });
    },
  });
}

export function useRejectMapping() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ mappingId, rejectedBy, reason }: { mappingId: string; rejectedBy: string; reason?: string }) => {
      const response = await api.post<StoredMapping>(`/api/mappings/stored/${mappingId}/reject`, {
        rejected_by: rejectedBy,
        reason,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mappings', 'stored'] });
    },
  });
}
