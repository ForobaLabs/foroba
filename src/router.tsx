import { AboutPage, HelpPage, LegalPage } from '@foroba/ui';
import { lazy, Suspense } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { Spinner } from '@foroba/ui';
import { App } from './App';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { FOROBA_FAQ } from './data/faq';

const DashboardPage     = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const AccountsPage      = lazy(() => import('./pages/AccountsPage').then(m => ({ default: m.AccountsPage })));
const AccountDetailPage = lazy(() => import('./pages/AccountDetailPage').then(m => ({ default: m.AccountDetailPage })));
const PortfolioPage     = lazy(() => import('./pages/PortfolioPage').then(m => ({ default: m.PortfolioPage })));
const PortfolioDetailPage = lazy(() => import('./pages/PortfolioDetailPage').then(m => ({ default: m.PortfolioDetailPage })));
const AppSettingsPage   = lazy(() => import('./pages/AppSettingsPage').then(m => ({ default: m.AppSettingsPage })));
const AppOnboardingPage = lazy(() => import('./pages/AppOnboardingPage').then(m => ({ default: m.AppOnboardingPage })));
const ProfilePage       = lazy(() => import('./pages/ProfilePage').then(m => ({ default: m.ProfilePage })));
const HouseholdPage     = lazy(() => import('./pages/HouseholdPage').then(m => ({ default: m.HouseholdPage })));
const GoalsPage         = lazy(() => import('./pages/GoalsPage').then(m => ({ default: m.GoalsPage })));
const AdminPage         = lazy(() => import('./pages/AdminPage'));
const MarketsPage       = lazy(() => import('./pages/MarketsPage').then(m => ({ default: m.MarketsPage })));
const MarketDetailPage  = lazy(() => import('./pages/MarketDetailPage').then(m => ({ default: m.MarketDetailPage })));
const JeliLabPage       = lazy(() => import('./pages/JeliLabPage').then(m => ({ default: m.JeliLabPage })));
const StatusPage        = lazy(() => import('./pages/StatusPage').then(m => ({ default: m.StatusPage })));
const WhatIfPage        = lazy(() => import('./pages/WhatIfPage').then(m => ({ default: m.WhatIfPage })));
const MonthlyReportPage = lazy(() => import('./pages/MonthlyReportPage').then(m => ({ default: m.MonthlyReportPage })));
const DeveloperPage      = lazy(() => import('./pages/DeveloperPage').then(m => ({ default: m.DeveloperPage })));

const Loading = () => (
  <div className="flex h-full items-center justify-center py-20">
    <Spinner size="lg" />
  </div>
);

export const router = createBrowserRouter([
  { path: '/login',    element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/status',   element: <Suspense fallback={<Loading />}><StatusPage /></Suspense> },
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
      { path: 'accounts/:id', element: <Suspense fallback={<Loading />}><AccountDetailPage /></Suspense> },
      { path: 'portfolio',element: <Suspense fallback={<Loading />}><PortfolioPage /></Suspense> },
      { path: 'portfolio/:source/:isin', element: <Suspense fallback={<Loading />}><PortfolioDetailPage /></Suspense> },
      { path: 'markets', element: <Suspense fallback={<Loading />}><MarketsPage /></Suspense> },
      { path: 'markets/:assetClass/:symbol', element: <Suspense fallback={<Loading />}><MarketDetailPage /></Suspense> },
      { path: 'lab', element: <Suspense fallback={<Loading />}><JeliLabPage /></Suspense> },
      { path: 'settings',  element: <Suspense fallback={<Loading />}><AppSettingsPage /></Suspense> },
      { path: 'profile',   element: <Suspense fallback={<Loading />}><ProfilePage /></Suspense> },
      { path: 'household', element: <Suspense fallback={<Loading />}><HouseholdPage /></Suspense> },
      { path: 'goals',     element: <Suspense fallback={<Loading />}><GoalsPage /></Suspense> },
      { path: 'whatif',    element: <Suspense fallback={<Loading />}><WhatIfPage /></Suspense> },
      { path: 'reports/monthly', element: <Suspense fallback={<Loading />}><MonthlyReportPage /></Suspense> },
      { path: 'developer', element: <Suspense fallback={<Loading />}><DeveloperPage /></Suspense> },
      { path: 'admin',     element: <Suspense fallback={<Loading />}><AdminPage /></Suspense> },
      { path: 'help',      element: <HelpPage faqItems={FOROBA_FAQ} gitlabIssueUrl="https://gitlab.com/bambac961/foroba/-/issues" /> },
      { path: 'legal',    element: <LegalPage /> },
      { path: 'about',    element: <AboutPage appName="Foroba" version={__APP_VERSION__} /> },
    ],
  },
]);

declare const __APP_VERSION__: string;
