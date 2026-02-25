interface Props {
  audioPath: string;
  transcription: string;
}

export function AudioPlayer({ audioPath, transcription }: Props) {
  return (
    <div className="detail-section">
      <div className="detail-label">音声</div>
      <audio controls className="audio-player" preload="none">
        <source src={`/media/${audioPath}`} type="audio/wav" />
      </audio>
      {transcription && <div className="transcription">{transcription}</div>}
    </div>
  );
}
