import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';
import { getRuntime } from '../lib/runtime';
import type { ProviderValidationResult } from '../lib/types';

interface Props {
  onClose: () => void;
  onOpenSettings: () => void;
}

interface OnboardingSettingsData {
  llm: {
    provider: string;
    gemini_model: string;
    claude_model: string;
    codex_model: string;
  };
  env_masked: Record<string, string>;
}

const STORAGE_KEY = 'vida_onboarded';

const DEFAULT_SETTINGS_DATA: OnboardingSettingsData = {
  llm: {
    provider: 'claude',
    gemini_model: 'gemini-3.1-flash-lite-preview',
    claude_model: 'haiku',
    codex_model: 'gpt-5.4',
  },
  env_masked: {},
};

export function isOnboarded(): boolean {
  return localStorage.getItem(STORAGE_KEY) === '1';
}

const DEFAULT_CONTEXT = `# コンテキスト

## ユーザー
- 名前:
- 職業:
- 性格/趣味:

## 環境
- 作業場所:
- OS/環境:

## よく登場する人
-

## よく使うツール
-

## メモ
-
`;

function normalizeSettingsData(input: Partial<OnboardingSettingsData> | null | undefined): OnboardingSettingsData {
  const provider = input?.llm?.provider === 'external'
    ? DEFAULT_SETTINGS_DATA.llm.provider
    : input?.llm?.provider ?? DEFAULT_SETTINGS_DATA.llm.provider;
  return {
    llm: {
      provider,
      gemini_model: input?.llm?.gemini_model ?? DEFAULT_SETTINGS_DATA.llm.gemini_model,
      claude_model: input?.llm?.claude_model ?? DEFAULT_SETTINGS_DATA.llm.claude_model,
      codex_model: input?.llm?.codex_model ?? DEFAULT_SETTINGS_DATA.llm.codex_model,
    },
    env_masked: input?.env_masked ?? DEFAULT_SETTINGS_DATA.env_masked,
  };
}

