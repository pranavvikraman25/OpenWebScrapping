import React, { useState } from 'react';
import './styles.css';

const API_URL = '/api/extract'; // Vercel routes /api/* to backend

export default function App() {
  const [url, setUrl] = useState('');
  const [instruction, setInstruction] = useState('Extract only invention and technology-related information.');
  const [status, setStatus] = useState([]); // array of strings for progress
  const [result, setResult] = useState(null); // {filename, blobUrl}
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const addStatus = (msg) => setStatus((prev) => [...prev, msg]);

  const handleExtract = async () => {
    setError(null);
    setResult(null);
    setStatus([]);
    setLoading(true);
    addStatus('Opening Website...');
    try {
      const resp = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, instruction }),
      });
      if (!resp.ok) {
        const errMsg = await resp.text();
        throw new Error(errMsg || 'Server error');
      }
      // Vercel streams the Excel file directly; we can treat it as blob
      addStatus('Generating Excel...');
      const blob = await resp.blob();
      const disposition = resp.headers.get('Content-Disposition');
      const filenameMatch = disposition && disposition.match(/filename=(.*)$/);
      const filename = (filenameMatch && filenameMatch[1]) || 'result.xlsx';
      const blobUrl = URL.createObjectURL(blob);
      setResult({ filename, blobUrl });
      addStatus('Completed.');
    } catch (e) {
      console.error(e);
      setError(e.message);
      addStatus('Error: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <h1 className="title">AI Universal Web Scraping Dashboard</h1>
      <div className="card input-card">
        <label>Website URL</label>
        <input type="url" placeholder="https://example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
        <label>Instruction</label>
        <textarea rows={3} value={instruction} onChange={(e) => setInstruction(e.target.value)} />
        <button onClick={handleExtract} disabled={loading || !url} className="extract-btn">
          {loading ? 'Extracting...' : 'Start Extraction'}
        </button>
      </div>
      {status.length > 0 && (
        <div className="card progress-card">
          <h2>Live Progress</h2>
          <ul>
            {status.map((msg, i) => (
              <li key={i}>{msg}</li>
            ))}
          </ul>
        </div>
      )}
      {error && (
        <div className="card error-card">
          <h2>Error</h2>
          <p>{error}</p>
        </div>
      )}
      {result && (
        <div className="card result-card">
          <h2>Results</h2>
          <p>File: {result.filename}</p>
          <a href={result.blobUrl} download={result.filename} className="download-btn">
            Download Excel
          </a>
        </div>
      )}
    </div>
  );
}
