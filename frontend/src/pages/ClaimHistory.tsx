import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { History, FileSearch, AlertTriangle, CheckCircle, Clock, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useJobs } from '@/api/hooks';
import { getRiskLevel, formatScore } from '@/api/types';
import { FraudScoreGauge } from '@/components/analysis';

export function ClaimHistory() {
  const { data, isLoading, error } = useJobs();

  const riskColors = {
    safe: 'text-risk-safe border-risk-safe/20 bg-risk-safe/10',
    caution: 'text-risk-caution border-risk-caution/20 bg-risk-caution/10',
    alert: 'text-risk-alert border-risk-alert/20 bg-risk-alert/10',
    critical: 'text-risk-critical border-risk-critical/20 bg-risk-critical/10',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl font-bold text-white mb-2">
          Claims History
        </h1>
        <p className="text-navy-400">
          View previously analyzed claims and their results
        </p>
      </motion.div>

      {/* Loading State */}
      {isLoading && (
        <div className="py-16 text-center">
          <div className="w-8 h-8 mx-auto mb-4 border-2 border-kirk border-t-transparent rounded-full animate-spin" />
          <p className="text-navy-400">Loading claims...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="py-16 text-center">
          <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-risk-caution" />
          <p className="text-white mb-2">Failed to load claims</p>
          <p className="text-navy-400 text-sm">Please try again later</p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && data?.jobs.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="py-16 text-center"
        >
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-navy-800/50 border border-navy-700/50 flex items-center justify-center">
            <History className="w-10 h-10 text-navy-500" />
          </div>
          <h3 className="text-lg font-medium text-white mb-2">
            No Claims Yet
          </h3>
          <p className="text-navy-400 max-w-md mx-auto mb-6">
            Claims you analyze will appear here for easy reference.
            Start by submitting your first claim for analysis.
          </p>
          <Link
            to="/analyze"
            className={cn(
              'inline-flex items-center gap-2 px-6 py-3 rounded-xl',
              'bg-gradient-to-r from-kirk to-electric',
              'text-white font-medium',
              'hover:shadow-lg hover:shadow-kirk/25',
              'transition-all duration-200'
            )}
          >
            <FileSearch className="w-5 h-5" />
            Analyze Your First Claim
          </Link>
        </motion.div>
      )}

      {/* Claims List */}
      {!isLoading && !error && data && data.jobs.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-navy-400 text-sm">
              {data.total} claim{data.total !== 1 ? 's' : ''} analyzed
            </p>
            <Link
              to="/analyze"
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2 rounded-lg',
                'bg-kirk/10 border border-kirk/20 text-kirk',
                'hover:bg-kirk/20 transition-colors'
              )}
            >
              <FileSearch className="w-4 h-4" />
              New Analysis
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {data.jobs.map((job, index) => {
              const riskLevel = getRiskLevel(job.fraud_score);
              return (
                <motion.div
                  key={job.job_id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={cn(
                    'p-5 rounded-xl border bg-navy-800/30',
                    'border-navy-700/50 hover:border-navy-600/50',
                    'transition-all duration-200'
                  )}
                >
                  <div className="flex items-start gap-4">
                    {/* Fraud Score Gauge */}
                    <div className="flex-shrink-0">
                      <FraudScoreGauge score={job.fraud_score} size="sm" showLabel={false} />
                    </div>

                    {/* Claim Details */}
                    <div className="flex-grow min-w-0">
                      <div className="flex items-start justify-between gap-4 mb-2">
                        <div>
                          <h3 className="text-white font-medium">
                            Claim {job.claim_id}
                          </h3>
                          <p className="text-navy-400 text-sm flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(job.created_at).toLocaleString()}
                          </p>
                        </div>
                        <span
                          className={cn(
                            'px-3 py-1 rounded-full text-xs font-medium border',
                            riskColors[riskLevel]
                          )}
                        >
                          {formatScore(job.fraud_score)} Risk
                        </span>
                      </div>

                      {/* Flags Summary */}
                      <div className="flex flex-wrap gap-2 mb-3">
                        {job.flags_count > 0 ? (
                          <>
                            {job.ncci_flags.length > 0 && (
                              <span className="px-2 py-0.5 rounded text-xs bg-risk-caution/10 text-risk-caution border border-risk-caution/20">
                                {job.ncci_flags.length} NCCI
                              </span>
                            )}
                            {job.coverage_flags.length > 0 && (
                              <span className="px-2 py-0.5 rounded text-xs bg-risk-alert/10 text-risk-alert border border-risk-alert/20">
                                {job.coverage_flags.length} Coverage
                              </span>
                            )}
                            {job.provider_flags.length > 0 && (
                              <span className="px-2 py-0.5 rounded text-xs bg-risk-critical/10 text-risk-critical border border-risk-critical/20">
                                {job.provider_flags.length} Provider
                              </span>
                            )}
                            {job.rule_hits.length > 0 && (
                              <span className="px-2 py-0.5 rounded text-xs bg-electric/10 text-electric border border-electric/20">
                                {job.rule_hits.length} Rules
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-xs bg-risk-safe/10 text-risk-safe border border-risk-safe/20 flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" />
                            Clean
                          </span>
                        )}
                      </div>

                      {/* Decision Mode */}
                      <div className="flex items-center justify-between">
                        <span className="text-navy-400 text-sm capitalize">
                          {job.decision_mode.replace(/_/g, ' ')}
                        </span>
                        {job.roi_estimate && job.roi_estimate > 0 && (
                          <span className="text-teal text-sm font-medium">
                            ${job.roi_estimate.toLocaleString()} potential savings
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default ClaimHistory;
