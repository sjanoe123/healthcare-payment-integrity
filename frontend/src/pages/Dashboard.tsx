import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useStats } from '@/api/hooks/useStats';
import { useHealth } from '@/api/hooks/useHealth';
import {
  FileSearch,
  Shield,
  TrendingUp,
  Database,
  Clock,
  CheckCircle,
  AlertTriangle,
  Activity,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { KirkAvatar } from '@/components/kirk';

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

export function Dashboard() {
  const { data: stats, isLoading: statsLoading } = useStats();
  const { data: health, isLoading: healthLoading } = useHealth();

  return (
    <div className="space-y-8">
      {/* Welcome Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            Compliance Command Center
          </h1>
          <p className="text-navy-400">
            Healthcare payment integrity monitoring and analysis
          </p>
        </div>
        <Link
          to="/analyze"
          className={cn(
            'flex items-center gap-2 px-6 py-3 rounded-xl',
            'bg-gradient-to-r from-kirk to-electric',
            'text-white font-medium',
            'hover:shadow-lg hover:shadow-kirk/25',
            'transition-all duration-200 hover:scale-105'
          )}
        >
          <FileSearch className="w-5 h-5" />
          Analyze Claim
        </Link>
      </motion.div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Claims Analyzed"
          value={stats?.claims_analyzed ?? '—'}
          subtitle="Total processed"
          icon={Shield}
          color="kirk"
          delay={0}
        />
        <StatCard
          title="Flags Detected"
          value={stats?.flags_detected ?? '—'}
          subtitle="Compliance issues"
          icon={AlertTriangle}
          color="caution"
          delay={1}
        />
        <StatCard
          title="Auto Approved"
          value={stats?.auto_approved ?? '—'}
          subtitle="Clean claims"
          icon={CheckCircle}
          color="safe"
          delay={2}
        />
        <StatCard
          title="Potential Savings"
          value={stats?.potential_savings ? `$${stats.potential_savings.toLocaleString()}` : '—'}
          subtitle="ROI estimate"
          icon={TrendingUp}
          color="teal"
          delay={3}
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* System Status Panel */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
          className="lg:col-span-2 p-6 rounded-2xl bg-navy-800/30 border border-navy-700/50"
        >
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-electric" />
            System Status
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-navy-900/50 border border-navy-700/30">
              <div className="flex items-center gap-2 mb-2">
                <div
                  className={cn(
                    'w-2 h-2 rounded-full',
                    health?.status === 'healthy' ? 'bg-risk-safe' : 'bg-risk-critical'
                  )}
                />
                <span className="text-sm text-navy-400">Backend</span>
              </div>
              <p className="text-white font-medium capitalize">
                {health?.status || 'Checking...'}
              </p>
            </div>
            <div className="p-4 rounded-xl bg-navy-900/50 border border-navy-700/30">
              <div className="flex items-center gap-2 mb-2">
                <Database className="w-4 h-4 text-navy-400" />
                <span className="text-sm text-navy-400">RAG Docs</span>
              </div>
              <p className="text-white font-medium">
                {health?.rag_documents?.toLocaleString() || '—'}
              </p>
            </div>
            <div className="p-4 rounded-xl bg-navy-900/50 border border-navy-700/30">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-navy-400" />
                <span className="text-sm text-navy-400">NCCI Rules</span>
              </div>
              <p className="text-white font-medium">
                {health?.ncci_rules?.toLocaleString() || '—'}
              </p>
            </div>
            <div className="p-4 rounded-xl bg-navy-900/50 border border-navy-700/30">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-navy-400" />
                <span className="text-sm text-navy-400">Uptime</span>
              </div>
              <p className="text-white font-medium">
                {health?.uptime || '—'}
              </p>
            </div>
          </div>
        </motion.div>

        {/* Kirk Welcome Panel */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
          className="p-6 rounded-2xl bg-gradient-to-br from-kirk/10 to-navy-800/50 border border-kirk/20"
        >
          <div className="flex items-center gap-3 mb-4">
            <KirkAvatar size="lg" mood="neutral" />
            <div>
              <h3 className="text-lg font-semibold text-white">Meet Kirk</h3>
              <p className="text-sm text-navy-400">AI Compliance Analyst</p>
            </div>
          </div>
          <p className="text-sm text-navy-300 leading-relaxed mb-4">
            I'm your AI-powered compliance expert. Submit a claim and I'll analyze it against
            CMS policies, NCCI edits, and OIG guidelines to identify potential issues.
          </p>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2 text-navy-400">
              <CheckCircle className="w-4 h-4 text-risk-safe" />
              <span>Real-time NCCI PTP checks</span>
            </div>
            <div className="flex items-center gap-2 text-navy-400">
              <CheckCircle className="w-4 h-4 text-risk-safe" />
              <span>OIG LEIE provider screening</span>
            </div>
            <div className="flex items-center gap-2 text-navy-400">
              <CheckCircle className="w-4 h-4 text-risk-safe" />
              <span>MUE limit validation</span>
            </div>
            <div className="flex items-center gap-2 text-navy-400">
              <CheckCircle className="w-4 h-4 text-risk-safe" />
              <span>LCD/NCD policy guidance</span>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Quick Actions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
      >
        <Link
          to="/analyze"
          className={cn(
            'group p-6 rounded-2xl border border-navy-700/50',
            'bg-navy-800/30 hover:bg-navy-800/50',
            'transition-all duration-200'
          )}
        >
          <FileSearch className="w-8 h-8 text-kirk mb-3 group-hover:scale-110 transition-transform" />
          <h3 className="text-white font-medium mb-1">Analyze a Claim</h3>
          <p className="text-sm text-navy-400">
            Submit JSON claim data for comprehensive analysis
          </p>
        </Link>
        <Link
          to="/search"
          className={cn(
            'group p-6 rounded-2xl border border-navy-700/50',
            'bg-navy-800/30 hover:bg-navy-800/50',
            'transition-all duration-200'
          )}
        >
          <Database className="w-8 h-8 text-electric mb-3 group-hover:scale-110 transition-transform" />
          <h3 className="text-white font-medium mb-1">Search Policies</h3>
          <p className="text-sm text-navy-400">
            Query CMS guidelines and coverage policies
          </p>
        </Link>
        <Link
          to="/claims"
          className={cn(
            'group p-6 rounded-2xl border border-navy-700/50',
            'bg-navy-800/30 hover:bg-navy-800/50',
            'transition-all duration-200'
          )}
        >
          <Clock className="w-8 h-8 text-teal mb-3 group-hover:scale-110 transition-transform" />
          <h3 className="text-white font-medium mb-1">View History</h3>
          <p className="text-sm text-navy-400">
            Browse previously analyzed claims
          </p>
        </Link>
      </motion.div>
    </div>
  );
}
