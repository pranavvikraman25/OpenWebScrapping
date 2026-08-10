import React, { useState, useRef, useCallback } from 'react';
import './styles.css';

const API_BASE = '/api';

export default function App() {
  // ── State ──
  const [page, setPage] = useState('scraper');
  const [url, setUrl] = useState('');
  const [instruction, setInstruction] = useState('');
  const [format, setFormat] = useState('json');
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [progress, setProgress] = useState([]);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const iframeRef = useRef(null);

  // ── Preview: Load live website ──
  const handlePreview = useCallback(async () => {
    if (!url) return;
    setPreviewLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/proxy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to load website');
      }
      const html = await resp.text();
      const blob = new Blob([html], { type: 'text/html' });
      const blobUrl = URL.createObjectURL(blob);
      setPreviewUrl(blobUrl);
    } catch (e) {
      setError(e.message);
    } finally {
      setPreviewLoading(false);
    }
  }, [url]);

  // ── Extract data ──
  const handleExtract = useCallback(async () => {
    if (!url) return;
    setExtracting(true);
    setError(null);
    setResults(null);
    setProgress([]);

    const addStep = (icon, text, status) => {
      setProgress(prev => [...prev, { icon, text, status }]);
    };

    try {
      addStep('🌐', 'Opening website...', 'active');

      // Also trigger preview if not already loaded
      if (!previewUrl) {
        fetch(`${API_BASE}/proxy`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
        }).then(async (resp) => {
          if (resp.ok) {
            const html = await resp.text();
            const blob = new Blob([html], { type: 'text/html' });
            setPreviewUrl(URL.createObjectURL(blob));
          }
        }).catch(() => {});
      }

      // Step 1: Extract as JSON first (for preview)
      addStep('⚙️', 'Rendering & extracting data...', 'active');

      const resp = await fetch(`${API_BASE}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, instruction: instruction || 'Extract all data', format: 'json' }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Extraction failed');
      }

      const data = await resp.json();
      addStep('🧠', `Smart filter applied: ${data.keywords.length} keywords detected`, 'done');
      addStep('✅', `Extracted ${data.total} records`, 'done');

      setResults(data);

      // Add to history
      setHistory(prev => [{
        url,
        instruction,
        total: data.total,
        title: data.page_title,
        timestamp: new Date().toLocaleString(),
        status: 'success',
      }, ...prev]);

    } catch (e) {
      addStep('❌', e.message, 'error');
      setError(e.message);

      setHistory(prev => [{
        url,
        instruction,
        total: 0,
        title: '—',
        timestamp: new Date().toLocaleString(),
        status: 'failed',
      }, ...prev]);
    } finally {
      setExtracting(false);
    }
  }, [url, instruction, previewUrl]);

  // ── Download file ──
  const handleDownload = useCallback(async (downloadFormat) => {
    if (!url) return;
    try {
      const resp = await fetch(`${API_BASE}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, instruction: instruction || 'Extract all data', format: downloadFormat }),
      });
      if (!resp.ok) throw new Error('Download failed');
      const blob = await resp.blob();
      const disposition = resp.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename=(.+)/);
      const filename = match ? match[1] : `data.${downloadFormat === 'excel' ? 'xlsx' : downloadFormat}`;
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
    } catch (e) {
      setError(e.message);
    }
  }, [url, instruction]);

  // ── Render ──
  return (
    <div className="app-layout">

      {/* ══ SIDEBAR ══ */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="logo">🕸️</span>
          <div>
            <h1>DataForge</h1>
            <span>v2.0</span>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-label">Workspace</div>
          <button className={`sidebar-link ${page === 'scraper' ? 'active' : ''}`} onClick={() => setPage('scraper')}>
            <span className="icon">🔍</span> Scraper
          </button>
          <button className={`sidebar-link ${page === 'results' ? 'active' : ''}`} onClick={() => setPage('results')}>
            <span className="icon">📊</span> Results
          </button>
          <button className={`sidebar-link ${page === 'history' ? 'active' : ''}`} onClick={() => setPage('history')}>
            <span className="icon">📋</span> History
          </button>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-label">System</div>
          <button className={`sidebar-link ${page === 'settings' ? 'active' : ''}`} onClick={() => setPage('settings')}>
            <span className="icon">⚙️</span> Settings
          </button>
        </div>

        <div className="sidebar-footer">
          Built with ❤️ by Pranav
        </div>
      </aside>

      {/* ══ MAIN CONTENT ══ */}
      <main className="main-content">

        {/* ── Topbar ── */}
        <div className="topbar">
          <span className="topbar-title">
            {page === 'scraper' && '🔍 Web Scraper'}
            {page === 'results' && '📊 Extracted Data'}
            {page === 'history' && '📋 Scrape History'}
            {page === 'settings' && '⚙️ Settings'}
          </span>
          <span className="topbar-subtitle">Universal Data Extraction Agent</span>
        </div>

        {/* ══ PAGE: SCRAPER ══ */}
        {page === 'scraper' && (
          <div className="workspace">

            {/* ── Left Panel: Controls ── */}
            <div className="panel-left">

              {/* URL Input */}
              <div className="card">
                <div className="card-header">
                  <span className="icon">🌐</span>
                  <h3>Target Website</h3>
                </div>
                <div className="input-group">
                  <label>Website URL</label>
                  <div className="input-pill">
                    <input
                      type="url"
                      placeholder="https://example.com — paste any URL"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handlePreview()}
                    />
                    <button
                      className="btn-preview"
                      onClick={handlePreview}
                      disabled={!url || previewLoading}
                    >
                      {previewLoading ? '⏳ Loading...' : '👁️ Preview'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Instruction */}
              <div className="card">
                <div className="card-header">
                  <span className="icon">🧠</span>
                  <h3>Extraction Instruction</h3>
                </div>
                <div className="input-group">
                  <label>What data do you need? (plain English)</label>
                  <textarea
                    className="instruction-input"
                    placeholder='e.g. "Extract only invention and technology-related information" or "Get all faculty names and departments"'
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    rows={3}
                  />
                </div>
              </div>

              {/* Format + Extract */}
              <div className="card">
                <div className="card-header">
                  <span className="icon">📦</span>
                  <h3>Output</h3>
                </div>
                <div className="input-group" style={{ marginBottom: 14 }}>
                  <label>Format</label>
                  <div className="format-toggle">
                    {['excel', 'csv', 'json'].map((f) => (
                      <button
                        key={f}
                        className={format === f ? 'active' : ''}
                        onClick={() => setFormat(f)}
                      >
                        {f === 'excel' ? '📗 Excel' : f === 'csv' ? '📄 CSV' : '{ } JSON'}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  className="btn-extract"
                  onClick={handleExtract}
                  disabled={!url || extracting}
                >
                  {extracting ? (<><span className="spinner">⏳</span> Extracting...</>) : (<>🚀 Start Extraction</>)}
                </button>
              </div>

              {/* Progress */}
              {progress.length > 0 && (
                <div className="card">
                  <div className="card-header">
                    <span className="icon">📡</span>
                    <h3>Progress</h3>
                  </div>
                  <div className="progress-steps">
                    {progress.map((step, i) => (
                      <div key={i} className={`progress-step ${step.status}`}>
                        <span className="step-icon">{step.icon}</span>
                        <span>{step.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="banner banner-error">
                  <span>❌</span>
                  <span>{error}</span>
                </div>
              )}

              {/* Results Preview */}
              {results && (
                <div className="card">
                  <div className="card-header">
                    <span className="icon">✅</span>
                    <h3>Results</h3>
                  </div>

                  <div className="stats-row" style={{ marginBottom: 14 }}>
                    <div className="stat-badge">
                      📊 <span className="num">{results.total}</span> records
                    </div>
                    <div className="stat-badge">
                      🔑 <span className="num">{results.keywords.length}</span> keywords
                    </div>
                  </div>

                  {results.keywords.length > 0 && (
                    <div style={{ marginBottom: 14 }}>
                      <div className="keywords-row">
                        {results.keywords.map((kw, i) => (
                          <span key={i} className="keyword-badge">{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Data Table */}
                  {results.records.length > 0 && (
                    <div className="data-table-wrapper" style={{ marginBottom: 14 }}>
                      <table className="data-table">
                        <thead>
                          <tr>
                            {Object.keys(results.records[0]).map((col) => (
                              <th key={col}>{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {results.records.slice(0, 20).map((row, i) => (
                            <tr key={i}>
                              {Object.values(row).map((val, j) => (
                                <td key={j} title={String(val)}>
                                  {String(val).length > 80 ? String(val).slice(0, 80) + '...' : String(val)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {results.total > 20 && (
                    <div className="banner banner-warning" style={{ marginBottom: 14 }}>
                      <span>ℹ️</span>
                      <span>Showing first 20 of {results.total} records. Download to see all.</span>
                    </div>
                  )}

                  {/* Download Buttons */}
                  <div className="download-row">
                    <button className="btn-download" onClick={() => handleDownload('excel')}>
                      📗 Download Excel
                    </button>
                    <button className="btn-download" onClick={() => handleDownload('csv')}>
                      📄 Download CSV
                    </button>
                    <button className="btn-download" onClick={() => handleDownload('json')}>
                      {'{ }'} Download JSON
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* ── Right Panel: Live Preview ── */}
            <div className="panel-right">
              {previewUrl ? (
                <>
                  <div className="preview-toolbar">
                    <span className="dot red"></span>
                    <span className="dot yellow"></span>
                    <span className="dot green"></span>
                    <div className="url-display">{url}</div>
                  </div>
                  <iframe
                    ref={iframeRef}
                    src={previewUrl}
                    className="preview-frame"
                    sandbox="allow-same-origin allow-scripts"
                    title="Website Preview"
                  />
                </>
              ) : (
                <div className="preview-empty">
                  <span className="big-icon">🌐</span>
                  <span>Paste a URL and click <strong>Preview</strong></span>
                  <span style={{ fontSize: 12 }}>The live website will appear here</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ══ PAGE: RESULTS ══ */}
        {page === 'results' && (
          <div className="workspace no-preview">
            <div className="panel-left">
              {results ? (
                <div className="card">
                  <div className="card-header">
                    <span className="icon">📊</span>
                    <h3>Extracted Data — {results.page_title}</h3>
                  </div>
                  <div className="stats-row" style={{ marginBottom: 14 }}>
                    <div className="stat-badge">📊 <span className="num">{results.total}</span> records</div>
                  </div>
                  {results.records.length > 0 && (
                    <div className="data-table-wrapper" style={{ marginBottom: 14 }}>
                      <table className="data-table">
                        <thead>
                          <tr>
                            {Object.keys(results.records[0]).map((col) => (
                              <th key={col}>{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {results.records.map((row, i) => (
                            <tr key={i}>
                              {Object.values(row).map((val, j) => (
                                <td key={j} title={String(val)}>
                                  {String(val).length > 100 ? String(val).slice(0, 100) + '...' : String(val)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <div className="download-row">
                    <button className="btn-download" onClick={() => handleDownload('excel')}>📗 Excel</button>
                    <button className="btn-download" onClick={() => handleDownload('csv')}>📄 CSV</button>
                    <button className="btn-download" onClick={() => handleDownload('json')}>{'{ }'} JSON</button>
                  </div>
                </div>
              ) : (
                <div className="card" style={{ textAlign: 'center', padding: 60 }}>
                  <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>📊</div>
                  <h3 style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>No data yet</h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                    Go to the Scraper page and extract some data first.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ══ PAGE: HISTORY ══ */}
        {page === 'history' && (
          <div className="workspace no-preview">
            <div className="panel-left">
              <div className="card">
                <div className="card-header">
                  <span className="icon">📋</span>
                  <h3>Scrape History</h3>
                </div>
                {history.length > 0 ? (
                  <div className="data-table-wrapper">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Status</th>
                          <th>URL</th>
                          <th>Instruction</th>
                          <th>Records</th>
                          <th>Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {history.map((h, i) => (
                          <tr key={i}>
                            <td>{h.status === 'success' ? '✅' : '❌'}</td>
                            <td title={h.url}>{h.url.length > 40 ? h.url.slice(0, 40) + '...' : h.url}</td>
                            <td>{h.instruction || '—'}</td>
                            <td>{h.total}</td>
                            <td>{h.timestamp}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                    <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>📋</div>
                    <p>No scraping history yet. Start extracting!</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ══ PAGE: SETTINGS ══ */}
        {page === 'settings' && (
          <div className="workspace no-preview">
            <div className="panel-left">
              <div className="card">
                <div className="card-header">
                  <span className="icon">⚙️</span>
                  <h3>Settings</h3>
                </div>
                <div className="banner banner-warning">
                  <span>🚧</span>
                  <span>Settings page coming soon. Default configuration is active.</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
