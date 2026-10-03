import { useCallback, useRef, useState } from 'react';
import i18n from '../i18n';

export interface JeliMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface JeliPersonality {
  tone: number;      // 0 (analytical) → 10 (friendly griot)
  expertise: number; // 0 (novice-friendly) → 10 (expert)
}

function loadPersonality(): JeliPersonality {
  try {
    const saved = localStorage.getItem('foroba.jeli.personality');
    if (saved) return JSON.parse(saved) as JeliPersonality;
  } catch {
    // Corrupt/invalid stored value — fall through to defaults below.
  }
  return { tone: 5, expertise: 5 };
}

export function useJeli(userName?: string) {
  const [messages, setMessages] = useState<JeliMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [personality, setPersonalityState] = useState<JeliPersonality>(loadPersonality);
  const abortRef = useRef<AbortController | null>(null);

  const setPersonality = useCallback((next: JeliPersonality) => {
    setPersonalityState(next);
    localStorage.setItem('foroba.jeli.personality', JSON.stringify(next));
  }, []);

  const sendMessage = useCallback(async (text: string) => {
    if (isStreaming || !text.trim()) return;
    setError(null);
    const userMsg: JeliMessage = { role: 'user', content: text.trim(), timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);

    const assistantMsg: JeliMessage = { role: 'assistant', content: '', timestamp: new Date() };
    setMessages((prev) => [...prev, assistantMsg]);
    setIsStreaming(true);

    abortRef.current = new AbortController();

    try {
      const res = await fetch('/jeli/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text.trim(),
          user_name: userName || 'User',
          personality,
          lang: ['en', 'it', 'fr'].includes(i18n.language?.slice(0, 2))
            ? i18n.language.slice(0, 2)
            : 'en',
        }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('No response body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        accumulated += chunk;
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: accumulated,
          };
          return updated;
        });
      }
      if (!accumulated) {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: i18n.t('jeli.unavailable'),
          };
          return updated;
        });
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        const serverSide = err instanceof Error && err.message.startsWith('HTTP');
        const friendly = i18n.t(serverSide ? 'jeli.unavailable' : 'jeli.unreachable');
        setError(friendly);
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: friendly,
          };
          return updated;
        });
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [isStreaming, personality, userName]);

  const clearMessages = useCallback(() => setMessages([]), []);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { messages, isStreaming, error, personality, setPersonality, sendMessage, clearMessages, stopStreaming };
}
