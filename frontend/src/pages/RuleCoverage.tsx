import { useState } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import {
  RuleStats,
  CoverageStats,
  EffectivenessStats,
} from '@/api/types';
import {
  Shield,
  Activity,
  BarChart3,
  Target,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  FileCheck,
  Loader2,
} from 'lucide-react';
import { KirkAvatar } from '@/components/kirk';

// Hooks for fetching rule data
function useRuleStats() {
  return useQuery<RuleStats>({
    queryKey: ['rule-stats'],
    queryFn: async () => {
      const response = await api.get('/api/rules/stats');
      return response.data;
    },
    staleTime: 30000,
  });
}

function useFieldCoverage() {
  return useQuery<CoverageStats>({
    queryKey: ['field-coverage'],
    queryFn: async () => {
      const response = await api.get('/api/rules/coverage');
      return response.data;
    },
    staleTime: 30000,
  });
}

function useRuleEffectiveness() {
  return useQuery<EffectivenessStats>({
    queryKey: ['rule-effectiveness'],
    queryFn: async () => {
      const response = await api.get('/api/rules/effectiveness');
      return response.data;
    },
    staleTime: 30000,
  });
}

// Stat Card component
interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: typeof Shield;
  color: 'kirk' | 'teal' | 'electric' | 'caution' | 'safe';
  delay?: number;
}

const colorClasses = {
  kirk: 'from-kirk/10 to-kirk/5 border-kirk/20 text-kirk',
  teal: 'from-teal/10 to-teal/5 border-teal/20 text-teal',
  electric: 'from-electric/10 to-electric/5 border-electric/20 text-electric',
  caution: 'from-risk-caution/10 to-risk-caution/5 border-risk-caution/20 text-risk-caution',
  safe: 'from-risk-safe/10 to-risk-safe/5 border-risk-safe/20 text-risk-safe',
};

function StatCard({ title, value, subtitle, icon: Icon, color, delay = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: delay * 0.1 }}
      className={cn(
        'p-6 rounded-2xl border bg-gradient-to-br',
        colorClasses[color],
        'backdrop-blur-sm'
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-navy-400 mb-1">{title}</p>
          <p className="text-3xl font-bold text-white tabular-nums">{value}</p>
          {subtitle && (
            <p className="text-sm mt-1" style={{ opacity: 0.7 }}>
              {subtitle}
            </p>
          )}
        </div>
        <div className={cn('p-3 rounded-xl', `bg-${color}/10`)}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </motion.div>
  );
}

// Coverage bar component
function CoverageBar({ field, coverage }: { field: string; coverage: number }) {
  const getBarColor = (pct: number) => {
    if (pct >= 90) return 'bg-risk-safe';
    if (pct >= 70) return 'bg-teal';
    if (pct >= 50) return 'bg-risk-caution';
    return 'bg-risk-high';
  };

  return (
    <div className="flex items-center gap-4 py-2">
      <span className="w-36 text-sm text-navy-300 font-mono truncate" title={field}>
        {field}
      </span>
      <div className="flex-1 h-2 bg-navy-700 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${coverage}%` }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className={cn('h-full rounded-full', getBarColor(coverage))}
        />
      </div>
      <span className={cn(
        'w-14 text-right text-sm font-medium tabular-nums',
        coverage >= 90 ? 'text-risk-safe' : coverage >= 70 ? 'text-teal' : coverage >= 50 ? 'text-risk-caution' : 'text-risk-high'
      )}>
        {coverage}%
      </span>
    </div>
  );
}

// Rule frequency row
function RuleRow({ rule, index }: { rule: RuleFrequency; index: number }) {
  return (
    <motion.tr
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className="border-b border-navy-700/50 hover:bg-navy-700/20"
    >
      <td className="py-3 px-4 font-mono text-sm text-white">{rule.rule_id}</td>
      <td className="py-3 px-4 text-right tabular-nums text-navy-300">{rule.count}</td>
      <td className="py-3 px-4 text-right">
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium tabular-nums',
          rule.percentage >= 50 ? 'bg-risk-high/20 text-risk-high' :
          rule.percentage >= 25 ? 'bg-risk-caution/20 text-risk-caution' :
          'bg-navy-600 text-navy-300'
        )}>
          {rule.percentage}%
        </span>
      </td>
    </motion.tr>
  );
}

