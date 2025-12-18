import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { History, FileSearch } from 'lucide-react';
import { Link } from 'react-router-dom';

export function ClaimHistory() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl font-bold text-white mb-2">
          Claims History
        </h1>
        <p className="text-navy-400">
          View previously analyzed claims and their results
        </p>
      </motion.div>

      {/* Empty State */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="py-16 text-center"
      >
        <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-navy-800/50 border border-navy-700/50 flex items-center justify-center">
          <History className="w-10 h-10 text-navy-500" />
        </div>
        <h3 className="text-lg font-medium text-white mb-2">
          No Claims Yet
        </h3>
        <p className="text-navy-400 max-w-md mx-auto mb-6">
          Claims you analyze will appear here for easy reference.
          Start by submitting your first claim for analysis.
        </p>
        <Link
          to="/analyze"
          className={cn(
            'inline-flex items-center gap-2 px-6 py-3 rounded-xl',
            'bg-gradient-to-r from-kirk to-electric',
            'text-white font-medium',
            'hover:shadow-lg hover:shadow-kirk/25',
            'transition-all duration-200'
          )}
        >
          <FileSearch className="w-5 h-5" />
          Analyze Your First Claim
        </Link>
      </motion.div>

      {/* Future: Claims List */}
      <div className="grid grid-cols-1 gap-3">
        {/* Placeholder for future claims */}
      </div>
    </div>
  );
}

export default ClaimHistory;
