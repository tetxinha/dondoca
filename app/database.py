"""
Acesso à base de dados. SQLite chega perfeitamente para este volume de dados
(é só uma casa, não um supermercado) e não obriga a gerir um servidor extra.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

from app.config import DB_PATH


def init_db() -> None:
    """Cria as tabelas se ainda não existirem. Chamar uma vez no arranque."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS faltas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                texto TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                resolvido INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tarefas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                texto TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                enviado INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def adicionar_falta(texto: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO faltas (texto, criado_em) VALUES (?, ?)",
            (texto, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid


def adicionar_tarefa(texto: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO tarefas (texto, criado_em) VALUES (?, ?)",
            (texto, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid


def listar_faltas(so_por_resolver: bool = True) -> list[sqlite3.Row]:
    query = "SELECT * FROM faltas"
    if so_por_resolver:
        query += " WHERE resolvido = 0"
    query += " ORDER BY criado_em"
    with get_connection() as conn:
        return conn.execute(query).fetchall()


def listar_tarefas(so_por_enviar: bool = True) -> list[sqlite3.Row]:
    query = "SELECT * FROM tarefas"
    if so_por_enviar:
        query += " WHERE enviado = 0"
    query += " ORDER BY criado_em"
    with get_connection() as conn:
        return conn.execute(query).fetchall()
