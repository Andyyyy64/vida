import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../lib/api';

interface DataStats {
  counts: Record<string, number>;
  firstDate: string;
  lastDate: string;
  dbSizeBytes: number;
}

interface ImportResult {
  imported: number;
  skipped: number;
  total: number;
}

const EXPORT_TABLES = [
  'frames',
  'summaries',
  'events',
  'chat_messages',
  'memos',
  'reports',
  'activity_mappings',
];

const IMPORT_TABLES = [
  'frames',
  'summaries',
  'events',
  'chat_messages',
  'memos',
  'reports',
];

interface Props {
  onClose: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDateShort(ts: string): string {
  if (!ts) return '—';
  return ts.slice(0, 10);
}

export function DataModal({ onClose }: Props) {
  const { t } = useTranslation();
  const [stats, setStats] = useState<DataStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState('');
  const [importTable, setImportTable] = useState('frames');
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (api.data.stats() as Promise<DataStats>)
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleEsc = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [handleEsc]);

  async function handleExport(table: string, format: 'csv' | 'json' = 'csv') {
    try {
      const content = await api.data.exportTable(table, format);
      // If result is a string, create a download from it
      if (typeof content === 'string') {
        const blob = new Blob([content], { type: format === 'json' ? 'application/json' : 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${table}-all.${format}`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        // Fallback: direct download link (browser mode may return non-string)
        const a = document.createElement('a');
        a.href = `/api/data/export/${table}?format=${format}`;
        a.download = `${table}-all.${format}`;
        a.click();
      }
    } catch {
      // Fallback to direct link for browser mode
      const a = document.createElement('a');
      a.href = `/api/data/export/${table}?format=${format}`;
      a.download = `${table}-all.${format}`;
      a.click();
    }
  }

  function handleExportAll(format: 'csv' | 'json') {
    EXPORT_TABLES.forEach((table, i) => {
      setTimeout(() => handleExport(table, format), i * 300);
    });
  }

  async function importOneFile(table: string, file: File): Promise<ImportResult> {
    // Import is only supported via the Hono API (file uploads).
    // In Tauri mode this will fail gracefully.
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`/api/data/import/${table}`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { error?: string }).error ?? `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function handleImport() {
    const files = fileRef.current?.files;
    if (!files || files.length === 0) return;

    setImporting(true);
    setImportResult(null);
    setImportError('');

    try {
      let totalImported = 0;
      let totalSkipped = 0;

      if (importTable === 'all') {
        // Auto-detect table from filename for each file
        for (const file of Array.from(files)) {
          const match = IMPORT_TABLES.find((t) => file.name.toLowerCase().includes(t));
          if (!match) continue;
          const result = await importOneFile(match, file);
          totalImported += result.imported;
          totalSkipped += result.skipped;
        }
      } else {
        const result = await importOneFile(importTable, files[0]);
        totalImported = result.imported;
        totalSkipped = result.skipped;
      }

      setImportResult({ imported: totalImported, skipped: totalSkipped, total: totalImported + totalSkipped });
      // Refresh stats
      (api.data.stats() as Promise<DataStats>)
        .then(setStats)
        .catch(() => {});
    } catch (e) {
      setImportError(String(e));
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  // Primary stat tables shown with counts
  const statEntries = stats
    ? Object.entries(stats.counts).filter(([, v]) => v > 0 || true)
    : [];

  const totalRecords = stats
    ? Object.values(stats.counts).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div
      className="data-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t('data.title')}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="data-modal">
        <div className="data-header">
          <span className="data-title">{t('data.title')}</span>
          <button className="data-close" onClick={onClose}>
            &times;
          </button>
        </div>

        {loading ? (
          <div className="data-loading">{t('common.loading')}</div>
        ) : stats ? (
          <div className="data-body">
            {/* ── Overview ── */}
            <section className="data-section">
              <h3 className="data-section-title">{t('data.overview')}</h3>
              <div className="data-overview-row">
                <span className="data-overview-label">{t('data.dbSize')}</span>
                <span className="data-overview-value">{formatBytes(stats.dbSizeBytes)}</span>
              </div>
              <div className="data-overview-row">
                <span className="data-overview-label">{t('data.dateRange')}</span>
                <span className="data-overview-value">
                  {formatDateShort(stats.firstDate)} — {formatDateShort(stats.lastDate)}
                </span>
              </div>
              <div className="data-overview-row">
                <span className="data-overview-label">{t('data.totalRecords')}</span>
                <span className="data-overview-value">{totalRecords.toLocaleString()}</span>
              </div>
            </section>

            {/* ── Table Counts ── */}
            <section className="data-section">
              <h3 className="data-section-title">{t('data.tables')}</h3>
              <div className="data-table-grid">
                {statEntries.map(([table, count]) => (
                  <div className="data-table-row" key={table}>
                    <span className="data-table-name">{t(`data.table_${table}`)}</span>
                    <span className="data-table-count">{count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </section>

            {/* ── Export ── */}
            <section className="data-section">
              <h3 className="data-section-title">{t('data.export')}</h3>
              <p className="data-hint">{t('data.exportHint')}</p>
              <div className="data-export-grid">
                <div className="data-export-row data-export-row--all">
                  <span className="data-export-name">{t('data.all')}</span>
                  <div className="data-export-actions">
                    <button
                      className="data-btn data-btn--sm data-btn--primary"
                      onClick={() => handleExportAll('csv')}
                    >
                      CSV
                    </button>
                    <button
                      className="data-btn data-btn--sm data-btn--primary"
                      onClick={() => handleExportAll('json')}
                    >
                      JSON
                    </button>
                  </div>
                </div>
                {EXPORT_TABLES.map((table) => (
                  <div className="data-export-row" key={table}>
                    <span className="data-export-name">{t(`data.table_${table}`)}</span>
                    <div className="data-export-actions">
                      <button
                        className="data-btn data-btn--sm"
                        onClick={() => handleExport(table, 'csv')}
                      >
                        CSV
                      </button>
                      <button
                        className="data-btn data-btn--sm"
                        onClick={() => handleExport(table, 'json')}
                      >
                        JSON
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* ── Import ── */}
            <section className="data-section">
              <h3 className="data-section-title">{t('data.import')}</h3>
              <p className="data-hint">{t('data.importHint')}</p>
              <div className="data-import-form">
                <select
                  className="data-import-select"
                  value={importTable}
                  onChange={(e) => setImportTable(e.target.value)}
                >
                  <option value="all">{t('data.all')}</option>
                  {IMPORT_TABLES.map((table) => (
                    <option key={table} value={table}>
                      {t(`data.table_${table}`)}
                    </option>
                  ))}
                </select>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv"
                  multiple={importTable === 'all'}
                  className="data-import-file"
                />
                <button
                  className="data-btn data-btn--primary"
                  onClick={handleImport}
                  disabled={importing}
                >
                  {importing ? t('data.importing') : t('data.importCsv')}
                </button>
              </div>
              {importResult && (
                <div className="data-import-result data-import-result--success">
                  {t('data.importSuccess', {
                    imported: importResult.imported,
                    skipped: importResult.skipped,
                  })}
                </div>
              )}
              {importError && (
                <div className="data-import-result data-import-result--error">
                  {importError}
                </div>
              )}
            </section>
          </div>
        ) : (
          <div className="data-loading">{t('errors.network')}</div>
        )}

        <div className="data-footer">
          <button className="data-btn" onClick={onClose}>
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  );
}
