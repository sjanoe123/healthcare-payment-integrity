import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import {
  RefreshCw,
  Play,
  Pause,
  XCircle,
  CheckCircle,
  Clock,
  AlertTriangle,
  Database,
  ChevronDown,
  ChevronUp,
  Terminal,
  Loader2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  useSyncJobs,
  useSyncJob,
  useCancelSyncJob,
  useSyncJobLogs,
  type SyncJob,
} from '@/api/hooks/useConnectors';

const statusConfig: Record<
  SyncJob['status'],
  { icon: typeof CheckCircle; color: string; bg: string }
> = {
  pending: {
    icon: Clock,
    color: 'text-yellow-500',
    bg: 'bg-yellow-500/10 border-yellow-500/20',
  },
  running: {
    icon: Loader2,
    color: 'text-blue-500',
    bg: 'bg-blue-500/10 border-blue-500/20',
  },
  success: {
    icon: CheckCircle,
    color: 'text-green-500',
    bg: 'bg-green-500/10 border-green-500/20',
  },
  failed: {
    icon: XCircle,
    color: 'text-red-500',
    bg: 'bg-red-500/10 border-red-500/20',
  },
  cancelled: {
    icon: Pause,
    color: 'text-gray-500',
    bg: 'bg-gray-500/10 border-gray-500/20',
  },
};

function JobCard({ job, onSelect }: { job: SyncJob; onSelect: () => void }) {
  const { icon: StatusIcon, color, bg } = statusConfig[job.status];
  const cancelJob = useCancelSyncJob();

  const handleCancel = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to cancel this job?')) {
      cancelJob.mutate(job.id);
    }
  };

  const progress =
    job.total_records > 0
      ? Math.round((job.processed_records / job.total_records) * 100)
      : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'p-4 rounded-xl border bg-navy-800/30',
        'border-navy-700/50 hover:border-navy-600/50',
        'transition-all duration-200 cursor-pointer'
      )}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className={cn('p-2 rounded-lg border', bg)}>
            <StatusIcon
              className={cn('w-5 h-5', color, job.status === 'running' && 'animate-spin')}
            />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-white font-medium">
                {job.connector_name || 'Unknown Connector'}
              </h3>
              <span
                className={cn(
                  'px-2 py-0.5 rounded text-xs font-medium border',
                  bg,
                  color
                )}
              >
                {job.status}
              </span>
            </div>
            <p className="text-navy-400 text-sm mt-1">
              <span className="capitalize">{job.job_type}</span> &middot;{' '}
              <span className="capitalize">{job.sync_mode}</span> sync
            </p>
          </div>
        </div>

        {(job.status === 'pending' || job.status === 'running') && (
          <button
            onClick={handleCancel}
            disabled={cancelJob.isPending}
            className={cn(
              'p-2 rounded-lg',
              'bg-red-500/10 border border-red-500/20 text-red-400',
              'hover:bg-red-500/20 transition-colors',
              'disabled:opacity-50'
            )}
            title="Cancel job"
          >
            <XCircle className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Progress bar for running jobs */}
      {job.status === 'running' && job.total_records > 0 && (
        <div className="mt-4">
          <div className="flex justify-between text-xs text-navy-400 mb-1">
            <span>Progress</span>
            <span>
              {job.processed_records.toLocaleString()} / {job.total_records.toLocaleString()}
            </span>
          </div>
          <div className="h-2 bg-navy-700 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-kirk to-electric"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
          <p className="text-xs text-navy-500 mt-1 text-right">{progress}%</p>
        </div>
      )}

      {/* Stats */}
      <div className="mt-4 flex items-center gap-4 text-xs">
        {job.started_at && (
          <span className="text-navy-400">
            Started: {new Date(job.started_at).toLocaleString()}
          </span>
        )}
        {job.completed_at && (
          <span className="text-navy-400">
            Completed: {new Date(job.completed_at).toLocaleString()}
          </span>
        )}
        {job.failed_records > 0 && (
          <span className="text-red-400">
            {job.failed_records.toLocaleString()} failed
          </span>
        )}
      </div>

      {/* Error message */}
      {job.error_message && (
        <div className="mt-3 p-2 rounded bg-red-500/10 border border-red-500/20">
          <p className="text-red-400 text-xs font-mono">{job.error_message}</p>
        </div>
      )}
    </motion.div>
  );
}

