interface MemoPanelProps {
  content: string;
  onChange: (value: string) => void;
  saving: boolean;
  readonly: boolean;
}

export function MemoPanel({ content, onChange, saving, readonly }: MemoPanelProps) {
  return (
    <div className="memo-panel">
      <div className="panel-header">
        <span>Memo</span>
        {saving && <span className="memo-status">saving...</span>}
      </div>
      <textarea
        className="memo-textarea"
        value={content}
        onChange={(e) => onChange(e.target.value)}
        readOnly={readonly}
        placeholder={readonly ? 'メモなし' : '今日のメモ...'}
        style={readonly ? { opacity: 0.5 } : undefined}
      />
    </div>
  );
}
