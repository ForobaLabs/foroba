import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AdminPage from './AdminPage';

vi.mock('@foroba/ui', async () => {
  const actual = await vi.importActual<typeof import('@foroba/ui')>('@foroba/ui');
  return {
    ...actual,
    useAdminSettings: () => ({ settings: [], loading: false, toggle: vi.fn() }),
    useAdminUsers: () => ({ users: [] }),
  };
});

describe('AdminPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a Status tab that fetches detailed health for all 3 apps', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'ok',
        checks: { db: 'ok' },
        dependencies: { ollama: { status: 'ok', last_checked: '2026-07-14T10:00:00Z' } },
      }),
    } as Response);

    render(<AdminPage />);
    fireEvent.click(screen.getByText('Status'));

    await waitFor(() => {
      expect(screen.getAllByText('Operational').length).toBeGreaterThan(0);
    });
  });
});
