import { useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadAndAnalyze } from '../client';
import type { ClaimSubmission, AnalysisResult } from '../types';

export function useAnalyzeClaim() {
  const queryClient = useQueryClient();

  return useMutation<AnalysisResult, Error, ClaimSubmission>({
    mutationFn: uploadAndAnalyze,
    onSuccess: () => {
      // Invalidate stats to refresh counts
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
}
