'use client';

import { useState, useCallback } from 'react';
import Link from 'next/link';
import { fetchAnalyses, runAnalyze } from '@/lib/api';
import styles from './page.module.css';

const PERIODS = ['1wk','2wk', '1mo', '2mo', '3mo', '6mo', '1y', '2y', '5y'];

export default function AnalysesPage() {
  const [ticker, setTicker] = useState('AAPL');
  const [period, setPeriod] = useState('3mo');
  const [limit, setLimit] = useState(5);
  
  const [analyses, setAnalyses] = useState([]);
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const clearError = useCallback(() => setError(null), []);

  const handleFetchRecent = useCallback(async () => {
    clearError();
    setLoading(true);
    try {
      const data = await fetchAnalyses(ticker, limit);
      setAnalyses(data || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [ticker, limit, clearError]);

  const handleFetchAll = useCallback(async () => {
    clearError();
    setLoading(true);
    try {
      const data = await fetchAnalyses(ticker, 1000);
      setAnalyses(data || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [ticker, clearError]);

  const handleRunAnalyze = useCallback(async () => {
    clearError();
    setLoading(true);
    try {
      const result = await runAnalyze(ticker, period, true);
      setCurrentAnalysis(result);
      // Refresh the recent analyses list
      const data = await fetchAnalyses(ticker, limit);
      setAnalyses(data || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [ticker, period, limit, clearError]);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>Stock Analysis</h1>
        <Link href="/" className={styles.homeLink}>← Home</Link>
      </header>

      {error && (
        <div className={styles.errorBanner}>
          <p>{error}</p>
          <button onClick={clearError} className={styles.closeBtn}>×</button>
        </div>
      )}

      <div className={styles.controlPanel}>
        <div className={styles.controlGroup}>
          <label htmlFor="ticker">Ticker:</label>
          <input
            id="ticker"
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="e.g., AAPL"
            disabled={loading}
            className={styles.input}
          />
        </div>

        <div className={styles.controlGroup}>
          <label htmlFor="period">Period:</label>
          <select
            id="period"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            disabled={loading}
            className={styles.select}
          >
            {PERIODS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>

        <div className={styles.controlGroup}>
          <label htmlFor="limit">Limit:</label>
          <input
            id="limit"
            type="number"
            value={limit}
            onChange={(e) => setLimit(Math.max(1, parseInt(e.target.value) || 1))}
            min="1"
            max="1000"
            disabled={loading}
            className={styles.input}
          />
        </div>
      </div>

      <div className={styles.buttonGroup}>
        <button
          onClick={handleFetchRecent}
          disabled={loading}
          className={styles.btnPrimary}
        >
          {loading ? 'Loading...' : 'Fetch Recent Analyses'}
        </button>
        <button
          onClick={handleFetchAll}
          disabled={loading}
          className={styles.btnSecondary}
        >
          {loading ? 'Loading...' : 'Fetch All Analyses'}
        </button>
        <button
          onClick={handleRunAnalyze}
          disabled={loading}
          className={styles.btnSuccess}
        >
          {loading ? 'Running...' : 'Run Analysis + Store'}
        </button>
      </div>

      {currentAnalysis && (
        <section className={styles.section}>
          <h2>Latest Analysis Result</h2>
          <AnalysisCard analysis={currentAnalysis} />
        </section>
      )}

      <section className={styles.section}>
        <h2>Stored Analyses for {ticker}</h2>
        {analyses.length === 0 ? (
          <p className={styles.emptyState}>
            No analyses found. Run an analysis and store it to see results here.
          </p>
        ) : (
          <div className={styles.analysisList}>
            {analyses.map((analysis, idx) => (
              <AnalysisCard key={idx} analysis={analysis} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

/**
 * Reusable card component for displaying analysis results
 */
function AnalysisCard({ analysis }) {
  const bias = analysis.bias_assessment || {};
  const price = analysis.price_summary || {};

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div>
          <strong>{analysis.ticker}</strong> • {analysis.period}
        </div>
        <div className={`${styles.scoreLabel} ${styles[`score_${bias.label?.replace(' ', '_')}`]}`}>
          {bias.label || 'N/A'} ({bias.score?.toFixed(2) || 'N/A'})
        </div>
      </div>

      <div className={styles.cardContent}>
        <div className={styles.priceRow}>
          <span className={styles.label}>Current Price:</span>
          <span>${analysis.current_price?.toFixed(2) || 'N/A'}</span>
        </div>
        <div className={styles.priceRow}>
          <span className={styles.label}>Total Return:</span>
          <span className={price.total_return_pct >= 0 ? styles.positive : styles.negative}>
            {price.total_return_pct?.toFixed(2) || 'N/A'}%
          </span>
        </div>
        <div className={styles.priceRow}>
          <span className={styles.label}>As Of:</span>
          <span>
            {analysis.as_of && !isNaN(new Date(analysis.as_of).getTime())
              ? new Date(analysis.as_of).toLocaleDateString()
              : 'Unavailable'}
          </span>
        </div>
      </div>

      {bias.evidence && bias.evidence.length > 0 && (
        <div className={styles.evidence}>
          <strong>Evidence:</strong>
          <ul>
            {bias.evidence.map((item, idx) => (
              <li key={idx} className={styles.evidenceItem}>
                <span className={styles.key}>{item.key}</span>
                <span>{item.message}</span>
                {item.impact !== 0 && (
                  <span className={`${styles.impact} ${item.direction === 'bullish' ? styles.bullish : styles.bearish}`}>
                    ({item.impact > 0 ? '+' : ''}{item.impact.toFixed(2)})
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