export function Onboarding({ onClose, onOpenSettings }: Props) {
  const { t, i18n } = useTranslation();
  const [step, setStep] = useState(0);
  const [context, setContext] = useState('');
  const [settingsData, setSettingsData] = useState<OnboardingSettingsData>(DEFAULT_SETTINGS_DATA);
  const [geminiApiKey, setGeminiApiKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [setupError, setSetupError] = useState('');
  const [checkingProvider, setCheckingProvider] = useState(false);
  const [providerValidation, setProviderValidation] = useState<ProviderValidationResult | null>(null);
  const validationRunId = useRef(0);
  const totalSteps = 4;

  const isDemo = getRuntime().isDemo;
  const selectedProvider = settingsData.llm.provider;
  const providerLabel = useMemo(
    () => t(`settings.llm.providers.${selectedProvider}`),
    [selectedProvider, t],
  );

  // Load existing context + settings
  useEffect(() => {
    Promise.all([
      api.context.get().catch(() => ({ content: DEFAULT_CONTEXT })),
      api.settings.get().catch(() => null) as Promise<Partial<OnboardingSettingsData> | null>,
    ]).then(([ctx, settings]) => {
      setContext(ctx.content || DEFAULT_CONTEXT);
      setSettingsData(normalizeSettingsData(settings));
    }).catch(() => {
      setContext(DEFAULT_CONTEXT);
      setSettingsData(DEFAULT_SETTINGS_DATA);
    });
  }, []);

  const saveContext = useCallback(async () => {
    if (isDemo || !context.trim()) return;
    setSaving(true);
    try {
      await api.context.put(context);
    } finally {
      setSaving(false);
    }
  }, [context, isDemo]);

  const saveSetup = useCallback(async () => {
    if (isDemo) return;
    setSaving(true);
    setSetupError('');
    try {
      const env: Record<string, string> = {};
      if (geminiApiKey.trim()) {
        env.GEMINI_API_KEY = geminiApiKey.trim();
      }
      await api.settings.put({
        llm: settingsData.llm,
        env,
      });
      window.dispatchEvent(new CustomEvent('vida:settings-updated'));
    } catch (error) {
      setSetupError(String(error));
      throw error;
    } finally {
      setSaving(false);
    }
  }, [geminiApiKey, isDemo, settingsData.llm]);

  const finish = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, '1');
    onClose();
  }, [onClose]);

  const handleNext = useCallback(async () => {
    try {
      if (step === 1 && context.trim()) {
        await saveContext();
      }
      if (step === 2) {
        await saveSetup();
      }
      if (step < totalSteps - 1) {
        setStep(step + 1);
      } else {
        finish();
      }
    } catch {
      // saveSetup already surfaced the error
    }
  }, [context, finish, saveContext, saveSetup, step, totalSteps]);

  const handleEsc = useCallback(
    (e: KeyboardEvent) => { if (e.key === 'Escape') finish(); },
    [finish],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [handleEsc]);

  useEffect(() => {
    if (step !== 2) return;

    validationRunId.current += 1;
    const runId = validationRunId.current;
    setSetupError('');

    if (isDemo) {
      setCheckingProvider(false);
      setProviderValidation({ ok: true, code: 'ready' });
      return;
    }

    if (
      selectedProvider === 'gemini'
      && !geminiApiKey.trim()
      && !settingsData.env_masked.GEMINI_API_KEY
    ) {
      setCheckingProvider(false);
      setProviderValidation({ ok: false, code: 'missing_api_key' });
      return;
    }

    setCheckingProvider(true);
    setProviderValidation(null);

    const timer = window.setTimeout(() => {
      api.settings.validateProvider({
        provider: settingsData.llm.provider,
        gemini_model: settingsData.llm.gemini_model,
        claude_model: settingsData.llm.claude_model,
        codex_model: settingsData.llm.codex_model,
        gemini_api_key: geminiApiKey.trim() || undefined,
      }).then((result) => {
        if (validationRunId.current !== runId) return;
        setProviderValidation(result);
      }).catch((error) => {
        if (validationRunId.current !== runId) return;
        setProviderValidation({
          ok: false,
          code: 'request_failed',
          detail: String(error),
        });
      }).finally(() => {
        if (validationRunId.current === runId) {
          setCheckingProvider(false);
        }
      });
    }, 350);

    return () => window.clearTimeout(timer);
  }, [
    geminiApiKey,
    isDemo,
    selectedProvider,
    settingsData.env_masked.GEMINI_API_KEY,
    settingsData.llm.claude_model,
    settingsData.llm.codex_model,
    settingsData.llm.gemini_model,
    settingsData.llm.provider,
    step,
  ]);

  function setLlm<K extends keyof OnboardingSettingsData['llm']>(key: K, value: OnboardingSettingsData['llm'][K]) {
    setSettingsData((current) => ({
      ...current,
      llm: {
        ...current.llm,
        [key]: value,
      },
    }));
  }

  function validationMessage(result: ProviderValidationResult | null): string {
    if (checkingProvider) {
      return t('onboarding.setup.status.checking', { provider: providerLabel });
    }
    if (!result) {
      return '';
    }
    switch (result.code) {
      case 'ready':
        return t('onboarding.setup.status.ready', { provider: providerLabel });
      case 'external':
        return t('onboarding.setup.status.external');
      case 'missing_api_key':
        return t('onboarding.setup.status.missingApiKey');
      case 'missing_binary':
        return t('onboarding.setup.status.missingBinary', { provider: providerLabel });
      case 'binary_found_but_failed':
        return t('onboarding.setup.status.binaryFoundButFailed', { provider: providerLabel });
      case 'python_not_found':
        return t('onboarding.setup.status.pythonNotFound');
      case 'checker_not_found':
        return t('onboarding.setup.status.checkerNotFound');
      case 'invalid_provider':
        return t('onboarding.setup.status.invalidProvider');
      default:
        return t('onboarding.setup.status.requestFailed', { provider: providerLabel });
    }
  }

  function canProceedFromSetup(result: ProviderValidationResult | null): boolean {
    if (!result) return false;
    return result.ok || result.code === 'binary_found_but_failed';
  }

  const nextDisabled = saving || (step === 2 && !isDemo && (checkingProvider || !canProceedFromSetup(providerValidation)));
  const statusText = validationMessage(providerValidation);
  const hasSavedGeminiKey = Boolean(settingsData.env_masked.GEMINI_API_KEY);

  function setLanguage(language: 'ja' | 'en') {
    i18n.changeLanguage(language);
  }

  return (
    <div
      className="onboarding-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) finish(); }}
    >
      <div className="onboarding-modal">
        <div className="onboarding-stepper">
          {Array.from({ length: totalSteps }, (_, i) => (
            <span
              key={i}
              className={`onboarding-dot ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}
            />
          ))}
        </div>

        <div className="onboarding-body">
          {step === 0 && (
            <>
              <div className="onboarding-language-picker" role="group" aria-label={t('onboarding.welcome.languageLabel')}>
                <span className="onboarding-field-label">{t('onboarding.welcome.languageLabel')}</span>
                <div className="onboarding-language-options">
                  <button
                    type="button"
                    className={`onboarding-language-button ${i18n.language.startsWith('ja') ? 'active' : ''}`}
                    onClick={() => setLanguage('ja')}
                  >
                    日本語
                  </button>
                  <button
                    type="button"
                    className={`onboarding-language-button ${i18n.language.startsWith('en') ? 'active' : ''}`}
                    onClick={() => setLanguage('en')}
                  >
                    English
                  </button>
                </div>
              </div>
              <h2 className="onboarding-title">{t('onboarding.welcome.title')}</h2>
              <p className="onboarding-description">{t('onboarding.welcome.description')}</p>
              <div className="onboarding-pillars">
                <div className="onboarding-pillar">
                  <span className="onboarding-pillar-icon">1</span>
                  <span className="onboarding-pillar-label">{t('onboarding.welcome.pillars.monitoring')}</span>
                </div>
                <div className="onboarding-pillar">
                  <span className="onboarding-pillar-icon">2</span>
                  <span className="onboarding-pillar-label">{t('onboarding.welcome.pillars.management')}</span>
                </div>
                <div className="onboarding-pillar">
                  <span className="onboarding-pillar-icon">3</span>
                  <span className="onboarding-pillar-label">{t('onboarding.welcome.pillars.analysis')}</span>
                </div>
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <h2 className="onboarding-title">{t('onboarding.profile.title')}</h2>
              <p className="onboarding-description">{t('onboarding.profile.description')}</p>
              {isDemo && <p className="onboarding-hint">{t('demo.onboardingReadonly')}</p>}
              <textarea
                className="onboarding-context-input"
                value={context}
                onChange={(e) => setContext(e.target.value)}
                rows={12}
                spellCheck={false}
                readOnly={isDemo}
              />
              <p className="onboarding-hint">{t('onboarding.profile.hint')}</p>
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="onboarding-title">{t('onboarding.setup.title')}</h2>
              <p className="onboarding-description">{t('onboarding.setup.description')}</p>
              {isDemo && <p className="onboarding-hint">{t('demo.settingsReadonly')}</p>}
              <fieldset className="onboarding-setup-form" disabled={isDemo}>
                <label className="onboarding-field">
                  <span className="onboarding-field-label">{t('onboarding.setup.providerLabel')}</span>
                  <select
                    className="onboarding-select"
                    value={settingsData.llm.provider}
                    onChange={(e) => setLlm('provider', e.target.value)}
                  >
                    <option value="claude">{t('settings.llm.providers.claude')}</option>
                    <option value="codex">{t('settings.llm.providers.codex')}</option>
                    <option value="gemini">{t('settings.llm.providers.gemini')}</option>
                  </select>
                </label>

                {selectedProvider === 'gemini' && (
                  <>
                    <label className="onboarding-field">
                      <span className="onboarding-field-label">{t('onboarding.setup.geminiApiKeyLabel')}</span>
                      <input
                        className="onboarding-input"
                        type="password"
                        value={geminiApiKey}
                        placeholder={hasSavedGeminiKey ? t('onboarding.setup.existingKeyPlaceholder') : 'AIza...'}
                        onChange={(e) => setGeminiApiKey(e.target.value)}
                        autoComplete="off"
                      />
                    </label>
                    <p className="onboarding-hint">
                      {hasSavedGeminiKey
                        ? t('onboarding.setup.geminiApiKeyHintExisting')
                        : t('onboarding.setup.geminiApiKeyHint')}
                    </p>
                    <label className="onboarding-field">
                      <span className="onboarding-field-label">{t('settings.llm.geminiModel')}</span>
                      <input
                        className="onboarding-input"
                        value={settingsData.llm.gemini_model}
                        onChange={(e) => setLlm('gemini_model', e.target.value)}
                        placeholder="gemini-3.1-flash-lite-preview"
                      />
                    </label>
                  </>
                )}

                {selectedProvider === 'claude' && (
                  <label className="onboarding-field">
                    <span className="onboarding-field-label">{t('settings.llm.claudeModel')}</span>
                    <input
                      className="onboarding-input"
                      value={settingsData.llm.claude_model}
                      onChange={(e) => setLlm('claude_model', e.target.value)}
                      placeholder="haiku"
                    />
                  </label>
                )}

                {selectedProvider === 'codex' && (
                  <label className="onboarding-field">
                    <span className="onboarding-field-label">{t('settings.llm.codexModel')}</span>
                    <input
                      className="onboarding-input"
                      value={settingsData.llm.codex_model}
                      onChange={(e) => setLlm('codex_model', e.target.value)}
                      placeholder="gpt-5.4"
                    />
                  </label>
                )}

                {statusText && (
                  <div className={`onboarding-provider-status ${checkingProvider ? 'checking' : providerValidation?.ok ? 'ok' : 'error'}`}>
                    {statusText}
                    {providerValidation?.detail && !providerValidation.ok && (
                      <span className="onboarding-provider-status-detail">{providerValidation.detail}</span>
                    )}
                  </div>
                )}

                <button
                  type="button"
                  className="onboarding-settings-btn onboarding-settings-btn--secondary"
                  onClick={() => {
                    finish();
                    onOpenSettings();
                  }}
                >
                  {t('onboarding.setup.openSettings')}
                </button>
              </fieldset>
              {setupError && <p className="onboarding-error">{setupError}</p>}
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="onboarding-title">{t('onboarding.start.title')}</h2>
              <p className="onboarding-description">{t('onboarding.start.description')}</p>
              <code className="onboarding-command">life start</code>
            </>
          )}
        </div>

        <div className="onboarding-footer">
          <button className="onboarding-skip-btn" onClick={finish}>
            {t('onboarding.skip')}
          </button>
          <div className="onboarding-nav">
            {step > 0 && (
              <button className="onboarding-back-btn" onClick={() => setStep(step - 1)}>
                {t('onboarding.back')}
              </button>
            )}
            <button className="onboarding-next-btn" onClick={handleNext} disabled={nextDisabled}>
              {step < totalSteps - 1 ? t('onboarding.next') : t('onboarding.start.done')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
