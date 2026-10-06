"""FastAPI app: /health, /index, /index/status/{job_id}, /query, /repos."""
import logging
import uuid
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import CORS_ORIGINS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Codebase RAG Assistant", version="1.0.0")

logger.info("CORS allowed origins: %s", CORS_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store ─────────────────────────────────────────────────────
# { job_id: { status, repo, chunk_count?, error? } }
# Resets on restart — acceptable for a free-tier demo.
_jobs: dict[str, dict] = {}


class IndexRequest(BaseModel):
    github_url: str


class QueryRequest(BaseModel):
    question: str
    repo: str


# ── Background worker ────────────────────────────────────────────────────────

def _do_index(job_id: str, github_url: str) -> None:
    from .embed import embed_texts
    from .ingest import ingest_repo, repo_name_from_url
    from .store import delete_repo, init_db, insert_chunks

    repo = repo_name_from_url(github_url)
    logger.info("[job %s] starting index for %s", job_id, github_url)
    try:
        _jobs[job_id]["status"] = "cloning"
        chunks = ingest_repo(github_url)
        if not chunks:
            _jobs[job_id] = {"status": "failed", "error": "No supported code files found in this repo."}
            return

        _jobs[job_id]["status"] = "embedding"
        _jobs[job_id]["chunk_count"] = len(chunks)
        embeddings = embed_texts([c["content"] for c in chunks])

        _jobs[job_id]["status"] = "storing"
        init_db()
        delete_repo(repo)
        insert_chunks(repo, chunks, embeddings)

        _jobs[job_id] = {"status": "done", "repo": repo, "chunk_count": len(chunks)}
        logger.info("[job %s] done — %d chunks", job_id, len(chunks))
    except Exception as e:
        logger.exception("[job %s] failed: %s", job_id, e)
        _jobs[job_id] = {"status": "failed", "error": str(e)}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/index")
def index_repo(req: IndexRequest, background_tasks: BackgroundTasks):
    """Start indexing in the background and return a job_id immediately."""
    from .ingest import repo_name_from_url
    try:
        repo = repo_name_from_url(req.github_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GitHub URL: {e}")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "repo": repo}
    background_tasks.add_task(_do_index, job_id, req.github_url)
    logger.info("[job %s] queued for repo %s", job_id, repo)
    return {"job_id": job_id, "repo": repo, "status": "processing"}


@app.get("/index/status/{job_id}")
def index_status(job_id: str):
    """Poll this endpoint to check indexing progress."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found. The backend may have restarted — please re-index.")
    return job


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
