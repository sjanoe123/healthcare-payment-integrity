import { useQuery } from '@tanstack/react-query';
import { getJobs } from '../client';
import type { JobsResponse } from '../types';

export function useJobs() {
  return useQuery<JobsResponse>({
    queryKey: ['jobs'],
    queryFn: getJobs,
    staleTime: 30000,
    refetchInterval: 60000,
  });
}
