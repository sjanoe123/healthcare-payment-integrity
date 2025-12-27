import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/api/client';
import { cn } from '@/lib/utils';
import {
  Play,
  AlertTriangle,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Target,
  TrendingUp,
  Shield,
} from 'lucide-react';

interface SampleResult {
  claim_id: string;
  fraud_score: number;
  risk_level: 'high' | 'medium' | 'low';
  flags_count: number;
  top_flags: string[];
}

interface SampleAnalysisResponse {
  connector_id: string;
  connector_name: string;
  status: 'completed' | 'no_data';
  sample_size: number;
  last_sync_at: string | null;
  summary?: {
    high_risk: number;
    medium_risk: number;
    low_risk: number;
    total_flags: number;
    avg_score: number;
  };
  results: SampleResult[];
  message: string;
}

interface SampleAnalysisProps {
  connectorId: string;
  connectorName: string;
  hasCompletedSync: boolean;
}

const riskColors = {
  high: 'bg-risk-high/20 text-risk-high border-risk-high/30',
  medium: 'bg-risk-caution/20 text-risk-caution border-risk-caution/30',
  low: 'bg-risk-safe/20 text-risk-safe border-risk-safe/30',
};

const riskIcons = {
  high: AlertTriangle,
  medium: AlertCircle,
  low: CheckCircle,
};

function RiskBadge({ level }: { level: 'high' | 'medium' | 'low' }) {
  const Icon = riskIcons[level];
  return (
    <span className={cn('px-2 py-1 rounded-full text-xs font-medium border flex items-center gap-1', riskColors[level])}>
      <Icon className="w-3 h-3" />
      {level.charAt(0).toUpperCase() + level.slice(1)}
    </span>
  );
}

function FraudScoreBar({ score }: { score: number }) {
  const percentage = score * 100;
  const getColor = () => {
    if (percentage >= 70) return 'bg-risk-high';
    if (percentage >= 40) return 'bg-risk-caution';
    return 'bg-risk-safe';
  };

  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-navy-700 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.3 }}
          className={cn('h-full rounded-full', getColor())}
        />
      </div>
      <span className="text-sm tabular-nums text-navy-300 w-12">
        {percentage.toFixed(0)}%
      </span>
    </div>
  );
}

export function SampleAnalysis({
  connectorId,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  connectorName,
  hasCompletedSync,
}: SampleAnalysisProps) {
  // connectorName reserved for future use in UI display
  const [expanded, setExpanded] = useState(false);
  const [results, setResults] = useState<SampleAnalysisResponse | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const response = await api.post<SampleAnalysisResponse>(
        `/api/connectors/${connectorId}/sample-analysis`,
        null,
        { params: { sample_size: 10 } }
      );
      return response.data;
    },
    onSuccess: (data) => {
      setResults(data);
      setExpanded(true);
    },
  });

  if (!hasCompletedSync) {
    return (
      <div className="p-4 rounded-xl bg-navy-800/50 border border-navy-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-navy-700 flex items-center justify-center">
            <Target className="w-5 h-5 text-navy-500" />
          </div>
          <div>
            <h4 className="font-medium text-white">Sample Analysis</h4>
            <p className="text-sm text-navy-400">
              Complete a sync first to analyze sample claims
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-navy-800/50 border border-navy-700 overflow-hidden">
      {/* Header */}
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-kirk/20 to-electric/20 flex items-center justify-center">
            <Target className="w-5 h-5 text-kirk" />
          </div>
          <div>
            <h4 className="font-medium text-white">Sample Analysis</h4>
            <p className="text-sm text-navy-400">
              {results
                ? `${results.sample_size} claims analyzed`
                : 'Analyze sample claims to preview fraud detection'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!results && (
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg',
                'bg-kirk text-white font-medium text-sm',
                'hover:bg-kirk/90 transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Run Analysis
                </>
              )}
            </button>
          )}

          {results && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-2 rounded-lg text-navy-400 hover:text-white hover:bg-navy-700/50 transition-colors"
            >
              {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <AnimatePresence>
        {results && results.summary && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="px-4 pb-4"
          >
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-risk-high/10 border border-risk-high/20">
                <div className="text-2xl font-bold text-risk-high tabular-nums">
                  {results.summary.high_risk}
                </div>
                <div className="text-xs text-navy-400">High Risk</div>
              </div>
              <div className="p-3 rounded-lg bg-risk-caution/10 border border-risk-caution/20">
                <div className="text-2xl font-bold text-risk-caution tabular-nums">
                  {results.summary.medium_risk}
                </div>
                <div className="text-xs text-navy-400">Medium Risk</div>
              </div>
              <div className="p-3 rounded-lg bg-risk-safe/10 border border-risk-safe/20">
                <div className="text-2xl font-bold text-risk-safe tabular-nums">
                  {results.summary.low_risk}
                </div>
                <div className="text-xs text-navy-400">Low Risk</div>
              </div>
              <div className="p-3 rounded-lg bg-navy-700/50 border border-navy-600">
                <div className="text-2xl font-bold text-white tabular-nums">
                  {results.summary.total_flags}
                </div>
                <div className="text-xs text-navy-400">Total Flags</div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Detailed Results */}
      <AnimatePresence>
        {results && expanded && results.results.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-navy-700"
          >
            <div className="p-4">
              <h5 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                <Shield className="w-4 h-4 text-teal" />
                Sample Claim Results
              </h5>
              <div className="space-y-2">
                {results.results.map((result) => (
                  <motion.div
                    key={result.claim_id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="p-3 rounded-lg bg-navy-700/30 hover:bg-navy-700/50 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="font-mono text-sm text-white truncate">
                          {result.claim_id}
                        </span>
                        <RiskBadge level={result.risk_level} />
                      </div>
                      <FraudScoreBar score={result.fraud_score} />
                    </div>
                    {result.top_flags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {result.top_flags.map((flag) => (
                          <span
                            key={flag}
                            className="px-2 py-0.5 rounded bg-navy-600 text-xs text-navy-300 font-mono"
                          >
                            {flag}
                          </span>
                        ))}
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Action Footer */}
            <div className="p-4 border-t border-navy-700 bg-navy-800/30">
              <div className="flex items-center justify-between">
                <p className="text-sm text-navy-400 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Average fraud score: {((results.summary?.avg_score || 0) * 100).toFixed(0)}%
                </p>
                <button
                  onClick={() => mutation.mutate()}
                  disabled={mutation.isPending}
                  className="text-sm text-kirk hover:text-kirk/80 transition-colors"
                >
                  Re-run Analysis
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error State */}
      {mutation.isError && (
        <div className="p-4 border-t border-navy-700 bg-risk-high/5">
          <p className="text-sm text-risk-high flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Failed to analyze samples. Please try again.
          </p>
        </div>
      )}
    </div>
  );
}

export default SampleAnalysis;