// Type distribution chip
function TypeChip({ type, count }: { type: string; count: number }) {
  const typeColors: Record<string, string> = {
    ncci: 'bg-electric/20 text-electric border-electric/30',
    coverage: 'bg-teal/20 text-teal border-teal/30',
    provider: 'bg-risk-caution/20 text-risk-caution border-risk-caution/30',
    financial: 'bg-kirk/20 text-kirk border-kirk/30',
    modifier: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    format: 'bg-navy-500/20 text-navy-300 border-navy-500/30',
    eligibility: 'bg-risk-safe/20 text-risk-safe border-risk-safe/30',
  };

  return (
    <span className={cn(
      'px-3 py-1.5 rounded-lg text-sm font-medium border',
      typeColors[type.toLowerCase()] || 'bg-navy-600/50 text-navy-300 border-navy-600'
    )}>
      {type}: {count}
    </span>
  );
}

// Loading state
function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="w-8 h-8 animate-spin text-kirk" />
      <span className="ml-3 text-navy-400">Loading rule statistics...</span>
    </div>
  );
}

// Empty state
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-8">
      <div className="w-16 h-16 rounded-full bg-navy-700 flex items-center justify-center mb-4">
        <BarChart3 className="w-8 h-8 text-navy-400" />
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">No Analysis Data Yet</h3>
      <p className="text-navy-400 text-center max-w-md">
        Analyze some claims to see rule coverage statistics. The dashboard will show which rules
        fire most frequently and their impact on fraud detection.
      </p>
    </div>
  );
}

