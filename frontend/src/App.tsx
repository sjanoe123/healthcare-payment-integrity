import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './components/layout';
import { Loader2 } from 'lucide-react';

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'));
const AnalyzeClaim = lazy(() => import('./pages/AnalyzeClaim'));
const ClaimHistory = lazy(() => import('./pages/ClaimHistory'));
const PolicySearch = lazy(() => import('./pages/PolicySearch'));

/**
 * React Query client configuration
 * - staleTime: Data considered fresh for 5 minutes (no background refetches)
 * - gcTime: Unused data garbage collected after 10 minutes
 * - retry: Only retry failed requests once
 * - refetchOnWindowFocus: Disabled to prevent unnecessary API calls
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes (was cacheTime)
      retry: 1,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 0, // Don't retry mutations
    },
  },
});

// Loading fallback component
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-center">
        <Loader2 className="w-8 h-8 animate-spin text-kirk mx-auto mb-3" />
        <p className="text-navy-400 text-sm">Loading...</p>
      </div>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/analyze" element={<AnalyzeClaim />} />
              <Route path="/claims" element={<ClaimHistory />} />
              <Route path="/search" element={<PolicySearch />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
