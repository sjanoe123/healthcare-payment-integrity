import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { KirkAvatar } from './KirkAvatar';
import { KirkMessage } from './KirkMessage';
import { KirkTyping } from './KirkTyping';
import { KirkThinking } from './KirkThinking';
import { MessageSquare, Sparkles } from 'lucide-react';
import type { AnalysisResult, RuleHit } from '@/api/types';
import { getRiskLevel } from '@/api/types';

interface KirkChatProps {
  result?: AnalysisResult | null;
  isLoading?: boolean;
  className?: string;
}

function getSeverityFromScore(score: number): 'low' | 'medium' | 'high' | 'critical' {
  if (score < 0.3) return 'low';
  if (score < 0.6) return 'medium';
  if (score < 0.8) return 'high';
  return 'critical';
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
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-navy-700/50">
        <KirkAvatar size="md" mood={result ? riskLevel : 'neutral'} />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">Kirk</h3>
            <Sparkles className="w-3.5 h-3.5 text-kirk" />
          </div>
          <p className="text-xs text-navy-400">AI Compliance Analyst</p>
        </div>
        <MessageSquare className="w-5 h-5 text-navy-500" />
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
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
                  claudeAnalysis?.summary ||
                  `I've completed my analysis of claim ${result.claim_id}. Here's what I found.`
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
                  {result.rule_hits.slice(0, 5).map((hit, i) => (
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
                  {result.rule_hits.length > 5 && (
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="text-xs text-navy-500 text-center py-2"
                    >
                      + {result.rule_hits.length - 5} more findings
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
                    {claudeAnalysis.recommendations.map((rec, i) => (
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
          <input
            type="text"
            placeholder="Ask Kirk a follow-up question..."
            disabled
            className="flex-1 bg-transparent text-sm text-navy-300 placeholder:text-navy-600 focus:outline-none"
          />
          <span className="text-xs text-navy-600">Coming soon</span>
        </div>
      </div>
    </div>
  );
}
