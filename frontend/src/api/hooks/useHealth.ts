import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../client';

const REFETCH_INTERVAL_MS = 30000; // Refetch every 30 seconds
const STALE_TIME_MS = 10000; // Consider stale after 10 seconds

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: REFETCH_INTERVAL_MS,
    refetchIntervalInBackground: false, // Stop polling when tab is inactive
    staleTime: STALE_TIME_MS,
  });
}
