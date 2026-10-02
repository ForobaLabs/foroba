import type { ComponentType } from 'react';
import {
  BarChart3, FileText, FlaskConical, GitBranch, Home, KeyRound, LayoutDashboard,
  LineChart, ShieldCheck, Target, Wallet,
} from 'lucide-react';

export interface NavDef {
  labelKey: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
}

export interface NavGroupDef {
  id: 'overview' | 'wealth' | 'plan' | 'people' | 'build';
  labelKey: string;
  items: NavDef[];
}

/** Kelen navigation: 5 groups; Admin is listed under Build for admins only. Account items live in the user menu. */
export function navGroupDefs(isAdmin: boolean): NavGroupDef[] {
  const groups: NavGroupDef[] = [
    {
      id: 'overview', labelKey: 'navGroups.overview',
      items: [{ labelKey: 'kelenNav.dashboard', path: '/', icon: LayoutDashboard }],
    },
    {
      id: 'wealth', labelKey: 'navGroups.wealth',
      items: [
        { labelKey: 'kelenNav.accounts', path: '/accounts', icon: Wallet },
        { labelKey: 'kelenNav.portfolio', path: '/portfolio', icon: BarChart3 },
        { labelKey: 'kelenNav.markets', path: '/markets', icon: LineChart },
      ],
    },
    {
      id: 'plan', labelKey: 'navGroups.plan',
      items: [
        { labelKey: 'kelenNav.goals', path: '/goals', icon: Target },
        { labelKey: 'kelenNav.whatif', path: '/whatif', icon: GitBranch },
        { labelKey: 'kelenNav.monthlyReport', path: '/reports/monthly', icon: FileText },
      ],
    },
    {
      id: 'people', labelKey: 'navGroups.people',
      items: [{ labelKey: 'kelenNav.household', path: '/household', icon: Home }],
    },
  ];
  const build: NavDef[] = [
    { labelKey: 'kelenNav.developer', path: '/developer', icon: KeyRound },
    { labelKey: 'kelenNav.lab', path: '/lab', icon: FlaskConical },
  ];
  if (isAdmin) build.push({ labelKey: 'kelenNav.admin', path: '/admin', icon: ShieldCheck });
  groups.push({ id: 'build', labelKey: 'navGroups.build', items: build });
  return groups;
}

/** Bottom-bar destinations on mobile (a "More" slot is added by the shell). */
export const MOBILE_TAB_PATHS = ['/', '/accounts', '/goals'] as const;
