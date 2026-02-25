import type { Frame } from '../lib/types';
import { FrameViewer } from './FrameViewer';
import { AudioPlayer } from './AudioPlayer';

interface Props {
  frame: Frame | null;
}

export function DetailPanel({ frame }: Props) {
  if (!frame) {
    return (
      <div className="detail-panel">
        <div className="panel-empty">フレームを選択してください</div>
      </div>
    );
  }

  const time = new Date(frame.timestamp);

  return (
    <div className="detail-panel">
      <div className="panel-header">
        {time.toLocaleTimeString('ja-JP')}
        <span className="detail-id">#{frame.id}</span>
      </div>

      <FrameViewer framePath={frame.path} screenPath={frame.screen_path} />

      {frame.audio_path && (
        <AudioPlayer audioPath={frame.audio_path} transcription={frame.transcription} />
      )}

      {frame.claude_description && (
        <div className="detail-section">
          <div className="detail-label">分析</div>
          <div className="detail-text">{frame.claude_description}</div>
        </div>
      )}

      <div className="detail-section">
        <div className="detail-label">メタデータ</div>
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
      </div>
    </div>
  );
}
