import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  FileSearch,
  History,
  BookOpen,
  Shield,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState } from 'react';

const navItems = [
  {
    to: '/',
    icon: LayoutDashboard,
    label: 'Dashboard',
    description: 'System overview',
  },
  {
    to: '/analyze',
    icon: FileSearch,
    label: 'Analyze Claim',
    description: 'Submit for review',
  },
  {
    to: '/claims',
    icon: History,
    label: 'Claims History',
    description: 'Past analyses',
  },
  {
    to: '/search',
    icon: BookOpen,
    label: 'Policy Search',
    description: 'RAG knowledge base',
  },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 72 : 256 }}
      className={cn(
        'fixed left-0 top-0 h-screen z-40',
        'bg-navy-900 border-r border-navy-700/50',
        'flex flex-col',
        'transition-all duration-300'
      )}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-navy-700/50">
        <motion.div
          className="flex items-center gap-3"
          animate={{ opacity: 1 }}
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-kirk to-electric flex items-center justify-center shadow-lg shadow-kirk/20">
            <Shield className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              className="flex flex-col"
            >
              <span className="font-semibold text-white text-sm tracking-tight">
                Payment Integrity
              </span>
              <span className="text-xs text-navy-400">
                Healthcare AI
              </span>
            </motion.div>
          )}
        </motion.div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-3 px-3 py-2.5 rounded-lg',
                'transition-all duration-200',
                'hover:bg-navy-800/50',
                isActive
                  ? 'bg-kirk/10 text-kirk border border-kirk/20'
                  : 'text-navy-400 hover:text-white border border-transparent'
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  className={cn(
                    'w-5 h-5 flex-shrink-0 transition-colors',
                    isActive ? 'text-kirk' : 'text-navy-500 group-hover:text-kirk-light'
                  )}
                />
                {!collapsed && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex flex-col min-w-0"
                  >
                    <span className="text-sm font-medium truncate">
                      {item.label}
                    </span>
                    <span className="text-xs text-navy-500 truncate">
                      {item.description}
                    </span>
                  </motion.div>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Collapse Toggle */}
      <div className="p-3 border-t border-navy-700/50">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={cn(
            'w-full flex items-center justify-center gap-2 px-3 py-2',
            'rounded-lg text-navy-400 hover:text-white',
            'hover:bg-navy-800/50 transition-colors',
            'text-sm'
          )}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </motion.aside>
  );
}
