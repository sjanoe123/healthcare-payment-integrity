import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { KirkAvatar } from './KirkAvatar';

interface KirkTypingProps {
  message?: string;
  className?: string;
}

export function KirkTyping({ message = 'Kirk is thinking...', className }: KirkTypingProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={cn('flex items-start gap-3 py-2', className)}
    >
      <KirkAvatar size="sm" mood="thinking" />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm text-kirk font-medium">Kirk</span>
          <span className="text-xs text-navy-500">analyzing</span>
        </div>
        <div className="mt-1.5 flex items-center gap-2">
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className="w-2 h-2 rounded-full bg-kirk"
                animate={{
                  scale: [1, 1.3, 1],
                  opacity: [0.4, 1, 0.4],
                }}
                transition={{
                  duration: 1.2,
                  repeat: Infinity,
                  delay: i * 0.2,
                  ease: 'easeInOut',
                }}
              />
            ))}
          </div>
          <span className="text-sm text-navy-400 italic">{message}</span>
        </div>
      </div>
    </motion.div>
  );
}
