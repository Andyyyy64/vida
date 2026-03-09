import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { Frame } from '../lib/types';
import { activityColor } from '../lib/activity';
import { AudioPlayer } from './AudioPlayer';
import { LOCALE_MAP } from '../i18n';

interface Props {
  frame: Frame | null;
}

export function DetailPanel({ frame }: Props) {
  const { t, i18n } = useTranslation();
  const [modalSrc, setModalSrc] = useState<string | null>(null);
  const locale = LOCALE_MAP[i18n.language] || LOCALE_MAP[i18n.language.split('-')[0]] || 'en-US';

  const closeModal = useCallback(() => setModalSrc(null), []);

  useEffect(() => {
    if (!modalSrc) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeModal();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [modalSrc, closeModal]);

  if (!frame) {
    return (
      <div className="detail-panel">
        <div className="panel-empty">{t('detail.selectFrame')}</div>
      </div>
    );
  }

  const time = new Date(frame.timestamp);
  const color = activityColor(frame.activity);

  // Collect screen paths
  const screenPaths: { label: string; path: string }[] = [];
  if (frame.screen_path) {
    screenPaths.push({ label: t('detail.main'), path: frame.screen_path });
  }
  if (frame.screen_extra_paths) {
    frame.screen_extra_paths.split(',').filter(Boolean).forEach((p, i) => {
      screenPaths.push({ label: t('detail.change', { num: i + 1 }), path: p });
    });
  }

  return (
    <div className="detail-panel">
      <div className="panel-header">
        {time.toLocaleTimeString(locale)}
        <span className="detail-id">#{frame.id}</span>
      </div>

      {frame.claude_description && (
        <div className="detail-analysis">
          {frame.activity && (
            <span className="analysis-badge" style={{ background: color }}>
              {frame.activity}
            </span>
          )}
          <p className="analysis-text">{frame.claude_description}</p>
        </div>
      )}

      {frame.path && (
        <DetailSection title={t('detail.camera')}>
          <div className="detail-image-wrap" onClick={() => setModalSrc(`/media/${frame.path}`)}>
            <img src={`/media/${frame.path}`} alt={t('detail.camera')} className="detail-img" />
          </div>
        </DetailSection>
      )}

      {screenPaths.length > 0 && (
        <DetailSection title={t('detail.screen')}>
          <ScreenStrip screens={screenPaths} onClickImage={setModalSrc} />
        </DetailSection>
      )}

      {frame.audio_path && (
        <DetailSection title={t('detail.audio')}>
          <AudioPlayer audioPath={frame.audio_path} transcription={frame.transcription} />
        </DetailSection>
      )}

      <DetailSection title={t('detail.metadata')}>
        <div className="detail-meta">
          {frame.foreground_window && (() => {
            const sep = frame.foreground_window.indexOf('|');
            const proc = sep >= 0 ? frame.foreground_window.slice(0, sep) : frame.foreground_window;
            const title = sep >= 0 ? frame.foreground_window.slice(sep + 1) : '';
            return (
              <>
                <div className="meta-row">
                  <span className="meta-key">{t('detail.app')}</span>
                  <span className="meta-value">{proc}</span>
                </div>
                {title && (
                  <div className="meta-row">
                    <span className="meta-key">{t('detail.window')}</span>
                    <span className="meta-value" style={{ fontSize: 11 }}>{title}</span>
                  </div>
                )}
              </>
            );
          })()}
          <div className="meta-row">
            <span className="meta-key">{t('detail.scene')}</span>
            <span className={`meta-value scene-${frame.scene_type}`}>{frame.scene_type}</span>
          </div>
          <div className="meta-row">
            <span className="meta-key">{t('detail.motion')}</span>
            <span className="meta-value">{(frame.motion_score * 100).toFixed(1)}%</span>
          </div>
          <div className="meta-row">
            <span className="meta-key">{t('detail.brightness')}</span>
            <span className="meta-value">{frame.brightness.toFixed(0)}</span>
          </div>
        </div>
      </DetailSection>

      {modalSrc && (
        <div className="img-modal-overlay" onClick={closeModal}>
          <img src={modalSrc} alt={t('detail.enlarge')} className="img-modal-image" onClick={(e) => e.stopPropagation()} />
        </div>
      )}
    </div>
  );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="detail-section">
      <div className="detail-label">{title}</div>
      {children}
    </div>
  );
}

function ScreenStrip({ screens, onClickImage }: {
  screens: { label: string; path: string }[];
  onClickImage: (src: string) => void;
}) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState(0);

  return (
    <div className="screen-strip">
      <div className="screen-strip-main" onClick={() => onClickImage(`/media/${screens[selected].path}`)}>
        <img
          src={`/media/${screens[selected].path}`}
          alt={t('detail.screenLabel', { label: screens[selected].label })}
          className="detail-img"
        />
      </div>
      {screens.length > 1 && (
        <div className="screen-strip-thumbs">
          {screens.map((s, i) => (
            <button
              key={i}
              className={`screen-thumb ${i === selected ? 'active' : ''}`}
              onClick={() => setSelected(i)}
            >
              <img src={`/media/${s.path}`} alt={s.label} />
              <span className="screen-thumb-label">{s.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
