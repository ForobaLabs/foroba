import { Button, Card, CardContent, PageContainer, SectionHeader } from '@foroba/ui';
import { useEffect, useRef, useState } from 'react';

interface TableArtifact { type: 'artifact'; kind: 'table'; data: Record<string, unknown>[] }
interface ChartArtifact { type: 'artifact'; kind: 'chart'; mime: string; base64: string }
type Artifact = TableArtifact | ChartArtifact;

interface Message {
  role: 'user' | 'assistant';
  content: string;
  code?: string;
  artifacts: Artifact[];
  streaming?: boolean;
  errored?: boolean;
}

export function JeliLabPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [allowInternet, setAllowInternet] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function patchLast(patch: Partial<Message>) {
    setMessages((prev) => {
      const updated = [...prev];
      const idx = updated.length - 1;
      if (idx >= 0 && updated[idx].role === 'assistant') {
        updated[idx] = { ...updated[idx], ...patch };
      }
      return updated;
    });
  }

  async function sendMessage() {
    if (!input.trim() || isStreaming) return;

    setMessages((prev) => [...prev, { role: 'user', content: input.trim(), artifacts: [] }]);
    const question = input.trim();
    setInput('');
    setIsStreaming(true);
    setMessages((prev) => [...prev, { role: 'assistant', content: '', artifacts: [], streaming: true }]);

    try {
      const res = await fetch('/foroba-api/lab/chat', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question, session_id: sessionId, allow_internet: allowInternet }),
      });

      if (!res.ok || !res.body) {
        patchLast({ content: 'Jeli Lab is unavailable right now.', streaming: false, errored: true });
        setIsStreaming(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let reading = true;

      while (reading) {
        const { done, value } = await reader.read();
        if (done) { reading = false; break; }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line) as
            | { type: 'status'; value: string }
            | { type: 'token'; value: string }
            | { type: 'artifact'; kind: 'table'; data: Record<string, unknown>[] }
            | { type: 'artifact'; kind: 'chart'; mime: string; base64: string }
            | { type: 'error'; value: string }
            | { type: 'done'; code: string };

          if (event.type === 'status') {
            patchLast({ content: 'Starting sandbox engine…' });
          } else if (event.type === 'token') {
            setMessages((prev) => {
              const updated = [...prev];
              const idx = updated.length - 1;
              updated[idx] = { ...updated[idx], content: `${updated[idx].content} ${event.value}`.trim() };
              return updated;
            });
          } else if (event.type === 'artifact') {
            setMessages((prev) => {
              const updated = [...prev];
              const idx = updated.length - 1;
              updated[idx] = { ...updated[idx], artifacts: [...updated[idx].artifacts, event as Artifact] };
              return updated;
            });
          } else if (event.type === 'error') {
            patchLast({ content: event.value, streaming: false, errored: true });
            reading = false;
          } else if (event.type === 'done') {
            patchLast({ code: event.code, streaming: false });
          }
        }
      }
    } catch {
      patchLast({ content: 'Connection error. Is the backend running?', streaming: false, errored: true });
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <PageContainer>
      <SectionHeader
        title="Jeli Lab"
        description="Ask questions about your own data across Pazuru and Tsumi. Jeli writes and runs Python in an isolated sandbox."
        className="mb-6"
      />

      <Card>
        <CardContent className="flex h-[60vh] flex-col gap-4 p-6">
          <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
            {messages.map((msg, i) => (
              <div key={i} className={`max-w-[80%] ${msg.role === 'user' ? 'self-end' : 'self-start'}`}>
                <div
                  className={`rounded-[var(--radius-md)] border px-3.5 py-2.5 text-sm ${
                    msg.role === 'user'
                      ? 'border-transparent bg-[var(--color-accent)] text-[var(--color-accent-fg)]'
                      : 'border-[var(--color-bg-border)] bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)]'
                  }`}
                >
                  {msg.content}
                  {msg.streaming && <span className="animate-pulse">▍</span>}
                </div>

                {msg.artifacts.map((a, j) =>
                  a.kind === 'table' ? (
                    <table key={j} className="mt-2 w-full text-xs" style={{ borderCollapse: 'collapse' }}>
                      <thead>
                        <tr>
                          {Object.keys(a.data[0] ?? {}).map((col) => (
                            <th
                              key={col}
                              className="border-b border-[var(--color-bg-border)] px-2 py-1 text-left text-[var(--color-text-secondary)]"
                            >
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {a.data.map((row, r) => (
                          <tr key={r}>
                            {Object.values(row).map((val, c) => (
                              <td key={c} className="border-b border-[var(--color-bg-border)] px-2 py-1 text-[var(--color-text-primary)]">
                                {String(val)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <img
                      key={j}
                      src={`data:${a.mime};base64,${a.base64}`}
                      alt="chart"
                      className="mt-2 max-w-full rounded-[var(--radius-md)]"
                    />
                  )
                )}

                {msg.code && (
                  <details className="mt-1.5 text-xs">
                    <summary className="cursor-pointer text-[var(--color-text-secondary)]">Show code</summary>
                    <pre className="mt-1 overflow-x-auto rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)] p-2 text-[var(--color-text-primary)]">
                      {msg.code}
                    </pre>
                  </details>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="flex flex-col gap-2">
            <label
              className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)]"
              title="Searches the public web via a local search instance; results are not saved beyond this conversation's memory."
            >
              <input type="checkbox" checked={allowInternet} onChange={(e) => setAllowInternet(e.target.checked)} />
              Allow web search for this question
            </label>
            <div className="text-[11px] text-[var(--color-text-secondary)]">
              Searches the public web via a local search instance; results are not saved beyond this conversation's memory.
            </div>
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') void sendMessage(); }}
                placeholder="Ask about your finances…"
                className="flex-1 rounded-[var(--radius-md)] border border-[var(--color-bg-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
              />
              <Button onClick={() => void sendMessage()} disabled={isStreaming}>
                Send
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}
