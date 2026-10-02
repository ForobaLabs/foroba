/** Longest-prefix match of a pathname to the `kelenNav.*` i18n key that names the page. */
const TITLE_KEYS: [string, string][] = [
  ['/reports/monthly', 'kelenNav.monthlyReport'],
  ['/accounts', 'kelenNav.accounts'],
  ['/portfolio', 'kelenNav.portfolio'],
  ['/markets', 'kelenNav.markets'],
  ['/goals', 'kelenNav.goals'],
  ['/whatif', 'kelenNav.whatif'],
  ['/household', 'kelenNav.household'],
  ['/developer', 'kelenNav.developer'],
  ['/lab', 'kelenNav.lab'],
  ['/admin', 'kelenNav.admin'],
  ['/settings', 'kelenNav.settings'],
  ['/profile', 'kelenNav.profile'],
  ['/security', 'kelenNav.security'],
  ['/help', 'kelenNav.help'],
  ['/legal', 'kelenNav.legal'],
  ['/about', 'kelenNav.about'],
  ['/status', 'kelenNav.status'],
];

export function pageTitleKey(pathname: string): string {
  const hit = TITLE_KEYS.find(([prefix]) => pathname === prefix || pathname.startsWith(`${prefix}/`));
  return hit ? hit[1] : 'kelenNav.dashboard';
}
