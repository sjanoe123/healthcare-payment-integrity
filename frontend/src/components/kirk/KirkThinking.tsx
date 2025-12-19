import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { KirkAvatar } from './KirkAvatar';
import { Search, FileText, Scale, CheckCircle } from 'lucide-react';
import { useState, useEffect } from 'react';

interface KirkThinkingProps {
  isLoading: boolean;
  className?: string;
}

/** Steps displayed during analysis with their icons and durations */
const thinkingSteps = [
  { icon: FileText, text: 'Parsing claim data...', duration: 1500 },
  { icon: Search, text: 'Checking NCCI edits & policies...', duration: 2000 },
  { icon: Scale, text: 'Analyzing compliance rules...', duration: 1800 },
  { icon: CheckCircle, text: 'Preparing recommendations...', duration: 1200 },
] as const;

const TOTAL_DURATION = thinkingSteps.reduce((sum, step) => sum + step.duration, 0);

/**
 * Inner content component that manages the step cycling animation.
 * Separated to ensure clean state reset when loading restarts.
 */
function KirkThinkingContent({ className }: { className?: string }) {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const timeouts: NodeJS.Timeout[] = [];
    let elapsed = 0;

    // Schedule each step transition
    thinkingSteps.forEach((_, i) => {
      if (i > 0) {
        const timeout = setTimeout(() => setCurrentStep(i), elapsed);
        timeouts.push(timeout);
      }
      elapsed += thinkingSteps[i].duration;
    });

    // Loop back through steps after all complete
    const loopInterval = setInterval(() => {
      setCurrentStep(prev => (prev + 1) % thinkingSteps.length);
    }, TOTAL_DURATION);

    return () => {
      timeouts.forEach(clearTimeout);
      clearInterval(loopInterval);
    };
  }, []);

  const CurrentIcon = thinkingSteps[currentStep].icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={cn(
        'p-6 rounded-xl',
        'bg-navy-800/50 border border-kirk/20',
        'backdrop-blur-sm',
        className
      )}
    >
      <div className="flex items-start gap-4">
        <KirkAvatar size="lg" mood="thinking" />
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-3">
            <span className="font-semibold text-white">Kirk</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-kirk/20 text-kirk">
              Analyzing
            </span>
          </div>

          {/* Progress Steps */}
          <div className="space-y-2">
            <AnimatePresence mode="wait">
              <motion.div
                key={currentStep}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="flex items-center gap-3"
              >
                <div className="p-2 rounded-lg bg-kirk/10">
                  <CurrentIcon className="w-4 h-4 text-kirk" />
                </div>
                <span className="text-navy-300">
                  {thinkingSteps[currentStep].text}
                </span>
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Progress bar */}
          <div className="mt-4 h-1 bg-navy-700 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-kirk to-electric"
              animate={{
                width: ['0%', '100%'],
              }}
              transition={{
                duration: 3,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export function KirkThinking({ isLoading, className }: KirkThinkingProps) {
  // Render content component only when loading, which naturally resets state
  if (!isLoading) return null;

  return <KirkThinkingContent className={className} />;
}
