import { createContext, useContext } from 'react';

export interface LayoutContextType {
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const LayoutContext = createContext<LayoutContextType>({
  sidebarCollapsed: false,
  setSidebarCollapsed: () => {},
});

export function useLayout() {
  return useContext(LayoutContext);
}
