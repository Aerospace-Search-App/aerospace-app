"""PostgreSQL bağlantı havuzu ve şema kurulumu (psycopg 3 + pgvector)."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

log = logging.getLogger(__name__)
_pool: ConnectionPool | None = None


def _configure(conn: psycopg.Connection) -> None:
    register_vector(conn)


def init_schema() -> None:
    """Şemayı uygular. Uzantı kayıttan önce oluşturulmalı, bu yüzden ayrı bağlantı kullanılır."""
    s = get_settings()
    sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    sql = sql.replace("{dim}", str(int(s.embedding_dim)))
    last_err: Exception | None = None
    for attempt in range(30):  # docker'da DB geç açılabilir
        try:
            with psycopg.connect(s.database_url, autocommit=True) as conn:
                conn.execute(sql)
            return
        except psycopg.OperationalError as e:
            last_err = e
            log.warning("Veritabanına bağlanılamadı (%s). Tekrar deneniyor...", e.__class__.__name__)
            time.sleep(2)
    raise RuntimeError(f"Veritabanına bağlanılamadı: {last_err}")


def open_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = ConnectionPool(
            s.database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            configure=_configure,
            open=True,
        )
        _pool.wait(timeout=30)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    pool = open_pool()
    with pool.connection() as conn:
        yield conn


def fetch_one(sql: str, params: Any = None) -> dict | None:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchone()


def fetch_all(sql: str, params: Any = None) -> list[dict]:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def execute(sql: str, params: Any = None) -> None:
    with get_conn() as conn:
        conn.execute(sql, params)
