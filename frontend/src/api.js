const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function post(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

export const indexRepo = (githubUrl) => post("/index", { github_url: githubUrl });
export const queryRepo = (question, repo) => post("/query", { question, repo });
