import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KirkAvatar } from './KirkAvatar';

describe('KirkAvatar', () => {
  it('renders with default props', () => {
    render(<KirkAvatar />);
    expect(screen.getByText('K')).toBeInTheDocument();
  });

  it('renders with small size', () => {
    const { container } = render(<KirkAvatar size="sm" />);
    expect(container.firstChild).toHaveClass('w-8', 'h-8');
  });

  it('renders with medium size', () => {
    const { container } = render(<KirkAvatar size="md" />);
    expect(container.firstChild).toHaveClass('w-10', 'h-10');
  });

  it('renders with large size', () => {
    const { container } = render(<KirkAvatar size="lg" />);
    expect(container.firstChild).toHaveClass('w-14', 'h-14');
  });

  it('applies custom className', () => {
    const { container } = render(<KirkAvatar className="custom-class" />);
    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('renders with neutral mood by default', () => {
    const { container } = render(<KirkAvatar />);
    expect(container.firstChild).toHaveClass('from-kirk');
  });

  it('renders with safe mood styling', () => {
    const { container } = render(<KirkAvatar mood="safe" />);
    expect(container.firstChild).toHaveClass('from-risk-safe');
  });

  it('renders with critical mood styling', () => {
    const { container } = render(<KirkAvatar mood="critical" />);
    expect(container.firstChild).toHaveClass('from-risk-critical');
  });

  it('renders with thinking mood styling', () => {
    const { container } = render(<KirkAvatar mood="thinking" />);
    expect(container.firstChild).toHaveClass('from-kirk', 'to-electric');
  });
});
