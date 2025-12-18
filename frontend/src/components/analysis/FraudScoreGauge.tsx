import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { getRiskLevel, type RiskLevel } from '@/api/types';

interface FraudScoreGaugeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

const sizeConfig = {
  sm: { width: 120, height: 70, strokeWidth: 8, fontSize: 'text-lg' },
  md: { width: 200, height: 110, strokeWidth: 12, fontSize: 'text-3xl' },
  lg: { width: 280, height: 150, strokeWidth: 16, fontSize: 'text-4xl' },
};

const riskColors: Record<RiskLevel, { primary: string; gradient: string; glow: string }> = {
  safe: {
    primary: '#10B981',
    gradient: 'url(#gradient-safe)',
    glow: 'drop-shadow(0 0 12px rgba(16, 185, 129, 0.5))',
  },
  caution: {
    primary: '#F59E0B',
    gradient: 'url(#gradient-caution)',
    glow: 'drop-shadow(0 0 12px rgba(245, 158, 11, 0.5))',
  },
  alert: {
    primary: '#F97316',
    gradient: 'url(#gradient-alert)',
    glow: 'drop-shadow(0 0 12px rgba(249, 115, 22, 0.5))',
  },
  critical: {
    primary: '#EF4444',
    gradient: 'url(#gradient-critical)',
    glow: 'drop-shadow(0 0 16px rgba(239, 68, 68, 0.6))',
  },
};

const riskLabels: Record<RiskLevel, string> = {
  safe: 'Low Risk',
  caution: 'Elevated',
  alert: 'High Risk',
  critical: 'Critical',
};

export function FraudScoreGauge({
  score,
  size = 'md',
  showLabel = true,
  className,
}: FraudScoreGaugeProps) {
  const config = sizeConfig[size];
  const riskLevel = getRiskLevel(score);
  const colors = riskColors[riskLevel];

  // SVG arc calculations
  const cx = config.width / 2;
  const cy = config.height - 10;
  const radius = config.width / 2 - config.strokeWidth;

  // Arc path (semi-circle)
  const startAngle = Math.PI;
  const endAngle = 0;
  const arcLength = Math.PI * radius;

  // Needle position (0-180 degrees mapped to score 0-1)
  const needleAngle = Math.PI - score * Math.PI;
  const needleLength = radius - 10;
  const needleX = cx + needleLength * Math.cos(needleAngle);
  const needleY = cy - needleLength * Math.sin(needleAngle);

  const createArc = (startDeg: number, endDeg: number) => {
    const start = {
      x: cx + radius * Math.cos((startDeg * Math.PI) / 180),
      y: cy - radius * Math.sin((startDeg * Math.PI) / 180),
    };
    const end = {
      x: cx + radius * Math.cos((endDeg * Math.PI) / 180),
      y: cy - radius * Math.sin((endDeg * Math.PI) / 180),
    };
    const largeArc = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y}`;
  };

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <svg
        width={config.width}
        height={config.height}
        viewBox={`0 0 ${config.width} ${config.height}`}
        className="overflow-visible"
      >
        <defs>
          {/* Gradients for each risk level */}
          <linearGradient id="gradient-safe" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#14B8A6" />
            <stop offset="100%" stopColor="#10B981" />
          </linearGradient>
          <linearGradient id="gradient-caution" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#F59E0B" />
            <stop offset="100%" stopColor="#EAB308" />
          </linearGradient>
          <linearGradient id="gradient-alert" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#F97316" />
            <stop offset="100%" stopColor="#F59E0B" />
          </linearGradient>
          <linearGradient id="gradient-critical" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#EF4444" />
            <stop offset="100%" stopColor="#DC2626" />
          </linearGradient>

          {/* Background arc gradient */}
          <linearGradient id="bg-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#10B981" stopOpacity="0.2" />
            <stop offset="35%" stopColor="#F59E0B" stopOpacity="0.2" />
            <stop offset="60%" stopColor="#F97316" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#EF4444" stopOpacity="0.2" />
          </linearGradient>
        </defs>

        {/* Background track - colored zones */}
        <path
          d={createArc(0, 180)}
          fill="none"
          stroke="url(#bg-gradient)"
          strokeWidth={config.strokeWidth}
          strokeLinecap="round"
        />

        {/* Active arc */}
        <motion.path
          d={createArc(180 - score * 180, 180)}
          fill="none"
          stroke={colors.gradient}
          strokeWidth={config.strokeWidth}
          strokeLinecap="round"
          style={{ filter: colors.glow }}
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1, ease: 'easeOut' }}
        />

        {/* Center glow */}
        <circle
          cx={cx}
          cy={cy}
          r={8}
          fill={colors.primary}
          style={{ filter: colors.glow }}
        />

        {/* Needle */}
        <motion.g
          initial={{ rotate: -180 }}
          animate={{ rotate: -180 + score * 180 }}
          transition={{ duration: 1.2, ease: 'easeOut', delay: 0.2 }}
          style={{ transformOrigin: `${cx}px ${cy}px` }}
        >
          <line
            x1={cx}
            y1={cy}
            x2={cx + needleLength}
            y2={cy}
            stroke={colors.primary}
            strokeWidth={3}
            strokeLinecap="round"
            style={{ filter: colors.glow }}
          />
          {/* Needle tip */}
          <circle cx={cx + needleLength} cy={cy} r={4} fill={colors.primary} />
        </motion.g>

        {/* Center cap */}
        <circle cx={cx} cy={cy} r={12} fill="#1E293B" stroke={colors.primary} strokeWidth={2} />
      </svg>

      {/* Score Display */}
      <motion.div
        className="text-center -mt-2"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <div className={cn(config.fontSize, 'font-bold tabular-nums')} style={{ color: colors.primary }}>
          {(score * 100).toFixed(0)}%
        </div>
        {showLabel && (
          <div
            className="text-sm font-medium mt-1 px-3 py-1 rounded-full"
            style={{
              color: colors.primary,
              backgroundColor: `${colors.primary}15`,
            }}
          >
            {riskLabels[riskLevel]}
          </div>
        )}
      </motion.div>
    </div>
  );
}
