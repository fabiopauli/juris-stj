"""SQLite + FTS5 database layer for STJ acordao records."""

from __future__ import annotations

import sqlite3
from dataclasses import astuple, fields
from pathlib import Path

from .config import DB_PATH
from .models import Acordao

SCHEMA = """
CREATE TABLE IF NOT EXISTS acordaos (
    id TEXT PRIMARY KEY,
    numero_documento TEXT,
    numero_processo TEXT,
    numero_registro TEXT,
    sigla_classe TEXT,
    descricao_classe TEXT,
    classe_padronizada TEXT,
    orgao_julgador TEXT,
    ministro_relator TEXT,
    data_publicacao TEXT,
    ementa TEXT,
    tipo_decisao TEXT,
    data_decisao TEXT,
    decisao TEXT,
    jurisprudencia_citada TEXT,
    notas TEXT,
    informacoes_complementares TEXT,
    termos_auxiliares TEXT,
    tese_juridica TEXT,
    tema TEXT,
    referencias_legislativas TEXT,
    acordaos_similares TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS acordaos_fts USING fts5(
    ementa,
    decisao,
    informacoes_complementares,
    termos_auxiliares,
    notas,
    tese_juridica,
    content='acordaos',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

-- Triggers to keep FTS in sync with content table
CREATE TRIGGER IF NOT EXISTS acordaos_ai AFTER INSERT ON acordaos BEGIN
    INSERT INTO acordaos_fts(rowid, ementa, decisao, informacoes_complementares, termos_auxiliares, notas, tese_juridica)
    VALUES (new.rowid, new.ementa, new.decisao, new.informacoes_complementares, new.termos_auxiliares, new.notas, new.tese_juridica);
END;

CREATE TRIGGER IF NOT EXISTS acordaos_ad AFTER DELETE ON acordaos BEGIN
    INSERT INTO acordaos_fts(acordaos_fts, rowid, ementa, decisao, informacoes_complementares, termos_auxiliares, notas, tese_juridica)
    VALUES ('delete', old.rowid, old.ementa, old.decisao, old.informacoes_complementares, old.termos_auxiliares, old.notas, old.tese_juridica);
END;

CREATE TRIGGER IF NOT EXISTS acordaos_au AFTER UPDATE ON acordaos BEGIN
    INSERT INTO acordaos_fts(acordaos_fts, rowid, ementa, decisao, informacoes_complementares, termos_auxiliares, notas, tese_juridica)
    VALUES ('delete', old.rowid, old.ementa, old.decisao, old.informacoes_complementares, old.termos_auxiliares, old.notas, old.tese_juridica);
    INSERT INTO acordaos_fts(rowid, ementa, decisao, informacoes_complementares, termos_auxiliares, notas, tese_juridica)
    VALUES (new.rowid, new.ementa, new.decisao, new.informacoes_complementares, new.termos_auxiliares, new.notas, new.tese_juridica);
END;

CREATE TABLE IF NOT EXISTS sync_state (
    dataset TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    resource_name TEXT,
    downloaded_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (dataset, resource_id)
);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns that may be missing from older databases."""
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(acordaos)").fetchall()
    }
    migrations = [
        ("numero_documento", "TEXT"),
        ("classe_padronizada", "TEXT"),
    ]
    for col, col_type in migrations:
        if col not in existing:
            conn.execute(f"ALTER TABLE acordaos ADD COLUMN {col} {col_type}")
    conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate(conn)


def upsert_acordaos(conn: sqlite3.Connection, records: list[Acordao]) -> int:
    if not records:
        return 0
    cols = [f.name for f in fields(Acordao)]
    placeholders = ", ".join("?" for _ in cols)
    col_names = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO acordaos ({col_names}) VALUES ({placeholders})"
    rows = [astuple(r) for r in records]
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def mark_synced(
    conn: sqlite3.Connection,
    dataset: str,
    resource_id: str,
    resource_name: str,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sync_state (dataset, resource_id, resource_name) VALUES (?, ?, ?)",
        (dataset, resource_id, resource_name),
    )
    conn.commit()


def is_synced(conn: sqlite3.Connection, dataset: str, resource_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sync_state WHERE dataset = ? AND resource_id = ?",
        (dataset, resource_id),
    ).fetchone()
    return row is not None


