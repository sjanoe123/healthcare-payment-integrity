import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { KirkAvatar } from './KirkAvatar';
import { KirkMessage } from './KirkMessage';
import { KirkThinking } from './KirkThinking';
import { MessageSquare, Sparkles } from 'lucide-react';
import type { AnalysisResult, RuleHit } from '@/api/types';
import { getRiskLevel } from '@/api/types';

/** Maximum number of rule hits to display in the chat */
const MAX_DISPLAYED_HITS = 5;

interface KirkChatProps {
  result?: AnalysisResult | null;
  isLoading?: boolean;
  className?: string;
}

function getRuleTypeLabel(rule: RuleHit): string {
  const types: Record<string, string> = {
    ncci: 'NCCI Edit',
    coverage: 'Coverage Policy',
    provider: 'Provider Check',
    financial: 'Financial Flag',
    modifier: 'Modifier Issue',
  };
  return types[rule.rule_type] || rule.rule_type;
}

export function KirkChat({ result, isLoading = false, className }: KirkChatProps) {
  const riskLevel = result ? getRiskLevel(result.fraud_score) : 'neutral';
  const claudeAnalysis = result?.claude_analysis;

  return (
    <div
      className={cn(
        'flex flex-col h-full',
        'bg-navy-900/50 border-l border-navy-700/50',
        className
      )}
      role="region"
      aria-label="Kirk AI Analysis"
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-navy-700/50">
        <KirkAvatar size="md" mood={result ? riskLevel : 'neutral'} />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">Kirk</h3>
            <Sparkles className="w-3.5 h-3.5 text-kirk" aria-hidden="true" />
          </div>
          <p className="text-xs text-navy-400">AI Compliance Analyst</p>
        </div>
        <MessageSquare className="w-5 h-5 text-navy-500" aria-hidden="true" />
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4" role="log" aria-live="polite">
        <AnimatePresence mode="wait">
          {/* Loading State */}
          {isLoading && (
            <KirkThinking isLoading={isLoading} />
          )}

          {/* Empty State */}
          {!isLoading && !result && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col items-center justify-center h-full text-center py-12"
            >
              <KirkAvatar size="lg" mood="neutral" className="mb-4" />
              <h4 className="text-white font-medium mb-2">
                Ready to analyze
              </h4>
              <p className="text-sm text-navy-400 max-w-[200px]">
                Submit a claim and I'll provide detailed compliance analysis
              </p>
            </motion.div>
          )}

          {/* Analysis Results */}
          {!isLoading && result && (
            <div className="space-y-3">
              {/* Greeting / Summary */}
              <KirkMessage
                type="greeting"
                mood={riskLevel}
                content={
                  claudeAnalysis?.summary ??
                  `I've completed my analysis of claim ${result?.claim_id ?? 'unknown'}. Here's what I found.`
                }
                delay={0}
              />

              {/* Risk Score Context */}
              <KirkMessage
                type="summary"
                mood={riskLevel}
                content={`This claim has a fraud risk score of ${(result.fraud_score * 100).toFixed(0)}%, which places it in the ${riskLevel.toUpperCase()} risk category. ${
                  result.decision_mode === 'soft_hold'
                    ? 'I recommend a manual review before processing.'
                    : result.decision_mode === 'recommendation'
                    ? 'Some concerns warrant attention.'
                    : result.decision_mode === 'auto_approve'
                    ? 'This appears to be a clean claim.'
                    : 'Standard processing applies.'
                }`}
                delay={1}
              />

              {/* Rule Hit Findings */}
              {result.rule_hits.length > 0 && (
                <>
                  <div className="pt-2">
                    <span className="text-xs text-navy-500 uppercase tracking-wider font-medium">
                      Findings ({result.rule_hits.length})
                    </span>
                  </div>
                  {result.rule_hits.slice(0, MAX_DISPLAYED_HITS).map((hit: RuleHit, i: number) => (
                    <KirkMessage
                      key={`${hit.rule_id}-${i}`}
                      type="finding"
                      severity={hit.severity}
                      content={hit.description}
                      metadata={{
                        ruleType: getRuleTypeLabel(hit),
                        code: hit.affected_codes?.join(', '),
                      }}
                      delay={i + 2}
                    />
                  ))}
                  {result.rule_hits.length > MAX_DISPLAYED_HITS && (
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="text-xs text-navy-500 text-center py-2"
                    >
                      + {result.rule_hits.length - MAX_DISPLAYED_HITS} more findings
                    </motion.p>
                  )}
                </>
              )}

              {/* Recommendations */}
              {claudeAnalysis?.recommendations &&
                claudeAnalysis.recommendations.length > 0 && (
                  <>
                    <div className="pt-2">
                      <span className="text-xs text-navy-500 uppercase tracking-wider font-medium">
                        Recommendations
                      </span>
                    </div>
                    {claudeAnalysis.recommendations.map((rec: string, i: number) => (
                      <KirkMessage
                        key={i}
                        type="recommendation"
                        content={rec}
                        delay={result.rule_hits.length + i + 3}
                      />
                    ))}
                  </>
                )}

              {/* ROI Indicator */}
              {result.roi_estimate && result.roi_estimate > 0 && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.8 }}
                  className="mt-4 p-4 rounded-xl bg-gradient-to-r from-teal/10 to-risk-safe/10 border border-teal/20"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-navy-300">
                      Potential Recovery
                    </span>
                    <span className="text-lg font-semibold text-teal">
                      ${result.roi_estimate.toLocaleString()}
                    </span>
                  </div>
                </motion.div>
              )}
            </div>
          )}
        </AnimatePresence>
      </div>

      {/* Future: Input for follow-up questions */}
      <div className="p-3 border-t border-navy-700/50">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-navy-800/50 border border-navy-700/50">
          <label htmlFor="kirk-followup" className="sr-only">
            Ask Kirk a follow-up question
          </label>
          <input
            id="kirk-followup"
            type="text"
            placeholder="Ask Kirk a follow-up question..."
            disabled
            aria-disabled="true"
            aria-describedby="kirk-followup-note"
            className="flex-1 bg-transparent text-sm text-navy-300 placeholder:text-navy-600 focus:outline-none disabled:cursor-not-allowed"
          />
          <span id="kirk-followup-note" className="text-xs text-navy-600">
            Coming soon
          </span>
        </div>
      </div>
    </div>
  );
}
