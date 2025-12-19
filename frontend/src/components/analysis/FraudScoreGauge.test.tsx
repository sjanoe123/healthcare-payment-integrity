import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FraudScoreGauge } from './FraudScoreGauge';

describe('FraudScoreGauge', () => {
  it('renders with a score', () => {
    render(<FraudScoreGauge score={0.5} />);
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('displays Low Risk for safe scores', () => {
    render(<FraudScoreGauge score={0.3} />);
    expect(screen.getByText('Low Risk')).toBeInTheDocument();
  });

  it('displays Elevated for caution scores', () => {
    render(<FraudScoreGauge score={0.65} />);
    expect(screen.getByText('Elevated')).toBeInTheDocument();
  });

  it('displays High Risk for alert scores', () => {
    render(<FraudScoreGauge score={0.85} />);
    expect(screen.getByText('High Risk')).toBeInTheDocument();
  });

  it('displays Critical for critical scores', () => {
    render(<FraudScoreGauge score={0.95} />);
    expect(screen.getByText('Critical')).toBeInTheDocument();
  });

  it('renders with small size', () => {
    const { container } = render(<FraudScoreGauge score={0.5} size="sm" />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('width', '120');
  });

  it('renders with medium size', () => {
    const { container } = render(<FraudScoreGauge score={0.5} size="md" />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('width', '200');
  });

  it('renders with large size', () => {
    const { container } = render(<FraudScoreGauge score={0.5} size="lg" />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('width', '280');
  });

  it('hides label when showLabel is false', () => {
    render(<FraudScoreGauge score={0.5} showLabel={false} />);
    expect(screen.queryByText('Elevated')).not.toBeInTheDocument();
  });

  it('has accessible aria-label', () => {
    render(<FraudScoreGauge score={0.72} />);
    const svg = screen.getByRole('img');
    expect(svg).toHaveAttribute('aria-label', expect.stringContaining('72%'));
  });

  it('renders percentage correctly at boundaries', () => {
    const { rerender } = render(<FraudScoreGauge score={0} />);
    expect(screen.getByText('0%')).toBeInTheDocument();

    rerender(<FraudScoreGauge score={1} />);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(<FraudScoreGauge score={0.5} className="custom-gauge" />);
    expect(container.firstChild).toHaveClass('custom-gauge');
  });
});
