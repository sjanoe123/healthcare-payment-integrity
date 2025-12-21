import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { KirkAvatar } from './KirkAvatar';
import { KirkMessage } from './KirkMessage';
import { KirkThinking } from './KirkThinking';
import { MessageSquare, Sparkles, Send } from 'lucide-react';
import type { AnalysisResult, RuleHit } from '@/api/types';
import { getRiskLevel } from '@/api/types';

/** Maximum number of rule hits to display in the chat */
const MAX_DISPLAYED_HITS = 5;

interface FollowUpMessage {
  id: string;
  type: 'user' | 'kirk';
  content: string;
  timestamp: Date;
}

interface KirkChatProps {
  result?: AnalysisResult | null;
  isLoading?: boolean;
  className?: string;
  onFollowUp?: (question: string, result: AnalysisResult) => Promise<string>;
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

function generateKirkResponse(question: string, result: AnalysisResult): string {
  const q = question.toLowerCase();

  // Context-aware responses based on the analysis
  if (q.includes('why') && (q.includes('flag') || q.includes('score') || q.includes('risk'))) {
    const hitCount = result.rule_hits.length;
    const topHits = result.rule_hits.slice(0, 3).map(h => h.rule_id).join(', ');
    return `The claim received a ${(result.fraud_score * 100).toFixed(0)}% risk score primarily due to ${hitCount} rule violations detected. The most significant flags are: ${topHits}. Each rule has a weighted impact on the final score.`;
  }

  if (q.includes('recommend') || q.includes('should') || q.includes('next step')) {
    if (result.decision_mode === 'soft_hold') {
      return `For this claim, I recommend: 1) Verify the provider credentials with the primary source, 2) Request additional documentation for the flagged procedures, 3) Review the claim against local coverage determinations. Given the elevated risk score, a supervisor review before approval would be prudent.`;
    }
    return `Based on my analysis, the standard processing workflow applies. Ensure all required documentation is present and verify the patient eligibility status before final adjudication.`;
  }

  if (q.includes('ncci') || q.includes('ptp') || q.includes('mue')) {
    const ncciHits = result.rule_hits.filter(h => h.rule_id.includes('NCCI'));
    if (ncciHits.length > 0) {
      return `The NCCI edits flagged on this claim indicate potential bundling or unit limit violations. ${ncciHits[0].description}. These are based on CMS NCCI policy guidelines and require verification that proper modifiers are applied if the services were truly distinct.`;
    }
    return `No NCCI-related violations were detected on this claim. The procedure codes passed both PTP (Procedure-to-Procedure) and MUE (Medically Unlikely Edit) validation.`;
  }

  if (q.includes('appeal') || q.includes('deny') || q.includes('reject')) {
    return `If this claim is denied, the provider may submit an appeal with supporting documentation. Key elements for appeal include: 1) Operative notes demonstrating medical necessity, 2) Documentation of distinct procedures if modifier 59 was used, 3) Letter of medical necessity from the treating physician. The appeal must be filed within the timely filing limits.`;
  }

  if (q.includes('provider') || q.includes('oig') || q.includes('exclusion')) {
    const providerFlags = result.provider_flags;
    if (providerFlags.length > 0) {
      return `Provider concerns were flagged: ${providerFlags.join(', ')}. OIG exclusion screening is critical - billing by an excluded provider can result in Civil Monetary Penalties and program exclusion. Verify the provider's status in the LEIE database.`;
    }
    return `No provider-level concerns were identified. The rendering provider passed OIG exclusion screening and credential verification checks.`;
  }

  // Default contextual response
  return `Based on my analysis of claim ${result.claim_id}, the key consideration is the ${result.decision_mode.replace('_', ' ')} recommendation. The ${result.rule_hits.length} detected findings should be addressed according to your organization's compliance protocols. Would you like me to elaborate on any specific finding?`;
}

export function KirkChat({ result, isLoading = false, className, onFollowUp }: KirkChatProps) {
  const riskLevel = result ? getRiskLevel(result.fraud_score) : 'neutral';
  const claudeAnalysis = result?.claude_analysis;

  const [followUpMessages, setFollowUpMessages] = useState<FollowUpMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Clear follow-up messages and input when a new result is loaded
  useEffect(() => {
    setFollowUpMessages([]);
    setInputValue('');
  }, [result?.claim_id]);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [followUpMessages, isThinking]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!inputValue.trim() || !result || isThinking) return;

    const userMessage: FollowUpMessage = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setFollowUpMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsThinking(true);

    try {
      let response: string;

      if (onFollowUp) {
        // Use the provided callback for API-based responses
        response = await onFollowUp(userMessage.content, result);
      } else {
        // Use local response generation
        await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 1000));
        response = generateKirkResponse(userMessage.content, result);
      }

      const kirkMessage: FollowUpMessage = {
        id: `kirk-${Date.now()}`,
        type: 'kirk',
        content: response,
        timestamp: new Date(),
      };

      setFollowUpMessages(prev => [...prev, kirkMessage]);
    } catch (error) {
      // Log the error for debugging
      console.error('Kirk follow-up error:', error);

      const errorMessage: FollowUpMessage = {
        id: `kirk-error-${Date.now()}`,
        type: 'kirk',
        content: "I apologize, but I encountered an issue processing your question. Please try again or rephrase your query.",
        timestamp: new Date(),
      };
      setFollowUpMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsThinking(false);
    }
  };

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

              {/* Follow-up Messages */}
              {followUpMessages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    'p-3 rounded-xl',
                    msg.type === 'user'
                      ? 'bg-electric/10 border border-electric/20 ml-8'
                      : 'bg-navy-800/50 border border-navy-700/50'
                  )}
                >
                  {msg.type === 'kirk' && (
                    <div className="flex items-center gap-2 mb-2">
                      <KirkAvatar size="sm" mood="neutral" />
                      <span className="text-xs font-medium text-kirk">Kirk</span>
                    </div>
                  )}
                  {msg.type === 'user' && (
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-medium text-electric">You</span>
                    </div>
                  )}
                  <p className="text-sm text-navy-200 leading-relaxed">{msg.content}</p>
                </motion.div>
              ))}

              {/* Thinking indicator for follow-up */}
              {isThinking && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 p-3"
                >
                  <KirkAvatar size="sm" mood="neutral" />
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-kirk rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-kirk rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-kirk rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </motion.div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </AnimatePresence>
      </div>

      {/* Follow-up Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-navy-700/50">
        <div className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg',
          'bg-navy-800/50 border',
          result ? 'border-navy-700/50 focus-within:border-kirk/50' : 'border-navy-700/30',
          'transition-colors'
        )}>
          <label htmlFor="kirk-followup" className="sr-only">
            Ask Kirk a follow-up question
          </label>
          <input
            ref={inputRef}
            id="kirk-followup"
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={result ? "Ask Kirk a follow-up question..." : "Submit a claim first..."}
            disabled={!result || isThinking}
            aria-disabled={!result || isThinking}
            className={cn(
              'flex-1 bg-transparent text-sm text-navy-200 placeholder:text-navy-500',
              'focus:outline-none disabled:cursor-not-allowed disabled:opacity-50'
            )}
          />
          <button
            type="submit"
            disabled={!result || !inputValue.trim() || isThinking}
            className={cn(
              'p-1.5 rounded-md transition-all',
              result && inputValue.trim() && !isThinking
                ? 'text-kirk hover:bg-kirk/10'
                : 'text-navy-600 cursor-not-allowed'
            )}
            aria-label="Send message"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
