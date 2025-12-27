import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SampleAnalysis } from './SampleAnalysis';

// Mock the API client
vi.mock('@/api/client', () => ({
  api: {
    post: vi.fn(),
  },
}));

import { api } from '@/api/client';

const mockApiPost = vi.mocked(api.post);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('SampleAnalysis', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('when sync not completed', () => {
    it('shows disabled state', () => {
      render(
        <SampleAnalysis
          connectorId="test-123"
          connectorName="Test Connector"
          hasCompletedSync={false}
        />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText('Sample Analysis')).toBeInTheDocument();
      expect(screen.getByText('Complete a sync first to analyze sample claims')).toBeInTheDocument();
      expect(screen.queryByText('Run Analysis')).not.toBeInTheDocument();
    });
  });

  describe('when sync completed', () => {
    it('shows run analysis button', () => {
      render(
        <SampleAnalysis
          connectorId="test-123"
          connectorName="Test Connector"
          hasCompletedSync={true}
        />,
        { wrapper: createWrapper() }
      );

      expect(screen.getByText('Run Analysis')).toBeInTheDocument();
    });

    it('calls API when run analysis clicked', async () => {
      const user = userEvent.setup();

      mockApiPost.mockResolvedValueOnce({
        data: {
          connector_id: 'test-123',
          connector_name: 'Test Connector',
          status: 'completed',
          preview_mode: true,
          sample_size: 5,
          last_sync_at: '2024-01-15T10:00:00Z',
          summary: {
            high_risk: 2,
            medium_risk: 2,
            low_risk: 1,
            total_flags: 8,
            avg_score: 0.55,
          },
          results: [
            {
              claim_id: 'PREVIEW-test-001',
              fraud_score: 0.85,
              risk_level: 'high',
              flags_count: 3,
              top_flags: ['NCCI_CONFLICT', 'LCD_MISMATCH'],
            },
          ],
          message: 'Preview: Showing sample fraud detection results.',
        },
      });

      render(
        <SampleAnalysis
          connectorId="test-123"
          connectorName="Test Connector"
          hasCompletedSync={true}
        />,
        { wrapper: createWrapper() }
      );

      await user.click(screen.getByText('Run Analysis'));

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalledWith(
          '/api/connectors/test-123/sample-analysis',
          null,
          { params: { sample_size: 10 } }
        );
      });
    });

    it('displays results after analysis', async () => {
      const user = userEvent.setup();

      mockApiPost.mockResolvedValueOnce({
        data: {
          connector_id: 'test-123',
          connector_name: 'Test Connector',
          status: 'completed',
          preview_mode: false,
          sample_size: 3,
          last_sync_at: '2024-01-15T10:00:00Z',
          summary: {
            high_risk: 1,
            medium_risk: 1,
            low_risk: 1,
            total_flags: 5,
            avg_score: 0.5,
          },
          results: [
            {
              claim_id: 'CLAIM-001',
              fraud_score: 0.8,
              risk_level: 'high',
              flags_count: 2,
              top_flags: ['NCCI_CONFLICT'],
            },
            {
              claim_id: 'CLAIM-002',
              fraud_score: 0.5,
              risk_level: 'medium',
              flags_count: 2,
              top_flags: ['LCD_MISMATCH'],
            },
            {
              claim_id: 'CLAIM-003',
              fraud_score: 0.3,
              risk_level: 'low',
              flags_count: 1,
              top_flags: ['HIGH_DOLLAR'],
            },
          ],
          message: 'Analyzed 3 claims. 1 high-risk claims detected.',
        },
      });

      render(
        <SampleAnalysis
          connectorId="test-123"
          connectorName="Test Connector"
          hasCompletedSync={true}
        />,
        { wrapper: createWrapper() }
      );

      await user.click(screen.getByText('Run Analysis'));

      await waitFor(() => {
        expect(screen.getByText('3 claims from Test Connector')).toBeInTheDocument();
      });

      // Check summary cards
      expect(screen.getByText('High Risk')).toBeInTheDocument();
      expect(screen.getByText('Medium Risk')).toBeInTheDocument();
      expect(screen.getByText('Low Risk')).toBeInTheDocument();
      expect(screen.getByText('Total Flags')).toBeInTheDocument();
    });

    it('shows preview mode indicator when in preview', async () => {
      const user = userEvent.setup();

      mockApiPost.mockResolvedValueOnce({
        data: {
          connector_id: 'test-123',
          connector_name: 'Test Connector',
          status: 'completed',
          preview_mode: true,
          sample_size: 5,
          last_sync_at: '2024-01-15T10:00:00Z',
          summary: {
            high_risk: 2,
            medium_risk: 2,
            low_risk: 1,
            total_flags: 8,
            avg_score: 0.55,
          },
          results: [],
          message: 'Preview: Showing sample fraud detection results.',
        },
      });

      render(
        <SampleAnalysis
          connectorId="test-123"
          connectorName="Test Connector"
          hasCompletedSync={true}
        />,
        { wrapper: createWrapper() }
      );

      await user.click(screen.getByText('Run Analysis'));

      await waitFor(() => {
        expect(screen.getByText('Preview')).toBeInTheDocument();
        expect(screen.getByText('Preview for Test Connector')).toBeInTheDocument();
      });
    });

    it('shows error state when API fails', async () => {
      const user = userEvent.setup();

      mockApiPost.mockRejectedValueOnce(new Error('API Error'));

      render(
        <SampleAnalysis
          connectorId="test-123"
          connectorName="Test Connector"
          hasCompletedSync={true}
        />,
        { wrapper: createWrapper() }
      );

      await user.click(screen.getByText('Run Analysis'));

      await waitFor(() => {
        expect(screen.getByText('Failed to analyze samples. Please try again.')).toBeInTheDocument();
      });
    });
  });
});
