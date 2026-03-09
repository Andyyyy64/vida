import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';
import type { ChatChannel } from '../lib/types';
import { LOCALE_MAP } from '../i18n';

interface Props {
  date: string;
  onClose: () => void;
}

export function ChatModal({ date, onClose }: Props) {
  const { t, i18n } = useTranslation();
  const [channels, setChannels] = useState<ChatChannel[]>([]);
  const [total, setTotal] = useState(0);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const locale = LOCALE_MAP[i18n.language] || LOCALE_MAP[i18n.language.split('-')[0]] || 'en-US';

  useEffect(() => {
    api.chat(date).then((d) => {
      setChannels(d.channels);
      setTotal(d.total);
      if (d.channels.length <= 8) {
        setExpanded(new Set(d.channels.map((c) => c.channel_id)));
      }
    }).catch(() => {
      setChannels([]);
      setTotal(0);
    });
  }, [date]);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const fmtTime = (ts: string) =>
    new Date(ts).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="dashboard-overlay" onClick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}>
      <div className="chat-modal">
        <div className="dashboard-header">
          <span className="dashboard-title">{t('chat.title', { date })}</span>
          <span className="chat-modal-total">{t('common.messages_count', { count: total })}</span>
          <button className="dashboard-close" onClick={onClose}>×</button>
        </div>

        {total === 0 ? (
          <div className="panel-empty">{t('chat.noChat')}</div>
        ) : (
          <div className="chat-modal-body">
            {channels.map((ch) => {
              const isOpen = expanded.has(ch.channel_id);
              const label = ch.guild_name
                ? `${ch.guild_name} / ${ch.channel_name}`
                : ch.channel_name || t('common.dm');

              return (
                <div key={ch.channel_id} className="chat-modal-channel">
                  <button
                    className="chat-modal-ch-header"
                    onClick={() => toggle(ch.channel_id)}
                  >
                    <span className="chat-modal-ch-name">{label}</span>
                    <span className="chat-modal-ch-count">{ch.messages.length}</span>
                  </button>
                  {isOpen && (
                    <div className="chat-modal-messages">
                      {ch.messages.map((m, i) => (
                        <div key={i} className="chat-modal-msg">
                          <span className="chat-modal-msg-time">{fmtTime(m.timestamp)}</span>
                          <span className="chat-modal-msg-text">{m.content}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
