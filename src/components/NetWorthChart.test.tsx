import '../i18n';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { NetWorthChart } from './NetWorthChart';

const data = [
  { date: '2026-01-01', totalEur: 100 },
  { date: '2026-01-02', totalEur: 120 },
];

describe('NetWorthChart events', () => {
  it('shows the import legend when an event falls inside the series', () => {
    render(<NetWorthChart data={data} events={[{ date: '2026-01-02', label: 'jan.csv', kind: 'import' }]} />);
    expect(screen.getByText('Data import')).toBeInTheDocument();
  });

  it('hides the legend with no events or only out-of-range events', () => {
    const { rerender } = render(<NetWorthChart data={data} events={[]} />);
    expect(screen.queryByText('Data import')).toBeNull();
    rerender(<NetWorthChart data={data} events={[{ date: '2025-01-01', label: 'old.csv', kind: 'import' }]} />);
    expect(screen.queryByText('Data import')).toBeNull();
  });
});
