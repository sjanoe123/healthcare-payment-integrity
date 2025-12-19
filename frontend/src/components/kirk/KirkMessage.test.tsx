import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KirkMessage } from './KirkMessage';

describe('KirkMessage', () => {
  it('renders greeting message with content', () => {
    render(<KirkMessage type="greeting" content="Hello, I've analyzed your claim." />);
    expect(screen.getByText("Hello, I've analyzed your claim.")).toBeInTheDocument();
  });

  it('renders summary message', () => {
    render(<KirkMessage type="summary" content="This is a summary of findings." />);
    expect(screen.getByText('This is a summary of findings.')).toBeInTheDocument();
  });

  it('renders finding with severity badge', () => {
    render(
      <KirkMessage
        type="finding"
        content="NCCI edit violation detected"
        severity="high"
      />
    );
    expect(screen.getByText('NCCI edit violation detected')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
  });

  it('renders recommendation with icon', () => {
    render(
      <KirkMessage type="recommendation" content="Consider requesting additional documentation" />
    );
    expect(screen.getByText('Consider requesting additional documentation')).toBeInTheDocument();
    expect(screen.getByText('RECOMMENDATION')).toBeInTheDocument();
  });

  it('displays code metadata when provided', () => {
    render(
      <KirkMessage
        type="finding"
        content="Code bundling issue"
        severity="medium"
        metadata={{ code: '99213, 99214' }}
      />
    );
    expect(screen.getByText('99213, 99214')).toBeInTheDocument();
  });

  it('displays rule type in metadata', () => {
    render(
      <KirkMessage
        type="finding"
        content="Provider exclusion found"
        severity="critical"
        metadata={{ ruleType: 'NCCI Edit' }}
      />
    );
    expect(screen.getByText('NCCI Edit')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <KirkMessage type="greeting" content="Test" className="custom-message" />
    );
    expect(container.firstChild).toHaveClass('custom-message');
  });

  it('renders with different severity levels', () => {
    const { rerender } = render(
      <KirkMessage type="finding" content="Low severity" severity="low" />
    );
    expect(screen.getByText('LOW')).toBeInTheDocument();

    rerender(<KirkMessage type="finding" content="Critical severity" severity="critical" />);
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
  });
});
