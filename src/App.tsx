import { AppShell, Footer, Sidebar, Spinner, Topbar, useTheme, useUserProfile } from '@foroba/ui';
import { useState } from 'react';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { APP_NAV_ITEMS } from './components/AppNavItems';
import { JeliPanel } from './components/JeliPanel';
import { useAuth } from './auth/AuthProvider';

export function App() {
  useTheme(); // Applies dark/light class on mount
  const location = useLocation();
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--color-bg-primary)]">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  const navigate = useNavigate();
  const [jeliOpen, setJeliOpen] = useState(false);
  const { profile } = useUserProfile();
  const initials = profile.name ? profile.name.slice(0, 2).toUpperCase() : '?';

  return (
    <>
      <AppShell
        sidebar={
          <Sidebar
            navItems={APP_NAV_ITEMS}
            activePath={location.pathname}
            onNavigate={(href) => navigate(href)}
            logo={
              <span className="font-semibold tracking-tight text-[var(--color-text-primary)]">
                Foroba
              </span>
            }
          />
        }
        header={
          <Topbar
            breadcrumbs={[
              { label: 'Foroba', href: '/' },
              {
                label:
                  APP_NAV_ITEMS.find((n) => n.href === location.pathname)?.label ??
                  'Dashboard',
              },
            ]}
            right={
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {/* Profile avatar — links to /profile */}
                <button
                  onClick={() => navigate('/profile')}
                  title={profile.name || 'Profile'}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: 'var(--color-accent)',
                    color: '#fff',
                    fontSize: '12px',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {initials}
                </button>

                <button
                  onClick={() => setJeliOpen((o) => !o)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--color-accent)',
                    backgroundColor: jeliOpen ? 'var(--color-accent)' : 'transparent',
                    color: jeliOpen ? '#fff' : 'var(--color-accent)',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  🌿 Jeli
                </button>
              </div>
            }
          />
        }
        footer={<Footer appName="Foroba" />}
      >
        <Outlet />
      </AppShell>
      <JeliPanel open={jeliOpen} onClose={() => setJeliOpen(false)} userName={profile.name || undefined} />
    </>
  );
}
