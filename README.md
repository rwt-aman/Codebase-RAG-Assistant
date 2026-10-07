# 🔍 Codebase RAG Assistant

🚀 **Live Demo:** [codebase-ai-assistant.netlify.app](https://codebase-ai-assistant.netlify.app/)

> Paste a GitHub repo URL, let it index the code, then ask questions in plain English — every answer is grounded in the actual source and **cites file paths and line numbers** you can verify.

The same retrieval-augmented generation pattern that powers tools like Cursor and Sourcegraph Cody, stripped down to its shippable core — built as a learning project to deeply understand **RAG pipelines, vector embeddings, and LLM-grounded code search**.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL+pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_API-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)

---

## 📌 Table of Contents

- [How It Works](#-how-it-works)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Run Locally](#-run-locally)
- [API Reference](#-api-reference)
- [Design Decisions](#-design-decisions)
- [Future Improvements](#-future-improvements)
- [Author](#-author)

---

## ⚙️ How It Works

```
GitHub URL ──► clone (GitPython) ──► language-aware chunking ──► BGE embeddings (384-d)
                                                                       │
                                                                       ▼
User question ──► embed query ──► pgvector cosine search ──────► Postgres
                                        │
                                        ▼
                        top-6 chunks + file:line labels ──► Gemini ──► cited answer
```

1. **Ingest** — The repo is shallow-cloned, non-code files are skipped, and each source file is split using LangChain's `RecursiveCharacterTextSplitter.from_language`, which respects function and class boundaries per language. Every chunk retains its file path and start/end line numbers.

2. **Embed** — Chunks are embedded locally with [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) via ONNX runtime (free, no API key, 384 dimensions).

3. **Store** — Vectors are stored in PostgreSQL via **pgvector**, alongside chunk metadata, with an IVFFlat cosine-distance index for fast approximate nearest-neighbor search.

4. **Retrieve & Answer** — The user's question is embedded (with the BGE query instruction), the top-6 closest chunks are retrieved by cosine distance, and Gemini is prompted to answer *only* from that context — citing `file_path:start_line-end_line` for every claim.

---

## 🏗️ Architecture

```
Frontend (React/Vite :5173)
   ↓ fetch POST /index, POST /query
Backend (FastAPI/Uvicorn :8000)
   ├── ingest.py    → GitPython clone + LangChain language-aware splitting
   ├── embed.py     → fastembed BGE-small (384-d, ONNX)
   ├── store.py     → pgvector INSERT + cosine similarity search
   ├── rag.py       → prompt construction + Gemini API call
   ├── db.py        → psycopg2 connection + pgvector type registration
   └── config.py    → centralized settings from .env
Database (Postgres 16 + pgvector :5432)
   └── chunks table with IVFFlat cosine index
```

### Key Files

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app — 4 endpoints: `/health`, `/index`, `/query`, `/repos` |
| `backend/app/ingest.py` | Clone → walk → language-aware split → line-annotated chunks |
| `backend/app/embed.py` | BGE embedding wrapper (passage + query modes) |
| `backend/app/store.py` | pgvector schema, bulk insert, cosine search |
| `backend/app/rag.py` | RAG loop: embed → retrieve → prompt → Gemini → cited answer |
| `backend/app/config.py` | Loads `.env`, exports all tunable parameters |
| `frontend/src/App.jsx` | Single-page chat UI with repo indexing and Q&A |
| `frontend/src/api.js` | Fetch helpers for `/index` and `/query` |

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | FastAPI (Python) | Async-ready, auto-generated Swagger docs, Pydantic validation |
| **Vectors + Metadata** | PostgreSQL + pgvector | Single datastore for vectors and relational data; transactional inserts |
| **Embeddings** | `BAAI/bge-small-en-v1.5` via fastembed (ONNX) | Free, fast, no API key, top open model on MTEB |
| **Generation** | Google Gemini API | Powerful reasoning with free-tier access |
| **Frontend** | React 19 + Vite | Fast HMR, minimal config |
| **Deploy** | Render (backend) + Vercel (frontend) | Free-tier friendly |

---

## 🚀 Run Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for local Postgres) OR a [Supabase](https://supabase.com) project
- A free [Gemini API key](https://aistudio.google.com/apikey)
- Git

### 1. Start the Database

```bash
docker compose up -d
```

This starts Postgres 16 with pgvector. Your connection string:
```
postgresql://postgres:postgres@localhost:5432/codebase_rag
```

### 2. Start the Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
cp .env.example .env           # Then edit .env and add your GEMINI_API_KEY
uvicorn app.main:app --reload  # → http://localhost:8000/docs
```

### 3. Start the Frontend

```bash
cd frontend
npm install
npm run dev                    # → http://localhost:5173
```

### 4. Try It Out

1. Open http://localhost:5173
2. Paste a GitHub repo URL (e.g., `https://github.com/expressjs/express`)
3. Click **Index** — wait for cloning, chunking, and embedding
4. Ask a question like *"How does routing work?"*
5. Get a cited answer with file paths and line numbers!

---

## 📡 API Reference

Interactive Swagger docs available at [`/docs`](http://localhost:8000/docs) when running locally.

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/health` | `GET` | — | `{"ok": true}` |
| `/index` | `POST` | `{"github_url": "..."}` | `{"repo": "name", "chunk_count": 142}` |
| `/query` | `POST` | `{"question": "...", "repo": "..."}` | `{"answer": "...", "sources": [{file_path, start_line, end_line, ...}]}` |
| `/repos` | `GET` | — | `{"repos": ["repo1", "repo2"]}` |

### Example

```bash
# Index a repo
curl -X POST http://localhost:8000/index \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/expressjs/express"}'

# Ask a question
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How does routing work?", "repo": "express"}'
```

---

## 🧠 Design Decisions

| Decision | Rationale |
|----------|-----------|
| **pgvector over a dedicated vector DB** | One datastore holds both vectors and metadata — inserts are transactional, ops stay simple. Qdrant/Weaviate earn their complexity at larger scale. |
| **Language-aware chunking over fixed-size** | Splitting on function/class boundaries keeps each chunk semantically whole, so its embedding represents one coherent idea. Fixed-size cuts split functions mid-body and blur retrieval. |
| **BGE-small locally over an embeddings API** | Free, fast (384-dim), no key management, and a top open model on MTEB. Indexing a mid-size repo takes seconds on CPU. |
| **RAG over stuffing the repo in the prompt** | Repos exceed context windows, tokens cost money, and retrieval focuses the model on relevant code. Grounding with citations makes answers *verifiable*. |
| **Deferred imports in endpoints** | Heavy modules (embedding model, DB) are imported inside handler functions so `/health` starts instantly — important for cloud health checks. |

---

## 🔮 Future Improvements

- [ ] **Hybrid retrieval** — BM25 keyword search + vector search with a cross-encoder reranker
- [ ] **Streaming responses** — Token-by-token output over WebSockets
- [ ] **Evaluation harness** — Labeled question set + RAGAS metrics (faithfulness, answer relevance)
- [ ] **Auth & multi-tenancy** — JWT authentication, per-user repos, persisted chat history
- [ ] **Code graph retrieval** — Dependency/call-graph analysis (networkx → Neo4j at scale)
- [ ] **CI/CD pipeline** — GitHub Actions for linting, testing, and automated deployment

---

## 👤 Author

**Aman Rawat**

- GitHub: [@rwt-aman](https://github.com/rwt-aman)

---

## 📄 License

This project is open source and available for learning purposes.

---

<p align="center">
  Built with ❤️ to learn RAG, embeddings, vector search, and LLM-grounded code Q&A.
</p>
