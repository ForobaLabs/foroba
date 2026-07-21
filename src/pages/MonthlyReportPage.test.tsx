import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MonthlyReportPage } from './MonthlyReportPage';

const mockUseEntitlement = vi.fn();

vi.mock('@foroba/ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@foroba/ui')>();
  return { ...actual, useEntitlement: (key: string) => mockUseEntitlement(key) };
});

function mockListResponse(items: unknown[], quota = { used: 0, limit: 6 }) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ items, quota }),
  } as Response);
}

describe('MonthlyReportPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    mockUseEntitlement.mockReset();
  });

  it('shows locked CTA when unlocked=false', async () => {
    mockUseEntitlement.mockReturnValue({ visible: true, unlocked: false });
    mockListResponse([]);

    render(<MonthlyReportPage />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /monthly report/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /generate/i })).not.toBeInTheDocument();
  });

  it('renders report list with quota counter when unlocked', async () => {
    mockUseEntitlement.mockReturnValue({ visible: true, unlocked: true });
    mockListResponse(
      [{
        id: 1, year_month: '2026-07', trigger: 'manual', status: 'success',
        narrative_text: 'Great month overall.', error_message: null,
        attempt_count: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
      }],
      { used: 1, limit: 6 },
    );

    render(<MonthlyReportPage />);

    await waitFor(() => {
      expect(screen.getByText(/2026-07/)).toBeInTheDocument();
      expect(screen.getByText(/1\s*\/\s*6/)).toBeInTheDocument();
    });
  });

  it('disables Generate when quota is at cap', async () => {
    mockUseEntitlement.mockReturnValue({ visible: true, unlocked: true });
    mockListResponse([], { used: 6, limit: 6 });

    render(<MonthlyReportPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /generate/i })).toBeDisabled();
    });
  });

  it('shows Retry button only on failed rows', async () => {
    mockUseEntitlement.mockReturnValue({ visible: true, unlocked: true });
    mockListResponse(
      [{
        id: 2, year_month: '2026-07', trigger: 'manual', status: 'failed',
        narrative_text: null, error_message: 'Ollama timeout',
        attempt_count: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
      }],
      { used: 1, limit: 6 },
    );

    render(<MonthlyReportPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /download pdf/i })).not.toBeInTheDocument();
  });

  it('shows Download PDF button only on success rows', async () => {
    mockUseEntitlement.mockReturnValue({ visible: true, unlocked: true });
    mockListResponse(
      [{
        id: 3, year_month: '2026-07', trigger: 'manual', status: 'success',
        narrative_text: 'Great month overall.', error_message: null,
        attempt_count: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
      }],
      { used: 1, limit: 6 },
    );

    render(<MonthlyReportPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /download pdf/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /^retry$/i })).not.toBeInTheDocument();
  });
});
