"""Postgres connection helper. One short-lived connection per operation —
fine at v1 scale; swap in a pool when concurrency demands it."""
import psycopg2
from pgvector.psycopg2 import register_vector

from .config import DATABASE_URL


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set — copy backend/.env.example to backend/.env and fill it in.")
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    return conn
