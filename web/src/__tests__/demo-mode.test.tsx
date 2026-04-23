import { fireEvent, render, screen } from '@testing-library/react';
import { vi, test, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom/vitest';

const {
  mockSettingsGet,
  mockSettingsPut,
  mockValidateProvider,
  mockDevicesGet,
  mockContextGet,
  mockContextPut,
} = vi.hoisted(() => ({
  mockSettingsGet: vi.fn(),
  mockSettingsPut: vi.fn(),
  mockValidateProvider: vi.fn(),
  mockDevicesGet: vi.fn(),
  mockContextGet: vi.fn(),
  mockContextPut: vi.fn(),
}));

vi.mock('../lib/runtime', () => ({
  getRuntime: () => ({
    isDemo: true,
    liveFeed: {
      streamUrl: null,
      poseUrl: null,
      healthUrl: null,
      isLive: false,
    },
  }),
}));

vi.mock('../lib/api', () => ({
  api: {
    settings: { get: mockSettingsGet, put: mockSettingsPut, validateProvider: mockValidateProvider },
    devices: { get: mockDevicesGet },
    context: { get: mockContextGet, put: mockContextPut },
  },
}));

vi.mock('../lib/media', () => ({
  mediaUrl: (path: string) => `mocked:${path}`,
}));

import { LiveFeed } from '../components/LiveFeed';
import { Onboarding } from '../components/Onboarding';
import { Settings } from '../components/Settings';
import '../i18n';

function fullSettings() {
  return {
    llm: { provider: 'gemini', gemini_model: 'gemini-3.1-flash-lite-preview', claude_model: 'haiku', codex_model: 'gpt-5.4' },
    capture: { device: 0, interval_sec: 30, audio_device: '' },
    presence: { enabled: true, sleep_start_hour: 23, sleep_end_hour: 8 },
    chat: { enabled: false, discord_enabled: false, discord_poll_interval: 60, discord_backfill_months: 3 },
    env: {},
    env_masked: { GEMINI_API_KEY: '********' },
  };
}

beforeEach(() => {
  localStorage.clear();
  mockSettingsGet.mockReset();
  mockSettingsPut.mockReset();
  mockValidateProvider.mockReset();
  mockDevicesGet.mockReset();
  mockContextGet.mockReset();
  mockContextPut.mockReset();
  mockSettingsGet.mockResolvedValue(fullSettings());
  mockValidateProvider.mockResolvedValue({ ok: true, code: 'ready' });
  mockDevicesGet.mockResolvedValue({ cameras: [], audio: [] });
  mockContextGet.mockResolvedValue({ content: '' });
});

test('LiveFeed shows a clickable demo preview slot instead of an empty slot', async () => {
  render(<LiveFeed />);
  expect(await screen.findByText('Demo')).toBeInTheDocument();
  expect(document.getElementById('demo-live-feed-preview-slot')).not.toBeNull();
});

test('Settings disables save controls and profile editing in demo mode', async () => {
  render(<Settings onClose={() => {}} />);
  const badges = await screen.findAllByText(/read-only/i);
  expect(badges.length).toBeGreaterThanOrEqual(1);
  expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();
  expect(screen.getByDisplayValue('gemini-3.1-flash-lite-preview')).toBeDisabled();
  expect(document.querySelector('.settings-context-input')).toHaveAttribute('readonly');
});

test('Settings tolerates partial settings payloads without crashing', async () => {
  mockSettingsGet.mockResolvedValueOnce({
    env_masked: { GEMINI_API_KEY: '********' },
  });

  render(<Settings onClose={() => {}} />);

  const badges = await screen.findAllByText(/read-only/i);
  expect(badges.length).toBeGreaterThanOrEqual(1);
  expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();
});

test('Onboarding keeps the profile step visible but non-editable in demo mode', async () => {
  render(<Onboarding onClose={() => {}} onOpenSettings={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: /next/i }));
  expect(await screen.findByText(/tell us about yourself/i)).toBeInTheDocument();
  expect(document.querySelector('.onboarding-context-input')).toHaveAttribute('readonly');
});
