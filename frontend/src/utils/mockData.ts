/**
 * Mock data for demo mode.
 * Provides realistic-looking data for presentations and demos.
 */

export const DEMO_STATS = {
  claimsAnalyzed: 5432,
  flagsDetected: 1247,
  autoApproved: 4185,
  potentialSavings: 4200000,
  avgProcessingTime: 2.3,
  accuracyRate: 94.7,
};

export const DEMO_SAVINGS_TREND = [
  { month: 'Jan', savings: 320000, claims: 412 },
  { month: 'Feb', savings: 380000, claims: 456 },
  { month: 'Mar', savings: 420000, claims: 489 },
  { month: 'Apr', savings: 390000, claims: 467 },
  { month: 'May', savings: 450000, claims: 512 },
  { month: 'Jun', savings: 480000, claims: 534 },
  { month: 'Jul', savings: 510000, claims: 567 },
  { month: 'Aug', savings: 490000, claims: 545 },
  { month: 'Sep', savings: 530000, claims: 589 },
  { month: 'Oct', savings: 560000, claims: 612 },
  { month: 'Nov', savings: 540000, claims: 598 },
  { month: 'Dec', savings: 570000, claims: 621 },
];

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

export const DEMO_RECENT_CLAIMS = [
  {
    id: 'CLM-2024-001234',
    date: '2024-12-19',
    provider: 'ABC Medical Group',
    amount: 12450.00,
    score: 0.78,
    decision: 'soft_hold',
    flags: ['NCCI_PTP', 'HIGH_DOLLAR'],
  },
  {
    id: 'CLM-2024-001235',
    date: '2024-12-19',
    provider: 'XYZ Healthcare',
    amount: 3200.00,
    score: 0.92,
    decision: 'auto_approve',
    flags: [],
  },
  {
    id: 'CLM-2024-001236',
    date: '2024-12-18',
    provider: 'City Hospital',
    amount: 45600.00,
    score: 0.45,
    decision: 'recommendation',
    flags: ['OIG_EXCLUSION', 'HIGH_DOLLAR', 'REIMB_OUTLIER'],
  },
  {
    id: 'CLM-2024-001237',
    date: '2024-12-18',
    provider: 'Regional Clinic',
    amount: 890.00,
    score: 0.95,
    decision: 'auto_approve_fast',
    flags: [],
  },
  {
    id: 'CLM-2024-001238',
    date: '2024-12-17',
    provider: 'Specialty Care Inc',
    amount: 8750.00,
    score: 0.62,
    decision: 'recommendation',
    flags: ['LCD_MISMATCH', 'MODIFIER_59_ABUSE'],
  },
];

export const DEMO_SYSTEM_STATUS = {
  backendStatus: 'healthy',
  ragDocuments: 247,
  ncciRules: 56,
  uptime: '99.9%',
  lastUpdate: '2024-12-19T14:30:00Z',
  apiLatency: '145ms',
};

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
