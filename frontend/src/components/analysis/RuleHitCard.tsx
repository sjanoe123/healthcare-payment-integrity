import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { AlertTriangle, Info, XCircle, ChevronRight } from 'lucide-react';
import type { RuleHit, Severity } from '@/api/types';

interface RuleHitCardProps {
  hit: RuleHit;
  index?: number;
  className?: string;
}

const severityConfig: Record<
  Severity,
  {
    icon: typeof Info;
    colors: string;
    iconBg: string;
  }
> = {
  low: {
    icon: Info,
    colors: 'border-electric/20 hover:border-electric/40',
    iconBg: 'bg-electric/10 text-electric',
  },
  medium: {
    icon: AlertTriangle,
    colors: 'border-risk-caution/20 hover:border-risk-caution/40',
    iconBg: 'bg-risk-caution/10 text-risk-caution',
  },
  high: {
    icon: AlertTriangle,
    colors: 'border-risk-alert/20 hover:border-risk-alert/40',
    iconBg: 'bg-risk-alert/10 text-risk-alert',
  },
  critical: {
    icon: XCircle,
    colors: 'border-risk-critical/20 hover:border-risk-critical/40',
    iconBg: 'bg-risk-critical/10 text-risk-critical',
  },
};

export function RuleHitCard({ hit, index = 0, className }: RuleHitCardProps) {
  const config = severityConfig[hit.severity];
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className={cn(
        'group p-4 rounded-xl border bg-navy-800/30',
        'hover:bg-navy-800/50 transition-all cursor-pointer',
        config.colors,
        className
      )}
    >
      <div className="flex items-start gap-3">
        {/* Severity Icon */}
        <div className={cn('p-2 rounded-lg flex-shrink-0', config.iconBg)}>
          <Icon className="w-4 h-4" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-navy-400">{hit.rule_id}</span>
            <span
              className={cn(
                'text-xs px-1.5 py-0.5 rounded uppercase font-medium',
                config.iconBg
              )}
            >
              {hit.severity}
            </span>
          </div>
          <p className="text-sm text-navy-200 leading-relaxed">
            {hit.description}
          </p>

          {/* Affected Codes */}
          {hit.affected_codes && hit.affected_codes.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {hit.affected_codes.map((code) => (
                <code
                  key={code}
                  className="px-1.5 py-0.5 text-xs rounded bg-navy-900/50 text-kirk-light font-mono"
                >
                  {code}
                </code>
              ))}
            </div>
          )}
        </div>

        {/* Chevron */}
        <ChevronRight className="w-4 h-4 text-navy-600 group-hover:text-navy-400 transition-colors flex-shrink-0" />
      </div>
    </motion.div>
  );
}
