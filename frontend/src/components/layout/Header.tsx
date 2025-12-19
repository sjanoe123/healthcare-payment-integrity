import { motion } from 'framer-motion';
import { Activity, Database, Moon, Sun, Wifi, WifiOff, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useHealth } from '@/api/hooks/useHealth';
import { useState } from 'react';

interface HeaderProps {
  sidebarCollapsed?: boolean;
}

export function Header({ sidebarCollapsed = false }: HeaderProps) {
  const { data: health, isLoading, isError } = useHealth();
  const [darkMode, setDarkMode] = useState(true);

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
        'flex items-center justify-between px-6',
        'transition-all duration-300',
        sidebarCollapsed ? 'left-[72px]' : 'left-64'
      )}
    >
      {/* Page Title Area */}
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-white">
          Compliance Command Center
        </h1>
      </div>

      {/* Status Indicators */}
      <div className="flex items-center gap-4">
        {/* Backend Status */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-full',
            'bg-navy-800/50 border border-navy-700/50',
            'text-sm'
          )}
        >
          <span className={getStatusColor()}>{getStatusIcon()}</span>
          <span className="text-navy-300">
            {isLoading ? 'Connecting...' : isError ? 'Offline' : 'Connected'}
          </span>
        </motion.div>

        {/* RAG Doc Count */}
        {health?.rag_documents !== undefined && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-full',
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
