import { useQuery } from '@tanstack/react-query';
import { getStats } from '../client';

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 60000, // Refetch every minute
    staleTime: 30000,
  });
}
