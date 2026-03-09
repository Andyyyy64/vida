import { useTranslation } from 'react-i18next';

interface MemoPanelProps {
  content: string;
  onChange: (value: string) => void;
  saving: boolean;
  readonly: boolean;
}

export function MemoPanel({ content, onChange, saving, readonly }: MemoPanelProps) {
  const { t } = useTranslation();

  return (
    <div className="memo-panel">
      <div className="panel-header">
        <span>{t('memo.title')}</span>
        {saving && <span className="memo-status">{t('common.saving')}</span>}
      </div>
      <textarea
        className="memo-textarea"
        value={content}
        onChange={(e) => onChange(e.target.value)}
        readOnly={readonly}
        placeholder={readonly ? t('memo.noMemo') : t('memo.placeholder')}
        style={readonly ? { opacity: 0.5 } : undefined}
      />
    </div>
  );
}
