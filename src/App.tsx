import { NotificationBell, Spinner, useTheme, useUserProfile } from '@foroba/ui';
import { useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { KelenShell } from './components/KelenShell';
import { useAuth } from './auth/AuthProvider';
import { SessionUnavailable } from './auth/SessionUnavailable';
import { useNotifications } from './hooks/useNotifications';
import { fetchConsentStatus } from './auth/api';
import i18n from './i18n';

export function App() {
  useTheme(); // Applies dark/light class on mount
  const location = useLocation();
  const { user, loading, unavailable, retry } = useAuth();
  const { profile } = useUserProfile();
  const { notifications, dismiss } = useNotifications();
  // CL-2.1 (foroba#238): check consent status once the session is resolved. The query is
  // disabled until we have an authenticated user so it never fires on the login page.
  const { data: consentStatus } = useQuery({
    queryKey: ['consents-status'],
    queryFn: fetchConsentStatus,
    staleTime: 5 * 60_000,
    enabled: !loading && !!user,
  });

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

  if (unavailable) {
    return <SessionUnavailable onRetry={retry} />;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // GL-4.2 (foroba#173): new signups must complete MFA enrollment before using the app —
  // register() already redirects to /enroll, but this guard catches a user who navigates
  // away/refreshes/deep-links mid-setup, since register() alone can't be enforced. Existing
  // pre-feature accounts are unaffected (mfa_enrollment_pending defaults false for them).
  if (user.mfa_enrollment_pending) {
    return <Navigate to="/enroll" replace />;
  }

  // CL-2.1 (foroba#238): redirect to re-consent page when any required legal document
  // has been updated since the user last accepted.
  if (consentStatus && Object.values(consentStatus).some((v) => !v)) {
    return <Navigate to="/re-consent" replace />;
  }

  // Admin route guard: non-admin users attempting to access /admin are redirected to /
  if (location.pathname.startsWith('/admin') && !user.is_admin) {
    return <Navigate to="/" replace />;
  }

  return (
    <KelenShell
      isAdmin={user.is_admin}
      notifications={<NotificationBell notifications={notifications} onDismiss={dismiss} />}
    >
      <Outlet />
    </KelenShell>
  );
}
