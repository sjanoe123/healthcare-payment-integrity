import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useSearch } from '@/api/hooks/useSearch';
import type { SearchResult } from '@/api/types';
import {
  Search,
  FileText,
  ExternalLink,
  Loader2,
  BookOpen,
  Sparkles,
} from 'lucide-react';

export function PolicySearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);

  const { mutate: search, isPending } = useSearch();

  const handleSearch = () => {
    if (!query.trim()) return;
    search(
      { query, top_k: 10 },
      {
        onSuccess: (data) => {
          setResults(data.results);
        },
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl font-bold text-white mb-2">
          Policy Search
        </h1>
        <p className="text-navy-400">
          Search CMS guidelines, LCDs, NCDs, and coverage policies using AI-powered RAG
        </p>
      </motion.div>

      {/* Search Input */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="relative"
      >
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-navy-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g., 'What are the coverage requirements for CPT 99214?' or 'NCCI edits for modifier 59'"
              className={cn(
                'w-full pl-12 pr-4 py-4 rounded-xl',
                'bg-navy-800/50 border border-navy-700/50',
                'text-white placeholder:text-navy-500',
                'focus:outline-none focus:border-kirk/50',
                'transition-colors'
              )}
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={!query.trim() || isPending}
            className={cn(
              'px-8 rounded-xl font-medium',
              'bg-gradient-to-r from-kirk to-electric',
              'text-white',
              'hover:shadow-lg hover:shadow-kirk/25',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-all duration-200',
              'flex items-center gap-2'
            )}
          >
            {isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                Search
              </>
            )}
          </button>
        </div>
      </motion.div>

      {/* Results */}
      <AnimatePresence mode="wait">
        {results.length > 0 ? (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="space-y-4"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">
                Results ({results.length})
              </h2>
            </div>

            <div className="space-y-3">
              {results.map((result, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={cn(
                    'p-5 rounded-xl',
                    'bg-navy-800/30 border border-navy-700/50',
                    'hover:border-kirk/30 transition-colors'
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div className="p-2 rounded-lg bg-kirk/10 flex-shrink-0">
                      <FileText className="w-5 h-5 text-kirk" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-medium text-white truncate">
                          {result.source || 'Policy Document'}
                        </h3>
                        <span
                          className={cn(
                            'px-2 py-0.5 rounded-full text-xs',
                            'bg-electric/10 text-electric'
                          )}
                        >
                          {((result.score ?? 0) * 100).toFixed(0)}% match
                        </span>
                      </div>
                      <p className="text-sm text-navy-300 leading-relaxed line-clamp-3">
                        {result.content}
                      </p>
                      {result.metadata?.url && (
                        <a
                          href={result.metadata.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-3 inline-flex items-center gap-1 text-sm text-kirk hover:text-kirk-light"
                        >
                          View source
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        ) : !isPending ? (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="py-16 text-center"
          >
            <BookOpen className="w-16 h-16 mx-auto text-navy-600 mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">
              Search the Knowledge Base
            </h3>
            <p className="text-navy-400 max-w-md mx-auto">
              Ask questions about Medicare coverage policies, NCCI edits, LCDs, NCDs, and more.
              Our AI will find the most relevant policy documents.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {[
                'Modifier 59 usage guidelines',
                'MUE limits for E/M codes',
                'LCD for lumbar surgery',
                'NCCI column 1 and 2 edits',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setQuery(suggestion)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-sm',
                    'bg-navy-800/50 border border-navy-700/50',
                    'text-navy-400 hover:text-white hover:border-kirk/30',
                    'transition-colors'
                  )}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export default PolicySearch;
