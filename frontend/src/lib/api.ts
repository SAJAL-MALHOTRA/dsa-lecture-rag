import { SearchResponse, AnswerResponse, DSASnippet, RoadmapResponse } from "../types/api";

const DIRECT_BACKEND = "https://striver-dsa-platform.onrender.com";

function getApiUrl(path: string): string {
  // If explicitly overridden via env var, honor it
  if (process.env.NEXT_PUBLIC_API_URL) {
    return `${process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "")}${path}`;
  }
  // In the browser, use relative path so Next.js rewrites proxy to backend with zero CORS issues!
  if (typeof window !== "undefined") {
    return path;
  }
  // Server-side / SSR default
  return `${DIRECT_BACKEND}${path}`;
}

/**
 * Searches lecture transcripts, moments, and DSA problem solutions.
 */
export async function fetchSearch(
  query: string,
  k: number = 5,
  signal?: AbortSignal
): Promise<SearchResponse> {
  const relPath = `/api/search?q=${encodeURIComponent(query)}&k=${k}`;
  const primaryUrl = getApiUrl(relPath);

  try {
    const res = await fetch(primaryUrl, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
      cache: "no-store",
    });

    if (res.ok) {
      return res.json();
    }
    // If relative proxy returned 404 or 5xx, try direct backend URL as fallback
    if (primaryUrl !== `${DIRECT_BACKEND}${relPath}`) {
      const fallbackRes = await fetch(`${DIRECT_BACKEND}${relPath}`, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal,
        cache: "no-store",
      });
      if (fallbackRes.ok) return fallbackRes.json();
    }
    throw new Error(`Search failed with HTTP ${res.status}: ${res.statusText}`);
  } catch (err: any) {
    // If fetch failed completely (e.g. network failure on relative proxy), try direct backend
    if (primaryUrl !== `${DIRECT_BACKEND}${relPath}`) {
      try {
        const fallbackRes = await fetch(`${DIRECT_BACKEND}${relPath}`, {
          method: "GET",
          headers: { Accept: "application/json" },
          signal,
          cache: "no-store",
        });
        if (fallbackRes.ok) return fallbackRes.json();
      } catch {
        // Fall through to throw original error
      }
    }
    throw err;
  }
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
  const relPath = `/api/answer`;
  const primaryUrl = getApiUrl(relPath);
  const payload = JSON.stringify({
    query,
    provider: options.provider || "extractive",
    api_key: options.apiKey || "",
    model: options.model || "",
  });

  try {
    const res = await fetch(primaryUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: payload,
      signal,
      cache: "no-store",
    });

    if (res.ok) {
      return res.json();
    }
    if (primaryUrl !== `${DIRECT_BACKEND}${relPath}`) {
      const fallbackRes = await fetch(`${DIRECT_BACKEND}${relPath}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: payload,
        signal,
        cache: "no-store",
      });
      if (fallbackRes.ok) return fallbackRes.json();
    }
    throw new Error(`Answer generation failed with HTTP ${res.status}`);
  } catch (err: any) {
    if (primaryUrl !== `${DIRECT_BACKEND}${relPath}`) {
      try {
        const fallbackRes = await fetch(`${DIRECT_BACKEND}${relPath}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: payload,
          signal,
          cache: "no-store",
        });
        if (fallbackRes.ok) return fallbackRes.json();
      } catch {
        // Fall through
      }
    }
    throw err;
  }
}

/**
 * Fetches standalone DSA snippet & multi-language code for a problem title.
 */
export async function fetchDsaSnippet(
  query: string,
  signal?: AbortSignal
): Promise<{ found: boolean; problem: DSASnippet | null }> {
  const relPath = `/api/dsa-snippet?q=${encodeURIComponent(query)}`;
  const primaryUrl = getApiUrl(relPath);

  const res = await fetch(primaryUrl, {
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
  const relPath = `/api/health`;
  const primaryUrl = getApiUrl(relPath);

  try {
    const res = await fetch(primaryUrl, {
      method: "GET",
      cache: "no-store",
    });
    if (res.ok) return res.json();
    const fallback = await fetch(`${DIRECT_BACKEND}${relPath}`, {
      method: "GET",
      cache: "no-store",
    });
    if (fallback.ok) return fallback.json();
    return { status: "unhealthy", corpus_loaded: false };
  } catch {
    return { status: "offline", corpus_loaded: false };
  }
}

/**
 * Fetches Striver's A2Z DSA Sheet topic hierarchy and problems.
 */
export async function fetchRoadmap(signal?: AbortSignal): Promise<RoadmapResponse> {
  const relPath = `/api/roadmap`;
  const primaryUrl = getApiUrl(relPath);

  try {
    const res = await fetch(primaryUrl, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
    if (res.ok) return res.json();
    if (primaryUrl !== `${DIRECT_BACKEND}${relPath}`) {
      const fallbackRes = await fetch(`${DIRECT_BACKEND}${relPath}`, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal,
      });
      if (fallbackRes.ok) return fallbackRes.json();
    }
    throw new Error(`Roadmap fetch failed with HTTP ${res.status}`);
  } catch (err) {
    if (primaryUrl !== `${DIRECT_BACKEND}${relPath}`) {
      const fallbackRes = await fetch(`${DIRECT_BACKEND}${relPath}`, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal,
      });
      if (fallbackRes.ok) return fallbackRes.json();
    }
    throw err;
  }
}
