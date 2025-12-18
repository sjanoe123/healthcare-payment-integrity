import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import {
  CheckCircle,
  AlertTriangle,
  Hand,
  Info,
  Zap,
} from 'lucide-react';
import type { DecisionMode } from '@/api/types';

interface DecisionModeBadgeProps {
  mode: DecisionMode;
  size?: 'sm' | 'md' | 'lg';
  showDescription?: boolean;
  className?: string;
}

const modeConfig: Record<
  DecisionMode,
  {
    icon: typeof CheckCircle;
    label: string;
    description: string;
    colors: string;
    iconColor: string;
  }
> = {
  auto_approve: {
    icon: CheckCircle,
    label: 'Auto Approve',
    description: 'Claim passed all checks',
    colors: 'bg-risk-safe/10 border-risk-safe/30 text-risk-safe',
    iconColor: 'text-risk-safe',
  },
  auto_approve_fast: {
    icon: Zap,
    label: 'Fast Track',
    description: 'Low-risk, expedited approval',
    colors: 'bg-teal/10 border-teal/30 text-teal',
    iconColor: 'text-teal',
  },
  informational: {
    icon: Info,
    label: 'Informational',
    description: 'Minor findings for awareness',
    colors: 'bg-electric/10 border-electric/30 text-electric',
    iconColor: 'text-electric',
  },
  recommendation: {
    icon: AlertTriangle,
    label: 'Recommendation',
    description: 'Review suggested before processing',
    colors: 'bg-risk-caution/10 border-risk-caution/30 text-risk-caution',
    iconColor: 'text-risk-caution',
  },
  soft_hold: {
    icon: Hand,
    label: 'Soft Hold',
    description: 'Manual review required',
    colors: 'bg-risk-alert/10 border-risk-alert/30 text-risk-alert',
    iconColor: 'text-risk-alert',
  },
};

const sizeClasses = {
  sm: 'px-2 py-1 text-xs gap-1.5',
  md: 'px-3 py-1.5 text-sm gap-2',
  lg: 'px-4 py-2 text-base gap-2.5',
};

const iconSizes = {
  sm: 'w-3 h-3',
  md: 'w-4 h-4',
  lg: 'w-5 h-5',
};

export function DecisionModeBadge({
  mode,
  size = 'md',
  showDescription = false,
  className,
}: DecisionModeBadgeProps) {
  const config = modeConfig[mode];
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        'inline-flex items-center rounded-full border font-medium',
        config.colors,
        sizeClasses[size],
        className
      )}
    >
      <Icon className={cn(iconSizes[size], config.iconColor)} />
      <span>{config.label}</span>
      {showDescription && (
        <span className="text-navy-400 ml-1">— {config.description}</span>
      )}
    </motion.div>
  );
}
