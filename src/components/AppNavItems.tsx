import {
  BarChart3,
  HelpCircle,
  Info,
  LayoutDashboard,
  Scale,
  Settings,
  Wallet,
} from 'lucide-react';
import type { NavItem } from '@foroba/ui';

export const APP_NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard },
  { label: 'Accounts', href: '/accounts', icon: Wallet },
  { label: 'Portfolio', href: '/portfolio', icon: BarChart3 },
  { label: 'Settings', href: '/settings', icon: Settings },
  { label: 'Help', href: '/help', icon: HelpCircle },
  { label: 'Legal', href: '/legal', icon: Scale },
  { label: 'About', href: '/about', icon: Info },
];
