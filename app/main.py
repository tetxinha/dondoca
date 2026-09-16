"""
dondoca — backend principal.

Fase atual: receber, via webhook do IFTTT, o que dizes ao Google Nest Mini
e guardar em duas listas (faltas / tarefas). As funções 2, 3 e 4
(receitas, encomenda, WhatsApp) vêm nas próximas fases, a partir desta base.
"""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.ai import escolher_receitas_semana, validar_item, validar_tarefa
from app.config import WEBHOOK_SECRET
from app.database import (
    adicionar_falta,
    adicionar_tarefa,
    guardar_cardapio_semanal,
    init_db,
    listar_compras_historico,
    listar_faltas,
    listar_tarefas,
    marcar_compra,
    ultimo_cardapio_semanal,
)
from app.receitas import receitas_como_lista


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


class ItemComprado(BaseModel):
    item: str
    quantidade: str | None = None


class ComprasPayload(BaseModel):
    itens: list[ItemComprado]


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


@app.post("/job/cardapio-semanal")
def job_cardapio_semanal(force: bool = False, x_dondoca_secret: str | None = Header(default=None)):
    """
    Job semanal que escolhe 5 receitas, equilibrando proteína/hidratos/
    leguminosas e evitando repetir as da semana passada. Pensado para ser
    chamado por um cron externo (Render Cron Job, IFTTT Date & Time, etc.)
    aos domingos — usa `?force=true` para testar manualmente noutro dia.
    """
    _verificar_secret(x_dondoca_secret)

    if not force and datetime.now().weekday() != 6:
        raise HTTPException(
            status_code=409,
            detail="Hoje não é domingo. Usa ?force=true para testar mesmo assim.",
        )

    receitas = receitas_como_lista()
    evitar = ultimo_cardapio_semanal()
    historico_compras = [row["texto"] for row in listar_faltas(so_por_resolver=False)][-30:]

    resultado = escolher_receitas_semana(receitas, evitar, historico_compras)
    novo_id = guardar_cardapio_semanal(resultado["escolhidas"], resultado.get("justificacao", ""))

    return {
        "ok": True,
        "id": novo_id,
        "escolhidas": resultado["escolhidas"],
        "justificacao": resultado.get("justificacao", ""),
    }


@app.get("/cardapio-semanal")
def get_cardapio_semanal():
    """Só para testares o que foi escolhido na última vez que o job correu."""
    return {"escolhidas": ultimo_cardapio_semanal()}


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
