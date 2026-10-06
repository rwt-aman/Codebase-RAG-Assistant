"""Embedding wrapper around BAAI/bge-small-en-v1.5 (384-dim).

Uses fastembed (ONNX runtime) rather than sentence-transformers/torch: the same
model and the same 384-dim output, but a ~250MB footprint instead of ~700MB, so
it fits comfortably on small free-tier instances. The model is loaded lazily on
first use so FastAPI starts fast and routes that don't embed stay cheap.
"""
from functools import lru_cache

from .config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=EMBEDDING_MODEL)


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Embed passages (code chunks) in batches. Normalized for cosine search."""
    return [v.tolist() for v in _model().embed(texts, batch_size=batch_size)]


def embed_query(query: str) -> list[float]:
    """Embed a search query. fastembed prepends the BGE query instruction itself."""
    return next(iter(_model().query_embed(query))).tolist()


if __name__ == "__main__":
    vecs = embed_texts(["def add(a, b): return a + b", "SELECT * FROM users", "hello world"])
    print(f"{len(vecs)} vectors, dim={len(vecs[0])}")
    q = embed_query("how do I add two numbers?")
    print(f"query vector dim={len(q)}")
