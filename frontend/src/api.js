const API_BASE = import.meta.env.VITE_API_BASE || "https://codebase-rag-assistant-backend.onrender.com";

/**
 * Generic POST with timeout. Render free tier cold-starts can take ~30s,
 * and /index does git clone + embedding which can take 2+ minutes on big repos.
 */
async function post(path, body, timeoutMs = 120_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error(`Request timed out after ${timeoutMs / 1000}s. The backend may be cold-starting — try again in a moment.`);
    }
    // Network error or CORS block — fetch throws a TypeError with no status
    throw new Error(
      `Network error: could not reach the backend (${err.message}). ` +
      `Check that CORS_ORIGINS on Render includes your Netlify URL, ` +
      `and that VITE_API_BASE on Netlify points to https://codebase-rag-assistant-backend.onrender.com`
    );
  } finally {
    clearTimeout(timer);
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

/** Wake up the Render backend (useful to call on page load to reduce cold-start lag). */
export const healthCheck = () =>
  fetch(`${API_BASE}/health`).catch(() => null);

export const indexRepo = (githubUrl) =>
  post("/index", { github_url: githubUrl }, 180_000); // 3 min — clone + embed can be slow

export const queryRepo = (question, repo) =>
  post("/query", { question, repo }, 60_000);

