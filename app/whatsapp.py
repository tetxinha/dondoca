"""
Envio de mensagens de WhatsApp através da WhatsApp Cloud API (Meta).

Ver README para os passos manuais de configuração na Meta for Developers
(conta, número de testes, token de acesso) — não há nada aqui que os
substitua, o `.env` só guarda o resultado final (token + phone number ID).
"""

import requests

from app.config import (
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TEMPLATE_LINGUA,
    WHATSAPP_TEMPLATE_LISTA_CONTINENTE,
    WHATSAPP_TEMPLATE_LISTA_MERCADO,
    WHATSAPP_TEMPLATE_LISTA_TAREFAS,
    WHATSAPP_TOKEN,
)

VERSAO_API = "v21.0"


def _enviar(payload: dict) -> dict:
    url = f"https://graph.facebook.com/{VERSAO_API}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    resposta = requests.post(url, headers=headers, json=payload, timeout=10)
    try:
        resposta.raise_for_status()
    except requests.HTTPError as erro:
        raise requests.HTTPError(f"{erro} — resposta da Meta: {resposta.text}") from erro

    return resposta.json()


def enviar_mensagem(numero: str, texto: str) -> dict:
    """
    Envia uma mensagem de texto simples pelo WhatsApp Cloud API.

    - numero: número de destino em formato internacional, só dígitos
      (ex: "351912345678", sem "+" nem espaços).
    - texto: o corpo da mensagem.

    Devolve a resposta JSON da Meta. Nota: fora da janela de 24h desde a
    última mensagem do destinatário, a Meta só entrega mensagens de modelo
    (template) pré-aprovado — texto livre como este só chega se o
    destinatário já vos tiver escrito recentemente.
    """
    return _enviar(
        {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"body": texto},
        }
    )


def enviar_template(
    numero: str, nome_template: str, variaveis_corpo: list[str], lingua: str = WHATSAPP_TEMPLATE_LINGUA
) -> dict:
    """
    Envia uma mensagem usando um template (aprovado, ou em revisão) na Meta.
    Ao contrário de `enviar_mensagem`, funciona fora da janela de 24h.

    - nome_template: o nome exato do template, tal como configurado na Meta.
    - variaveis_corpo: valores para as variáveis {{1}}, {{2}}, ... do corpo
      do template, por ordem.
    - lingua: código de idioma do template, tal como escolhido ao criá-lo.
    """
    return _enviar(
        {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "template",
            "template": {
                "name": nome_template,
                "language": {"code": lingua},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": valor} for valor in variaveis_corpo],
                    }
                ],
            },
        }
    )


def formatar_lista_bullets(itens: list[str]) -> str:
    """Formata itens como bullet points, um por parágrafo — para caber
    numa única variável de template."""
    return "\n\n".join(f"• {item}" for item in itens)


def enviar_lista_mercado(numero: str, itens: list[str]) -> dict:
    """Envia a lista do mercado pelo template WHATSAPP_TEMPLATE_LISTA_MERCADO."""
    return enviar_template(numero, WHATSAPP_TEMPLATE_LISTA_MERCADO, [formatar_lista_bullets(itens)])


def enviar_lista_continente(numero: str, itens: list[str]) -> dict:
    """Envia a lista do Continente pelo template WHATSAPP_TEMPLATE_LISTA_CONTINENTE."""
    return enviar_template(numero, WHATSAPP_TEMPLATE_LISTA_CONTINENTE, [formatar_lista_bullets(itens)])


def enviar_lista_tarefas(numero: str, itens: list[str]) -> dict:
    """Envia a lista de tarefas pelo template WHATSAPP_TEMPLATE_LISTA_TAREFAS."""
    return enviar_template(numero, WHATSAPP_TEMPLATE_LISTA_TAREFAS, [formatar_lista_bullets(itens)])
