import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../client';

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30000, // Refetch every 30 seconds
    staleTime: 10000,
  });
}
