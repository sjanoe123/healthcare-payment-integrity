import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useConnectors, useSyncJobs } from '../api/hooks/useConnectors';
import { ConnectorCard } from '../components/connectors/ConnectorCard';
import { ConnectionTest } from '../components/connectors/ConnectionTest';
import type { Connector } from '../api/hooks/useConnectors';
import { api } from '../api/client';

type FilterType = 'all' | 'database' | 'api' | 'file';
type StatusFilter = 'all' | 'active' | 'inactive' | 'error';

interface ImportResult {
  status: string;
  message: string;
  connectors?: { name: string; type: string; subtype: string; data_type: string }[];
  results?: {
    created: { name: string; id: string }[];
    updated: { name: string; id: string }[];
    skipped: { name: string; reason: string }[];
    errors: { name: string; error: string }[];
  };
}

export function DataSources() {
  const navigate = useNavigate();
  const [typeFilter, setTypeFilter] = useState<FilterType>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [testingConnector, setTestingConnector] = useState<Connector | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [exporting, setExporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: connectorsData, isLoading: loadingConnectors, refetch } = useConnectors({
    connector_type: typeFilter === 'all' ? undefined : typeFilter,
    status: statusFilter === 'all' ? undefined : statusFilter,
  });

  const { data: jobsData } = useSyncJobs({ limit: 5 });

  const connectors = connectorsData?.connectors || [];
  const recentJobs = jobsData?.jobs || [];

  const handleEdit = (connector: Connector) => {
    navigate(`/connectors/${connector.id}/edit`);
  };

  const handleAddConnector = () => {
    navigate('/connectors/new');
  };

  const handleExport = async (format: 'yaml' | 'json') => {
    setExporting(true);
    try {
      const response = await api.post(
        `/api/connectors/config/export?format=${format}`,
        {},
        { responseType: 'blob' }
      );

      // Create download link
      const blob = new Blob([response.data], {
        type: format === 'yaml' ? 'application/x-yaml' : 'application/json'
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `connectors.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  const handleImportFile = async (file: File, dryRun: boolean) => {
    setImporting(true);
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post(
        `/api/connectors/config/import?dry_run=${dryRun}&overwrite=false`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      setImportResult(response.data);

      if (!dryRun) {
        refetch();
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string | { message: string } } } };
      const detail = err.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message || 'Import failed';
      setImportResult({
        status: 'error',
        message: message,
      });
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Data Sources</h1>
          <p className="text-gray-500 mt-1">
            Configure and manage data source connections for claim processing
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Export Dropdown */}
          {connectors.length > 0 && (
            <div className="relative group">
              <button
                disabled={exporting}
                className="inline-flex items-center px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                {exporting ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600 mr-2"></div>
                ) : (
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                )}
                Export
                <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              <div className="absolute right-0 mt-1 w-32 bg-white rounded-md shadow-lg border border-gray-200 hidden group-hover:block z-10">
                <button
                  onClick={() => handleExport('yaml')}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                >
                  Export YAML
                </button>
                <button
                  onClick={() => handleExport('json')}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                >
                  Export JSON
                </button>
              </div>
            </div>
          )}

          {/* Import Button */}
          <button
            onClick={() => setShowImportModal(true)}
            className="inline-flex items-center px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Import
          </button>

          {/* Add Connector Button */}
          <button
            onClick={handleAddConnector}
            className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Connector
          </button>
        </div>
      </div>

      {/* Hidden file input for import */}
      <input
        type="file"
        ref={fileInputRef}
        accept=".yaml,.yml,.json"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            handleImportFile(file, true);
          }
        }}
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Connectors</p>
              <p className="text-2xl font-bold text-gray-900">{connectors.length}</p>
            </div>
            <div className="p-3 bg-indigo-100 rounded-full">
              <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Active</p>
              <p className="text-2xl font-bold text-green-600">
                {connectors.filter(c => c.status === 'active').length}
              </p>
            </div>
            <div className="p-3 bg-green-100 rounded-full">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">With Errors</p>
              <p className="text-2xl font-bold text-red-600">
                {connectors.filter(c => c.status === 'error').length}
              </p>
            </div>
            <div className="p-3 bg-red-100 rounded-full">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Recent Jobs</p>
              <p className="text-2xl font-bold text-gray-900">{recentJobs.length}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-full">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as FilterType)}
              className="block w-40 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
            >
              <option value="all">All Types</option>
              <option value="database">Database</option>
              <option value="api">API</option>
              <option value="file">File</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              className="block w-40 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="error">Error</option>
            </select>
          </div>
        </div>
      </div>

      {/* Connectors Grid */}
      {loadingConnectors ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
        </div>
      ) : connectors.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center"
        >
          <div className="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Connectors Found</h3>
          <p className="text-gray-500 mb-4">
            {typeFilter !== 'all' || statusFilter !== 'all'
              ? 'No connectors match your current filters.'
              : 'Get started by adding your first data source connector.'}
          </p>
          <button
            onClick={handleAddConnector}
            className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Your First Connector
          </button>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <AnimatePresence>
            {connectors.map((connector) => (
              <ConnectorCard
                key={connector.id}
                connector={connector}
                onEdit={handleEdit}
              />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Recent Sync Jobs */}
      {recentJobs.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recent Sync Jobs</h2>
          </div>
          <div className="divide-y divide-gray-200">
            {recentJobs.map((job) => (
              <div key={job.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    job.status === 'success' ? 'bg-green-500' :
                    job.status === 'failed' ? 'bg-red-500' :
                    job.status === 'running' ? 'bg-blue-500 animate-pulse' :
                    'bg-gray-400'
                  }`} />
                  <div>
                    <p className="font-medium text-gray-900">{job.connector_name || 'Unknown'}</p>
                    <p className="text-sm text-gray-500">
                      {job.sync_mode} sync - {job.processed_records} records
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                    job.status === 'success' ? 'bg-green-100 text-green-800' :
                    job.status === 'failed' ? 'bg-red-100 text-red-800' :
                    job.status === 'running' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {job.status}
                  </span>
                  {job.started_at && (
                    <p className="text-xs text-gray-500 mt-1">
                      {new Date(job.started_at).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Connection Test Modal */}
      <AnimatePresence>
        {testingConnector && (
          <ConnectionTest
            connector={testingConnector}
            onClose={() => setTestingConnector(null)}
          />
        )}
      </AnimatePresence>

      {/* Import Modal */}
      <AnimatePresence>
        {showImportModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => {
              if (!importing) {
                setShowImportModal(false);
                setImportResult(null);
              }
            }}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4"
            >
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Import Connectors</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Upload a YAML or JSON configuration file
                </p>
              </div>

              <div className="p-4 space-y-4">
                {!importResult && (
                  <div
                    className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-indigo-500 transition-colors cursor-pointer"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <svg className="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    {importing ? (
                      <div className="flex items-center justify-center gap-2">
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
                        <span className="text-gray-600">Validating...</span>
                      </div>
                    ) : (
                      <>
                        <p className="text-gray-600 mb-1">Click to upload or drag and drop</p>
                        <p className="text-sm text-gray-400">YAML or JSON files only</p>
                      </>
                    )}
                  </div>
                )}

                {importResult && (
                  <div className="space-y-4">
                    {/* Status Message */}
                    <div className={`p-4 rounded-lg ${
                      importResult.status === 'error' ? 'bg-red-50 text-red-800' :
                      importResult.status === 'validated' ? 'bg-blue-50 text-blue-800' :
                      'bg-green-50 text-green-800'
                    }`}>
                      <p className="font-medium">{importResult.message}</p>
                    </div>

                    {/* Validated Connectors Preview */}
                    {importResult.status === 'validated' && importResult.connectors && (
                      <div className="space-y-2">
                        <p className="text-sm font-medium text-gray-700">Connectors to import:</p>
                        <div className="border border-gray-200 rounded-lg divide-y divide-gray-200 max-h-48 overflow-y-auto">
                          {importResult.connectors.map((c, i) => (
                            <div key={i} className="p-3 flex items-center justify-between">
                              <div>
                                <p className="font-medium text-gray-900">{c.name}</p>
                                <p className="text-sm text-gray-500">{c.subtype} - {c.data_type}</p>
                              </div>
                              <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-800 rounded">
                                {c.type}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Import Results */}
                    {importResult.results && (
                      <div className="space-y-2 text-sm">
                        {importResult.results.created.length > 0 && (
                          <div className="flex items-center gap-2 text-green-600">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            Created: {importResult.results.created.map(c => c.name).join(', ')}
                          </div>
                        )}
                        {importResult.results.updated.length > 0 && (
                          <div className="flex items-center gap-2 text-blue-600">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            Updated: {importResult.results.updated.map(c => c.name).join(', ')}
                          </div>
                        )}
                        {importResult.results.skipped.length > 0 && (
                          <div className="flex items-center gap-2 text-yellow-600">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            Skipped: {importResult.results.skipped.map(c => c.name).join(', ')}
                          </div>
                        )}
                        {importResult.results.errors.length > 0 && (
                          <div className="flex items-center gap-2 text-red-600">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            Errors: {importResult.results.errors.map(c => c.name).join(', ')}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="p-4 border-t border-gray-200 flex justify-end gap-2">
                {importResult?.status === 'validated' ? (
                  <>
                    <button
                      onClick={() => {
                        setImportResult(null);
                        if (fileInputRef.current) fileInputRef.current.value = '';
                      }}
                      className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                      Upload Different File
                    </button>
                    <button
                      onClick={() => {
                        const file = fileInputRef.current?.files?.[0];
                        if (file) handleImportFile(file, false);
                      }}
                      disabled={importing}
                      className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
                    >
                      {importing ? 'Importing...' : 'Import Connectors'}
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => {
                      setShowImportModal(false);
                      setImportResult(null);
                      if (fileInputRef.current) fileInputRef.current.value = '';
                    }}
                    className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                  >
                    Close
                  </button>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default DataSources;