def clear_sync_state(conn: sqlite3.Connection, dataset: str | None = None) -> None:
    if dataset:
        conn.execute("DELETE FROM sync_state WHERE dataset = ?", (dataset,))
    else:
        conn.execute("DELETE FROM sync_state")
    conn.commit()


def _build_filters(
    *,
    ministro: str | None = None,
    classe: str | None = None,
    desde: str | None = None,
) -> tuple[str, list[str]]:
    clauses = []
    params: list[str] = []
    if ministro:
        clauses.append("a.ministro_relator LIKE ?")
        params.append(f"%{ministro}%")
    if classe:
        clauses.append("a.sigla_classe LIKE ?")
        params.append(f"%{classe}%")
    if desde:
        clauses.append("a.data_decisao >= ?")
        params.append(desde)
    sql = (" AND " + " AND ".join(clauses)) if clauses else ""
    return sql, params


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    ministro: str | None = None,
    classe: str | None = None,
    desde: str | None = None,
    limit: int = 20,
    order: str = "data",
) -> list[sqlite3.Row]:
    filter_sql, filter_params = _build_filters(
        ministro=ministro, classe=classe, desde=desde
    )
    order_clause = "a.data_decisao DESC" if order == "data" else "rank"
    sql = f"""
        SELECT a.*, bm25(acordaos_fts) AS rank
        FROM acordaos_fts f
        JOIN acordaos a ON a.rowid = f.rowid
        WHERE acordaos_fts MATCH ?
        {filter_sql}
        ORDER BY {order_clause} LIMIT ?
    """
    params: list[str | int] = [query, *filter_params, limit]
    return conn.execute(sql, params).fetchall()


def search_stats(
    conn: sqlite3.Connection,
    query: str,
    *,
    ministro: str | None = None,
    classe: str | None = None,
    desde: str | None = None,
) -> dict:
    filter_sql, filter_params = _build_filters(
        ministro=ministro, classe=classe, desde=desde
    )
    base = f"""
        FROM acordaos_fts f
        JOIN acordaos a ON a.rowid = f.rowid
        WHERE acordaos_fts MATCH ?
        {filter_sql}
    """
    base_params: list[str] = [query, *filter_params]

    total = conn.execute(f"SELECT COUNT(*) {base}", base_params).fetchone()[0]
    by_orgao = conn.execute(
        f"SELECT a.orgao_julgador, COUNT(*) as cnt {base} GROUP BY a.orgao_julgador ORDER BY cnt DESC",
        base_params,
    ).fetchall()
    by_classe = conn.execute(
        f"SELECT a.sigla_classe, COUNT(*) as cnt {base} GROUP BY a.sigla_classe ORDER BY cnt DESC LIMIT 10",
        base_params,
    ).fetchall()
    by_relator = conn.execute(
        f"SELECT a.ministro_relator, COUNT(*) as cnt {base} GROUP BY a.ministro_relator ORDER BY cnt DESC LIMIT 10",
        base_params,
    ).fetchall()
    by_year = conn.execute(
        f"SELECT SUBSTR(a.data_decisao, 1, 4) as ano, COUNT(*) as cnt {base} AND a.data_decisao != '' GROUP BY ano ORDER BY ano DESC LIMIT 15",
        base_params,
    ).fetchall()

    return {
        "total": total,
        "by_orgao": by_orgao,
        "by_classe": by_classe,
        "by_relator": by_relator,
        "by_year": by_year,
    }


def get_by_id(conn: sqlite3.Connection, record_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM acordaos WHERE id = ?", (record_id,)
    ).fetchone()


def get_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM acordaos").fetchone()[0]
    by_orgao = conn.execute(
        "SELECT orgao_julgador, COUNT(*) as cnt FROM acordaos GROUP BY orgao_julgador ORDER BY cnt DESC"
    ).fetchall()
    by_classe = conn.execute(
        "SELECT sigla_classe, COUNT(*) as cnt FROM acordaos GROUP BY sigla_classe ORDER BY cnt DESC LIMIT 20"
    ).fetchall()
    sync_info = conn.execute(
        "SELECT dataset, COUNT(*) as resources, MAX(downloaded_at) as last_sync FROM sync_state GROUP BY dataset"
    ).fetchall()
    return {
        "total": total,
        "by_orgao": by_orgao,
        "by_classe": by_classe,
        "sync_info": sync_info,
    }
