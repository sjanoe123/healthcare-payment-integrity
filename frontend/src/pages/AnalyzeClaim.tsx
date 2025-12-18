import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useAnalyzeClaim } from '@/api/hooks/useAnalyzeClaim';
import { getErrorMessage } from '@/api/client';
import { validateClaimJson } from '@/api/validation';
import { KirkChat } from '@/components/kirk';
import { FraudScoreGauge, DecisionModeBadge, RuleHitsPanel } from '@/components/analysis';
import { sampleClaims } from '@/utils/sampleClaims';
import type { AnalysisResult, ClaimSubmission } from '@/api/types';
import {
  Play,
  FileJson,
  Beaker,
  AlertCircle,
  CheckCircle,
  Loader2,
} from 'lucide-react';

export function AnalyzeClaim() {
  const [claimJson, setClaimJson] = useState('');
  const [parseError, setParseError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const { mutate: analyze, isPending } = useAnalyzeClaim();

  const handleSubmit = () => {
    setParseError(null);

    // Validate JSON with Zod schema
    const validationResult = validateClaimJson(claimJson);

    if (!validationResult.success) {
      setParseError(validationResult.error);
      return;
    }

    const claim: ClaimSubmission = validationResult.data;

    analyze(claim, {
      onSuccess: (data: AnalysisResult) => {
        setResult(data);
      },
      onError: (error: unknown) => {
        // Use safe error message handler
        const userMessage = getErrorMessage(error);
        setParseError(userMessage);
      },
    });
  };

  const loadSampleClaim = (claim: ClaimSubmission) => {
    setClaimJson(JSON.stringify(claim, null, 2));
    setParseError(null);
    setResult(null);
  };

  return (
    <div className="h-[calc(100vh-6rem)]">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
        {/* Left Panel - Input & Results */}
        <div className="lg:col-span-2 flex flex-col space-y-6 overflow-y-auto pr-2">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <h1 className="text-2xl font-bold text-white mb-2">
              Analyze Claim
            </h1>
            <p className="text-navy-400">
              Submit a healthcare claim for comprehensive compliance analysis
            </p>
          </motion.div>

          {/* Sample Claims */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="flex flex-wrap gap-2"
          >
            <span className="flex items-center gap-2 text-sm text-navy-400 mr-2">
              <Beaker className="w-4 h-4" aria-hidden="true" />
              Demo claims:
            </span>
            {sampleClaims.map((sample) => (
              <button
                key={sample.name}
                onClick={() => loadSampleClaim(sample.claim)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-sm',
                  'bg-navy-800/50 border border-navy-700/50',
                  'text-navy-300 hover:text-white hover:border-kirk/30',
                  'transition-colors'
                )}
                title={sample.description}
                aria-label={`Load ${sample.name} demo claim: ${sample.description}`}
              >
                {sample.name}
              </button>
            ))}
          </motion.div>

          {/* JSON Input */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="flex-shrink-0"
          >
            <div className="flex items-center justify-between mb-2">
              <label
                htmlFor="claim-json-input"
                className="flex items-center gap-2 text-sm font-medium text-navy-300"
              >
                <FileJson className="w-4 h-4" aria-hidden="true" />
                Claim JSON
              </label>
              {parseError && (
                <span
                  className="flex items-center gap-1 text-sm text-risk-critical"
                  role="alert"
                  aria-live="polite"
                >
                  <AlertCircle className="w-4 h-4" aria-hidden="true" />
                  {parseError}
                </span>
              )}
            </div>
            <textarea
              id="claim-json-input"
              value={claimJson}
              onChange={(e) => {
                setClaimJson(e.target.value);
                setParseError(null);
              }}
              placeholder='{\n  "claim_id": "TEST-001",\n  "patient_id": "PT-1234",\n  "provider_npi": "1234567890",\n  ...\n}'
              aria-invalid={parseError ? 'true' : 'false'}
              aria-describedby={parseError ? 'claim-error' : undefined}
              className={cn(
                'w-full h-48 p-4 rounded-xl',
                'bg-navy-900/50 border',
                parseError ? 'border-risk-critical/50' : 'border-navy-700/50',
                'text-sm font-mono text-navy-200',
                'placeholder:text-navy-600',
                'focus:outline-none focus:border-kirk/50',
                'resize-none'
              )}
            />
            <button
              onClick={handleSubmit}
              disabled={!claimJson.trim() || isPending}
              aria-busy={isPending}
              className={cn(
                'mt-4 w-full flex items-center justify-center gap-2',
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
                  <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" aria-hidden="true" />
                  Analyze Claim
                </>
              )}
            </button>
          </motion.div>

          {/* Results Section */}
          <AnimatePresence mode="wait">
            {result && (
              <motion.div
                key="results"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="flex-1 space-y-6"
                role="region"
                aria-label="Analysis Results"
              >
                {/* Score & Decision Banner */}
                <div className="p-6 rounded-2xl bg-navy-800/30 border border-navy-700/50">
                  <div className="flex flex-col md:flex-row items-center gap-6">
                    <FraudScoreGauge score={result.fraud_score} size="lg" />
                    <div className="flex-1 text-center md:text-left">
                      <h2 className="text-xl font-semibold text-white mb-2">
                        Claim: {result.claim_id}
                      </h2>
                      <DecisionModeBadge mode={result.decision_mode} size="lg" showDescription />
                      {result.roi_estimate && result.roi_estimate > 0 && (
                        <p className="mt-3 text-sm text-navy-400">
                          Potential recovery:{' '}
                          <span className="text-teal font-semibold">
                            ${result.roi_estimate.toLocaleString()}
                          </span>
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Rule Hits */}
                {result.rule_hits.length > 0 && (
                  <div className="p-6 rounded-2xl bg-navy-800/30 border border-navy-700/50">
                    <RuleHitsPanel hits={result.rule_hits} />
                  </div>
                )}

                {/* No Issues Found */}
                {result.rule_hits.length === 0 && (
                  <div className="p-8 rounded-2xl bg-risk-safe/5 border border-risk-safe/20 text-center">
                    <CheckCircle className="w-12 h-12 text-risk-safe mx-auto mb-3" aria-hidden="true" />
                    <h3 className="text-lg font-semibold text-white mb-1">
                      Clean Claim
                    </h3>
                    <p className="text-navy-400">
                      No compliance issues detected
                    </p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right Panel - Kirk Chat */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="hidden lg:block h-full rounded-2xl overflow-hidden"
          role="complementary"
          aria-label="Kirk AI Analysis Chat"
        >
          <KirkChat result={result} isLoading={isPending} className="h-full" />
        </motion.div>
      </div>
    </div>
  );
}

export default AnalyzeClaim;
