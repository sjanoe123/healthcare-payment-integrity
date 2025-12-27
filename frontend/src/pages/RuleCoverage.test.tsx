import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import RuleCoverage from './RuleCoverage';

// Mock the API client
vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from '@/api/client';

const mockApiGet = vi.mocked(api.get);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

const mockRuleStats = {
  total_claims_analyzed: 150,
  total_rule_hits: 320,
  average_rules_per_claim: 2.13,
  rules_by_frequency: [
    { rule_id: 'NCCI_PTP', count: 45, percentage: 30 },
    { rule_id: 'LCD_MISMATCH', count: 38, percentage: 25.3 },
    { rule_id: 'HIGH_DOLLAR', count: 25, percentage: 16.7 },
  ],
  rules_by_type: {
    billing: 85,
    coverage: 55,
    financial: 40,
  },
  rules_by_severity: {
    high: 45,
    medium: 60,
    low: 25,
  },
};

const mockCoverageStats = {
  total_claims: 150,
  field_coverage: [
    { field: 'procedure_code', present: 148, missing: 2, coverage_pct: 98.7 },
    { field: 'diagnosis_code', present: 145, missing: 5, coverage_pct: 96.7 },
    { field: 'billing_npi', present: 140, missing: 10, coverage_pct: 93.3 },
    { field: 'patient_dob', present: 100, missing: 50, coverage_pct: 66.7 },
  ],
  coverage_score: 88.5,
};

const mockEffectivenessStats = {
  rules: [
    {
      rule_id: 'NCCI_PTP',
      times_fired: 45,
      avg_weight: -0.15,
      total_weight_contribution: -6.75,
      avg_claim_score: 0.72,
    },
    {
      rule_id: 'LCD_MISMATCH',
      times_fired: 38,
      avg_weight: -0.1,
      total_weight_contribution: -3.8,
      avg_claim_score: 0.65,
    },
  ],
  total_rules_fired: 83,
};

describe('RuleCoverage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    mockApiGet.mockImplementation((url) => {
      if (url === '/api/rules/stats') {
        return Promise.resolve({ data: mockRuleStats });
      }
      if (url === '/api/rules/coverage') {
        return Promise.resolve({ data: mockCoverageStats });
      }
      if (url === '/api/rules/effectiveness') {
        return Promise.resolve({ data: mockEffectivenessStats });
      }
      return Promise.reject(new Error('Unknown endpoint'));
    });
  });

  it('renders the page header', async () => {
    render(<RuleCoverage />, { wrapper: createWrapper() });

    expect(screen.getByText('Rule Coverage Dashboard')).toBeInTheDocument();
  });

  it('fetches rule stats on mount', async () => {
    render(<RuleCoverage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/api/rules/stats');
    });
  });

  it('shows loading state initially', () => {
    // Delay the API response
    mockApiGet.mockImplementation(() => new Promise(() => {}));

    render(<RuleCoverage />, { wrapper: createWrapper() });

    expect(screen.getByText('Loading rule statistics...')).toBeInTheDocument();
  });

  it('displays rule data after loading', async () => {
    render(<RuleCoverage />, { wrapper: createWrapper() });

    // Wait for data to load and display
    await waitFor(() => {
      expect(screen.getByText('NCCI_PTP')).toBeInTheDocument();
    });
  });

  it('shows empty state when no claims analyzed', async () => {
    mockApiGet.mockImplementation((url) => {
      if (url === '/api/rules/stats') {
        return Promise.resolve({
          data: {
            total_claims_analyzed: 0,
            total_rule_hits: 0,
            average_rules_per_claim: 0,
            rules_by_frequency: [],
            rules_by_type: {},
            rules_by_severity: {},
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    render(<RuleCoverage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No Analysis Data Yet')).toBeInTheDocument();
    });
  });

  it('has tab navigation buttons', async () => {
    render(<RuleCoverage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalled();
    });

    // Check for tab buttons using role to avoid duplicate text matches
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Rule Frequency/i })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /Field Coverage/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Rule Effectiveness/i })).toBeInTheDocument();
  });

  it('displays rule types in the frequency tab', async () => {
    render(<RuleCoverage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Check for rule type chips - they render as "type: count" format
      expect(screen.getByText('billing: 85')).toBeInTheDocument();
    });
  });
});
