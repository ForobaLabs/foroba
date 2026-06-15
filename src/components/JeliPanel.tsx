import { useEffect, useRef, useState } from 'react';
import { useJeli } from '../hooks/useJeli';

interface JeliPanelProps {
  open: boolean;
  onClose: () => void;
}

export function JeliPanel({ open, onClose }: JeliPanelProps) {
  const { messages, isStreaming, error, sendMessage, clearMessages, stopStreaming } = useJeli();
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    void sendMessage(input);
    setInput('');
  };

  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed',
        right: 0,
        top: 0,
        bottom: 0,
        width: '400px',
        zIndex: 200,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--color-bg-card)',
        borderLeft: '1px solid var(--color-border)',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <span
            style={{
              fontWeight: 600,
              fontSize: '15px',
              color: 'var(--color-accent)',
            }}
          >
            Jeli
          </span>
          <span
            style={{
              marginLeft: '6px',
              fontSize: '12px',
              color: 'var(--color-text-secondary)',
            }}
          >
            Your financial guide
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={clearMessages}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '12px',
              color: 'var(--color-text-muted)',
              padding: '4px 8px',
              borderRadius: '4px',
            }}
          >
            Clear
          </button>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '18px',
              color: 'var(--color-text-secondary)',
              lineHeight: 1,
              padding: '4px',
            }}
          >
            ×
          </button>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {messages.length === 0 && (
          <div
            style={{
              textAlign: 'center',
              padding: '40px 20px',
              color: 'var(--color-text-muted)',
              fontSize: '14px',
            }}
          >
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>🌿</div>
            <p>Ask Jeli about your finances.</p>
            <p style={{ fontSize: '12px', marginTop: '8px' }}>
              Examples: "How much can I invest this month?" or "How is my portfolio doing?"
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              marginBottom: '16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '85%',
                padding: '10px 14px',
                borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                backgroundColor:
                  msg.role === 'user'
                    ? 'var(--color-accent)'
                    : 'var(--color-bg-elevated)',
                color:
                  msg.role === 'user'
                    ? '#fff'
                    : 'var(--color-text-primary)',
                fontSize: '14px',
                lineHeight: '1.5',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {msg.content}
              {msg.role === 'assistant' && isStreaming && i === messages.length - 1 && (
                <span
                  style={{
                    display: 'inline-block',
                    width: '2px',
                    height: '14px',
                    backgroundColor: 'var(--color-accent)',
                    marginLeft: '2px',
                    animation: 'blink 1s infinite',
                    verticalAlign: 'middle',
                  }}
                />
              )}
            </div>
          </div>
        ))}

        {error && (
          <div
            style={{
              padding: '8px 12px',
              borderRadius: '8px',
              backgroundColor: 'rgba(220,38,38,0.1)',
              border: '1px solid var(--color-negative)',
              color: 'var(--color-negative)',
              fontSize: '13px',
              marginBottom: '12px',
            }}
          >
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        style={{
          padding: '12px 16px',
          borderTop: '1px solid var(--color-border)',
          display: 'flex',
          gap: '8px',
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Jeli..."
          disabled={isStreaming}
          style={{
            flex: 1,
            padding: '8px 12px',
            borderRadius: '8px',
            border: '1px solid var(--color-border)',
            backgroundColor: 'var(--color-bg-primary)',
            color: 'var(--color-text-primary)',
            fontSize: '14px',
            outline: 'none',
          }}
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={stopStreaming}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: 'var(--color-negative)',
              color: '#fff',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 600,
            }}
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              backgroundColor: input.trim() ? 'var(--color-accent)' : 'var(--color-border)',
              color: '#fff',
              cursor: input.trim() ? 'pointer' : 'not-allowed',
              fontSize: '13px',
              fontWeight: 600,
            }}
          >
            Send
          </button>
        )}
      </form>
    </div>
  );
}
