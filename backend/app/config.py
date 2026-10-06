"""Central config: loads .env once, everything else imports from here."""
import os
from pathlib import Path

from dotenv import load_dotenv

# .env lives at backend/.env (one level above app/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MAX_FILE_BYTES = 200 * 1024
TOP_K = 6
