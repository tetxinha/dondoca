"""
dondoca — backend principal.

Fase atual: receber, via Atalhos da Siri no iPhone, o que dizes sobre
faltas e tarefas, e guardar em duas listas (faltas / tarefas). As funções
2, 3 e 4 (receitas, encomenda, WhatsApp) vêm nas próximas fases, a partir
desta base.
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.ai import validar_item, validar_tarefa
from app.config import WEBHOOK_SECRET
from app.database import (
    adicionar_falta,
    adicionar_tarefa,
    init_db,
    listar_compras_historico,
    listar_faltas,
    listar_tarefas,
    marcar_compra,
    ultimo_cardapio_semanal,
)
from app.jobs import escolher_e_guardar_receitas_semana, montar_lista_compras_semanal
from app.scheduler import iniciar_agendador


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    agendador = iniciar_agendador()
    yield
    agendador.shutdown()


app = FastAPI(title="dondoca", lifespan=lifespan)


class VozPayload(BaseModel):
    """
    O Atalho da Siri manda no campo `texto` o que disseste depois de ele
    te perguntar "O que falta?" ou "Que tarefas?" (ver README para o passo
    a passo de configuração do Atalho).
    """

    texto: str


class ItemComprado(BaseModel):
    item: str
    quantidade: str | None = None


class ComprasPayload(BaseModel):
    itens: list[ItemComprado]


def _verificar_secret(secret: str | None) -> None:
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Secret inválido")


def _texto_whatsapp(titulo: str, itens: list[str]) -> str:
    if not itens:
        return f"{titulo}: nada a comprar esta semana."
    linhas = "\n".join(f"- {item}" for item in itens)
    return f"{titulo}:\n{linhas}"


@app.post("/webhook/falta")
def webhook_falta(payload: VozPayload, x_dondoca_secret: str | None = Header(default=None)):
    """Chamado pelo Atalho da Siri quando dizes 'Ei Siri, Falta'."""
    _verificar_secret(x_dondoca_secret)

    itens_atuais = [row["texto"] for row in listar_faltas()]
    resultado = validar_item(payload.texto, itens_atuais)

    if not resultado["valido"] or resultado["duplicado"]:
        return {
            "ok": True,
            "adicionado": False,
            "mensagem": resultado["mensagem"],
        }

    novo_id = adicionar_falta(resultado["item_limpo"])
    return {
        "ok": True,
        "adicionado": True,
        "id": novo_id,
        "texto": resultado["item_limpo"],
        "mensagem": resultado["mensagem"],
    }


@app.post("/webhook/tarefa")
def webhook_tarefa(payload: VozPayload, x_dondoca_secret: str | None = Header(default=None)):
    """Chamado pelo Atalho da Siri quando dizes 'Ei Siri, Tarefa'."""
    _verificar_secret(x_dondoca_secret)

    itens_atuais = [row["texto"] for row in listar_tarefas()]
    resultado = validar_tarefa(payload.texto, itens_atuais)

    if not resultado["valido"] or resultado["duplicado"]:
        return {
            "ok": True,
            "adicionado": False,
            "mensagem": resultado["mensagem"],
        }

    novo_id = adicionar_tarefa(resultado["item_limpo"])
    return {
        "ok": True,
        "adicionado": True,
        "id": novo_id,
        "texto": resultado["item_limpo"],
        "mensagem": resultado["mensagem"],
    }


@app.post("/job/cardapio-semanal")
def job_cardapio_semanal(force: bool = False, x_dondoca_secret: str | None = Header(default=None)):
    """
    Escolhe 5 receitas, equilibrando proteína/hidratos/leguminosas e
    evitando repetir as da semana passada. Corre automaticamente às
    sextas-feiras às 20h (ver app/scheduler.py) — este endpoint serve para
    testares manualmente. Usa `?force=true` para testar noutro dia.
    """
    _verificar_secret(x_dondoca_secret)

    if not force and datetime.now().weekday() != 4:
        raise HTTPException(
            status_code=409,
            detail="Hoje não é sexta-feira. Usa ?force=true para testar mesmo assim.",
        )

    resultado = escolher_e_guardar_receitas_semana()

    return {
        "ok": True,
        "id": resultado["id"],
        "escolhidas": resultado["escolhidas"],
        "justificacao": resultado.get("justificacao", ""),
    }


@app.get("/cardapio-semanal")
def get_cardapio_semanal():
    """Só para testares o que foi escolhido na última vez que o job correu."""
    return {"escolhidas": ultimo_cardapio_semanal()}


@app.get("/lista-compras-semanal")
def get_lista_compras_semanal():
    """
    Junta os ingredientes das 5 receitas escolhidas esta semana com os
    itens ainda por resolver na lista de faltas, remove duplicados e separa
    tudo em duas listas prontas a enviar por WhatsApp: mercado (fresco) e
    Continente (tudo o resto).
    """
    nomes_receitas = ultimo_cardapio_semanal()
    if not nomes_receitas:
        raise HTTPException(
            status_code=404,
            detail="Ainda não há nenhum cardápio semanal gerado. Corre primeiro /job/cardapio-semanal.",
        )

    resultado = montar_lista_compras_semanal(nomes_receitas)

    return {
        "mercado": {
            "itens": resultado["mercado"],
            "texto": _texto_whatsapp("Mercado", resultado["mercado"]),
        },
        "continente": {
            "itens": resultado["continente"],
            "texto": _texto_whatsapp("Continente", resultado["continente"]),
        },
    }


@app.post("/compras/marcar")
def marcar_compras(payload: ComprasPayload, x_dondoca_secret: str | None = Header(default=None)):
    """Regista uma lista de itens como comprados."""
    _verificar_secret(x_dondoca_secret)

    ids = [marcar_compra(item.item, item.quantidade) for item in payload.itens]
    return {"ok": True, "registadas": len(ids), "ids": ids}


@app.get("/compras/historico")
def get_compras_historico(dias: int = 7):
    """Compras registadas nos últimos `dias` dias (por omissão, 7)."""
    return [dict(row) for row in listar_compras_historico(dias)]


@app.get("/faltas")
def get_faltas():
    """Só para testares que as coisas estão a ser guardadas."""
    return [dict(row) for row in listar_faltas()]


@app.get("/tarefas")
def get_tarefas():
    """Só para testares que as coisas estão a ser guardadas."""
    return [dict(row) for row in listar_tarefas()]


@app.get("/")
def raiz():
    return {"app": "dondoca", "estado": "a funcionar"}
