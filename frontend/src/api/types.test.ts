import { describe, it, expect } from 'vitest';
import {
  getRiskLevel,
  getRiskColor,
  getSeverityColor,
  formatCurrency,
  formatScore,
} from './types';

describe('getRiskLevel', () => {
  it('returns safe for scores below 0.6', () => {
    expect(getRiskLevel(0)).toBe('safe');
    expect(getRiskLevel(0.3)).toBe('safe');
    expect(getRiskLevel(0.59)).toBe('safe');
  });

  it('returns caution for scores between 0.6 and 0.8', () => {
    expect(getRiskLevel(0.6)).toBe('caution');
    expect(getRiskLevel(0.7)).toBe('caution');
    expect(getRiskLevel(0.79)).toBe('caution');
  });

  it('returns alert for scores between 0.8 and 0.9', () => {
    expect(getRiskLevel(0.8)).toBe('alert');
    expect(getRiskLevel(0.85)).toBe('alert');
    expect(getRiskLevel(0.89)).toBe('alert');
  });

  it('returns critical for scores 0.9 and above', () => {
    expect(getRiskLevel(0.9)).toBe('critical');
    expect(getRiskLevel(0.95)).toBe('critical');
    expect(getRiskLevel(1)).toBe('critical');
  });
});

describe('getRiskColor', () => {
  it('returns green for safe scores', () => {
    expect(getRiskColor(0.3)).toBe('#10B981');
  });

  it('returns amber for caution scores', () => {
    expect(getRiskColor(0.7)).toBe('#F59E0B');
  });

  it('returns orange for alert scores', () => {
    expect(getRiskColor(0.85)).toBe('#F97316');
  });

  it('returns red for critical scores', () => {
    expect(getRiskColor(0.95)).toBe('#EF4444');
  });
});

describe('getSeverityColor', () => {
  it('returns correct colors for each severity level', () => {
    expect(getSeverityColor('low')).toBe('#10B981');
    expect(getSeverityColor('medium')).toBe('#F59E0B');
    expect(getSeverityColor('high')).toBe('#F97316');
    expect(getSeverityColor('critical')).toBe('#EF4444');
  });
});

describe('formatCurrency', () => {
  it('formats whole numbers', () => {
    expect(formatCurrency(1000)).toBe('$1,000.00');
  });

  it('formats decimals', () => {
    expect(formatCurrency(1234.56)).toBe('$1,234.56');
  });

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('$0.00');
  });

  it('formats large numbers', () => {
    expect(formatCurrency(1000000)).toBe('$1,000,000.00');
  });
});

describe('formatScore', () => {
  it('converts decimal to percentage', () => {
    expect(formatScore(0.5)).toBe('50%');
    expect(formatScore(0.75)).toBe('75%');
    expect(formatScore(1)).toBe('100%');
  });

  it('rounds to nearest whole number', () => {
    expect(formatScore(0.725)).toBe('73%');
    expect(formatScore(0.724)).toBe('72%');
  });

  it('handles zero', () => {
    expect(formatScore(0)).toBe('0%');
  });
});
