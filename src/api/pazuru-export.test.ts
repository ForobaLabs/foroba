import { afterEach, describe, expect, it, vi } from 'vitest';
import { downloadPazuruTransactions } from './pazuru';

afterEach(() => vi.restoreAllMocks());

describe('downloadPazuruTransactions (foroba#301)', () => {
  it('requests the real /api/export path with credentials', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('a,b', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} }));
    await downloadPazuruTransactions('csv');
    expect(fetchMock).toHaveBeenCalledWith(
      '/pazuru-api/api/export/transactions?format=csv',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('throws on a failing response instead of navigating away', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('nope', { status: 404 })));
    await expect(downloadPazuruTransactions('xlsx')).rejects.toThrow('export failed: 404');
  });
});
