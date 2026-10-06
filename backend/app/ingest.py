"""Clone a GitHub repo, walk its code files, and split them into
line-annotated chunks ready for embedding."""
import os
import shutil
import stat
import sys
import tempfile

from git import Repo
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from .config import CHUNK_OVERLAP, CHUNK_SIZE, MAX_FILE_BYTES

EXT_LANGUAGE = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
    ".java": Language.JAVA,
    ".cpp": Language.CPP,
    ".c": Language.C,
    ".go": Language.GO,
    ".rs": Language.RUST,
}

SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", "vendor"}


def repo_name_from_url(github_url: str) -> str:
    return github_url.rstrip("/").removesuffix(".git").split("/")[-1]


def _splitter_for(language: Language) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter.from_language(
        language=language, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )


def _chunk_file(rel_path: str, text: str, language: Language) -> list[dict]:
    """Split one file and attach 1-based start/end line numbers to each chunk.

    Chunks overlap, so we locate each chunk in the source starting from the
    previous chunk's start offset to keep the search anchored and O(n) overall.
    """
    splitter = _splitter_for(language)
    chunks = []
    search_from = 0
    for piece in splitter.split_text(text):
        idx = text.find(piece, search_from)
        if idx == -1:  # fallback: search from the top (shouldn't happen)
            idx = text.find(piece)
            if idx == -1:
                continue
        start_line = text.count("\n", 0, idx) + 1
        end_line = start_line + piece.count("\n")
        chunks.append(
            {
                "file_path": rel_path,
                "start_line": start_line,
                "end_line": end_line,
                "language": language.value,
                "content": piece,
            }
        )
        search_from = idx + 1
    return chunks


def _on_rm_error(func, path, exc_info):
    """git objects are read-only on Windows; make writable and retry."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def ingest_repo(github_url: str) -> list[dict]:
    """Clone `github_url` and return a list of chunk dicts:
    {file_path, start_line, end_line, language, content}."""
    tmp_dir = tempfile.mkdtemp(prefix="repo_")
    all_chunks: list[dict] = []
    try:
        Repo.clone_from(github_url, tmp_dir, depth=1)
        for root, dirs, files in os.walk(tmp_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                language = EXT_LANGUAGE.get(ext)
                if language is None:
                    continue
                full = os.path.join(root, fname)
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
                try:
                    with open(full, encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                except OSError:
                    continue
                if not text.strip():
                    continue
                rel_path = os.path.relpath(full, tmp_dir).replace(os.sep, "/")
                all_chunks.extend(_chunk_file(rel_path, text, language))
    finally:
        # onexc was added in 3.12; the deploy image runs 3.11 which uses onerror.
        if sys.version_info >= (3, 12):
            shutil.rmtree(tmp_dir, onexc=_on_rm_error)
        else:
            shutil.rmtree(tmp_dir, onerror=_on_rm_error)
    return all_chunks


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/pallets/click"
    result = ingest_repo(url)
    print(f"{len(result)} chunks from {url}")
    for c in result[:3]:
        print(f"  {c['file_path']}:{c['start_line']}-{c['end_line']} [{c['language']}] {len(c['content'])} chars")
