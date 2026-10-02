import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { I18nextProvider } from 'react-i18next';
import { describe, expect, it } from 'vitest';
import i18n from '../i18n';
import { PremiumGate } from './PremiumGate';

const gate = (unlocked: boolean) => (
  <I18nextProvider i18n={i18n}>
    <PremiumGate visible unlocked={unlocked} feature="What-If" description="Desc">
      <p>builder</p>
    </PremiumGate>
  </I18nextProvider>
);

describe('PremiumGate', () => {
  it('renders children when unlocked', () => {
    render(gate(true));
    expect(screen.getByText('builder')).toBeInTheDocument();
  });

  it('shows a locked card with an honest CTA when locked', async () => {
    await i18n.changeLanguage('en');
    render(gate(false));
    expect(screen.queryByText('builder')).toBeNull();
    expect(screen.getByRole('region', { name: 'What-If' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Unlock Premium' }));
    expect(screen.getByRole('status')).toHaveTextContent(/isn't available to buy yet/);
    expect(screen.queryByText(/free trial/i)).toBeNull();
  });
});
