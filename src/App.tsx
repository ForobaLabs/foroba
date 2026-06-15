import { AppShell, Footer, Sidebar, Topbar, useTheme } from '@foroba/ui';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { APP_NAV_ITEMS } from './components/AppNavItems';

export function App() {
  useTheme(); // Applies dark/light class on mount
  const location = useLocation();
  const navigate = useNavigate();

  return (
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
        />
      }
      footer={<Footer appName="Foroba" />}
    >
      <Outlet />
    </AppShell>
  );
}
