/**
 * Shared form styling utilities for consistent dark theme forms.
 *
 * These classes ensure WCAG AA contrast compliance on navy-900 backgrounds.
 */

/** Base input classes for text inputs, textareas, and number inputs */
export const inputClasses =
  'w-full px-3 py-2 border border-navy-600 rounded-lg bg-navy-900/50 text-white placeholder-navy-500 focus:ring-2 focus:ring-kirk focus:border-kirk';

/** Select element classes */
export const selectClasses =
  'w-full px-3 py-2 border border-navy-600 rounded-lg bg-navy-900/50 text-white focus:ring-2 focus:ring-kirk focus:border-kirk';

/** Checkbox classes */
export const checkboxClasses =
  'w-4 h-4 text-kirk border-navy-600 rounded bg-navy-900/50 focus:ring-kirk focus:ring-2';

/** Helper/hint text below form fields - uses navy-400 for WCAG AA contrast */
export const helperTextClasses = 'text-xs text-navy-400 mt-1';

/** Form label classes */
export const labelClasses = 'block text-sm font-medium text-navy-200 mb-1';

/** Section header within forms */
export const sectionHeaderClasses = 'font-medium text-white';

/** Error message text */
export const errorTextClasses = 'text-sm text-risk-critical mt-1';

/** Primary button classes */
export const primaryButtonClasses =
  'px-4 py-2 bg-gradient-to-r from-kirk to-electric text-white rounded-lg hover:shadow-lg hover:shadow-kirk/25 transition-all disabled:opacity-50';

/** Secondary button classes */
export const secondaryButtonClasses =
  'px-4 py-2 bg-navy-800 text-navy-300 border border-navy-600 rounded-lg hover:bg-navy-700 hover:text-white transition-colors disabled:opacity-50';

/** Ghost/text button classes */
export const ghostButtonClasses =
  'px-4 py-2 text-navy-400 hover:text-white transition-colors';

/** Card/panel container classes */
export const cardClasses =
  'bg-navy-800/50 rounded-xl border border-navy-700/50';

/** Form section divider */
export const dividerClasses = 'border-t border-navy-700/50 pt-4 mt-4';
