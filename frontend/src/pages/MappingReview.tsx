import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useSmartMapping, useRerank } from '@/api/hooks';
import type { MappingReviewItem, MappingCandidate } from '@/api/hooks';
import { getErrorMessage } from '@/api/client';
import {
  GitMerge,
  Play,
  AlertTriangle,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  ChevronDown,
  RefreshCw,
  FileText,
  Sparkles,
  Eye,
} from 'lucide-react';

type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'manual';

interface ReviewedMapping extends MappingReviewItem {
  reviewStatus: ReviewStatus;
  selectedField?: string;
}

function ConfidenceGauge({
  confidence,
  size = 'md',
}: {
  confidence: number;
  size?: 'sm' | 'md';
}) {
  const percentage = Math.round(confidence * 100);
  const getColor = () => {
    if (percentage >= 85) return { bar: 'bg-risk-safe', text: 'text-risk-safe' };
    if (percentage >= 70) return { bar: 'bg-risk-caution', text: 'text-risk-caution' };
    if (percentage >= 50) return { bar: 'bg-risk-alert', text: 'text-risk-alert' };
    return { bar: 'bg-risk-critical', text: 'text-risk-critical' };
  };
  const colors = getColor();
  const barWidth = size === 'sm' ? 'w-20' : 'w-32';
  const barHeight = size === 'sm' ? 'h-1.5' : 'h-2';

  return (
    <div className="flex items-center gap-2">
      <div className={cn(barWidth, barHeight, 'bg-navy-700 rounded-full overflow-hidden')}>
        <motion.div
          className={cn('h-full rounded-full', colors.bar)}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
      <span className={cn('text-sm font-medium tabular-nums', colors.text)}>
        {percentage}%
      </span>
    </div>
  );
}

