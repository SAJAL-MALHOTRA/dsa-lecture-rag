import { SearchResponse, AnswerResponse, DSASnippet } from "../types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "https://striver-dsa-platform.onrender.com";

/**
 * Searches lecture transcripts, moments, and DSA problem solutions.
 */
export async function fetchSearch(
  query: string,
  k: number = 5,
  signal?: AbortSignal
): Promise<SearchResponse> {
  const url = `${API_BASE_URL}/api/search?q=${encodeURIComponent(query)}&k=${k}`;
  const res = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Search failed with HTTP ${res.status}: ${res.statusText}`);
  }

  return res.json();
}

/**
 * Generates an evidence-grounded answer with timestamp citations.
 */
export async function fetchAnswer(
  query: string,
  options: {
    provider?: string;
    apiKey?: string;
    model?: string;
  } = {},
  signal?: AbortSignal
): Promise<AnswerResponse> {
  const url = `${API_BASE_URL}/api/answer`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      query,
      provider: options.provider || "extractive",
      api_key: options.apiKey || "",
      model: options.model || "",
    }),
    signal,
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Answer generation failed with HTTP ${res.status}`);
  }

  return res.json();
}

/**
 * Fetches standalone DSA snippet & multi-language code for a problem title.
 */
export async function fetchDsaSnippet(
  query: string,
  signal?: AbortSignal
): Promise<{ found: boolean; problem: DSASnippet | null }> {
  const url = `${API_BASE_URL}/api/dsa-snippet?q=${encodeURIComponent(query)}`;
  const res = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!res.ok) {
    throw new Error(`DSA snippet fetch failed with HTTP ${res.status}`);
  }

  return res.json();
}

/**
 * Health check to verify backend connectivity.
 */
export async function checkBackendHealth(): Promise<{ status: string; corpus_loaded: boolean }> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`, {
      method: "GET",
      cache: "no-store",
    });
    if (!res.ok) return { status: "unhealthy", corpus_loaded: false };
    return res.json();
  } catch {
    return { status: "offline", corpus_loaded: false };
  }
}
