import { OnboardingPage } from '@foroba/ui';
import { useNavigate } from 'react-router-dom';

export function AppOnboardingPage() {
  const navigate = useNavigate();

  return (
    <OnboardingPage
      onComplete={(state) => {
        localStorage.setItem('foroba.onboarding.done', '1');
        localStorage.setItem('foroba.language', state.language);
        localStorage.setItem('foroba.theme', state.theme);
        navigate('/');
      }}
    />
  );
}
