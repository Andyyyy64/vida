import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { marked } from 'marked';
import { api } from '../lib/api';

// Configure marked for safe, compact output
marked.setOptions({
  breaks: true,
  gfm: true,
});

function renderMarkdown(text: string): string {
  return marked.parse(text, { async: false }) as string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: { type: string; timestamp: string; preview: string; distance: number }[];
}

// Inline SVG icons (no emoji)
function ChatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4 }}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <circle cx="12" cy="10" r="3" strokeWidth="1.5" />
    </svg>
  );
}

export function RagChat() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleSend = async () => {
    const query = input.trim();
    if (!query || loading) return;

    const userMsg: Message = { role: 'user', content: query };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const result = await api.rag.ask(query, history);
      const assistantMsg: Message = {
        role: 'assistant',
        content: result.response,
        sources: result.sources,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: t('ragChat.error') },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const fmtTime = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString('ja-JP', {
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  const typeLabel = (type: string) => {
    switch (type) {
      case 'frame': return t('ragChat.sourceFrame');
      case 'chat': return t('ragChat.sourceChat');
      case 'summary': return t('ragChat.sourceSummary');
      default: return type;
    }
  };

  return (
    <>
      <button
        className={`rag-chat-fab ${isOpen ? 'rag-chat-fab--open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        title={t('ragChat.title')}
        aria-label={t('ragChat.title')}
      >
        {isOpen ? '\u00d7' : <ChatIcon />}
      </button>

      {isOpen && (
        <div className="rag-chat-panel">
          <div className="rag-chat-header">
            <span className="rag-chat-title">{t('ragChat.title')}</span>
            <button className="rag-chat-close" onClick={() => setIsOpen(false)}>&times;</button>
          </div>

          <div className="rag-chat-messages">
            {messages.length === 0 && (
              <div className="rag-chat-empty">
                <SearchIcon />
                <p>{t('ragChat.placeholder')}</p>
                <div className="rag-chat-suggestions">
                  {[t('ragChat.suggestion1'), t('ragChat.suggestion2'), t('ragChat.suggestion3')].map((s, i) => (
                    <button
                      key={i}
                      className="rag-chat-suggestion"
                      onClick={() => {
                        setInput(s);
                        inputRef.current?.focus();
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} fmtTime={fmtTime} typeLabel={typeLabel} t={t} />
            ))}

            {loading && (
              <div className="rag-chat-msg rag-chat-msg--assistant">
                <div className="rag-chat-msg-bubble rag-chat-loading">
                  <span className="rag-chat-dot"></span>
                  <span className="rag-chat-dot"></span>
                  <span className="rag-chat-dot"></span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div className="rag-chat-input-area">
            <textarea
              ref={inputRef}
              className="rag-chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('ragChat.inputPlaceholder')}
              rows={1}
              disabled={loading}
            />
            <button
              className="rag-chat-send"
              onClick={handleSend}
              disabled={!input.trim() || loading}
              title={t('ragChat.send')}
            >
              {'\u2191'}
            </button>
          </div>
        </div>
      )}
    </>
  );
}

// Separate component so markdown is memoized per message
function MessageBubble({ msg, fmtTime, typeLabel, t }: {
  msg: Message;
  fmtTime: (ts: string) => string;
  typeLabel: (type: string) => string;
  t: (key: string) => string;
}) {
  const html = useMemo(() => {
    if (msg.role === 'assistant') {
      return renderMarkdown(msg.content);
    }
    return null;
  }, [msg.content, msg.role]);

  return (
    <div className={`rag-chat-msg rag-chat-msg--${msg.role}`}>
      <div className="rag-chat-msg-bubble">
        {html ? (
          <div className="rag-chat-msg-content rag-chat-md" dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <div className="rag-chat-msg-content">{msg.content}</div>
        )}
        {msg.sources && msg.sources.length > 0 && (
          <div className="rag-chat-sources">
            <span className="rag-chat-sources-label">{t('ragChat.sources')}</span>
            {msg.sources.slice(0, 5).map((s, j) => (
              <div key={j} className="rag-chat-source">
                <span className="rag-chat-source-type">{typeLabel(s.type)}</span>
                <span className="rag-chat-source-time">{fmtTime(s.timestamp)}</span>
                {s.preview && <span className="rag-chat-source-preview">{s.preview.slice(0, 80)}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