export function RuleCoverage() {
  const { data: stats, isLoading: statsLoading } = useRuleStats();
  const { data: coverage, isLoading: coverageLoading } = useFieldCoverage();
  const { data: effectiveness, isLoading: effectivenessLoading } = useRuleEffectiveness();
  const [activeTab, setActiveTab] = useState<'frequency' | 'coverage' | 'effectiveness'>('frequency');

  const isLoading = statsLoading || coverageLoading || effectivenessLoading;
  const hasData = stats && stats.total_claims_analyzed > 0;

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-electric/20 to-kirk/20 flex items-center justify-center">
            <BarChart3 className="w-6 h-6 text-electric" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Rule Coverage Dashboard</h1>
            <p className="text-navy-400">Monitor which fraud detection rules are firing and their effectiveness</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <KirkAvatar size="sm" />
          <span className="text-sm text-navy-400">
            {hasData ? `${stats.total_claims_analyzed} claims analyzed` : 'No data yet'}
          </span>
        </div>
      </motion.div>

      {isLoading ? (
        <LoadingState />
      ) : !hasData ? (
        <EmptyState />
      ) : (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard
              title="Claims Analyzed"
              value={stats.total_claims_analyzed.toLocaleString()}
              icon={FileCheck}
              color="kirk"
              delay={0}
            />
            <StatCard
              title="Total Rule Hits"
              value={stats.total_rule_hits.toLocaleString()}
              subtitle={`${stats.average_rules_per_claim.toFixed(1)} avg per claim`}
              icon={Target}
              color="electric"
              delay={1}
            />
            <StatCard
              title="Field Coverage"
              value={coverage ? `${coverage.coverage_score}%` : '—'}
              icon={CheckCircle}
              color={coverage && coverage.coverage_score >= 80 ? 'safe' : 'caution'}
              delay={2}
            />
            <StatCard
              title="Unique Rules Fired"
              value={effectiveness?.total_rules_fired || 0}
              icon={Activity}
              color="teal"
              delay={3}
            />
          </div>

          {/* Rule Type Distribution */}
          {stats.rules_by_type && Object.keys(stats.rules_by_type).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="p-6 rounded-2xl bg-navy-800/50 border border-navy-700"
            >
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Shield className="w-5 h-5 text-teal" />
                Rule Type Distribution
              </h2>
              <div className="flex flex-wrap gap-3">
                {Object.entries(stats.rules_by_type)
                  .sort(([, a], [, b]) => b - a)
                  .map(([type, count]) => (
                    <TypeChip key={type} type={type} count={count} />
                  ))}
              </div>
            </motion.div>
          )}

          {/* Tabs */}
          <div className="flex gap-2 border-b border-navy-700">
            {[
              { id: 'frequency' as const, label: 'Rule Frequency', icon: BarChart3 },
              { id: 'coverage' as const, label: 'Field Coverage', icon: FileCheck },
              { id: 'effectiveness' as const, label: 'Rule Effectiveness', icon: TrendingUp },
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px',
                  activeTab === id
                    ? 'text-kirk border-kirk'
                    : 'text-navy-400 border-transparent hover:text-white hover:border-navy-600'
                )}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="p-6 rounded-2xl bg-navy-800/50 border border-navy-700"
          >
            {activeTab === 'frequency' && stats.rules_by_frequency.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-electric" />
                  Most Frequently Triggered Rules
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-sm text-navy-400 border-b border-navy-700">
                        <th className="py-3 px-4 font-medium">Rule ID</th>
                        <th className="py-3 px-4 text-right font-medium">Times Fired</th>
                        <th className="py-3 px-4 text-right font-medium">% of Claims</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.rules_by_frequency.slice(0, 20).map((rule, i) => (
                        <RuleRow key={rule.rule_id} rule={rule} index={i} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'coverage' && coverage && coverage.field_coverage.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <FileCheck className="w-5 h-5 text-teal" />
                  Field Coverage Analysis
                  <span className="ml-auto text-sm font-normal text-navy-400">
                    Overall Score: <span className={cn(
                      'font-medium',
                      coverage.coverage_score >= 80 ? 'text-risk-safe' :
                      coverage.coverage_score >= 60 ? 'text-risk-caution' : 'text-risk-high'
                    )}>{coverage.coverage_score}%</span>
                  </span>
                </h3>
                <div className="space-y-1">
                  {coverage.field_coverage.map((field) => (
                    <CoverageBar
                      key={field.field}
                      field={field.field}
                      coverage={field.coverage_pct}
                    />
                  ))}
                </div>
                <p className="mt-4 text-sm text-navy-400 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-risk-caution" />
                  Low coverage fields may indicate data quality issues in source systems.
                </p>
              </div>
            )}

            {activeTab === 'effectiveness' && effectiveness && effectiveness.rules.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-kirk" />
                  Rule Impact Analysis
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-sm text-navy-400 border-b border-navy-700">
                        <th className="py-3 px-4 font-medium">Rule ID</th>
                        <th className="py-3 px-4 text-right font-medium">Times Fired</th>
                        <th className="py-3 px-4 text-right font-medium">Avg Weight</th>
                        <th className="py-3 px-4 text-right font-medium">Total Impact</th>
                        <th className="py-3 px-4 text-right font-medium">Avg Claim Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {effectiveness.rules.slice(0, 20).map((rule, i) => (
                        <motion.tr
                          key={rule.rule_id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.05 }}
                          className="border-b border-navy-700/50 hover:bg-navy-700/20"
                        >
                          <td className="py-3 px-4 font-mono text-sm text-white">{rule.rule_id}</td>
                          <td className="py-3 px-4 text-right tabular-nums text-navy-300">{rule.times_fired}</td>
                          <td className="py-3 px-4 text-right">
                            <span className={cn(
                              'tabular-nums font-medium',
                              rule.avg_weight >= 0 ? 'text-risk-high' : 'text-risk-safe'
                            )}>
                              {rule.avg_weight > 0 ? '+' : ''}{rule.avg_weight.toFixed(3)}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <span className={cn(
                              'px-2 py-1 rounded-full text-xs font-medium tabular-nums',
                              Math.abs(rule.total_weight_contribution) >= 1 ? 'bg-risk-high/20 text-risk-high' :
                              Math.abs(rule.total_weight_contribution) >= 0.5 ? 'bg-risk-caution/20 text-risk-caution' :
                              'bg-navy-600 text-navy-300'
                            )}>
                              {rule.total_weight_contribution > 0 ? '+' : ''}{rule.total_weight_contribution.toFixed(2)}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right tabular-nums text-navy-300">
                            {(rule.avg_claim_score * 100).toFixed(0)}%
                          </td>
                        </motion.tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Empty states for tabs */}
            {activeTab === 'frequency' && stats.rules_by_frequency.length === 0 && (
              <p className="text-center text-navy-400 py-8">No rule frequency data available.</p>
            )}
            {activeTab === 'coverage' && (!coverage || coverage.field_coverage.length === 0) && (
              <p className="text-center text-navy-400 py-8">No field coverage data available.</p>
            )}
            {activeTab === 'effectiveness' && (!effectiveness || effectiveness.rules.length === 0) && (
              <p className="text-center text-navy-400 py-8">No effectiveness data available.</p>
            )}
          </motion.div>
        </>
      )}
    </div>
  );
}

export default RuleCoverage;
