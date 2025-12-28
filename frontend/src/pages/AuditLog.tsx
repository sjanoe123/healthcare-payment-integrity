import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { api, getErrorMessage } from '@/api/client';
import type { AuditLogListResponse, AuditStats } from '@/api/types';
import { cn } from '@/lib/utils';
import {
  Shield,
  FileText,
  Download,
  Filter,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  AlertCircle,
  CheckCircle,
  Clock,
  User,
  Activity,
  Database,
  Search,
  Loader2,
  Calendar,
} from 'lucide-react';
import { KirkAvatar } from '@/components/kirk';

// Action category colors
const actionCategoryColors: Record<string, string> = {
  claim: 'bg-electric/20 text-electric border-electric/30',
  connector: 'bg-teal/20 text-teal border-teal/30',
  policy: 'bg-kirk/20 text-kirk border-kirk/30',
  auth: 'bg-risk-caution/20 text-risk-caution border-risk-caution/30',
  audit: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

function getActionCategory(action: string): string {
  const category = action.split('.')[0];
  return category || 'other';
}

function ActionBadge({ action }: { action: string }) {
  const category = getActionCategory(action);
  const colorClass = actionCategoryColors[category] || 'bg-navy-600/50 text-navy-300 border-navy-600';

  return (
    <span className={cn('px-2 py-1 rounded-lg text-xs font-medium border', colorClass)}>
      {action}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'success') {
    return (
      <span className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-risk-safe/20 text-risk-safe border border-risk-safe/30">
        <CheckCircle className="w-3 h-3" />
        Success
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-risk-high/20 text-risk-high border border-risk-high/30">
      <AlertCircle className="w-3 h-3" />
      Error
    </span>
  );
}

function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleString();
  } catch {
    return timestamp;
  }
}

function StatCard({ title, value, icon: Icon, color }: {
  title: string;
  value: string | number;
  icon: typeof Shield;
  color: string;
}) {
  return (
    <div className={cn(
      'p-4 rounded-xl border backdrop-blur-sm',
      color
    )}>
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-white/10">
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
          <p className="text-xs text-navy-400">{title}</p>
        </div>
      </div>
    </div>
  );
}

