import { useState, useEffect, useCallback } from 'react';
import type { Frame } from '../lib/types';

const META_CATEGORIES: Record<string, string[]> = {
  focus: ['プログラミング', 'ドキュメント閲覧', 'コンテンツ制作', '読書'],
  communication: ['チャット', '会話'],
  entertainment: ['YouTube視聴', 'ゲーム', 'SNS', '音楽'],
  browsing: ['ブラウジング'],
  break: ['休憩', '離席', '食事'],
  idle: ['睡眠', '不在'],
};

const META_COLORS: Record<string, string> = {
  focus: '#60a860',
  communication: '#6088d0',
  entertainment: '#d06060',
  browsing: '#d0a840',
  break: '#888888',
  idle: '#444466',
  other: '#a060b0',
};

function activityColor(activity: string): string {
  if (!activity) return META_COLORS.other;
  for (const [meta, activities] of Object.entries(META_CATEGORIES)) {
    if (activities.includes(activity)) return META_COLORS[meta];
  }
  return META_COLORS.other;
}

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
          <audio controls className="audio-player" preload="none">
            <source src={`/media/${frame.audio_path}`} type="audio/wav" />
          </audio>
          {frame.transcription && (
            <div className="transcription">「{frame.transcription}」</div>
          )}
        </DetailSection>
      )}

      {/* メタデータ */}
      <DetailSection title="メタデータ">
        <div className="detail-meta">
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
