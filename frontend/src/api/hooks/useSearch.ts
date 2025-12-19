import { useMutation } from '@tanstack/react-query';
import { searchPolicies } from '../client';
import type { SearchQuery, SearchResponse } from '../types';

export function useSearch() {
  return useMutation<SearchResponse, Error, SearchQuery>({
    mutationFn: searchPolicies,
  });
}
