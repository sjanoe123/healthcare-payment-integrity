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
        className="bg-navy-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-navy-700/50 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">Connection Test</h2>
            <p className="text-sm text-navy-400">{connector.name}</p>
          </div>
          <button onClick={onClose} className="text-navy-400 hover:text-white">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {/* Test Status */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-navy-300 mb-3">Connection Status</h3>

            {testConnection.isPending ? (
              <div className="flex items-center gap-3 p-4 bg-navy-900/50 rounded-lg">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-kirk"></div>
                <span className="text-navy-300">Testing connection...</span>
              </div>
            ) : testConnection.isError ? (
              <div className="p-4 bg-risk-critical/10 border border-risk-critical/30 rounded-lg">
                <div className="flex items-center gap-2 text-risk-critical">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="font-medium">Connection Failed</span>
                </div>
                <p className="mt-2 text-sm text-risk-critical">
                  {testConnection.error instanceof Error ? testConnection.error.message : 'Unknown error'}
                </p>
              </div>
            ) : testConnection.data ? (
              <div className={`p-4 rounded-lg ${
                testConnection.data.success
                  ? 'bg-risk-safe/10 border border-risk-safe/30'
                  : 'bg-risk-critical/10 border border-risk-critical/30'
              }`}>
                <div className={`flex items-center gap-2 ${
                  testConnection.data.success ? 'text-risk-safe' : 'text-risk-critical'
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
                  testConnection.data.success ? 'text-risk-safe' : 'text-risk-critical'
                }`}>
                  {testConnection.data.message}
                </p>
                {testConnection.data.latency_ms && (
                  <p className="mt-1 text-xs text-navy-500">
                    Latency: {testConnection.data.latency_ms}ms
                  </p>
                )}

                {/* Details */}
                {testConnection.data.details && Object.keys(testConnection.data.details).length > 0 && (
                  <div className="mt-3 pt-3 border-t border-navy-700/50">
                    <p className="text-xs font-medium text-navy-500 mb-2">Details:</p>
                    <dl className="text-xs space-y-1">
                      {Object.entries(testConnection.data.details).map(([key, value]) => (
                        <div key={key} className="flex">
                          <dt className="text-navy-500 w-32">{key}:</dt>
                          <dd className="text-navy-300">
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
                <h3 className="text-sm font-medium text-navy-300">Schema Discovery</h3>
                <button
                  onClick={handleDiscoverSchema}
                  disabled={discoverSchema.isFetching}
                  className="text-sm text-kirk hover:text-kirk-light font-medium disabled:opacity-50"
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
                    className="flex items-center gap-3 p-4 bg-navy-900/50 rounded-lg"
                  >
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-kirk"></div>
                    <span className="text-navy-300 text-sm">Discovering database schema...</span>
                  </motion.div>
                )}

                {discoverSchema.data && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="border border-navy-700/50 rounded-lg overflow-hidden"
                  >
                    <div className="bg-navy-900/50 px-4 py-2 border-b border-navy-700/50">
                      <span className="text-sm font-medium text-navy-300">
                        Found {discoverSchema.data.tables.length} tables
                      </span>
                    </div>
                    <div className="max-h-48 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-navy-900/50 sticky top-0">
                          <tr>
                            <th className="px-4 py-2 text-left text-navy-400">Table</th>
                            <th className="px-4 py-2 text-left text-navy-400">Columns</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-navy-700/50">
                          {discoverSchema.data.tables.map((table) => (
                            <tr key={table} className="hover:bg-navy-700/30">
                              <td className="px-4 py-2 font-medium text-white">{table}</td>
                              <td className="px-4 py-2 text-navy-300">
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
        <div className="px-6 py-4 border-t border-navy-700/50 flex items-center justify-between">
          <button
            onClick={() => testConnection.mutate(connector.id)}
            disabled={testConnection.isPending}
            className="px-4 py-2 text-kirk hover:text-kirk-light font-medium disabled:opacity-50"
          >
            {testConnection.isPending ? 'Testing...' : 'Retest'}
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-navy-700 text-navy-300 rounded-lg hover:bg-navy-600"
          >
            Close
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default ConnectionTest;
