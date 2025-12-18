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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
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
