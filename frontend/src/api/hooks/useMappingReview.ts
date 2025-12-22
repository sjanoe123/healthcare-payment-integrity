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

export function useMappingQueue() {
  return useQuery<MappingReviewItem[]>({
    queryKey: ['mappings', 'queue'],
    queryFn: async () => {
      // This would fetch from a backend endpoint if available
      // For now, return empty array as placeholder
      return [];
    },
    staleTime: 30000,
  });
}
