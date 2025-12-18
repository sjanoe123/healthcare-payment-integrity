import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { KirkAvatar } from './KirkAvatar';
import { Search, FileText, Scale, CheckCircle } from 'lucide-react';
import { useState, useEffect } from 'react';

interface KirkThinkingProps {
  isLoading: boolean;
  className?: string;
}

const thinkingSteps = [
  { icon: FileText, text: 'Parsing claim data...', duration: 1500 },
  { icon: Search, text: 'Checking NCCI edits & policies...', duration: 2000 },
  { icon: Scale, text: 'Analyzing compliance rules...', duration: 1800 },
  { icon: CheckCircle, text: 'Preparing recommendations...', duration: 1200 },
];

export function KirkThinking({ isLoading, className }: KirkThinkingProps) {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (!isLoading) {
      setCurrentStep(0);
      return;
    }

    const totalSteps = thinkingSteps.length;
    let stepIndex = 0;

    const advanceStep = () => {
      stepIndex = (stepIndex + 1) % totalSteps;
      setCurrentStep(stepIndex);
    };

    // Cycle through steps
    const intervals: NodeJS.Timeout[] = [];
    let elapsed = 0;

    thinkingSteps.forEach((step, i) => {
      const timeout = setTimeout(() => {
        setCurrentStep(i);
      }, elapsed);
      intervals.push(timeout);
      elapsed += step.duration;
    });

    // Loop back
    const loopInterval = setInterval(() => {
      advanceStep();
    }, elapsed);

    return () => {
      intervals.forEach(clearTimeout);
      clearInterval(loopInterval);
    };
  }, [isLoading]);

  if (!isLoading) return null;

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
