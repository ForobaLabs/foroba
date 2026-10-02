import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import i18n from '../../i18n';
import { AccountMenu } from './AccountMenu';

describe('AccountMenu placement', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('en');
  });
  afterEach(() => vi.restoreAllMocks());

  const open = () => {
    render(
      <MemoryRouter>
        <AccountMenu profile={null} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /account menu/i }));
    return screen.getByRole('dialog', { name: /account menu/i });
  };

  it('opens downward when it fits in the viewport', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ bottom: 300 } as DOMRect);
    expect(open().className).toContain('top-full');
  });

  it('opens upward when a downward panel would be clipped by the viewport', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ bottom: window.innerHeight + 200 } as DOMRect);
    const panel = open();
    expect(panel.className).toContain('bottom-full');
    expect(panel.className).not.toContain('top-full');
  });
});
