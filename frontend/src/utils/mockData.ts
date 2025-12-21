/**
 * Mock data for demo mode.
 * Provides realistic-looking data for presentations and demos.
 * Data is generated dynamically based on current date.
 */

// Helper to get month name
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Helper to format date as YYYY-MM-DD
function formatDate(date: Date): string {
  return date.toISOString().split('T')[0];
}

// Generate last N months ending with current month
function generateMonthlyTrend(months: number = 12): Array<{ month: string; savings: number; claims: number }> {
  const now = new Date();
  const result = [];

  // Base values with slight randomization for realistic variation
  const baseSavings = 400000;
  const baseClaims = 500;

  for (let i = months - 1; i >= 0; i--) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const monthName = MONTH_NAMES[date.getMonth()];

    // Add realistic variation: trending upward with seasonal fluctuation
    const trendFactor = 1 + (months - i - 1) * 0.02;
    const seasonalFactor = 1 + Math.sin((date.getMonth() / 12) * Math.PI * 2) * 0.1;

    result.push({
      month: monthName,
      savings: Math.round(baseSavings * trendFactor * seasonalFactor),
      claims: Math.round(baseClaims * trendFactor * seasonalFactor),
    });
  }

  return result;
}

export const DEMO_STATS = {
  claimsAnalyzed: 5432,
  flagsDetected: 1247,
  autoApproved: 4185,
  potentialSavings: 4200000,
  avgProcessingTime: 2.3,
  accuracyRate: 94.7,
};

// Generate dynamic savings trend based on current date
export const DEMO_SAVINGS_TREND = generateMonthlyTrend(12);

export const DEMO_CATEGORY_DATA = [
  { name: 'NCCI Edits', value: 324, color: '#8B5CF6' },
  { name: 'Coverage Issues', value: 278, color: '#06B6D4' },
  { name: 'Provider Flags', value: 198, color: '#F59E0B' },
  { name: 'Financial Outliers', value: 245, color: '#EF4444' },
  { name: 'Duplicates', value: 112, color: '#10B981' },
  { name: 'Modifier Issues', value: 90, color: '#6366F1' },
];

export const DEMO_RULE_DISTRIBUTION = [
  { rule: 'NCCI_PTP', count: 156, severity: 'critical' },
  { rule: 'NCCI_MUE', count: 168, severity: 'high' },
  { rule: 'LCD_MISMATCH', count: 145, severity: 'high' },
  { rule: 'HIGH_DOLLAR', count: 134, severity: 'medium' },
  { rule: 'REIMB_OUTLIER', count: 111, severity: 'medium' },
  { rule: 'OIG_EXCLUSION', count: 23, severity: 'critical' },
  { rule: 'DUPLICATE_LINE', count: 112, severity: 'medium' },
  { rule: 'FWA_WATCH', count: 67, severity: 'high' },
];

// Generate recent claims with dates relative to today
function generateRecentClaims(): Array<{
  id: string;
  date: string;
  provider: string;
  amount: number;
  score: number;
  decision: string;
  flags: string[];
}> {
  const now = new Date();
  const year = now.getFullYear();

  // Sample data with relative days
  const claimTemplates = [
    { daysAgo: 0, provider: 'ABC Medical Group', amount: 12450.00, score: 0.78, decision: 'soft_hold', flags: ['NCCI_PTP', 'HIGH_DOLLAR'] },
    { daysAgo: 0, provider: 'XYZ Healthcare', amount: 3200.00, score: 0.92, decision: 'auto_approve', flags: [] },
    { daysAgo: 1, provider: 'City Hospital', amount: 45600.00, score: 0.45, decision: 'recommendation', flags: ['OIG_EXCLUSION', 'HIGH_DOLLAR', 'REIMB_OUTLIER'] },
    { daysAgo: 1, provider: 'Regional Clinic', amount: 890.00, score: 0.95, decision: 'auto_approve_fast', flags: [] },
    { daysAgo: 2, provider: 'Specialty Care Inc', amount: 8750.00, score: 0.62, decision: 'recommendation', flags: ['LCD_MISMATCH', 'MODIFIER_59_ABUSE'] },
  ];

  return claimTemplates.map((template, idx) => {
    const claimDate = new Date(now);
    claimDate.setDate(claimDate.getDate() - template.daysAgo);
    return {
      id: `CLM-${year}-${String(1234 + idx).padStart(6, '0')}`,
      date: formatDate(claimDate),
      provider: template.provider,
      amount: template.amount,
      score: template.score,
      decision: template.decision,
      flags: template.flags,
    };
  });
}

export const DEMO_RECENT_CLAIMS = generateRecentClaims();

// Generate system status with dynamic timestamp
function generateSystemStatus(): {
  backendStatus: string;
  ragDocuments: number;
  ncciRules: number;
  uptime: string;
  lastUpdate: string;
  apiLatency: string;
} {
  // Set lastUpdate to a few minutes ago
  const lastUpdate = new Date();
  lastUpdate.setMinutes(lastUpdate.getMinutes() - 5);

  return {
    backendStatus: 'healthy',
    ragDocuments: 247,
    ncciRules: 56,
    uptime: '99.9%',
    lastUpdate: lastUpdate.toISOString(),
    apiLatency: '145ms',
  };
}

export const DEMO_SYSTEM_STATUS = generateSystemStatus();

// Format currency for display
export function formatCurrency(value: number): string {
  if (value >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(0)}K`;
  }
  return `$${value.toFixed(0)}`;
}

// Format percentage for display
export function formatPercentage(value: number): string {
  return `${value.toFixed(1)}%`;
}
