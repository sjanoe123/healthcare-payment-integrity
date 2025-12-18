import { Outlet } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { LayoutContext } from './LayoutContext';

export function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <LayoutContext.Provider value={{ sidebarCollapsed, setSidebarCollapsed }}>
      <div className="min-h-screen bg-navy-900">
        {/* Background gradient effects */}
        <div className="fixed inset-0 pointer-events-none overflow-hidden">
          <div className="absolute -top-1/2 -right-1/4 w-[800px] h-[800px] rounded-full bg-kirk/5 blur-[120px]" />
          <div className="absolute -bottom-1/2 -left-1/4 w-[600px] h-[600px] rounded-full bg-electric/5 blur-[100px]" />
        </div>

        {/* Sidebar */}
        <Sidebar />

        {/* Header */}
        <Header sidebarCollapsed={sidebarCollapsed} />

        {/* Main Content */}
        <motion.main
          className={cn(
            'pt-20 pb-8 px-8 min-h-screen',
            'transition-all duration-300',
            sidebarCollapsed ? 'ml-[72px]' : 'ml-64'
          )}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Outlet />
        </motion.main>
      </div>
    </LayoutContext.Provider>
  );
}
