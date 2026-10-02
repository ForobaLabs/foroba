import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { AppSwitcher, SuiteShell, useSuiteProfile, useTheme, useUserProfile, type NavGroup, type NavItem } from '@foroba/ui';
import { usePrivacy } from '../contexts/PrivacyContext';
import { useJeli } from '../hooks/useJeli';
import { AccountMenu } from './shell/AccountMenu';
import { JeliPanel } from './shell/JeliPanel';
import { MOBILE_TAB_PATHS, navGroupDefs } from './shell/navGroups';
import { pageTitleKey } from './shell/pageTitle';

const YIRIBA_APP_URL = import.meta.env.VITE_YIRIBA_APP_URL ?? 'http://localhost:5178';
const NAFORO_APP_URL = import.meta.env.VITE_NAFORO_APP_URL ?? 'http://localhost:5173';

interface KelenShellProps {
  children: ReactNode;
  isAdmin?: boolean;
  /** Extra topbar content (e.g. the notification bell). */
  notifications?: ReactNode;
}

/** Kelen (net worth, goals, simulation) on the common suite shell: grouped nav, one Jeli drawer, account menu. */
export function KelenShell({ children, isAdmin = false, notifications }: KelenShellProps) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { isPrivate, toggle } = usePrivacy();
  const { profile: userProfile } = useUserProfile();
  const { profile } = useSuiteProfile({ enabled: false });
  useTheme(); // applies the theme class to <html>
  const [jeliOpen, setJeliOpen] = useState(false);
  const jeli = useJeli(userProfile.name || undefined);

  const pageTitle = t(pageTitleKey(pathname));
  useEffect(() => {
    document.title = `${pageTitle} · Kelen by Foroba`;
  }, [pageTitle]);

  const defs = useMemo(() => navGroupDefs(isAdmin), [isAdmin]);
  const navGroups: NavGroup[] = useMemo(
    () =>
      defs.map((g) => ({
        id: g.id,
        label: t(g.labelKey),
        items: g.items.map<NavItem>((i) => ({ label: t(i.labelKey), href: i.path, icon: i.icon })),
      })),
    [defs, t],
  );
  const mobileTabs: NavItem[] = useMemo(
    () =>
      defs
        .flatMap((g) => g.items)
        .filter((i) => (MOBILE_TAB_PATHS as readonly string[]).includes(i.path))
        .map((i) => ({ label: t(i.labelKey), href: i.path, icon: i.icon })),
    [defs, t],
  );

  const onSelectApp = (id: string) => {
    if (id === 'yiriba') window.location.href = YIRIBA_APP_URL;
    else if (id === 'naforo') window.location.href = NAFORO_APP_URL;
  };

  return (
    <SuiteShell
      app="kelen"
      switcher={
        <AppSwitcher
          current="kelen"
          onSelect={onSelectApp}
          apps={[
            { id: 'kelen', name: 'Kelen', blurb: t('switcher.kelen') },
            { id: 'yiriba', name: 'Yiriba', blurb: t('switcher.yiriba'), href: YIRIBA_APP_URL },
            { id: 'naforo', name: 'Naforo', blurb: t('switcher.naforo'), href: NAFORO_APP_URL },
          ]}
        />
      }
      navGroups={navGroups}
      activePath={pathname}
      onNavigate={(href) => {
        void navigate(href);
      }}
      amountsHidden={isPrivate}
      onToggleAmounts={toggle}
      notifications={notifications}
      userMenu={<AccountMenu profile={profile} />}
      jeli={{
        open: jeliOpen,
        onToggle: () => { setJeliOpen((v) => !v); },
        panel: (
          <JeliPanel
            messages={jeli.messages}
            streaming={jeli.isStreaming}
            onSend={(text) => void jeli.sendMessage(text)}
            onStop={jeli.stopStreaming}
            onReset={jeli.clearMessages}
          />
        ),
      }}
      mobileTabs={mobileTabs}
    >
      {children}
    </SuiteShell>
  );
}
