import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';

// Types
export interface Connector {
  id: string;
  name: string;
  connector_type: 'database' | 'api' | 'file';
  subtype: string;
  data_type: 'claims' | 'eligibility' | 'providers' | 'reference';
  connection_config: Record<string, unknown>;
  sync_schedule: string | null;
  sync_mode: 'full' | 'incremental';
  batch_size: number;
  field_mapping_id: string | null;
  status: 'active' | 'inactive' | 'error' | 'testing';
  last_sync_at: string | null;
  last_sync_status: string | null;
  created_at: string;
  created_by: string | null;
}

export interface ConnectorType {
  type: string;
  subtypes: Array<{
    subtype: string;
    name: string;
    description: string;
  }>;
}

export interface SyncJob {
  id: string;
  connector_id: string;
  connector_name: string | null;
  job_type: 'scheduled' | 'manual';
  sync_mode: 'full' | 'incremental';
  status: 'pending' | 'running' | 'success' | 'failed' | 'cancelled';
  started_at: string | null;
  completed_at: string | null;
  total_records: number;
  processed_records: number;
  failed_records: number;
  watermark_value: string | null;
  error_message: string | null;
  triggered_by: string | null;
}

export interface SyncJobLog {
  id: string;
  timestamp: string;
  level: string;
  message: string;
  context: Record<string, unknown>;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  latency_ms: number | null;
  details: Record<string, unknown>;
}

// API hooks

export function useConnectorTypes() {
  return useQuery({
    queryKey: ['connectors', 'types'],
    queryFn: async () => {
      const response = await api.get<{
        types: ConnectorType[];
        data_types: string[];
      }>('/api/connectors/types');
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - types rarely change
  });
}

export function useConnectors(params?: {
  connector_type?: string;
  status?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ['connectors', 'list', params],
    queryFn: async () => {
      const response = await api.get<{
        connectors: Connector[];
        total: number;
        limit: number;
        offset: number;
      }>('/api/connectors', { params });
      return response.data;
    },
    staleTime: 30000, // 30 seconds
  });
}

export function useConnector(connectorId: string | undefined) {
  return useQuery({
    queryKey: ['connectors', 'detail', connectorId],
    queryFn: async () => {
      const response = await api.get<Connector>(`/api/connectors/${connectorId}`);
      return response.data;
    },
    enabled: !!connectorId,
  });
}

export function useCreateConnector() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      name: string;
      connector_type: string;
      subtype: string;
      data_type: string;
      connection_config: Record<string, unknown>;
      sync_schedule?: string;
      sync_mode?: string;
      batch_size?: number;
      field_mapping_id?: string;
      created_by?: string;
    }) => {
      const response = await api.post<Connector>('/api/connectors', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });
}

export function useUpdateConnector() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      connectorId,
      ...data
    }: {
      connectorId: string;
      name?: string;
      connection_config?: Record<string, unknown>;
      sync_schedule?: string;
      sync_mode?: string;
      batch_size?: number;
      field_mapping_id?: string;
    }) => {
      const response = await api.put(`/api/connectors/${connectorId}`, data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
      queryClient.invalidateQueries({
        queryKey: ['connectors', 'detail', variables.connectorId],
      });
    },
  });
}

export function useDeleteConnector() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (connectorId: string) => {
      const response = await api.delete(`/api/connectors/${connectorId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: async (connectorId: string) => {
      const response = await api.post<ConnectionTestResult>(
        `/api/connectors/${connectorId}/test`
      );
      return response.data;
    },
  });
}

export function useActivateConnector() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (connectorId: string) => {
      const response = await api.post(`/api/connectors/${connectorId}/activate`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });
}

export function useDeactivateConnector() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (connectorId: string) => {
      const response = await api.post(`/api/connectors/${connectorId}/deactivate`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });
}

export function useTriggerSync() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      connectorId,
      syncMode,
      triggeredBy,
    }: {
      connectorId: string;
      syncMode?: string;
      triggeredBy?: string;
    }) => {
      const response = await api.post<SyncJob>(`/api/connectors/${connectorId}/sync`, null, {
        params: { sync_mode: syncMode, triggered_by: triggeredBy },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sync-jobs'] });
    },
  });
}

// Sync Job hooks

export function useSyncJobs(params?: {
  connector_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ['sync-jobs', 'list', params],
    queryFn: async () => {
      const response = await api.get<{
        jobs: SyncJob[];
        total: number;
        limit: number;
        offset: number;
      }>('/api/sync-jobs', { params });
      return response.data;
    },
    staleTime: 10000, // 10 seconds - jobs update frequently
    refetchInterval: 30000, // Refetch every 30 seconds for running jobs
  });
}

export function useSyncJob(jobId: string | undefined) {
  return useQuery({
    queryKey: ['sync-jobs', 'detail', jobId],
    queryFn: async () => {
      const response = await api.get<SyncJob>(`/api/sync-jobs/${jobId}`);
      return response.data;
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      // Poll every 5 seconds while job is running
      const status = query.state.data?.status;
      return status === 'running' || status === 'pending' ? 5000 : false;
    },
  });
}

export function useCancelSyncJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (jobId: string) => {
      const response = await api.post(`/api/sync-jobs/${jobId}/cancel`);
      return response.data;
    },
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries({ queryKey: ['sync-jobs'] });
      queryClient.invalidateQueries({ queryKey: ['sync-jobs', 'detail', jobId] });
    },
  });
}

export function useSyncJobLogs(
  jobId: string | undefined,
  params?: { limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ['sync-jobs', 'logs', jobId, params],
    queryFn: async () => {
      const response = await api.get<{
        job_id: string;
        logs: SyncJobLog[];
        total: number;
      }>(`/api/sync-jobs/${jobId}/logs`, { params });
      return response.data;
    },
    enabled: !!jobId,
  });
}

// Schema discovery

export interface SchemaDiscoveryResult {
  connector_id: string;
  connector_name: string;
  tables: string[];
  columns: Record<string, Array<{ name: string; type: string; nullable?: boolean }>>;
  sample_data: Record<string, Array<Record<string, unknown>>>;
}

export function useDiscoverSchema(connectorId: string | undefined) {
  return useQuery({
    queryKey: ['connectors', 'schema', connectorId],
    queryFn: async () => {
      const response = await api.get<SchemaDiscoveryResult>(
        `/api/connectors/${connectorId}/schema`
      );
      return response.data;
    },
    enabled: false, // Manual trigger only
    retry: false,
  });
}
