import { useQuery } from '@tanstack/react-query';
import { getStats } from '../client';

const REFETCH_INTERVAL_MS = 60000; // Refetch every minute
const STALE_TIME_MS = 30000; // Consider stale after 30 seconds

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: REFETCH_INTERVAL_MS,
    refetchIntervalInBackground: false, // Stop polling when tab is inactive
    staleTime: STALE_TIME_MS,
  });
}
