"""
Lógica dos jobs semanais: escolher as receitas, montar a lista de compras
e as prioridades da empregada, e enviá-las por WhatsApp.

Fica separado de app/main.py para o agendador (app/scheduler.py) e os
endpoints de teste manual poderem chamar exatamente a mesma lógica, sem
duplicar nada nos dois sítios.
"""

from datetime import datetime

import requests

from app.ai import escolher_receitas_semana, gerar_lista_compras_semanal
from app.config import EMPREGADA_DIAS, WHATSAPP_NUMERO_MARIDO, WHATSAPP_NUMERO_RITA
from app.database import (
    guardar_cardapio_semanal,
    listar_faltas,
    listar_tarefas,
    marcar_tarefas_enviadas,
    ultimo_cardapio_semanal,
)
from app.receitas import receitas_como_lista, receitas_por_nome
from app.whatsapp import enviar_mensagem, formatar_lista_bullets


def escolher_e_guardar_receitas_semana() -> dict:
    """Pede ao Claude as 5 receitas da semana e guarda o resultado.

    Devolve o dicionário de `escolher_receitas_semana` (escolhidas +
    justificacao), com um campo extra "id" (o id da linha guardada).
    """
    receitas = receitas_como_lista()
    evitar = ultimo_cardapio_semanal()
    historico_compras = [row["texto"] for row in listar_faltas(so_por_resolver=False)][-30:]

    resultado = escolher_receitas_semana(receitas, evitar, historico_compras)
    resultado["id"] = guardar_cardapio_semanal(resultado["escolhidas"], resultado.get("justificacao", ""))
    return resultado


def montar_lista_compras_semanal(nomes_receitas: list[str]) -> dict:
    """Junta os ingredientes das receitas dadas com as faltas por resolver e classifica em mercado/continente."""
    receitas_semana = receitas_por_nome(nomes_receitas)
    itens_faltas = [row["texto"] for row in listar_faltas()]
    return gerar_lista_compras_semanal(receitas_semana, itens_faltas)


def _destinatarios_casal() -> list[str]:
    return [numero for numero in (WHATSAPP_NUMERO_RITA, WHATSAPP_NUMERO_MARIDO) if numero]


def _enviar_com_tolerancia(numero: str, texto: str) -> bool:
    """
    Envia uma mensagem sem rebentar o job todo se a Meta recusar — ex:
    fora da janela de 24h desde a última mensagem do destinatário,
    enquanto os templates não são aprovados. Devolve se resultou.
    """
    try:
        enviar_mensagem(numero, texto)
        return True
    except requests.RequestException as erro:
        print(f"[whatsapp] falha ao enviar para {numero}: {erro}")
        return False


def job_cardapio_e_lista_compras() -> None:
    """
    Sexta-feira às 20h: escolhe as receitas da semana, monta a lista de
    compras e envia duas mensagens de WhatsApp — mercado e Continente —
    para cada destinatário configurado (Rita e marido, por agora).
    """
    resultado = escolher_e_guardar_receitas_semana()
    lista = montar_lista_compras_semanal(resultado["escolhidas"])

    texto_mercado = "🛍️ Lista do Mercado (sábado)\n\n" + formatar_lista_bullets(lista["mercado"])
    texto_continente = "📦 Lista Continente\n\n" + formatar_lista_bullets(lista["continente"])

    for numero in _destinatarios_casal():
        _enviar_com_tolerancia(numero, texto_mercado)
        _enviar_com_tolerancia(numero, texto_continente)


def job_prioridades_empregada() -> None:
    """
    Segunda e terça-feira: junta as tarefas ainda por enviar com a
    obrigação fixa da empregada para o dia seguinte (EMPREGADA_DIAS) e
    envia as prioridades por WhatsApp — por agora, só para a Rita,
    enquanto se espera pela aprovação dos templates na Meta.
    """
    if not WHATSAPP_NUMERO_RITA:
        return

    amanha = (datetime.now().weekday() + 1) % 7
    tarefa_fixa = EMPREGADA_DIAS.get(amanha)

    tarefas = listar_tarefas()
    itens_tarefas = [row["texto"] for row in tarefas]

    if not tarefa_fixa and not itens_tarefas:
        return

    partes = ["📋 Prioridades de amanhã"]
    if tarefa_fixa:
        partes.append(f"Empregada: {tarefa_fixa}")
    if itens_tarefas:
        partes.append("Tarefas pendentes:\n" + formatar_lista_bullets(itens_tarefas))

    enviado = _enviar_com_tolerancia(WHATSAPP_NUMERO_RITA, "\n\n".join(partes))

    if enviado and tarefas:
        marcar_tarefas_enviadas([row["id"] for row in tarefas])