export function AuditLog() {
  const [page, setPage] = useState(0);
  const [actionFilter, setActionFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [exportError, setExportError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const limit = 20;

  const toggleRowExpanded = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Clear export error after 5 seconds
  const showExportError = (message: string) => {
    setExportError(message);
    setTimeout(() => setExportError(null), 5000);
  };

  // Fetch audit logs
  const { data: logsData, isLoading: logsLoading, error: logsError } = useQuery<AuditLogListResponse>({
    queryKey: ['audit-logs', page, actionFilter, statusFilter],
    queryFn: async () => {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: (page * limit).toString(),
      });
      if (actionFilter) params.set('action', actionFilter);
      if (statusFilter) params.set('status', statusFilter);

      const response = await api.get(`/api/audit?${params.toString()}`);
      return response.data;
    },
    staleTime: 10000,
  });

  // Fetch audit stats
  const { data: statsData, isLoading: statsLoading, error: statsError } = useQuery<AuditStats>({
    queryKey: ['audit-stats'],
    queryFn: async () => {
      const response = await api.get('/api/audit/stats');
      return response.data;
    },
    staleTime: 30000,
  });

  // Fetch available actions
  const { data: actionsData } = useQuery<{ actions: string[]; categories: Record<string, string[]> }>({
    queryKey: ['audit-actions'],
    queryFn: async () => {
      const response = await api.get('/api/audit/actions');
      return response.data;
    },
    staleTime: 300000,
  });

  const handleExport = async (format: 'csv' | 'json') => {
    if (isExporting) return;
    setIsExporting(true);
    setExportError(null);

    try {
      const params = new URLSearchParams({ format });
      if (actionFilter) params.set('action', actionFilter);

      const response = await api.get(`/api/audit/export?${params.toString()}`, {
        responseType: 'blob',
      });

      const blob = new Blob([response.data], {
        type: format === 'csv' ? 'text/csv' : 'application/json',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_export.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
      showExportError(getErrorMessage(error));
    } finally {
      setIsExporting(false);
    }
  };

  const totalPages = logsData ? Math.ceil(logsData.total / limit) : 0;

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/20 to-kirk/20 flex items-center justify-center">
            <Shield className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Audit Log</h1>
            <p className="text-navy-400">HIPAA-compliant activity tracking and compliance reporting</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <KirkAvatar size="sm" />
          <span className="text-sm text-navy-400">
            {statsData ? `${statsData.total_entries.toLocaleString()} total events` : 'Loading...'}
          </span>
        </div>
      </motion.div>

      {/* Stats Cards */}
      {statsLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-kirk" />
        </div>
      ) : statsError ? (
        <div className="flex items-center justify-center py-8 px-4 rounded-xl bg-risk-high/10 border border-risk-high/30">
          <AlertCircle className="w-5 h-5 text-risk-high mr-3" />
          <span className="text-sm text-risk-high">{getErrorMessage(statsError)}</span>
        </div>
      ) : statsData && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Events"
            value={statsData.total_entries.toLocaleString()}
            icon={Activity}
            color="bg-gradient-to-br from-kirk/10 to-kirk/5 border-kirk/20"
          />
          <StatCard
            title="Successful"
            value={statsData.entries_by_status['success'] || 0}
            icon={CheckCircle}
            color="bg-gradient-to-br from-risk-safe/10 to-risk-safe/5 border-risk-safe/20"
          />
          <StatCard
            title="Errors"
            value={statsData.entries_by_status['error'] || 0}
            icon={AlertCircle}
            color="bg-gradient-to-br from-risk-high/10 to-risk-high/5 border-risk-high/20"
          />
          <StatCard
            title="Unique Users"
            value={Object.keys(statsData.entries_by_user).length}
            icon={User}
            color="bg-gradient-to-br from-teal/10 to-teal/5 border-teal/20"
          />
        </div>
      )}

      {/* Filters and Export */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex flex-wrap items-center gap-4 p-4 rounded-xl bg-navy-800/50 border border-navy-700"
      >
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-navy-400" />
          <span className="text-sm font-medium text-navy-300">Filters:</span>
        </div>

        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(0); }}
          className="px-3 py-2 rounded-lg bg-navy-700 border border-navy-600 text-white text-sm focus:outline-none focus:ring-2 focus:ring-kirk/50"
        >
          <option value="">All Actions</option>
          {actionsData?.actions.map((action) => (
            <option key={action} value={action}>{action}</option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
          className="px-3 py-2 rounded-lg bg-navy-700 border border-navy-600 text-white text-sm focus:outline-none focus:ring-2 focus:ring-kirk/50"
        >
          <option value="">All Status</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
        </select>

        <div className="flex-1" />

        <div className="flex items-center gap-2">
          <button
            onClick={() => handleExport('csv')}
            disabled={isExporting}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors",
              isExporting
                ? "bg-navy-800 border-navy-700 text-navy-500 cursor-not-allowed"
                : "bg-navy-700 border-navy-600 text-white hover:bg-navy-600"
            )}
          >
            {isExporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Export CSV
          </button>
          <button
            onClick={() => handleExport('json')}
            disabled={isExporting}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors",
              isExporting
                ? "bg-navy-800 border-navy-700 text-navy-500 cursor-not-allowed"
                : "bg-navy-700 border-navy-600 text-white hover:bg-navy-600"
            )}
          >
            {isExporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            Export JSON
          </button>
        </div>
      </motion.div>

      {/* Export Error Toast */}
      <AnimatePresence>
        {exportError && (
          <motion.div
            initial={{ opacity: 0, y: 20, x: '-50%' }}
            animate={{ opacity: 1, y: 0, x: '-50%' }}
            exit={{ opacity: 0, y: 20, x: '-50%' }}
            className="fixed bottom-6 left-1/2 transform z-50 flex items-center gap-3 px-4 py-3 rounded-lg bg-risk-high/20 border border-risk-high/30 text-risk-high shadow-lg"
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span className="text-sm">{exportError}</span>
            <button
              onClick={() => setExportError(null)}
              className="ml-2 text-risk-high/70 hover:text-risk-high"
            >
              ×
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Audit Log Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="rounded-xl bg-navy-800/50 border border-navy-700 overflow-hidden"
      >
        {logsLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-kirk" />
            <span className="ml-3 text-navy-400">Loading audit logs...</span>
          </div>
        ) : logsError ? (
          <div className="flex items-center justify-center py-12 px-4">
            <AlertCircle className="w-6 h-6 text-risk-high mr-3" />
            <div className="text-center">
              <p className="text-sm text-risk-high font-medium">Failed to load audit logs</p>
              <p className="text-xs text-risk-high/70 mt-1">{getErrorMessage(logsError)}</p>
            </div>
          </div>
        ) : logsData && logsData.entries.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-sm text-navy-400 border-b border-navy-700 bg-navy-800/50">
                    <th className="py-3 px-4 font-medium">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4" />
                        Timestamp
                      </div>
                    </th>
                    <th className="py-3 px-4 font-medium">Action</th>
                    <th className="py-3 px-4 font-medium">
                      <div className="flex items-center gap-2">
                        <User className="w-4 h-4" />
                        User
                      </div>
                    </th>
                    <th className="py-3 px-4 font-medium">
                      <div className="flex items-center gap-2">
                        <Database className="w-4 h-4" />
                        Resource
                      </div>
                    </th>
                    <th className="py-3 px-4 font-medium">Status</th>
                    <th className="py-3 px-4 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence>
                    {logsData.entries.map((entry, i) => {
                      const hasDetails = entry.details && Object.keys(entry.details).length > 0;
                      const isExpanded = expandedRows.has(entry.id);
                      // Disable animations for large datasets (>50 rows) for better performance
                      const shouldAnimate = logsData.entries.length <= 50;
                      const RowComponent = shouldAnimate ? motion.tr : 'tr';
                      const animationProps = shouldAnimate
                        ? {
                            initial: { opacity: 0, x: -10 },
                            animate: { opacity: 1, x: 0 },
                            transition: { delay: Math.min(i * 0.005, 0.1) },
                          }
                        : {};
                      return (
                        <React.Fragment key={entry.id}>
                          <RowComponent
                            {...animationProps}
                            className="border-b border-navy-700/50 hover:bg-navy-700/20"
                          >
                            <td className="py-3 px-4 text-sm text-navy-300 whitespace-nowrap">
                              {formatTimestamp(entry.timestamp)}
                            </td>
                            <td className="py-3 px-4">
                              <ActionBadge action={entry.action} />
                            </td>
                            <td className="py-3 px-4 text-sm text-navy-300">
                              {entry.user_email || entry.user_id || (
                                <span className="text-navy-500 italic">anonymous</span>
                              )}
                            </td>
                            <td className="py-3 px-4">
                              {entry.resource_type && (
                                <div className="flex items-center gap-2">
                                  <span className="text-sm text-navy-400">{entry.resource_type}:</span>
                                  <span className="font-mono text-xs text-white truncate max-w-32">
                                    {entry.resource_id}
                                  </span>
                                </div>
                              )}
                            </td>
                            <td className="py-3 px-4">
                              <StatusBadge status={entry.status} />
                            </td>
                            <td className="py-3 px-4">
                              {hasDetails && (
                                <button
                                  onClick={() => toggleRowExpanded(entry.id)}
                                  className="flex items-center gap-1 text-xs text-kirk hover:text-kirk/80"
                                >
                                  <ChevronDown className={cn(
                                    'w-3 h-3 transition-transform',
                                    isExpanded && 'rotate-180'
                                  )} />
                                  {isExpanded ? 'Hide' : 'View'} details
                                </button>
                              )}
                            </td>
                          </RowComponent>
                          {/* Expanded details row - rendered directly after parent for accessibility */}
                          {isExpanded && hasDetails && (
                            <motion.tr
                              key={`${entry.id}-details`}
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              className="bg-navy-900/50"
                            >
                              <td colSpan={6} className="py-3 px-4">
                                <pre className="text-xs text-navy-300 font-mono overflow-x-auto max-w-full whitespace-pre-wrap">
                                  {JSON.stringify(entry.details, null, 2)}
                                </pre>
                              </td>
                            </motion.tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>

            {/* Pagination - only show if there are multiple pages or at least one entry */}
            {totalPages > 0 && (
              <div className="flex items-center justify-between p-4 border-t border-navy-700">
                <p className="text-sm text-navy-400">
                  Showing {page * limit + 1} - {Math.min((page + 1) * limit, logsData.total)} of {logsData.total}
                </p>
                {totalPages > 1 && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPage(page - 1)}
                      disabled={page === 0}
                      className="p-2 rounded-lg text-navy-400 hover:text-white hover:bg-navy-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronLeft className="w-5 h-5" />
                    </button>
                    <span className="text-sm text-navy-300">
                      Page {page + 1} of {totalPages}
                    </span>
                    <button
                      onClick={() => setPage(page + 1)}
                      disabled={page >= totalPages - 1}
                      className="p-2 rounded-lg text-navy-400 hover:text-white hover:bg-navy-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 px-8">
            <div className="w-16 h-16 rounded-full bg-navy-700 flex items-center justify-center mb-4">
              <Search className="w-8 h-8 text-navy-400" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">No Audit Events</h3>
            <p className="text-navy-400 text-center max-w-md">
              No audit log entries found matching your filters. Activity will be logged as users
              interact with the system.
            </p>
          </div>
        )}
      </motion.div>

      {/* Date Range Info */}
      {statsData && statsData.date_range.earliest && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="flex items-center gap-2 text-sm text-navy-400"
        >
          <Calendar className="w-4 h-4" />
          <span>
            Log range: {formatTimestamp(statsData.date_range.earliest)} to {formatTimestamp(statsData.date_range.latest)}
          </span>
        </motion.div>
      )}
    </div>
  );
}

export default AuditLog;
