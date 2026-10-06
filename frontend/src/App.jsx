import { useRef, useState } from "react";
import { indexRepo, queryRepo } from "./api";
import "./App.css";

export default function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [repo, setRepo] = useState(null); // { name, chunkCount }
  const [indexing, setIndexing] = useState(false);
  const [indexError, setIndexError] = useState("");

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]); // { role, text, sources? }
  const [asking, setAsking] = useState(false);
  const chatEndRef = useRef(null);

  async function handleIndex(e) {
    e.preventDefault();
    if (!repoUrl.trim() || indexing) return;
    setIndexing(true);
    setIndexError("");
    setRepo(null);
    try {
      const data = await indexRepo(repoUrl.trim());
      setRepo({ name: data.repo, chunkCount: data.chunk_count });
      setMessages([]);
    } catch (err) {
      setIndexError(err.message);
    } finally {
      setIndexing(false);
    }
  }

  async function handleAsk(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || !repo || asking) return;
    setQuestion("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setAsking(true);
    try {
      const data = await queryRepo(q, repo.name);
      setMessages((m) => [...m, { role: "assistant", text: data.answer, sources: data.sources }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${err.message}`, sources: [] }]);
    } finally {
      setAsking(false);
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Codebase RAG Assistant</h1>
        <p className="tagline">Paste a GitHub repo, then ask questions — answers cite real files and lines.</p>
      </header>

      <form className="index-bar" onSubmit={handleIndex}>
        <input
          type="url"
          placeholder="https://github.com/owner/repo"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          disabled={indexing}
          required
        />
        <button type="submit" disabled={indexing}>
          {indexing ? <span className="spinner" aria-label="indexing" /> : "Index"}
        </button>
      </form>

      {indexing && <p className="status">Cloning, chunking and embedding — this can take a minute…</p>}
      {indexError && <p className="status error">{indexError}</p>}
      {repo && (
        <p className="status ok">
          Indexed <strong>{repo.name}</strong> — {repo.chunkCount} chunks. Ask away.
        </p>
      )}

      <main className="chat">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">
              <pre className="msg-text">{m.text}</pre>
              {m.sources?.length > 0 && (
                <div className="sources">
                  <span className="sources-label">Sources</span>
                  {m.sources.map((s, j) => (
                    <span key={j} className="chip" title={`cosine distance ${s.distance}`}>
                      {s.file_path}:{s.start_line}-{s.end_line}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {asking && (
          <div className="msg assistant">
            <div className="bubble thinking">Thinking…</div>
          </div>
        )}
        <div ref={chatEndRef} />
      </main>

      <form className="ask-bar" onSubmit={handleAsk}>
        <input
          placeholder={repo ? `Ask about ${repo.name}…` : "Index a repo first"}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={!repo || asking}
        />
        <button type="submit" disabled={!repo || asking}>
          Ask
        </button>
      </form>
    </div>
  );
}
