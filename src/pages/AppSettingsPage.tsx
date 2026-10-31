import { SettingsPage, Switch, useTheme } from '@foroba/ui';
import { useUserProfile } from '@foroba/ui';
import type { UserProfile } from '@foroba/ui';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchFxRates } from '../api/foroba';
import { fetchPazuruAccounts } from '../api/pazuru';
import { fetchInvestmentConnections } from '../api/tsumi';
import { updateDisplayCurrency, updateShowDebts } from '../auth/api';
import { useAuth } from '../auth/AuthProvider';
import { SecuritySettingsSection } from './SecuritySettingsSection';

export function AppSettingsPage() {
  const { profile, updateProfile } = useUserProfile();
  const { setTheme } = useTheme();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: pazuruAccounts } = useQuery({
    queryKey: ['pazuru-accounts'],
    queryFn: fetchPazuruAccounts,
  });
  const { data: tsumiConnections } = useQuery({
    queryKey: ['investment-connections'],
    queryFn: fetchInvestmentConnections,
  });

  const handleUpdateProfile = (updates: Partial<UserProfile>) => {
    updateProfile(updates);
    if (updates.theme) setTheme(updates.theme);
  };
  const queryClient = useQueryClient();
  const { data: fxRates } = useQuery({ queryKey: ['fxRates'], queryFn: fetchFxRates });
  const [savingCurrency, setSavingCurrency] = useState(false);
  const [savingShowDebts, setSavingShowDebts] = useState(false);

  const handleCurrencyChange = async (currency: string) => {
    setSavingCurrency(true);
    try {
      await updateDisplayCurrency(currency);
      await queryClient.invalidateQueries({ queryKey: ['session'] });
    } finally {
      setSavingCurrency(false);
    }
  };

  const handleShowDebtsChange = async (next: boolean) => {
    setSavingShowDebts(true);
    try {
      await updateShowDebts(next);
      await queryClient.invalidateQueries({ queryKey: ['session'] });
    } finally {
      setSavingShowDebts(false);
    }
  };

  return (
    <>
      {/* Audience & Tier — read-only display derived from session */}
      {user && (
        <div
          style={{
            padding: '20px 32px 0',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '14px 18px',
              borderRadius: '10px',
              backgroundColor: 'var(--color-bg-surface)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span
              style={{
                fontSize: '13px',
                fontWeight: 600,
                color: 'var(--color-text-secondary)',
                minWidth: '100px',
              }}
            >
              Access tier
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '2px 10px',
                borderRadius: '999px',
                fontSize: '12px',
                fontWeight: 700,
                backgroundColor:
                  user.tier === 'premium'
                    ? 'rgba(245,158,11,0.12)'
                    : 'rgba(148,163,184,0.12)',
                color:
                  user.tier === 'premium'
                    ? '#D97706'
                    : 'var(--color-text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              {user.tier}
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '14px 18px',
              borderRadius: '10px',
              backgroundColor: 'var(--color-bg-surface)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span
              style={{
                fontSize: '13px',
                fontWeight: 600,
                color: 'var(--color-text-secondary)',
                minWidth: '100px',
              }}
            >
              Audience
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '2px 10px',
                borderRadius: '999px',
                fontSize: '12px',
                fontWeight: 700,
                backgroundColor:
                  user.audience === 'expert'
                    ? 'rgba(47,129,247,0.12)'
                    : 'rgba(148,163,184,0.12)',
                color:
                  user.audience === 'expert'
                    ? '#2F81F7'
                    : 'var(--color-text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              {user.audience}
            </span>
            {user.audience_locked && (
              <span
                style={{
                  fontSize: '11px',
                  color: 'var(--color-text-secondary)',
                  fontStyle: 'italic',
                }}
              >
                Set by MiFID profiling
              </span>
            )}
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '14px 18px',
              borderRadius: '10px',
              backgroundColor: 'var(--color-bg-surface)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span
              style={{
                fontSize: '13px',
                fontWeight: 600,
                color: 'var(--color-text-secondary)',
                minWidth: '100px',
              }}
            >
              Display currency
            </span>
            <select
              value={user.display_currency}
              disabled={savingCurrency || !fxRates}
              onChange={(e) => handleCurrencyChange(e.target.value)}
              style={{
                padding: '4px 10px',
                minHeight: '44px',
                borderRadius: '6px',
                border: '1px solid var(--color-border)',
                backgroundColor: 'var(--color-bg-primary)',
                color: 'var(--color-text-primary)',
                fontSize: '16px',
              }}
            >
              <option value="EUR">EUR</option>
              {fxRates && Object.keys(fxRates.rates).sort().map((code) => (
                <option key={code} value={code}>{code}</option>
              ))}
            </select>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '14px 18px',
              borderRadius: '10px',
              backgroundColor: 'var(--color-bg-surface)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span
              style={{
                fontSize: '13px',
                fontWeight: 600,
                color: 'var(--color-text-secondary)',
                minWidth: '100px',
              }}
            >
              Show debts
            </span>
            <Switch
              checked={user.show_debts}
              disabled={savingShowDebts}
              onCheckedChange={handleShowDebtsChange}
            />
          </div>

          <p
            style={{
              fontSize: '11px',
              color: 'var(--color-text-secondary)',
              margin: '2px 2px 8px',
              lineHeight: 1.5,
            }}
          >
            Audience mode controls progressive feature disclosure (Base = essentials,
            Expert = advanced analytics). When MiFID profiling is enabled it sets this
            automatically; a manual override will be available in Settings.
          </p>

          <SecuritySettingsSection />
        </div>
      )}

      <SettingsPage
        aiApps={['foroba', 'pazuru', 'tsumi']}
        aiPlatform="web"
        aiUpgradeHref="/profile"
        profile={profile}
        onUpdateProfile={handleUpdateProfile}
        onExportData={() => {
          const data = {
            profile,
            exportedAt: new Date().toISOString(),
          };
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `foroba-export-${new Date().toISOString().slice(0, 10)}.json`;
          a.click();
          URL.revokeObjectURL(url);
        }}
        onDeleteData={() => {
          localStorage.clear();
          window.location.reload();
        }}
        connectionSlots={[
          ...(pazuruAccounts ?? []).map((acc) => (
            <div
              key={`pazuru-${acc.id}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                padding: '14px 18px',
                borderRadius: '10px',
                backgroundColor: 'var(--color-bg-surface)',
                border: '1px solid var(--color-border)',
              }}
            >
              <span style={{ fontSize: '13px', color: 'var(--color-text-primary)' }}>
                {acc.displayName} ({acc.bankName})
              </span>
              <button
                type="button"
                onClick={() => navigate('/accounts')}
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--color-accent)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                Manage in Naforo
              </button>
            </div>
          )),
          ...(tsumiConnections ?? []).map((c) => (
            <div
              key={`tsumi-${c.id}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                padding: '14px 18px',
                borderRadius: '10px',
                backgroundColor: 'var(--color-bg-surface)',
                border: '1px solid var(--color-border)',
              }}
            >
              <span style={{ fontSize: '13px', color: 'var(--color-text-primary)' }}>
                {c.label} ({c.provider}) — {c.sync_status}
              </span>
              <button
                type="button"
                onClick={() => navigate('/portfolio')}
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--color-accent)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                Manage in Yiriba
              </button>
            </div>
          )),
        ]}
        appVersion={__APP_VERSION__}
      />
    </>
  );
}

declare const __APP_VERSION__: string;