function JobDetail({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const { data: job, isLoading } = useSyncJob(jobId);
  const { data: logsData } = useSyncJobLogs(jobId, { limit: 100 });
  const [showLogs, setShowLogs] = useState(true);

  if (isLoading || !job) {
    return (
      <div className="p-8 text-center">
        <Loader2 className="w-8 h-8 mx-auto animate-spin text-kirk" />
        <p className="text-navy-400 mt-2">Loading job details...</p>
      </div>
    );
  }

  const { icon: StatusIcon, color, bg } = statusConfig[job.status];

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className="h-full flex flex-col"
    >
      {/* Header */}
      <div className="p-4 border-b border-navy-700/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn('p-2 rounded-lg border', bg)}>
            <StatusIcon
              className={cn('w-5 h-5', color, job.status === 'running' && 'animate-spin')}
            />
          </div>
          <div>
            <h2 className="text-white font-bold">{job.connector_name || 'Unknown'}</h2>
            <p className="text-navy-400 text-sm">Job ID: {job.id.slice(0, 8)}...</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-navy-700/50 text-navy-400"
        >
          <XCircle className="w-5 h-5" />
        </button>
      </div>

      {/* Stats Grid */}
      <div className="p-4 grid grid-cols-2 gap-4">
        <div className="p-3 rounded-lg bg-navy-800/50 border border-navy-700/50">
          <p className="text-navy-400 text-xs">Status</p>
          <p className={cn('font-medium capitalize', color)}>{job.status}</p>
        </div>
        <div className="p-3 rounded-lg bg-navy-800/50 border border-navy-700/50">
          <p className="text-navy-400 text-xs">Type</p>
          <p className="text-white font-medium capitalize">{job.job_type}</p>
        </div>
        <div className="p-3 rounded-lg bg-navy-800/50 border border-navy-700/50">
          <p className="text-navy-400 text-xs">Sync Mode</p>
          <p className="text-white font-medium capitalize">{job.sync_mode}</p>
        </div>
        <div className="p-3 rounded-lg bg-navy-800/50 border border-navy-700/50">
          <p className="text-navy-400 text-xs">Triggered By</p>
          <p className="text-white font-medium">{job.triggered_by || 'System'}</p>
        </div>
      </div>

      {/* Records Stats */}
      {job.total_records > 0 && (
        <div className="px-4 pb-4">
          <div className="p-4 rounded-lg bg-navy-800/50 border border-navy-700/50">
            <div className="flex items-center justify-between mb-3">
              <p className="text-white font-medium">Records</p>
              <p className="text-navy-400 text-sm">
                {job.processed_records.toLocaleString()} / {job.total_records.toLocaleString()}
              </p>
            </div>
            <div className="h-3 bg-navy-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-kirk to-electric"
                style={{
                  width: `${Math.round(
                    (job.processed_records / job.total_records) * 100
                  )}%`,
                }}
              />
            </div>
            {job.failed_records > 0 && (
              <p className="text-red-400 text-xs mt-2">
                {job.failed_records.toLocaleString()} records failed
              </p>
            )}
          </div>
        </div>
      )}

      {/* Logs Section */}
      <div className="flex-1 flex flex-col min-h-0">
        <button
          onClick={() => setShowLogs(!showLogs)}
          className="px-4 py-3 flex items-center justify-between border-t border-navy-700/50 hover:bg-navy-800/30"
        >
          <div className="flex items-center gap-2 text-white">
            <Terminal className="w-4 h-4" />
            <span className="font-medium">Logs</span>
            {logsData && (
              <span className="text-navy-400 text-sm">
                ({logsData.logs.length})
              </span>
            )}
          </div>
          {showLogs ? (
            <ChevronUp className="w-4 h-4 text-navy-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-navy-400" />
          )}
        </button>

        {showLogs && (
          <div className="flex-1 overflow-y-auto p-4 bg-navy-900/50">
            {logsData?.logs && logsData.logs.length > 0 ? (
              <div className="space-y-1 font-mono text-xs">
                {logsData.logs.map((log) => (
                  <div
                    key={log.id}
                    className={cn('p-2 rounded', {
                      'bg-red-500/10 text-red-400': log.level === 'error',
                      'bg-yellow-500/10 text-yellow-400': log.level === 'warning',
                      'text-navy-300': log.level === 'info',
                    })}
                  >
                    <span className="text-navy-500">
                      [{new Date(log.timestamp).toLocaleTimeString()}]
                    </span>{' '}
                    <span
                      className={cn('uppercase', {
                        'text-red-400': log.level === 'error',
                        'text-yellow-400': log.level === 'warning',
                        'text-blue-400': log.level === 'info',
                      })}
                    >
                      {log.level}
                    </span>{' '}
                    {log.message}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-navy-500 text-center py-8">No logs available</p>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

export function SyncJobs() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useSyncJobs({
    status: statusFilter,
    limit: 50,
  });

  const statusFilters = [
    { value: undefined, label: 'All' },
    { value: 'running', label: 'Running' },
    { value: 'pending', label: 'Pending' },
    { value: 'success', label: 'Success' },
    { value: 'failed', label: 'Failed' },
    { value: 'cancelled', label: 'Cancelled' },
  ];

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">Sync Jobs</h1>
            <p className="text-navy-400">
              Monitor data synchronization jobs from your connectors
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => refetch()}
              className={cn(
                'p-2 rounded-lg',
                'bg-navy-800/50 border border-navy-700/50',
                'text-navy-300 hover:text-white hover:border-navy-600',
                'transition-all'
              )}
              title="Refresh"
            >
              <RefreshCw className="w-5 h-5" />
            </button>
            <Link
              to="/data-sources"
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg',
                'bg-kirk/10 border border-kirk/20 text-kirk',
                'hover:bg-kirk/20 transition-colors'
              )}
            >
              <Database className="w-4 h-4" />
              Data Sources
            </Link>
          </div>
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-2 mt-4">
          {statusFilters.map((filter) => (
            <button
              key={filter.label}
              onClick={() => setStatusFilter(filter.value)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                statusFilter === filter.value
                  ? 'bg-kirk text-white'
                  : 'bg-navy-800/50 border border-navy-700/50 text-navy-300 hover:border-navy-600'
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Content */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Jobs List */}
        <div className={cn('flex-1 overflow-y-auto', selectedJobId && 'max-w-lg')}>
          {isLoading && (
            <div className="py-16 text-center">
              <Loader2 className="w-8 h-8 mx-auto animate-spin text-kirk" />
              <p className="text-navy-400 mt-2">Loading sync jobs...</p>
            </div>
          )}

          {error && (
            <div className="py-16 text-center">
              <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-risk-caution" />
              <p className="text-white mb-2">Failed to load sync jobs</p>
              <p className="text-navy-400 text-sm">Please try again later</p>
            </div>
          )}

          {!isLoading && !error && data?.jobs.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="py-16 text-center"
            >
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-navy-800/50 border border-navy-700/50 flex items-center justify-center">
                <RefreshCw className="w-10 h-10 text-navy-500" />
              </div>
              <h3 className="text-lg font-medium text-white mb-2">No Sync Jobs</h3>
              <p className="text-navy-400 max-w-md mx-auto mb-6">
                {statusFilter
                  ? `No ${statusFilter} jobs found.`
                  : 'Trigger a sync from a data source to see jobs here.'}
              </p>
              <Link
                to="/data-sources"
                className={cn(
                  'inline-flex items-center gap-2 px-6 py-3 rounded-xl',
                  'bg-gradient-to-r from-kirk to-electric',
                  'text-white font-medium',
                  'hover:shadow-lg hover:shadow-kirk/25',
                  'transition-all duration-200'
                )}
              >
                <Play className="w-5 h-5" />
                Go to Data Sources
              </Link>
            </motion.div>
          )}

          {!isLoading && !error && data && data.jobs.length > 0 && (
            <div className="space-y-3">
              <p className="text-navy-400 text-sm mb-4">
                {data.total} job{data.total !== 1 ? 's' : ''}
              </p>
              {data.jobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onSelect={() => setSelectedJobId(job.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Job Detail Panel */}
        <AnimatePresence>
          {selectedJobId && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 400 }}
              exit={{ opacity: 0, width: 0 }}
              className="rounded-xl border border-navy-700/50 bg-navy-800/30 overflow-hidden"
            >
              <JobDetail jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default SyncJobs;
