import { useState } from 'react';
import { motion } from 'framer-motion';
import type { Connector } from '../../api/hooks/useConnectors';
import {
  useTestConnection,
  useActivateConnector,
  useDeactivateConnector,
  useDeleteConnector,
  useTriggerSync,
} from '../../api/hooks/useConnectors';

interface ConnectorCardProps {
  connector: Connector;
  onEdit?: (connector: Connector) => void;
}

const CONNECTOR_ICONS: Record<string, string> = {
  database: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4',
  api: 'M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  file: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z',
};

const STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  active: { bg: 'bg-green-100', text: 'text-green-800', dot: 'bg-green-500' },
  inactive: { bg: 'bg-gray-100', text: 'text-gray-800', dot: 'bg-gray-500' },
  error: { bg: 'bg-red-100', text: 'text-red-800', dot: 'bg-red-500' },
  testing: { bg: 'bg-yellow-100', text: 'text-yellow-800', dot: 'bg-yellow-500' },
};

const DATA_TYPE_COLORS: Record<string, string> = {
  claims: 'bg-blue-100 text-blue-800',
  eligibility: 'bg-purple-100 text-purple-800',
  providers: 'bg-teal-100 text-teal-800',
  reference: 'bg-orange-100 text-orange-800',
};

export function ConnectorCard({ connector, onEdit }: ConnectorCardProps) {
  const [showActions, setShowActions] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const testConnection = useTestConnection();
  const activateConnector = useActivateConnector();
  const deactivateConnector = useDeactivateConnector();
  const deleteConnector = useDeleteConnector();
  const triggerSync = useTriggerSync();

  const statusColors = STATUS_COLORS[connector.status] || STATUS_COLORS.inactive;
  const dataTypeColor = DATA_TYPE_COLORS[connector.data_type] || 'bg-gray-100 text-gray-800';
  const iconPath = CONNECTOR_ICONS[connector.connector_type] || CONNECTOR_ICONS.database;

  const handleTest = async () => {
    setTestResult(null);
    try {
      const result = await testConnection.mutateAsync(connector.id);
      setTestResult({ success: result.success, message: result.message });
    } catch {
      setTestResult({ success: false, message: 'Connection test failed' });
    }
  };

  const handleToggleStatus = async () => {
    if (connector.status === 'active') {
      await deactivateConnector.mutateAsync(connector.id);
    } else {
      await activateConnector.mutateAsync(connector.id);
    }
  };

  const handleDelete = async () => {
    if (window.confirm(`Are you sure you want to delete "${connector.name}"?`)) {
      await deleteConnector.mutateAsync(connector.id);
    }
  };

  const handleSync = async () => {
    await triggerSync.mutateAsync({ connectorId: connector.id });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 rounded-lg">
              <svg
                className="w-6 h-6 text-indigo-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d={iconPath}
                />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{connector.name}</h3>
              <p className="text-sm text-gray-500 capitalize">
                {connector.subtype.replace(/_/g, ' ')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors.bg} ${statusColors.text}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${statusColors.dot} mr-1.5`} />
              {connector.status}
            </span>
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">Data Type</span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${dataTypeColor}`}>
            {connector.data_type}
          </span>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">Sync Mode</span>
          <span className="text-gray-900 capitalize">{connector.sync_mode}</span>
        </div>

        {connector.sync_schedule && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Schedule</span>
            <span className="text-gray-900 font-mono text-xs">{connector.sync_schedule}</span>
          </div>
        )}

        {connector.last_sync_at && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">Last Sync</span>
            <span className="text-gray-900">
              {new Date(connector.last_sync_at).toLocaleString()}
            </span>
          </div>
        )}

        {/* Test Result */}
        {testResult && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className={`p-2 rounded-md text-sm ${
              testResult.success
                ? 'bg-green-50 text-green-700'
                : 'bg-red-50 text-red-700'
            }`}
          >
            {testResult.message}
          </motion.div>
        )}
      </div>

      {/* Actions */}
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: showActions ? 1 : 0, height: showActions ? 'auto' : 0 }}
        className="border-t border-gray-100 bg-gray-50"
      >
        <div className="p-3 flex items-center gap-2">
          <button
            onClick={handleTest}
            disabled={testConnection.isPending}
            className="flex-1 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            {testConnection.isPending ? 'Testing...' : 'Test'}
          </button>

          <button
            onClick={handleSync}
            disabled={triggerSync.isPending || connector.status !== 'active'}
            className="flex-1 px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {triggerSync.isPending ? 'Starting...' : 'Sync Now'}
          </button>

          <button
            onClick={() => onEdit?.(connector)}
            className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-md"
            title="Edit"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>

          <button
            onClick={handleToggleStatus}
            disabled={activateConnector.isPending || deactivateConnector.isPending}
            className={`p-1.5 rounded-md ${
              connector.status === 'active'
                ? 'text-yellow-600 hover:bg-yellow-50'
                : 'text-green-600 hover:bg-green-50'
            }`}
            title={connector.status === 'active' ? 'Deactivate' : 'Activate'}
          >
            {connector.status === 'active' ? (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
          </button>

          <button
            onClick={handleDelete}
            disabled={deleteConnector.isPending}
            className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-md"
            title="Delete"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default ConnectorCard;
