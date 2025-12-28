import { describe, it, expect, vi, beforeEach, Mock } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuditLog } from './AuditLog';
import { api } from '@/api/client';
import type { ReactNode, HTMLAttributes } from 'react';

// Mock the API client
vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
  },
}));

// Types for framer-motion mock
interface MotionProps extends HTMLAttributes<HTMLElement> {
  children?: ReactNode;
}

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: MotionProps) => <div {...props}>{children}</div>,
    tr: ({ children, ...props }: MotionProps) => <tr {...props}>{children}</tr>,
  },
  AnimatePresence: ({ children }: { children: ReactNode }) => children,
}));

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

const renderWithClient = (ui: React.ReactElement) => {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
};

// Helper to get the mocked api.get function
const mockApiGet = api.get as Mock;

describe('AuditLog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows loading spinner while fetching data', async () => {
      // Mock slow response
      mockApiGet.mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      );

      renderWithClient(<AuditLog />);

      // Use queryAllByText since there might be multiple loading elements
      const loadingElements = screen.queryAllByText(/loading/i);
      expect(loadingElements.length).toBeGreaterThan(0);
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no audit logs exist', async () => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/api/audit/stats')) {
          return Promise.resolve({
            data: {
              total_entries: 0,
              entries_by_action: {},
              entries_by_status: {},
              entries_by_user: {},
              date_range: { earliest: '', latest: '' },
            },
          });
        }
        if (url.includes('/api/audit/actions')) {
          return Promise.resolve({
            data: {
              actions: ['claim.upload', 'claim.analyze'],
              categories: { claim: ['claim.upload', 'claim.analyze'] },
            },
          });
        }
        if (url.includes('/api/audit')) {
          return Promise.resolve({
            data: {
              entries: [],
              total: 0,
              limit: 20,
              offset: 0,
              filters_applied: {},
            },
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      renderWithClient(<AuditLog />);

      await waitFor(() => {
        expect(screen.getByText(/No Audit Events/i)).toBeInTheDocument();
      });
    });
  });

  describe('With Data', () => {
    const mockLogsResponse = {
      entries: [
        {
          id: '1',
          timestamp: '2024-01-15T10:00:00Z',
          action: 'claim.upload',
          user_id: 'user1',
          user_email: 'test@example.com',
          resource_type: 'claim',
          resource_id: 'claim123',
          details: { filename: 'test.csv' },
          status: 'success',
        },
        {
          id: '2',
          timestamp: '2024-01-15T11:00:00Z',
          action: 'claim.analyze',
          user_id: 'user1',
          user_email: 'test@example.com',
          resource_type: 'claim',
          resource_id: 'claim123',
          details: null,
          status: 'error',
          error_message: 'Analysis failed',
        },
      ],
      total: 2,
      limit: 20,
      offset: 0,
      filters_applied: {},
    };

    const mockStatsResponse = {
      total_entries: 2,
      entries_by_action: { 'claim.upload': 1, 'claim.analyze': 1 },
      entries_by_status: { success: 1, error: 1 },
      entries_by_user: { user1: 2 },
      date_range: {
        earliest: '2024-01-15T10:00:00Z',
        latest: '2024-01-15T11:00:00Z',
      },
    };

    beforeEach(() => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/api/audit/stats')) {
          return Promise.resolve({ data: mockStatsResponse });
        }
        if (url.includes('/api/audit/actions')) {
          return Promise.resolve({
            data: {
              actions: ['claim.upload', 'claim.analyze'],
              categories: { claim: ['claim.upload', 'claim.analyze'] },
            },
          });
        }
        if (url.includes('/api/audit')) {
          return Promise.resolve({ data: mockLogsResponse });
        }
        return Promise.reject(new Error('Unknown URL'));
      });
    });

    it('renders audit log entries', async () => {
      renderWithClient(<AuditLog />);

      await waitFor(() => {
        // The actions appear in the ActionBadge components
        // Use getAllByText since action names also appear in the dropdown
        const uploadElements = screen.getAllByText('claim.upload');
        const analyzeElements = screen.getAllByText('claim.analyze');
        expect(uploadElements.length).toBeGreaterThan(0);
        expect(analyzeElements.length).toBeGreaterThan(0);
      });
    });

    it('shows user email in entries', async () => {
      renderWithClient(<AuditLog />);

      await waitFor(() => {
        expect(screen.getAllByText('test@example.com')).toHaveLength(2);
      });
    });

    it('shows stats cards', async () => {
      renderWithClient(<AuditLog />);

      await waitFor(() => {
        expect(screen.getByText('Total Events')).toBeInTheDocument();
        expect(screen.getByText('2')).toBeInTheDocument();
      });
    });

    it('shows success and error badges', async () => {
      renderWithClient(<AuditLog />);

      await waitFor(() => {
        expect(screen.getByText('Success')).toBeInTheDocument();
        expect(screen.getByText('Error')).toBeInTheDocument();
      });
    });
  });

  describe('Filtering', () => {
    it('renders action filter dropdown', async () => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/api/audit/stats')) {
          return Promise.resolve({
            data: {
              total_entries: 0,
              entries_by_action: {},
              entries_by_status: {},
              entries_by_user: {},
              date_range: { earliest: '', latest: '' },
            },
          });
        }
        if (url.includes('/api/audit/actions')) {
          return Promise.resolve({
            data: {
              actions: ['claim.upload', 'claim.analyze', 'connector.create'],
              categories: {},
            },
          });
        }
        if (url.includes('/api/audit')) {
          return Promise.resolve({
            data: { entries: [], total: 0, limit: 20, offset: 0, filters_applied: {} },
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      renderWithClient(<AuditLog />);

      await waitFor(() => {
        // Check for the "All Actions" option which is in the action filter dropdown
        expect(screen.getByText('All Actions')).toBeInTheDocument();
      });
    });

    it('renders status filter dropdown', async () => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/api/audit/stats')) {
          return Promise.resolve({
            data: {
              total_entries: 0,
              entries_by_action: {},
              entries_by_status: {},
              entries_by_user: {},
              date_range: { earliest: '', latest: '' },
            },
          });
        }
        if (url.includes('/api/audit/actions')) {
          return Promise.resolve({
            data: {
              actions: ['claim.upload', 'claim.analyze'],
              categories: { claim: ['claim.upload', 'claim.analyze'] },
            },
          });
        }
        if (url.includes('/api/audit')) {
          return Promise.resolve({
            data: { entries: [], total: 0, limit: 20, offset: 0, filters_applied: {} },
          });
        }
        return Promise.resolve({ data: {} });
      });

      renderWithClient(<AuditLog />);

      await waitFor(() => {
        expect(screen.getByText('All Status')).toBeInTheDocument();
      });
    });
  });

  describe('Export', () => {
    const mockStatsResponse = {
      total_entries: 0,
      entries_by_action: {},
      entries_by_status: {},
      entries_by_user: {},
      date_range: { earliest: '', latest: '' },
    };

    it('renders export buttons', async () => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/api/audit/stats')) {
          return Promise.resolve({ data: mockStatsResponse });
        }
        if (url.includes('/api/audit/actions')) {
          return Promise.resolve({
            data: {
              actions: ['claim.upload', 'claim.analyze'],
              categories: { claim: ['claim.upload', 'claim.analyze'] },
            },
          });
        }
        if (url.includes('/api/audit')) {
          return Promise.resolve({
            data: { entries: [], total: 0, limit: 20, offset: 0, filters_applied: {} },
          });
        }
        return Promise.resolve({ data: {} });
      });

      renderWithClient(<AuditLog />);

      await waitFor(() => {
        expect(screen.getByText('Export CSV')).toBeInTheDocument();
        expect(screen.getByText('Export JSON')).toBeInTheDocument();
      });
    });

    it('calls export API when CSV button clicked', async () => {
      const mockBlob = new Blob(['test'], { type: 'text/csv' });
      mockApiGet.mockImplementation((url: string, config?: { responseType?: string }) => {
        if (url.includes('/api/audit/stats')) {
          return Promise.resolve({ data: mockStatsResponse });
        }
        if (url.includes('/api/audit/actions')) {
          return Promise.resolve({
            data: {
              actions: ['claim.upload', 'claim.analyze'],
              categories: { claim: ['claim.upload', 'claim.analyze'] },
            },
          });
        }
        if (config?.responseType === 'blob') {
          return Promise.resolve({ data: mockBlob });
        }
        if (url.includes('/api/audit')) {
          return Promise.resolve({
            data: { entries: [], total: 0, limit: 20, offset: 0, filters_applied: {} },
          });
        }
        return Promise.resolve({ data: {} });
      });

      // Mock URL.createObjectURL
      global.URL.createObjectURL = vi.fn(() => 'blob:test');
      global.URL.revokeObjectURL = vi.fn();

      renderWithClient(<AuditLog />);

      await waitFor(() => {
        expect(screen.getByText('Export CSV')).toBeInTheDocument();
      });

      const csvButton = screen.getByText('Export CSV');
      fireEvent.click(csvButton);

      await waitFor(() => {
        expect(api.get).toHaveBeenCalledWith(
          expect.stringContaining('/api/audit/export'),
          expect.objectContaining({ responseType: 'blob' })
        );
      });
    });
  });

  describe('Expandable Details', () => {
    it('shows view details button for entries with details', async () => {
      const mockLogsResponse = {
        entries: [
          {
            id: '1',
            timestamp: '2024-01-15T10:00:00Z',
            action: 'claim.upload',
            user_id: 'user1',
            user_email: 'test@example.com',
            resource_type: 'claim',
            resource_id: 'claim123',
            details: { filename: 'test.csv', size: 1024 },
            status: 'success',
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
        filters_applied: {},
      };

      const mockStatsResponse = {
        total_entries: 1,
        entries_by_action: { 'claim.upload': 1 },
        entries_by_status: { success: 1 },
        entries_by_user: { user1: 1 },
        date_range: { earliest: '2024-01-15T10:00:00Z', latest: '2024-01-15T10:00:00Z' },
      };

      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/api/audit/stats')) {
          return Promise.resolve({ data: mockStatsResponse });
        }
        if (url.includes('/api/audit/actions')) {
          return Promise.resolve({
            data: {
              actions: ['claim.upload'],
              categories: { claim: ['claim.upload'] },
            },
          });
        }
        if (url.includes('/api/audit')) {
          return Promise.resolve({ data: mockLogsResponse });
        }
        return Promise.resolve({ data: {} });
      });

      renderWithClient(<AuditLog />);

      await waitFor(() => {
        expect(screen.getByText(/View details/i)).toBeInTheDocument();
      });
    });
  });

  describe('Header', () => {
    it('displays Audit Log title', async () => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/api/audit/stats')) {
          return Promise.resolve({
            data: {
              total_entries: 0,
              entries_by_action: {},
              entries_by_status: {},
              entries_by_user: {},
              date_range: { earliest: '', latest: '' },
            },
          });
        }
        if (url.includes('/api/audit/actions')) {
          return Promise.resolve({
            data: {
              actions: ['claim.upload'],
              categories: { claim: ['claim.upload'] },
            },
          });
        }
        return Promise.resolve({
          data: { entries: [], total: 0, limit: 20, offset: 0, filters_applied: {} },
        });
      });

      renderWithClient(<AuditLog />);

      expect(screen.getByText('Audit Log')).toBeInTheDocument();
    });

    it('displays HIPAA compliance description', async () => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/api/audit/stats')) {
          return Promise.resolve({
            data: {
              total_entries: 0,
              entries_by_action: {},
              entries_by_status: {},
              entries_by_user: {},
              date_range: { earliest: '', latest: '' },
            },
          });
        }
        if (url.includes('/api/audit/actions')) {
          return Promise.resolve({
            data: {
              actions: ['claim.upload'],
              categories: { claim: ['claim.upload'] },
            },
          });
        }
        return Promise.resolve({
          data: { entries: [], total: 0, limit: 20, offset: 0, filters_applied: {} },
        });
      });

      renderWithClient(<AuditLog />);

      expect(screen.getByText(/HIPAA-compliant/i)).toBeInTheDocument();
    });
  });
});
