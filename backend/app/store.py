"""pgvector storage: schema setup, bulk insert, cosine similarity search."""
import numpy as np
from psycopg2.extras import execute_values

from .config import EMBEDDING_DIM, TOP_K
from .db import get_conn


def init_db():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id serial PRIMARY KEY,
                repo text NOT NULL,
                file_path text NOT NULL,
                start_line int NOT NULL,
                end_line int NOT NULL,
                language text NOT NULL,
                content text NOT NULL,
                embedding vector({EMBEDDING_DIM}) NOT NULL
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS chunks_repo_idx ON chunks (repo);")
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
            """
        )


def delete_repo(repo: str):
    """Drop existing chunks so re-indexing a repo replaces rather than duplicates."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM chunks WHERE repo = %s;", (repo,))


def insert_chunks(repo: str, chunks: list[dict], embeddings: list[list[float]]):
    rows = [
        (
            repo,
            c["file_path"],
            c["start_line"],
            c["end_line"],
            c["language"],
            c["content"],
            np.array(e),
        )
        for c, e in zip(chunks, embeddings)
    ]
    with get_conn() as conn, conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO chunks (repo, file_path, start_line, end_line, language, content, embedding)
            VALUES %s;
            """,
            rows,
            page_size=200,
        )


def search(query_embedding: list[float], repo: str, k: int = TOP_K) -> list[dict]:
    """Top-k chunks for one repo by cosine distance (embedding <=> query)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT file_path, start_line, end_line, language, content,
                   embedding <=> %s AS distance
            FROM chunks
            WHERE repo = %s
            ORDER BY distance
            LIMIT %s;
            """,
            (np.array(query_embedding), repo, k),
        )
        cols = ["file_path", "start_line", "end_line", "language", "content", "distance"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_repos() -> list[str]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT repo FROM chunks ORDER BY repo;")
        return [r[0] for r in cur.fetchall()]


if __name__ == "__main__":
    init_db()
    print("DB initialized. Indexed repos:", list_repos())
