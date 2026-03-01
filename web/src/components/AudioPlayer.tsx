import { useRef, useState, useEffect, useCallback } from 'react';

interface Props {
  audioPath: string;
  transcription?: string;
}

export function AudioPlayer({ audioPath, transcription }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [seeking, setSeeking] = useState(false);

  const src = `/media/${audioPath}`;

  // Reset state when audio source changes
  useEffect(() => {
    setPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  }, [src]);

  const onLoadedMetadata = useCallback(() => {
    const audio = audioRef.current;
    if (audio && isFinite(audio.duration)) {
      setDuration(audio.duration);
    }
  }, []);

  const onTimeUpdate = useCallback(() => {
    if (!seeking && audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  }, [seeking]);

  const onEnded = useCallback(() => {
    setPlaying(false);
    setCurrentTime(0);
  }, []);

  // Also try to get duration from durationchange (WAV files sometimes fire this later)
  const onDurationChange = useCallback(() => {
    const audio = audioRef.current;
    if (audio && isFinite(audio.duration) && audio.duration > 0) {
      setDuration(audio.duration);
    }
  }, []);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      audio.play();
      setPlaying(true);
    }
  }, [playing]);

  const onSeekStart = useCallback(() => {
    setSeeking(true);
  }, []);

  const onSeekChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    setCurrentTime(time);
  }, []);

  const onSeekEnd = useCallback((e: React.MouseEvent<HTMLInputElement> | React.TouchEvent<HTMLInputElement>) => {
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = currentTime;
    }
    setSeeking(false);
  }, [currentTime]);

  const fmt = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <div className="custom-audio-player">
      <audio
        ref={audioRef}
        src={src}
        preload="auto"
        onLoadedMetadata={onLoadedMetadata}
        onDurationChange={onDurationChange}
        onTimeUpdate={onTimeUpdate}
        onEnded={onEnded}
      />
      <button className="audio-play-btn" onClick={togglePlay} type="button">
        {playing ? '⏸' : '▶'}
      </button>
      <span className="audio-time">{fmt(currentTime)}</span>
      <input
        type="range"
        className="audio-seek"
        min={0}
        max={duration || 0}
        step={0.1}
        value={currentTime}
        onMouseDown={onSeekStart}
        onTouchStart={onSeekStart}
        onChange={onSeekChange}
        onMouseUp={onSeekEnd}
        onTouchEnd={onSeekEnd}
      />
      <span className="audio-time">{fmt(duration)}</span>
    </div>
  );
}
