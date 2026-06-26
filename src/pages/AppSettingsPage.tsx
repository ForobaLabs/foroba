import { SettingsPage } from '@foroba/ui';
import { useUserProfile } from '@foroba/ui';
import { useAuth } from '../auth/AuthProvider';

export function AppSettingsPage() {
  const { profile, updateProfile } = useUserProfile();
  const { user } = useAuth();

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
        </div>
      )}

      <SettingsPage
        profile={profile}
        onUpdateProfile={updateProfile}
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
        appVersion={__APP_VERSION__}
      />
    </>
  );
}

declare const __APP_VERSION__: string;
