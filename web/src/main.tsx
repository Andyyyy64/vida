import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ToastProvider } from './components/ToastProvider';
import { setDataDir } from './lib/media';
import './i18n';
import './global.css';

const IS_TAURI = !!(window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__;

async function init() {
  if (IS_TAURI) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const dataDir = await invoke<string>('get_data_dir');
      setDataDir(dataDir);
    } catch (e) {
      console.warn('Failed to get data_dir from Tauri:', e);
    }
  }

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ErrorBoundary>
        <ToastProvider>
          <App />
        </ToastProvider>
      </ErrorBoundary>
    </StrictMode>,
  );
}

init();
