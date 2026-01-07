const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

/**
 * Get auth headers with bearer token if available
 * @param {string} accessToken - Supabase access token
 * @returns {Object} Headers object
 */
function getAuthHeaders(accessToken = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  return headers;
}

/**
 * Fetch analyses for a given ticker
 * @param {string} ticker - Stock ticker symbol
 * @param {number} limit - Max number of analyses to return
 * @param {string} accessToken - Supabase access token
 * @returns {Promise<Array>} List of analyses
 */
export async function fetchAnalyses(ticker, limit = 50, accessToken = null) {
  const url = `${API_BASE}/api/analyses?ticker=${encodeURIComponent(ticker)}&limit=${limit}`;
  const response = await fetch(url, {
    headers: getAuthHeaders(accessToken),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to fetch analyses: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Run analysis for a ticker/period and optionally store it
 * @param {string} ticker - Stock ticker symbol
 * @param {string} period - Time period (e.g., "1mo", "3mo", "1y")
 * @param {boolean} store - Whether to save to database
 * @param {string} accessToken - Supabase access token
 * @returns {Promise<Object>} Analysis result
 */
export async function runAnalyze(ticker, period, store = true, accessToken = null) {
  const url = `${API_BASE}/api/analyze`;
  const body = {
    ticker,
    period,
    store,
    include_history: false,
    history_limit: 0,
  };

  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(accessToken),
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to run analysis: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch the latest analysis for a ticker (optionally filtered by period)
 * @param {string} ticker - Stock ticker symbol
 * @param {string} period - Optional time period filter
 * @param {string} accessToken - Supabase access token
 * @returns {Promise<Object|null>} Latest analysis or null
 */
export async function fetchLatestAnalysis(ticker, period = null, accessToken = null) {
  const url = period
    ? `${API_BASE}/api/analyses/latest?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}`
    : `${API_BASE}/api/analyses/latest?ticker=${encodeURIComponent(ticker)}`;

  const response = await fetch(url, {
    headers: getAuthHeaders(accessToken),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch latest analysis: ${response.statusText}`);
  }

  return response.json();
}
