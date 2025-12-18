import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { KirkAvatar } from './KirkAvatar';
import { AlertTriangle, Info, XCircle, Lightbulb } from 'lucide-react';
import type { RiskLevel, Severity } from '@/api/types';

type MessageType = 'greeting' | 'finding' | 'recommendation' | 'summary';

interface KirkMessageProps {
  type: MessageType;
  content: string;
  severity?: Severity;
  mood?: RiskLevel | 'neutral';
  metadata?: {
    ruleType?: string;
    code?: string;
  };
  className?: string;
  delay?: number;
}

const severityConfig = {
  low: {
    icon: Info,
    color: 'text-electric',
    bg: 'bg-electric/10',
    border: 'border-electric/20',
  },
  medium: {
    icon: AlertTriangle,
    color: 'text-risk-caution',
    bg: 'bg-risk-caution/10',
    border: 'border-risk-caution/20',
  },
  high: {
    icon: AlertTriangle,
    color: 'text-risk-alert',
    bg: 'bg-risk-alert/10',
    border: 'border-risk-alert/20',
  },
  critical: {
    icon: XCircle,
    color: 'text-risk-critical',
    bg: 'bg-risk-critical/10',
    border: 'border-risk-critical/20',
  },
};

const typeConfig = {
  greeting: {
    showAvatar: true,
    bubbleStyle: 'bg-navy-800/50 border-navy-700/50',
  },
  finding: {
    showAvatar: false,
    bubbleStyle: 'bg-navy-800/80 border-navy-700/50',
  },
  recommendation: {
    showAvatar: false,
    bubbleStyle: 'bg-kirk/5 border-kirk/20',
  },
  summary: {
    showAvatar: true,
    bubbleStyle: 'bg-gradient-to-br from-navy-800/80 to-kirk/5 border-kirk/30',
  },
};

export function KirkMessage({
  type,
  content,
  severity,
  mood = 'neutral',
  metadata,
  className,
  delay = 0,
}: KirkMessageProps) {
  const config = typeConfig[type];
  const severityStyle = severity ? severityConfig[severity] : null;
  const SeverityIcon = severityStyle?.icon || Info;

  return (
    <motion.div
      initial={{ opacity: 0, y: 15, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: delay * 0.15, duration: 0.3 }}
      className={cn('flex items-start gap-3', className)}
    >
      {config.showAvatar && (
        <KirkAvatar size="sm" mood={mood} className="flex-shrink-0 mt-1" />
      )}
      {!config.showAvatar && <div className="w-8" />}

      <div
        className={cn(
          'flex-1 p-4 rounded-xl border',
          config.bubbleStyle,
          'backdrop-blur-sm'
        )}
      >
        {/* Type-specific header */}
        {type === 'finding' && severity && (
          <div className="flex items-center gap-2 mb-2">
            <span
              className={cn(
                'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
                severityStyle?.bg,
                severityStyle?.color
              )}
            >
              <SeverityIcon className="w-3 h-3" />
              {severity.toUpperCase()}
            </span>
            {metadata?.ruleType && (
              <span className="text-xs text-navy-500">{metadata.ruleType}</span>
            )}
          </div>
        )}

        {type === 'recommendation' && (
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-kirk/10 text-kirk">
              <Lightbulb className="w-3 h-3" />
              RECOMMENDATION
            </span>
          </div>
        )}

        {/* Message Content */}
        <p className="text-sm text-navy-200 leading-relaxed">{content}</p>

        {/* Code reference if present */}
        {metadata?.code && (
          <code className="mt-2 inline-block px-2 py-1 rounded bg-navy-900/50 text-xs font-mono text-kirk-light">
            {metadata.code}
          </code>
        )}
      </div>
    </motion.div>
  );
}
