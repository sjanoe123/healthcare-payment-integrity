/**
 * Shared form styling utilities for consistent dark theme forms.
 *
 * These classes ensure WCAG AA contrast compliance on navy-900 backgrounds.
 */

/** Base input classes for text inputs, textareas, and number inputs */
export const inputClasses =
  'w-full px-3 py-2 border border-navy-600 rounded-lg bg-navy-900/50 text-white placeholder-navy-500 focus:ring-2 focus:ring-kirk focus:border-kirk';

/** Input with px-4 padding (used in some forms) */
export const inputClassesLg =
  'w-full px-4 py-2 border border-navy-600 rounded-lg bg-navy-900/50 text-white placeholder-navy-500 focus:ring-2 focus:ring-kirk focus:border-kirk';

/** Select element classes */
export const selectClasses =
  'w-full px-3 py-2 border border-navy-600 rounded-lg bg-navy-900/50 text-white focus:ring-2 focus:ring-kirk focus:border-kirk';

/** Select with px-4 padding */
export const selectClassesLg =
  'w-full px-4 py-2 border border-navy-600 rounded-lg bg-navy-900/50 text-white focus:ring-2 focus:ring-kirk focus:border-kirk';

/** Textarea classes */
export const textareaClasses =
  'w-full px-3 py-2 border border-navy-600 rounded-lg bg-navy-900/50 text-white placeholder-navy-500 focus:ring-2 focus:ring-kirk focus:border-kirk font-mono text-sm';

/** Checkbox classes */
export const checkboxClasses =
  'w-4 h-4 text-kirk border-navy-600 rounded bg-navy-900/50 focus:ring-kirk focus:ring-2';

/** Helper/hint text below form fields - uses navy-400 for WCAG AA contrast */
export const helperTextClasses = 'text-xs text-navy-400 mt-1';

/** Form label classes */
export const labelClasses = 'block text-sm font-medium text-navy-200 mb-1';

/** Inline label for checkboxes */
export const inlineLabelClasses = 'text-sm text-navy-200';

/** Section header within forms */
export const sectionHeaderClasses = 'font-medium text-white';

/** Subsection header (h4 level) */
export const subsectionHeaderClasses = 'text-sm font-medium text-white mb-3';

/** Error message text */
export const errorTextClasses = 'text-sm text-risk-critical mt-1';

/** Primary button classes */
export const primaryButtonClasses =
  'px-4 py-2 bg-gradient-to-r from-kirk to-electric text-white rounded-lg hover:shadow-lg hover:shadow-kirk/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed';

/** Primary button with px-6 */
export const primaryButtonClassesLg =
  'px-6 py-2 bg-gradient-to-r from-kirk to-electric text-white rounded-lg hover:shadow-lg hover:shadow-kirk/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed';

/** Solid primary button (kirk background) */
export const primaryButtonSolidClasses =
  'px-4 py-2 bg-kirk text-white rounded-lg hover:bg-kirk-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

/** Secondary button classes */
export const secondaryButtonClasses =
  'px-4 py-2 bg-navy-800 text-navy-300 border border-navy-600 rounded-lg hover:bg-navy-700 hover:text-white transition-colors disabled:opacity-50';

/** Ghost/text button classes */
export const ghostButtonClasses =
  'px-4 py-2 text-navy-400 hover:text-white transition-colors';

/** Success button (green) */
export const successButtonClasses =
  'px-6 py-2 bg-risk-safe text-white rounded-lg hover:bg-risk-safe/80 transition-colors disabled:opacity-50';

/** Card/panel container classes */
export const cardClasses =
  'bg-navy-800/50 rounded-xl border border-navy-700/50';

/** Card with shadow */
export const cardClassesWithShadow =
  'bg-navy-800 rounded-xl border border-navy-700/50 shadow-lg';

/** Form section divider */
export const dividerClasses = 'border-t border-navy-700/50 pt-4 mt-4';

/** Section border (top only) */
export const sectionBorderClasses = 'border-t border-navy-700/50';

/**
 * Combine base input classes with error state
 */
export function inputWithError(hasError: boolean): string {
  return hasError
    ? inputClasses.replace('border-navy-600', 'border-risk-critical')
    : inputClasses;
}

/**
 * Combine base input classes (lg) with error state
 */
export function inputLgWithError(hasError: boolean): string {
  return hasError
    ? inputClassesLg.replace('border-navy-600', 'border-risk-critical')
    : inputClassesLg;
}
