"""
Acesso ao ficheiro de receitas (data/receitas.csv).
"""

import pandas as pd

from app.config import RECEITAS_PATH


def listar_receitas() -> pd.DataFrame:
    """Lê o CSV de receitas e devolve-o como DataFrame."""
    return pd.read_csv(RECEITAS_PATH)


def receitas_como_lista() -> list[dict]:
    """Lê o CSV de receitas e devolve uma lista de dicionários, pronta para
    enviar ao Claude (sem NaN, que não é JSON válido)."""
    return listar_receitas().fillna("").to_dict(orient="records")


def receitas_por_nome(nomes: list[str]) -> list[dict]:
    """Filtra o livro de receitas pelos nomes dados (ex: as escolhidas para a semana)."""
    return [r for r in receitas_como_lista() if r["Nome"] in nomes]