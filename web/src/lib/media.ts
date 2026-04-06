import { convertFileSrc } from '@tauri-apps/api/core';

const IS_TAURI = !!(window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__;

/** Global data directory set at startup in Tauri mode. */
let _dataDir = '';

/**
 * Set the data directory (called once at startup from Tauri's get_data_dir command).
 */
export function setDataDir(dir: string): void {
  _dataDir = dir;
}

/**
 * Resolve a relative media path to a usable URL.
 *
 * Tauri mode: uses `asset://` protocol via `convertFileSrc()` with the
 * absolute path derived from the data directory.
 *
 * Browser mode (dev with Vite proxy): falls back to `/media/<path>`.
 */
export function mediaUrl(relativePath: string): string {
  if (!relativePath) return '';
  if (IS_TAURI && _dataDir) {
    // convertFileSrc needs an absolute path; the data_dir + relative path gives us that.
    // Normalize path separators for the platform.
    const absPath = `${_dataDir}/${relativePath}`.replace(/\\/g, '/');
    return convertFileSrc(absPath);
  }
  return `/media/${relativePath}`;
}
