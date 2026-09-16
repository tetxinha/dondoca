"""
dondoca — backend principal.

Fase atual: receber, via webhook do IFTTT, o que dizes ao Google Nest Mini
e guardar em duas listas (faltas / tarefas). As funções 2, 3 e 4
(receitas, encomenda, WhatsApp) vêm nas próximas fases, a partir desta base.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.ai import validar_item, validar_tarefa
from app.config import WEBHOOK_SECRET
from app.database import (
    adicionar_falta,
    adicionar_tarefa,
    init_db,
    listar_faltas,
    listar_tarefas,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="dondoca", lifespan=lifespan)


class VozPayload(BaseModel):
    """
    O IFTTT envia o texto que disseste ao Google Assistant num campo.
    Configuramos o applet para mandar esse texto no campo `texto`
    (ver README para o passo a passo de configuração do IFTTT).
    """

    texto: str


def _verificar_secret(secret: str | None) -> None:
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Secret inválido")


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
    """Chamado pelo IFTTT quando dizes 'Ei Google, adiciona X às tarefas'."""
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
