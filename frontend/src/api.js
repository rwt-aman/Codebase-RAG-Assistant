const API_BASE =
  import.meta.env.VITE_API_BASE ||
  "https://codebase-rag-assistant-backend.onrender.com";

/** Generic POST with a per-request timeout and one auto-retry on cold-start. */
async function post(path, body, timeoutMs = 30_000, attempt = 1) {
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
    if (err.name === "AbortError" && attempt === 1) {
      // Backend was cold-starting. It should be warm now -- retry once.
      return post(path, body, 60_000, 2);
    }
    if (err.name === "AbortError") {
      throw new Error(
        "Backend is taking too long to respond. Please try again in a moment."
      );
    }
    throw new Error(
      `Network error: ${err.message}. Check that CORS_ORIGINS on Render matches your Netlify URL (no trailing slash).`
    );
  } finally {
    clearTimeout(timer);
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

/** Poll GET /index/status/{jobId} until done or failed. */
async function pollIndexStatus(jobId, onProgress, maxWaitMs = 600_000) {
  const start = Date.now();
  const STEP_LABELS = {
    processing: "Starting up...",
    cloning: "Cloning repository...",
    embedding: "Generating embeddings...",
    storing: "Saving to database...",
  };

  while (Date.now() - start < maxWaitMs) {
    await new Promise((r) => setTimeout(r, 3000));

    let data;
    try {
      const res = await fetch(`${API_BASE}/index/status/${jobId}`);
      data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Status check failed (${res.status})`);
    } catch {
      // Transient network blip -- keep polling
      continue;
    }

    if (data.status === "done") {
      return { repo: data.repo, chunk_count: data.chunk_count };
    }
    if (data.status === "failed") {
      throw new Error(data.error || "Indexing failed on the server.");
    }
    if (onProgress) {
      const label = STEP_LABELS[data.status] || `Processing (${data.status})...`;
      const extra = data.chunk_count ? ` ${data.chunk_count} chunks found.` : "";
      onProgress(`${label}${extra}`);
    }
  }

  throw new Error("Indexing timed out after 10 minutes. The repo may be too large.");
}

/** Wake up the Render backend on page load to cut cold-start lag. */
export const healthCheck = () => fetch(`${API_BASE}/health`).catch(() => null);

/**
 * Start indexing a repo. Auto-retries once if backend was cold-starting.
 * onProgress(msg) receives live status updates while polling.
 */
export async function indexRepo(githubUrl, onProgress) {
  if (onProgress) onProgress("Connecting to backend (may take ~30s on first load)...");
  const { job_id } = await post("/index", { github_url: githubUrl }, 30_000);
  if (onProgress) onProgress("Job queued -- processing started...");
  return await pollIndexStatus(job_id, onProgress);
}

export const queryRepo = (question, repo) =>
  post("/query", { question, repo }, 60_000);
