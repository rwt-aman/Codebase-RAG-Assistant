"""FastAPI app: /health, /index, /query, /repos."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import CORS_ORIGINS

app = FastAPI(title="Codebase RAG Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IndexRequest(BaseModel):
    github_url: str


class QueryRequest(BaseModel):
    question: str
    repo: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/index")
def index_repo(req: IndexRequest):
    # Imports deferred so /health and startup don't pay the model/DB cost.
    from .embed import embed_texts
    from .ingest import ingest_repo, repo_name_from_url
    from .store import delete_repo, init_db, insert_chunks

    repo = repo_name_from_url(req.github_url)
    try:
        chunks = ingest_repo(req.github_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to clone/ingest repo: {e}")
    if not chunks:
        raise HTTPException(status_code=400, detail="No supported code files found in this repo.")

    embeddings = embed_texts([c["content"] for c in chunks])
    init_db()
    delete_repo(repo)
    insert_chunks(repo, chunks, embeddings)
    return {"repo": repo, "chunk_count": len(chunks)}


@app.post("/query")
def query(req: QueryRequest):
    from .rag import answer_question

    try:
        return answer_question(req.question, req.repo)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/repos")
def repos():
    from .store import list_repos

    try:
        return {"repos": list_repos()}
    except Exception:
        return {"repos": []}
