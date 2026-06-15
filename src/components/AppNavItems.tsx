import {
  BarChart3,
  HelpCircle,
  Home,
  Info,
  LayoutDashboard,
  Scale,
  Settings,
  Target,
  User,
  Wallet,
} from 'lucide-react';
import type { NavItem } from '@foroba/ui';

export const APP_NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard },
  { label: 'Accounts', href: '/accounts', icon: Wallet },
  { label: 'Portfolio', href: '/portfolio', icon: BarChart3 },
  { label: 'Goals', href: '/goals', icon: Target },
  { label: 'Profile', href: '/profile', icon: User },
  { label: 'Household', href: '/household', icon: Home },
  { label: 'Settings', href: '/settings', icon: Settings },
  { label: 'Help', href: '/help', icon: HelpCircle },
  { label: 'Legal', href: '/legal', icon: Scale },
  { label: 'About', href: '/about', icon: Info },
];
