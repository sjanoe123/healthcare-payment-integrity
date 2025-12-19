import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { RuleHitCard } from './RuleHitCard';
import type { RuleHit } from '@/api/types';
import { AlertCircle, FileWarning, UserX, DollarSign, Layers } from 'lucide-react';

interface RuleHitsPanelProps {
  hits: RuleHit[];
  className?: string;
}

type CategoryKey = 'all' | 'ncci' | 'coverage' | 'provider' | 'financial';

const categories: {
  key: CategoryKey;
  label: string;
  icon: typeof AlertCircle;
  filter: (hit: RuleHit) => boolean;
}[] = [
  {
    key: 'all',
    label: 'All',
    icon: Layers,
    filter: () => true,
  },
  {
    key: 'ncci',
    label: 'NCCI',
    icon: AlertCircle,
    filter: (hit) => hit.rule_type === 'ncci' || hit.rule_type === 'modifier',
  },
  {
    key: 'coverage',
    label: 'Coverage',
    icon: FileWarning,
    filter: (hit) => hit.rule_type === 'coverage',
  },
  {
    key: 'provider',
    label: 'Provider',
    icon: UserX,
    filter: (hit) => hit.rule_type === 'provider',
  },
  {
    key: 'financial',
    label: 'Financial',
    icon: DollarSign,
    filter: (hit) => hit.rule_type === 'financial',
  },
];

export function RuleHitsPanel({ hits, className }: RuleHitsPanelProps) {
  const [activeCategory, setActiveCategory] = useState<CategoryKey>('all');

  const categoryCounts = categories.reduce((acc, cat) => {
    acc[cat.key] = hits.filter(cat.filter).length;
    return acc;
  }, {} as Record<CategoryKey, number>);

  const filteredHits = hits.filter(
    categories.find((c) => c.key === activeCategory)?.filter || (() => true)
  );

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Rule Violations</h3>
        <span className="text-sm text-navy-400">
          {hits.length} total finding{hits.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Category Tabs */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
        {categories.map((cat) => {
          const count = categoryCounts[cat.key];
          const isActive = activeCategory === cat.key;
          const Icon = cat.icon;

          if (cat.key !== 'all' && count === 0) return null;

          return (
            <button
              key={cat.key}
              onClick={() => setActiveCategory(cat.key)}
              className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-lg',
                'text-sm font-medium whitespace-nowrap',
                'transition-all duration-200',
                isActive
                  ? 'bg-kirk/10 text-kirk border border-kirk/30'
                  : 'bg-navy-800/50 text-navy-400 border border-transparent hover:text-white hover:bg-navy-800'
              )}
            >
              <Icon className="w-4 h-4" />
              <span>{cat.label}</span>
              <span
                className={cn(
                  'px-1.5 py-0.5 rounded-full text-xs',
                  isActive ? 'bg-kirk/20' : 'bg-navy-700'
                )}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Rule Cards */}
      <div className="space-y-3 overflow-y-auto max-h-[500px] pr-1">
        <AnimatePresence mode="popLayout">
          {filteredHits.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="py-12 text-center"
            >
              <Layers className="w-10 h-10 mx-auto text-navy-600 mb-3" />
              <p className="text-navy-400">No findings in this category</p>
            </motion.div>
          ) : (
            filteredHits.map((hit, index) => (
              <RuleHitCard key={`${hit.rule_id}-${index}`} hit={hit} index={index} />
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
