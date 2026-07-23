import {
  BarChart3,
  FileText,
  FlaskConical,
  GitBranch,
  HelpCircle,
  Home,
  Info,
  KeyRound,
  LayoutDashboard,
  LineChart,
  Scale,
  Settings,
  ShieldCheck,
  Target,
  User,
  Wallet,
} from 'lucide-react';
import type { NavItem } from '@foroba/ui';
import type { SessionUser } from '../auth/api';

export const APP_NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard },
  { label: 'Accounts', href: '/accounts', icon: Wallet },
  { label: 'Portfolio', href: '/portfolio', icon: BarChart3 },
  { label: 'Markets', href: '/markets', icon: LineChart },
  { label: 'Jeli Lab', href: '/lab', icon: FlaskConical },
  { label: 'Goals', href: '/goals', icon: Target },
  { label: 'What-If', href: '/whatif', icon: GitBranch },
  { label: 'Monthly Report', href: '/reports/monthly', icon: FileText },
  { label: 'API & Webhooks', href: '/developer', icon: KeyRound },
  { label: 'Profile', href: '/profile', icon: User },
  { label: 'Household', href: '/household', icon: Home },
  { label: 'Settings', href: '/settings', icon: Settings },
  { label: 'Help', href: '/help', icon: HelpCircle },
  { label: 'Legal', href: '/legal', icon: Scale },
  { label: 'About', href: '/about', icon: Info },
];

export function getNavItems(user: SessionUser | null): NavItem[] {
  if (user?.is_admin) {
    return [...APP_NAV_ITEMS, { label: 'Admin', href: '/admin', icon: ShieldCheck }];
  }
  return APP_NAV_ITEMS;
}
