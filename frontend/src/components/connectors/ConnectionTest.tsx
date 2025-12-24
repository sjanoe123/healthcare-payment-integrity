import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTestConnection, useDiscoverSchema, type Connector } from '../../api/hooks/useConnectors';

interface ConnectionTestProps {
  connector: Connector;
  onClose: () => void;
}

export function ConnectionTest({ connector, onClose }: ConnectionTestProps) {
  const testConnection = useTestConnection();
  const discoverSchema = useDiscoverSchema(connector.id);

  useEffect(() => {
    // Auto-run test on mount
    testConnection.mutate(connector.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connector.id]);

  const handleDiscoverSchema = () => {
    discoverSchema.refetch();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Connection Test</h2>
            <p className="text-sm text-gray-500">{connector.name}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {/* Test Status */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Connection Status</h3>

            {testConnection.isPending ? (
              <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600"></div>
                <span className="text-gray-600">Testing connection...</span>
              </div>
            ) : testConnection.isError ? (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-center gap-2 text-red-700">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="font-medium">Connection Failed</span>
                </div>
                <p className="mt-2 text-sm text-red-600">
                  {testConnection.error instanceof Error ? testConnection.error.message : 'Unknown error'}
                </p>
              </div>
            ) : testConnection.data ? (
              <div className={`p-4 rounded-lg ${
                testConnection.data.success
                  ? 'bg-green-50 border border-green-200'
                  : 'bg-red-50 border border-red-200'
              }`}>
                <div className={`flex items-center gap-2 ${
                  testConnection.data.success ? 'text-green-700' : 'text-red-700'
                }`}>
                  {testConnection.data.success ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  )}
                  <span className="font-medium">
                    {testConnection.data.success ? 'Connection Successful' : 'Connection Failed'}
                  </span>
                </div>
                <p className={`mt-2 text-sm ${
                  testConnection.data.success ? 'text-green-600' : 'text-red-600'
                }`}>
                  {testConnection.data.message}
                </p>
                {testConnection.data.latency_ms && (
                  <p className="mt-1 text-xs text-gray-500">
                    Latency: {testConnection.data.latency_ms}ms
                  </p>
                )}

                {/* Details */}
                {testConnection.data.details && Object.keys(testConnection.data.details).length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-xs font-medium text-gray-500 mb-2">Details:</p>
                    <dl className="text-xs space-y-1">
                      {Object.entries(testConnection.data.details).map(([key, value]) => (
                        <div key={key} className="flex">
                          <dt className="text-gray-500 w-32">{key}:</dt>
                          <dd className="text-gray-700">
                            {Array.isArray(value) ? value.join(', ') : String(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
              </div>
            ) : null}
          </div>

          {/* Schema Discovery */}
          {connector.connector_type === 'database' && testConnection.data?.success && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-700">Schema Discovery</h3>
                <button
                  onClick={handleDiscoverSchema}
                  disabled={discoverSchema.isFetching}
                  className="text-sm text-indigo-600 hover:text-indigo-700 font-medium disabled:opacity-50"
                >
                  {discoverSchema.isFetching ? 'Discovering...' : 'Discover Schema'}
                </button>
              </div>

              <AnimatePresence>
                {discoverSchema.isFetching && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg"
                  >
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
                    <span className="text-gray-600 text-sm">Discovering database schema...</span>
                  </motion.div>
                )}

                {discoverSchema.data && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="border border-gray-200 rounded-lg overflow-hidden"
                  >
                    <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
                      <span className="text-sm font-medium text-gray-700">
                        Found {discoverSchema.data.tables.length} tables
                      </span>
                    </div>
                    <div className="max-h-48 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 sticky top-0">
                          <tr>
                            <th className="px-4 py-2 text-left text-gray-600">Table</th>
                            <th className="px-4 py-2 text-left text-gray-600">Columns</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {discoverSchema.data.tables.map((table) => (
                            <tr key={table} className="hover:bg-gray-50">
                              <td className="px-4 py-2 font-medium text-gray-900">{table}</td>
                              <td className="px-4 py-2 text-gray-600">
                                {discoverSchema.data?.columns[table]?.length || 0} columns
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
          <button
            onClick={() => testConnection.mutate(connector.id)}
            disabled={testConnection.isPending}
            className="px-4 py-2 text-indigo-600 hover:text-indigo-700 font-medium disabled:opacity-50"
          >
            {testConnection.isPending ? 'Testing...' : 'Retest'}
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
          >
            Close
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default ConnectionTest;
