import { useContext } from 'react';
import { LayoutContext } from './LayoutContext';

export function useLayout() {
  return useContext(LayoutContext);
}