function MappingCard({
  item,
  onApprove,
  onReject,
  onSelectField,
  onRerank,
  isReranking,
}: {
  item: ReviewedMapping;
  onApprove: () => void;
  onReject: () => void;
  onSelectField: (field: string) => void;
  onRerank: () => void;
  isReranking: boolean;
}) {
  const [showCandidates, setShowCandidates] = useState(false);

  const statusIndicator = {
    pending: {
      icon: AlertCircle,
      color: 'text-risk-caution border-risk-caution/20 bg-risk-caution/10',
      label: 'Needs Review',
    },
    approved: {
      icon: CheckCircle,
      color: 'text-risk-safe border-risk-safe/20 bg-risk-safe/10',
      label: 'Approved',
    },
    rejected: {
      icon: XCircle,
      color: 'text-risk-critical border-risk-critical/20 bg-risk-critical/10',
      label: 'Rejected',
    },
    manual: {
      icon: Eye,
      color: 'text-electric border-electric/20 bg-electric/10',
      label: 'Manual Override',
    },
  };

  const status = statusIndicator[item.reviewStatus];
  const StatusIcon = status.icon;

  const candidates = item.embedding_candidates || [];
  const bestMatch = item.best_match;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'p-5 rounded-xl border bg-navy-800/30',
        'border-navy-700/50 hover:border-navy-600/50',
        'transition-all duration-200'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-4 h-4 text-kirk" />
            <h3 className="text-white font-medium truncate">
              {item.source_field}
            </h3>
          </div>
          <span
            className={cn(
              'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border',
              status.color
            )}
          >
            <StatusIcon className="w-3 h-3" />
            {status.label}
          </span>
        </div>
      </div>

      {/* Best Match */}
      {bestMatch && (
        <div className="mb-4 p-4 rounded-lg bg-navy-900/50 border border-navy-700/30">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-electric" />
              <span className="text-sm text-navy-300">AI Recommended Match</span>
            </div>
            <ConfidenceGauge confidence={bestMatch.confidence} size="sm" />
          </div>
          <p className="text-white font-medium mb-2">
            {item.reviewStatus === 'manual' && item.selectedField
              ? item.selectedField
              : bestMatch.target_field}
          </p>
          {bestMatch.reasoning && (
            <p className="text-sm text-navy-400 leading-relaxed">
              {bestMatch.reasoning}
            </p>
          )}
        </div>
      )}

      {/* No match found */}
      {!bestMatch && (
        <div className="mb-4 p-4 rounded-lg bg-risk-critical/5 border border-risk-critical/20 text-center">
          <AlertTriangle className="w-6 h-6 text-risk-critical mx-auto mb-2" />
          <p className="text-sm text-navy-400">
            No suitable mapping found. Manual selection required.
          </p>
        </div>
      )}

      {/* Other Candidates Dropdown */}
      {candidates.length > 0 && (
        <div className="mb-4">
          <button
            onClick={() => setShowCandidates(!showCandidates)}
            className={cn(
              'flex items-center gap-2 text-sm text-navy-400',
              'hover:text-white transition-colors'
            )}
          >
            <ChevronDown
              className={cn(
                'w-4 h-4 transition-transform',
                showCandidates && 'rotate-180'
              )}
            />
            {candidates.length} other candidate{candidates.length !== 1 ? 's' : ''}
          </button>
          <AnimatePresence>
            {showCandidates && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="mt-3 space-y-2">
                  {candidates.map((candidate: MappingCandidate) => (
                    <button
                      key={candidate.field}
                      onClick={() => onSelectField(candidate.field)}
                      disabled={item.reviewStatus !== 'pending'}
                      className={cn(
                        'w-full flex items-center justify-between p-3 rounded-lg',
                        'bg-navy-900/30 border border-navy-700/30',
                        'hover:border-kirk/30 hover:bg-navy-800/50',
                        'disabled:opacity-50 disabled:cursor-not-allowed',
                        'transition-all duration-200',
                        item.selectedField === candidate.field && 'border-electric/50 bg-electric/5'
                      )}
                    >
                      <span className="text-sm text-navy-200">{candidate.field}</span>
                      <ConfidenceGauge confidence={candidate.score} size="sm" />
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center gap-3 pt-3 border-t border-navy-700/30">
        <button
          onClick={onApprove}
          disabled={item.reviewStatus !== 'pending' || !bestMatch}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
            'bg-risk-safe/10 border border-risk-safe/20 text-risk-safe',
            'hover:bg-risk-safe/20 transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <CheckCircle className="w-4 h-4" />
          Approve
        </button>
        <button
          onClick={onReject}
          disabled={item.reviewStatus !== 'pending'}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
            'bg-risk-critical/10 border border-risk-critical/20 text-risk-critical',
            'hover:bg-risk-critical/20 transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <XCircle className="w-4 h-4" />
          Reject
        </button>
        <button
          onClick={onRerank}
          disabled={item.reviewStatus !== 'pending' || isReranking}
          className={cn(
            'flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
            'bg-electric/10 border border-electric/20 text-electric',
            'hover:bg-electric/20 transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
          title="Re-analyze with LLM"
        >
          {isReranking ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
        </button>
      </div>
    </motion.div>
  );
}

export function MappingReview() {
  const [inputFields, setInputFields] = useState('');
  const [reviewItems, setReviewItems] = useState<ReviewedMapping[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);
  const [rerankingField, setRerankingField] = useState<string | null>(null);

  const { mutate: analyzeFields, isPending } = useSmartMapping();
  const { mutate: rerankField } = useRerank();

  const handleAnalyze = useCallback(() => {
    setParseError(null);
    const fields = inputFields
      .split('\n')
      .map((f) => f.trim())
      .filter((f) => f.length > 0);

    if (fields.length === 0) {
      setParseError('Please enter at least one field name');
      return;
    }

    analyzeFields(fields, {
      onSuccess: (data) => {
        const items: ReviewedMapping[] = data.results.map((item) => ({
          ...item,
          reviewStatus: item.best_match?.needs_review ? 'pending' : 'approved',
        }));
        setReviewItems(items);
      },
      onError: (error) => {
        setParseError(getErrorMessage(error));
      },
    });
  }, [inputFields, analyzeFields]);

  const handleApprove = useCallback((sourceField: string) => {
    setReviewItems((items) =>
      items.map((item) =>
        item.source_field === sourceField
          ? { ...item, reviewStatus: 'approved' as ReviewStatus }
          : item
      )
    );
  }, []);

  const handleReject = useCallback((sourceField: string) => {
    setReviewItems((items) =>
      items.map((item) =>
        item.source_field === sourceField
          ? { ...item, reviewStatus: 'rejected' as ReviewStatus }
          : item
      )
    );
  }, []);

  const handleSelectField = useCallback((sourceField: string, targetField: string) => {
    setReviewItems((items) =>
      items.map((item) =>
        item.source_field === sourceField
          ? { ...item, reviewStatus: 'manual' as ReviewStatus, selectedField: targetField }
          : item
      )
    );
  }, []);

  const handleRerank = useCallback(
    (item: ReviewedMapping) => {
      if (!item.embedding_candidates) return;

      setRerankingField(item.source_field);
      rerankField(
        {
          source_field: item.source_field,
          candidates: item.embedding_candidates,
        },
        {
          onSuccess: (data) => {
            setReviewItems((items) =>
              items.map((i) =>
                i.source_field === item.source_field
                  ? {
                      ...i,
                      best_match: data.best_match,
                      reviewStatus: data.best_match.needs_review ? 'pending' : 'approved',
                    }
                  : i
              )
            );
            setRerankingField(null);
          },
          onError: () => {
            setRerankingField(null);
          },
        }
      );
    },
    [rerankField]
  );

  const pendingItems = reviewItems.filter((i) => i.reviewStatus === 'pending');
  const approvedItems = reviewItems.filter((i) => i.reviewStatus === 'approved');
  const rejectedItems = reviewItems.filter((i) => i.reviewStatus === 'rejected');
  const manualItems = reviewItems.filter((i) => i.reviewStatus === 'manual');

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-lg bg-kirk/10 border border-kirk/20">
            <GitMerge className="w-6 h-6 text-kirk" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Field Mapping Review</h1>
            <p className="text-navy-400">
              Review and approve AI-suggested field mappings for healthcare data integration
            </p>
          </div>
        </div>
      </motion.div>

      {/* Input Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="p-6 rounded-xl bg-navy-800/30 border border-navy-700/50"
      >
        <div className="flex items-center justify-between mb-4">
          <label
            htmlFor="field-input"
            className="flex items-center gap-2 text-sm font-medium text-navy-300"
          >
            <FileText className="w-4 h-4" />
            Source Fields (one per line)
          </label>
          {parseError && (
            <span
              className="flex items-center gap-1 text-sm text-risk-critical"
              role="alert"
            >
              <AlertCircle className="w-4 h-4" />
              {parseError}
            </span>
          )}
        </div>
        <textarea
          id="field-input"
          value={inputFields}
          onChange={(e) => {
            setInputFields(e.target.value);
            setParseError(null);
          }}
          placeholder="patient_dob&#10;primary_dx_code&#10;rendering_provider_npi&#10;service_date"
          className={cn(
            'w-full h-40 p-4 rounded-xl',
            'bg-navy-900/50 border',
            parseError ? 'border-risk-critical/50' : 'border-navy-700/50',
            'text-sm font-mono text-navy-200',
            'placeholder:text-navy-600',
            'focus:outline-none focus:border-kirk/50',
            'resize-none'
          )}
        />
        <button
          onClick={handleAnalyze}
          disabled={!inputFields.trim() || isPending}
          className={cn(
            'mt-4 flex items-center justify-center gap-2',
            'px-6 py-3 rounded-xl font-medium',
            'bg-gradient-to-r from-kirk to-electric',
            'text-white',
            'hover:shadow-lg hover:shadow-kirk/25',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-all duration-200'
          )}
        >
          {isPending ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Analyzing Fields...
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              Analyze Fields
            </>
          )}
        </button>
      </motion.div>

      {/* Loading State */}
      {isPending && (
        <div className="py-16 text-center" role="status" aria-live="polite">
          <div className="w-8 h-8 mx-auto mb-4 border-2 border-kirk border-t-transparent rounded-full animate-spin" />
          <p className="text-navy-400">Analyzing field mappings with AI...</p>
        </div>
      )}

      {/* Results Summary */}
      {!isPending && reviewItems.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="flex flex-wrap gap-3"
        >
          <span className="px-3 py-1.5 rounded-lg text-sm bg-risk-caution/10 border border-risk-caution/20 text-risk-caution">
            {pendingItems.length} Pending Review
          </span>
          <span className="px-3 py-1.5 rounded-lg text-sm bg-risk-safe/10 border border-risk-safe/20 text-risk-safe">
            {approvedItems.length} Approved
          </span>
          <span className="px-3 py-1.5 rounded-lg text-sm bg-electric/10 border border-electric/20 text-electric">
            {manualItems.length} Manual Override
          </span>
          <span className="px-3 py-1.5 rounded-lg text-sm bg-risk-critical/10 border border-risk-critical/20 text-risk-critical">
            {rejectedItems.length} Rejected
          </span>
        </motion.div>
      )}

      {/* Pending Review Queue */}
      {!isPending && pendingItems.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-risk-caution" />
            Needs Review ({pendingItems.length})
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {pendingItems.map((item) => (
              <MappingCard
                key={item.source_field}
                item={item}
                onApprove={() => handleApprove(item.source_field)}
                onReject={() => handleReject(item.source_field)}
                onSelectField={(field) => handleSelectField(item.source_field, field)}
                onRerank={() => handleRerank(item)}
                isReranking={rerankingField === item.source_field}
              />
            ))}
          </div>
        </motion.div>
      )}

      {/* Approved Mappings */}
      {!isPending && approvedItems.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-risk-safe" />
            Approved ({approvedItems.length})
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {approvedItems.map((item) => (
              <MappingCard
                key={item.source_field}
                item={item}
                onApprove={() => {}}
                onReject={() => {}}
                onSelectField={() => {}}
                onRerank={() => {}}
                isReranking={false}
              />
            ))}
          </div>
        </motion.div>
      )}

      {/* Manual Override Mappings */}
      {!isPending && manualItems.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
        >
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Eye className="w-5 h-5 text-electric" />
            Manual Override ({manualItems.length})
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {manualItems.map((item) => (
              <MappingCard
                key={item.source_field}
                item={item}
                onApprove={() => {}}
                onReject={() => {}}
                onSelectField={() => {}}
                onRerank={() => {}}
                isReranking={false}
              />
            ))}
          </div>
        </motion.div>
      )}

      {/* Rejected Mappings */}
      {!isPending && rejectedItems.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <XCircle className="w-5 h-5 text-risk-critical" />
            Rejected ({rejectedItems.length})
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {rejectedItems.map((item) => (
              <MappingCard
                key={item.source_field}
                item={item}
                onApprove={() => {}}
                onReject={() => {}}
                onSelectField={() => {}}
                onRerank={() => {}}
                isReranking={false}
              />
            ))}
          </div>
        </motion.div>
      )}

      {/* Empty State */}
      {!isPending && reviewItems.length === 0 && inputFields.trim() === '' && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="py-16 text-center"
        >
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-navy-800/50 border border-navy-700/50 flex items-center justify-center">
            <GitMerge className="w-10 h-10 text-navy-500" />
          </div>
          <h3 className="text-lg font-medium text-white mb-2">
            No Mappings to Review
          </h3>
          <p className="text-navy-400 max-w-md mx-auto">
            Enter source field names above to get AI-powered mapping suggestions.
            Low-confidence mappings will appear here for your review.
          </p>
        </motion.div>
      )}
    </div>
  );
}

export default MappingReview;
