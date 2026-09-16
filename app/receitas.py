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