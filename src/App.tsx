import { AppShell, Footer, Sidebar, Spinner, Topbar, useTheme, useUserProfile } from '@foroba/ui';
import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { getNavItems } from './components/AppNavItems';
import { JeliPanel } from './components/JeliPanel';
import { useAuth } from './auth/AuthProvider';
import i18n from './i18n';

export function App() {
  useTheme(); // Applies dark/light class on mount
  const location = useLocation();
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const [jeliOpen, setJeliOpen] = useState(false);
  const { profile } = useUserProfile();

  useEffect(() => {
    i18n.changeLanguage(profile.language);
    document.documentElement.lang = profile.language;
  }, [profile.language]);

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

  // Admin route guard: non-admin users attempting to access /admin are redirected to /
  if (location.pathname.startsWith('/admin') && !user.is_admin) {
    return <Navigate to="/" replace />;
  }

  const initials = profile.name ? profile.name.slice(0, 2).toUpperCase() : '?';
  const navItems = getNavItems(user);

  return (
    <>
      <AppShell
        sidebar={
          <Sidebar
            navItems={navItems}
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
            hasSidebar={false}
            breadcrumbs={[
              { label: 'Foroba', href: '/' },
              {
                label:
                  navItems.find((n) => n.href === location.pathname)?.label ??
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
                  Jeli
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
