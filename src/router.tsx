import { AboutPage, HelpPage, LegalPage } from '@foroba/ui';
import { lazy, Suspense } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { Spinner } from '@foroba/ui';
import { App } from './App';

const DashboardPage     = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const AccountsPage      = lazy(() => import('./pages/AccountsPage').then(m => ({ default: m.AccountsPage })));
const PortfolioPage     = lazy(() => import('./pages/PortfolioPage').then(m => ({ default: m.PortfolioPage })));
const AppSettingsPage   = lazy(() => import('./pages/AppSettingsPage').then(m => ({ default: m.AppSettingsPage })));
const AppOnboardingPage = lazy(() => import('./pages/AppOnboardingPage').then(m => ({ default: m.AppOnboardingPage })));
const ProfilePage       = lazy(() => import('./pages/ProfilePage').then(m => ({ default: m.ProfilePage })));
const HouseholdPage     = lazy(() => import('./pages/HouseholdPage').then(m => ({ default: m.HouseholdPage })));
const GoalsPage         = lazy(() => import('./pages/GoalsPage').then(m => ({ default: m.GoalsPage })));

const Loading = () => (
  <div className="flex h-full items-center justify-center py-20">
    <Spinner size="lg" />
  </div>
);

export const router = createBrowserRouter([
  {
    path: '/onboarding',
    element: <Suspense fallback={<Loading />}><AppOnboardingPage /></Suspense>,
  },
  {
    path: '/',
    element: <App />,
    children: [
      { index: true,      element: <Suspense fallback={<Loading />}><DashboardPage /></Suspense> },
      { path: 'accounts', element: <Suspense fallback={<Loading />}><AccountsPage /></Suspense> },
      { path: 'portfolio',element: <Suspense fallback={<Loading />}><PortfolioPage /></Suspense> },
      { path: 'settings',  element: <Suspense fallback={<Loading />}><AppSettingsPage /></Suspense> },
      { path: 'profile',   element: <Suspense fallback={<Loading />}><ProfilePage /></Suspense> },
      { path: 'household', element: <Suspense fallback={<Loading />}><HouseholdPage /></Suspense> },
      { path: 'goals',     element: <Suspense fallback={<Loading />}><GoalsPage /></Suspense> },
      { path: 'help',      element: <HelpPage gitlabIssueUrl="https://gitlab.com/bambac961/foroba/-/issues" /> },
      { path: 'legal',    element: <LegalPage /> },
      { path: 'about',    element: <AboutPage appName="Foroba" version={__APP_VERSION__} /> },
    ],
  },
]);

declare const __APP_VERSION__: string;
