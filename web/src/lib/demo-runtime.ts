import type { Frame } from './types';

export const DEFAULT_LIVE_DATA_POLL_INTERVAL_MS = 30_000;
export const DEMO_LIVE_DATA_POLL_INTERVAL_MS = 1_000;

export function getLiveDataPollInterval(isDemo: boolean) {
  return isDemo ? DEMO_LIVE_DATA_POLL_INTERVAL_MS : DEFAULT_LIVE_DATA_POLL_INTERVAL_MS;
}

function findClosestFrame(target: Frame, frames: Frame[]) {
  const targetTime = new Date(target.timestamp).getTime();
  if (Number.isNaN(targetTime)) return target;

  let closestFrame = frames[0];
  let closestDiff = Math.abs(new Date(closestFrame.timestamp).getTime() - targetTime);

  for (const frame of frames.slice(1)) {
    const frameTime = new Date(frame.timestamp).getTime();
    if (Number.isNaN(frameTime)) continue;
    const diff = Math.abs(frameTime - targetTime);
    if (diff < closestDiff) {
      closestFrame = frame;
      closestDiff = diff;
    }
  }

  return closestFrame;
}

export function resolveDemoSelectedFrame({
  isDemo,
  autoFollowLatest,
  previousSelectedFrame,
  frames,
}: {
  isDemo: boolean;
  autoFollowLatest: boolean;
  previousSelectedFrame: Frame | null;
  frames: Frame[];
}) {
  if (frames.length === 0) return null;
  if (!isDemo) return previousSelectedFrame;

  const latestFrame = frames[frames.length - 1];
  if (autoFollowLatest || !previousSelectedFrame) {
    return latestFrame;
  }

  const matchingFrame = frames.find((frame) => frame.timestamp === previousSelectedFrame.timestamp);
  if (matchingFrame) return matchingFrame;

  return findClosestFrame(previousSelectedFrame, frames);
}
