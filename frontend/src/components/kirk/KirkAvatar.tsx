import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import type { RiskLevel } from '@/api/types';

interface KirkAvatarProps {
  size?: 'sm' | 'md' | 'lg';
  mood?: RiskLevel | 'neutral' | 'thinking';
  className?: string;
}

const sizeClasses = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-14 h-14 text-base',
};

const moodColors = {
  neutral: {
    bg: 'from-kirk to-kirk-dark',
    glow: 'shadow-kirk/30',
    animation: 'animate-pulse-slow',
  },
  thinking: {
    bg: 'from-kirk to-electric',
    glow: 'shadow-electric/40',
    animation: 'animate-pulse',
  },
  safe: {
    bg: 'from-risk-safe to-teal',
    glow: 'shadow-risk-safe/30',
    animation: 'animate-pulse-slow',
  },
  caution: {
    bg: 'from-risk-caution to-risk-alert',
    glow: 'shadow-risk-caution/30',
    animation: 'animate-pulse',
  },
  alert: {
    bg: 'from-risk-alert to-risk-critical',
    glow: 'shadow-risk-alert/40',
    animation: 'animate-pulse',
  },
  critical: {
    bg: 'from-risk-critical to-red-700',
    glow: 'shadow-risk-critical/50',
    animation: 'animate-glow',
  },
};

export function KirkAvatar({
  size = 'md',
  mood = 'neutral',
  className,
}: KirkAvatarProps) {
  const moodStyle = moodColors[mood];

  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={cn(
        'relative rounded-full flex items-center justify-center',
        'bg-gradient-to-br',
        moodStyle.bg,
        'shadow-lg',
        moodStyle.glow,
        sizeClasses[size],
        className
      )}
    >
      {/* Glow ring for elevated states */}
      {(mood === 'alert' || mood === 'critical') && (
        <motion.div
          className={cn(
            'absolute inset-0 rounded-full',
            'bg-gradient-to-br',
            moodStyle.bg,
            'opacity-50 blur-sm',
            moodStyle.animation
          )}
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.5, 0.3, 0.5],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      )}

      {/* Thinking animation dots */}
      {mood === 'thinking' && (
        <motion.div
          className="absolute inset-0 rounded-full border-2 border-white/20"
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
        />
      )}

      {/* K Letter */}
      <span className="font-bold text-white relative z-10">K</span>
    </motion.div>
  );
}
