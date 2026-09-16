"""
Acesso à base de dados. SQLite chega perfeitamente para este volume de dados
(é só uma casa, não um supermercado) e não obriga a gerir um servidor extra.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cardapio_semanal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receitas TEXT NOT NULL,
                justificacao TEXT,
                criado_em TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS compras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                quantidade TEXT,
                data TEXT NOT NULL
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


def guardar_cardapio_semanal(nomes_receitas: list[str], justificacao: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO cardapio_semanal (receitas, justificacao, criado_em) VALUES (?, ?, ?)",
            (json.dumps(nomes_receitas, ensure_ascii=False), justificacao, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid


def ultimo_cardapio_semanal() -> list[str]:
    """Nomes das receitas escolhidas da última vez que o job correu (lista vazia se ainda não correu nenhuma vez)."""
    with get_connection() as conn:
        linha = conn.execute(
            "SELECT receitas FROM cardapio_semanal ORDER BY criado_em DESC LIMIT 1"
        ).fetchone()
    return json.loads(linha["receitas"]) if linha else []


def marcar_compra(item: str, quantidade: str | None = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO compras (item, quantidade, data) VALUES (?, ?, ?)",
            (item, quantidade, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid


def listar_compras_historico(dias: int) -> list[sqlite3.Row]:
    desde = (datetime.now() - timedelta(days=dias)).isoformat()
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM compras WHERE data >= ? ORDER BY data DESC",
            (desde,),
        ).fetchall()
