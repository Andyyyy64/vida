import { useState, useEffect, useCallback } from 'react';
import type { Frame } from '../lib/types';
import { activityColor } from '../lib/activity';
import { AudioPlayer } from './AudioPlayer';

interface Props {
  frame: Frame | null;
}

export function DetailPanel({ frame }: Props) {
  const [modalSrc, setModalSrc] = useState<string | null>(null);

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
        <div className="panel-empty">フレームを選択してください</div>
      </div>
    );
  }

  const time = new Date(frame.timestamp);
  const color = activityColor(frame.activity);

  // Collect screen paths
  const screenPaths: { label: string; path: string }[] = [];
  if (frame.screen_path) {
    screenPaths.push({ label: 'メイン', path: frame.screen_path });
  }
  if (frame.screen_extra_paths) {
    frame.screen_extra_paths.split(',').filter(Boolean).forEach((p, i) => {
      screenPaths.push({ label: `変化${i + 1}`, path: p });
    });
  }

  return (
    <div className="detail-panel">
      <div className="panel-header">
        {time.toLocaleTimeString('ja-JP')}
        <span className="detail-id">#{frame.id}</span>
      </div>

      {/* 総合分析 */}
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

      {/* カメラ */}
      {frame.path && (
        <DetailSection title="カメラ">
          <div className="detail-image-wrap" onClick={() => setModalSrc(`/media/${frame.path}`)}>
            <img src={`/media/${frame.path}`} alt="カメラ" className="detail-img" />
          </div>
        </DetailSection>
      )}

      {/* 画面 */}
      {screenPaths.length > 0 && (
        <DetailSection title="画面">
          <ScreenStrip screens={screenPaths} onClickImage={setModalSrc} />
        </DetailSection>
      )}

      {/* 音声 */}
      {frame.audio_path && (
        <DetailSection title="音声">
          <AudioPlayer audioPath={frame.audio_path} transcription={frame.transcription} />
        </DetailSection>
      )}

      {/* メタデータ */}
      <DetailSection title="メタデータ">
        <div className="detail-meta">
          {frame.foreground_window && (() => {
            const sep = frame.foreground_window.indexOf('|');
            const proc = sep >= 0 ? frame.foreground_window.slice(0, sep) : frame.foreground_window;
            const title = sep >= 0 ? frame.foreground_window.slice(sep + 1) : '';
            return (
              <>
                <div className="meta-row">
                  <span className="meta-key">アプリ</span>
                  <span className="meta-value">{proc}</span>
                </div>
                {title && (
                  <div className="meta-row">
                    <span className="meta-key">ウィンドウ</span>
                    <span className="meta-value" style={{ fontSize: 11 }}>{title}</span>
                  </div>
                )}
              </>
            );
          })()}
          <div className="meta-row">
            <span className="meta-key">シーン</span>
            <span className={`meta-value scene-${frame.scene_type}`}>{frame.scene_type}</span>
          </div>
          <div className="meta-row">
            <span className="meta-key">動き</span>
            <span className="meta-value">{(frame.motion_score * 100).toFixed(1)}%</span>
          </div>
          <div className="meta-row">
            <span className="meta-key">明るさ</span>
            <span className="meta-value">{frame.brightness.toFixed(0)}</span>
          </div>
        </div>
      </DetailSection>

      {/* Image modal */}
      {modalSrc && (
        <div className="img-modal-overlay" onClick={closeModal}>
          <img src={modalSrc} alt="拡大" className="img-modal-image" onClick={(e) => e.stopPropagation()} />
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
  const [selected, setSelected] = useState(0);

  return (
    <div className="screen-strip">
      <div className="screen-strip-main" onClick={() => onClickImage(`/media/${screens[selected].path}`)}>
        <img
          src={`/media/${screens[selected].path}`}
          alt={`画面 ${screens[selected].label}`}
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
