import { Button } from '@foroba/ui';
import { OnboardingPage } from '@foroba/ui';
import { useNavigate } from 'react-router-dom';
import { completeOnboarding } from '../auth/api';

const PAZURU_APP_URL = import.meta.env.VITE_PAZURU_APP_URL ?? 'http://localhost:5173';
const TSUMI_APP_URL = import.meta.env.VITE_TSUMI_APP_URL ?? 'http://localhost:5178';

function ConnectSlot() {
  return (
    <div className="flex flex-col gap-3">
      <a href={`${PAZURU_APP_URL}/settings`}>
        <Button className="w-full justify-start">🏦 Connect your bank account</Button>
      </a>
      <a href={`${TSUMI_APP_URL}/settings`}>
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

  return (
    <OnboardingPage
      connectSlot={<ConnectSlot />}
      onComplete={(state) => {
        localStorage.setItem('foroba.onboarding.done', '1');
        localStorage.setItem('foroba.language', state.language);
        localStorage.setItem('foroba.theme', state.theme);
        void completeOnboarding();
        navigate('/');
      }}
    />
  );
}
