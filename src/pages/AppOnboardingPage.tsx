import { Button } from '@foroba/ui';
import { OnboardingPage, useLanguage } from '@foroba/ui';
import { useNavigate } from 'react-router';
import { completeOnboarding } from '../auth/api';

function ConnectSlot() {
  return (
    <div className="flex flex-col gap-3">
      <a href="/foroba-api/auth/handoff/pazuru?redirect=/settings">
        <Button className="w-full justify-start">🏦 Connect your bank account</Button>
      </a>
      <a href="/foroba-api/auth/handoff/tsumi?redirect=/settings">
        <Button variant="outline" className="w-full justify-start">
          📈 Add your stocks, ETFs, or crypto
        </Button>
      </a>
      <p className="text-xs text-[var(--color-text-muted)]">
        You can always do this later from the Accounts and Portfolio pages.
      </p>
    </div>
  );
}

export function AppOnboardingPage() {
  const navigate = useNavigate();
  const { setLanguage } = useLanguage();

  return (
    <OnboardingPage
      connectSlot={<ConnectSlot />}
      onComplete={(state) => {
        localStorage.setItem('foroba.onboarding.done', '1');
        setLanguage(state.language);
        localStorage.setItem('foroba.theme', state.theme);
        void completeOnboarding();
        navigate('/');
      }}
    />
  );
}
