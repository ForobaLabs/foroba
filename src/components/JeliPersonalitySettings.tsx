import { useJeli } from '../hooks/useJeli';

export function JeliPersonalitySettings() {
  const { personality, setPersonality } = useJeli();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div>
        <label
          style={{
            display: 'block',
            fontSize: '13px',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            marginBottom: '8px',
          }}
        >
          Tone: {personality.tone <= 2 ? 'Analytical' : personality.tone <= 5 ? 'Balanced' : personality.tone <= 8 ? 'Warm' : 'Griot storyteller'}
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '12px', color: 'var(--color-text-muted)', width: '80px' }}>Analytical</span>
          <input
            type="range"
            min={0}
            max={10}
            value={personality.tone}
            onChange={(e) => setPersonality({ ...personality, tone: Number(e.target.value) })}
            style={{ flex: 1, accentColor: 'var(--color-accent)' }}
          />
          <span style={{ fontSize: '12px', color: 'var(--color-text-muted)', width: '80px', textAlign: 'right' }}>Friendly</span>
        </div>
      </div>

      <div>
        <label
          style={{
            display: 'block',
            fontSize: '13px',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            marginBottom: '8px',
          }}
        >
          Expertise: {personality.expertise <= 2 ? 'Beginner-friendly' : personality.expertise <= 6 ? 'Intermediate' : 'Expert'}
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '12px', color: 'var(--color-text-muted)', width: '80px' }}>Simple</span>
          <input
            type="range"
            min={0}
            max={10}
            value={personality.expertise}
            onChange={(e) => setPersonality({ ...personality, expertise: Number(e.target.value) })}
            style={{ flex: 1, accentColor: 'var(--color-accent)' }}
          />
          <span style={{ fontSize: '12px', color: 'var(--color-text-muted)', width: '80px', textAlign: 'right' }}>Expert</span>
        </div>
      </div>

      <p style={{ fontSize: '12px', color: 'var(--color-text-muted)', margin: 0 }}>
        These settings control how Jeli communicates with you. They are stored locally and applied to every conversation.
      </p>
    </div>
  );
}
