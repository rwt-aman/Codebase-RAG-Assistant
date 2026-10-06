"""The core RAG loop: embed question -> retrieve chunks -> prompt Gemini -> cited answer."""
from google import genai
from google.genai import types

from .config import GEMINI_API_KEY, GEMINI_MODEL, TOP_K
from .embed import embed_query
from .store import search

SYSTEM_INSTRUCTION = """You are a codebase assistant. Answer the user's question using ONLY the code context provided below.

Rules:
- Every claim about the code must cite its source as `file_path:start_line-end_line` (matching the labels in the context).
- If the context does not contain the answer, say you can't find it in the indexed parts of this codebase — do not guess or use outside knowledge about the project.
- Be concise and technical. Quote small code snippets when they help.
"""


def _format_context(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        parts.append(
            f"--- {c['file_path']}:{c['start_line']}-{c['end_line']} ({c['language']}) ---\n{c['content']}"
        )
    return "\n\n".join(parts)


def answer_question(question: str, repo: str, k: int = TOP_K) -> dict:
    """Returns {"answer": str, "sources": [chunk metadata...]}."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set — add it to backend/.env.")

    query_vec = embed_query(question)
    chunks = search(query_vec, repo, k=k)

    if not chunks:
        return {
            "answer": f"No indexed code found for repo '{repo}'. Index it first via POST /index.",
            "sources": [],
        }

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"Code context from repository '{repo}':\n\n"
        f"{_format_context(chunks)}\n\n"
        f"Question: {question}"
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
    )

    sources = [
        {
            "file_path": c["file_path"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "language": c["language"],
            "distance": round(float(c["distance"]), 4),
        }
        for c in chunks
    ]
    return {"answer": response.text, "sources": sources}


if __name__ == "__main__":
    import json
    import sys

    repo = sys.argv[1] if len(sys.argv) > 1 else "click"
    question = sys.argv[2] if len(sys.argv) > 2 else "How are command line options parsed?"
    print(json.dumps(answer_question(question, repo), indent=2))
