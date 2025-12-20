import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Activity, Database, Moon, Sun, Wifi, WifiOff, AlertCircle, Menu, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useHealth } from '@/api/hooks/useHealth';
import { useLayout } from './useLayout';

const DARK_MODE_KEY = 'healthcare-pi-dark-mode';

interface HeaderProps {
  sidebarCollapsed?: boolean;
}

export function Header({ sidebarCollapsed = false }: HeaderProps) {
  const { data: health, isLoading, isError } = useHealth();
  const { isMobile, setMobileMenuOpen } = useLayout();

  // Initialize dark mode from localStorage, defaulting to true
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window === 'undefined') return true;
    const saved = localStorage.getItem(DARK_MODE_KEY);
    return saved !== null ? JSON.parse(saved) : true;
  });

  // Persist dark mode preference to localStorage
  useEffect(() => {
    localStorage.setItem(DARK_MODE_KEY, JSON.stringify(darkMode));

    // Apply dark mode class to document
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  const getStatusColor = () => {
    if (isLoading) return 'text-navy-400';
    if (isError || health?.status !== 'healthy') return 'text-risk-critical';
    return 'text-risk-safe';
  };

  const getStatusIcon = () => {
    if (isLoading) return <Activity className="w-4 h-4 animate-pulse" />;
    if (isError) return <WifiOff className="w-4 h-4" />;
    if (health?.status !== 'healthy') return <AlertCircle className="w-4 h-4" />;
    return <Wifi className="w-4 h-4" />;
  };

  return (
    <header
      className={cn(
        'fixed top-0 right-0 h-16 z-30',
        'bg-navy-900/80 backdrop-blur-xl',
        'border-b border-navy-700/50',
        'flex items-center justify-between px-4 md:px-6',
        'transition-all duration-300',
        isMobile ? 'left-0' : sidebarCollapsed ? 'left-[72px]' : 'left-64'
      )}
    >
      {/* Left Side - Mobile Menu + Title */}
      <div className="flex items-center gap-3">
        {isMobile && (
          <button
            onClick={() => setMobileMenuOpen(true)}
            className={cn(
              'p-2 -ml-1 rounded-lg',
              'text-navy-400 hover:text-white',
              'hover:bg-navy-800/50',
              'transition-colors'
            )}
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}

        {isMobile && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-kirk to-electric flex items-center justify-center shadow-lg shadow-kirk/20">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-white text-sm">PI</span>
          </div>
        )}

        {!isMobile && (
          <h1 className="text-lg font-semibold text-white">
            Compliance Command Center
          </h1>
        )}
      </div>

      {/* Status Indicators */}
      <div className="flex items-center gap-2 md:gap-4">
        {/* Backend Status */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            'flex items-center gap-2 px-2 md:px-3 py-1.5 rounded-full',
            'bg-navy-800/50 border border-navy-700/50',
            'text-sm'
          )}
        >
          <span className={getStatusColor()}>{getStatusIcon()}</span>
          <span className="text-navy-300 hidden sm:inline">
            {isLoading ? 'Connecting...' : isError ? 'Offline' : 'Connected'}
          </span>
        </motion.div>

        {/* RAG Doc Count - Hidden on mobile */}
        {health?.rag_documents !== undefined && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className={cn(
              'hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full',
              'bg-navy-800/50 border border-navy-700/50',
              'text-sm'
            )}
          >
            <Database className="w-4 h-4 text-teal" />
            <span className="text-navy-300">
              {health.rag_documents.toLocaleString()} policies
            </span>
          </motion.div>
        )}

        {/* Theme Toggle */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setDarkMode(!darkMode)}
          className={cn(
            'p-2 rounded-lg',
            'bg-navy-800/50 border border-navy-700/50',
            'text-navy-400 hover:text-white',
            'transition-colors'
          )}
        >
          {darkMode ? (
            <Moon className="w-4 h-4" />
          ) : (
            <Sun className="w-4 h-4" />
          )}
        </motion.button>
      </div>
    </header>
  );
}
