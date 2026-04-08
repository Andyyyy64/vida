import { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';
import { getRuntime } from '../lib/runtime';

interface Props {
  onClose: () => void;
  onOpenSettings: () => void;
}

const STORAGE_KEY = 'homelife_onboarded';

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

export function Onboarding({ onClose, onOpenSettings }: Props) {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  const [context, setContext] = useState('');
  const [saving, setSaving] = useState(false);
  const totalSteps = 4;

  // Load existing context
  useEffect(() => {
    api.context.get().then((res) => {
      setContext(res.content || DEFAULT_CONTEXT);
    }).catch(() => {
      setContext(DEFAULT_CONTEXT);
    });
  }, []);

  const isDemo = getRuntime().isDemo;

  const saveContext = useCallback(async () => {
    if (isDemo || !context.trim()) return;
    setSaving(true);
    try {
      await api.context.put(context);
    } catch {
      // silent fail
    } finally {
      setSaving(false);
    }
  }, [context, isDemo]);

  const finish = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, '1');
    onClose();
  }, [onClose]);

  const handleNext = useCallback(async () => {
    // Save context when leaving profile step
    if (step === 1 && context.trim()) {
      await saveContext();
    }
    if (step < totalSteps - 1) {
      setStep(step + 1);
    } else {
      finish();
    }
  }, [step, totalSteps, context, saveContext, finish]);

  const handleEsc = useCallback(
    (e: KeyboardEvent) => { if (e.key === 'Escape') finish(); },
    [finish],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [handleEsc]);

  return (
    <div
      className="onboarding-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) finish(); }}
    >
      <div className="onboarding-modal">
        {/* Step indicator */}
        <div className="onboarding-stepper">
          {Array.from({ length: totalSteps }, (_, i) => (
            <span
              key={i}
              className={`onboarding-dot ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}
            />
          ))}
        </div>

        {/* Step content */}
        <div className="onboarding-body">
          {step === 0 && (
            <>
              <h2 className="onboarding-title">{t('onboarding.welcome.title')}</h2>
              <p className="onboarding-description">{t('onboarding.welcome.description')}</p>
              <div className="onboarding-pillars">
                <div className="onboarding-pillar">
                  <span className="onboarding-pillar-icon">1</span>
                  <span className="onboarding-pillar-label">Monitoring</span>
                </div>
                <div className="onboarding-pillar">
                  <span className="onboarding-pillar-icon">2</span>
                  <span className="onboarding-pillar-label">Management</span>
                </div>
                <div className="onboarding-pillar">
                  <span className="onboarding-pillar-icon">3</span>
                  <span className="onboarding-pillar-label">Analysis</span>
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
              <button
                className="onboarding-settings-btn"
                onClick={() => {
                  finish();
                  onOpenSettings();
                }}
              >
                {t('onboarding.setup.openSettings')}
              </button>
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

        {/* Footer */}
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
            <button className="onboarding-next-btn" onClick={handleNext} disabled={saving}>
              {step < totalSteps - 1 ? t('onboarding.next') : t('onboarding.start.done')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
