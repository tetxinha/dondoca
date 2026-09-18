# dondoca

Assistente doméstico pessoal. Esta é a Fase 1: os webhooks de voz (Função 1
e Função 4). As funções 2 (receitas), 3 (lista de compras) e o envio por
WhatsApp para a empregada vêm nas próximas fases, construídas em cima desta
mesma base (SQLite + FastAPI).

## Correr localmente

```bash
python3 -m venv venv
source venv/bin/activate        # no Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edita o .env e escolhe um DONDOCA_WEBHOOK_SECRET só teu
# (o ficheiro .env é lido automaticamente, não precisas de mais nenhum comando)

uvicorn app.main:app --reload
```

O servidor fica em `http://localhost:8000`. Confirma no terminal que aparece uma
linha do tipo `Uvicorn running on http://127.0.0.1:8000` — só depois disso
é que faz sentido abrir o browser ou testar com curl. Testa:

```bash
curl -X POST http://localhost:8000/webhook/falta \
  -H "Content-Type: application/json" \
  -H "x-dondoca-secret: escolhe-uma-frase-secreta-longa" \
  -d '{"texto": "ovos"}'

curl http://localhost:8000/faltas
```

Se vires `ovos` na lista, está a funcionar.

## Configurar o Atalho da Siri (a parte da voz)

**Nota:** chegámos a tentar isto com IFTTT + Google Assistant, mas
desistimos — a Google só permite escrever no Google Keep por essa via, e a
API do Keep é má. A solução atual é um Atalho (Shortcut) no iPhone, que
fala diretamente com a Siri.

Precisas de 2 Atalhos (app **Atalhos** do iPhone):

### Atalho 1 — Faltas
1. Cria um Atalho novo chamado, por exemplo, "Falta".
2. Ação **"Perguntar"** (Ask for Input), tipo Texto, com a pergunta
   `O que falta?`.
3. Ação **"Obter Conteúdo de URL"** (Get Contents of URL):
   - URL: `https://<o-teu-dominio-quando-fizeres-deploy>/webhook/falta`
   - Método: `POST`
   - Cabeçalhos: `Content-Type: application/json` e
     `x-dondoca-secret: <o-mesmo-valor-do-teu-.env>`
   - Corpo do pedido: JSON, campo `texto` a apontar para a resposta da
     pergunta anterior (ex: `{"texto": [Resposta Fornecida]}`).
4. Nos detalhes do Atalho, ativa **"Adicionar à Siri"** e grava a frase
   `Ei Siri, Falta`.

### Atalho 2 — Tarefas
Igual ao Atalho 1, mas:
- Pergunta: `Que tarefas?`
- URL: `.../webhook/tarefa`
- Frase da Siri: `Ei Siri, Tarefa`

> Nota: enquanto testas localmente, a Siri não consegue chegar ao teu
> `localhost` (é preciso um URL público). Antes de fazeres deploy
> definitivo, podes usar o `ngrok` (`ngrok http 8000`) para teres um URL
> público temporário.

## Agendador (APScheduler)

A app tem um agendador interno (`app/scheduler.py`), que arranca sozinho
com o servidor — não precisas de nenhum cron externo para estes dois
jobs. A lógica de cada job vive em `app/jobs.py` (reutilizada também
pelos endpoints de teste manual, para não haver duas versões da mesma
coisa):

- **Sexta-feira às 20h** — `job_cardapio_e_lista_compras()`: escolhe as 5
  receitas da semana, monta a lista de compras e manda por WhatsApp duas
  mensagens (🛍️ Mercado e 📦 Continente) para cada número configurado
  (`WHATSAPP_NUMERO_RITA` / `WHATSAPP_NUMERO_MARIDO`). Este horário dá
  tempo de ver a lista antes de ires ao mercado no sábado de manhã.
- **Segunda e terça-feira às 20h** — `job_prioridades_empregada()`: junta
  a obrigação fixa do dia seguinte (`EMPREGADA_DIAS` em `app/config.py`)
  com as tarefas ainda por enviar, e manda as prioridades por WhatsApp —
  por agora, só para a Rita (`WHATSAPP_NUMERO_RITA`), enquanto a empregada
  ainda não tem número configurado.

Se um envio falhar (ex: fora da janela de 24h, enquanto os templates da
Meta não são aprovados), o job não rebenta nem perde as tarefas por
enviar — só volta a tentar da próxima vez.

> ⚠️ **Corre sempre com um único worker.** Com mais do que um
> (`uvicorn app.main:app --workers 2`, ou várias instâncias em produção),
> cada worker teria o seu próprio agendador e os jobs corriam em
> duplicado — cardápios a dobrar e mensagens de WhatsApp repetidas.

### Testar manualmente
Os jobs também têm endpoints para testares sem esperar pelo dia certo:

```bash
# escolher as receitas da semana (não manda WhatsApp)
curl -X POST "http://localhost:8000/job/cardapio-semanal?force=true" \
  -H "x-dondoca-secret: escolhe-uma-frase-secreta-longa"

curl http://localhost:8000/cardapio-semanal
```

Para testares o envio por WhatsApp em si (`job_cardapio_e_lista_compras`
ou `job_prioridades_empregada`), chama-os diretamente em Python:

```bash
python3 -c "from app.jobs import job_cardapio_e_lista_compras as j; j()"
```

## Lista de compras semanal

Depois de o job de sexta-feira escolher as receitas, `GET
/lista-compras-semanal` junta os ingredientes principais dessas 5 receitas
com os itens ainda por resolver na lista de faltas, remove duplicados e
variações do mesmo item (ex: "tomate" e "tomates" contam como um só) e
separa tudo em duas listas — cada uma já com um campo `texto` pronto a
colar numa conversa de WhatsApp:

- **`mercado`**: produtos frescos — legumes, fruta, carne, peixe, arroz.
- **`continente`**: tudo o resto — limpeza, higiene, mercearia não
  perecível, iogurtes, leite, massas, condimentos, cereais/aveia.

```bash
curl http://localhost:8000/lista-compras-semanal
```

Não precisa de secret (é só leitura, como `/faltas` ou `/cardapio-semanal`),
mas dá erro `404` se ainda não tiver corrido nenhum `/job/cardapio-semanal`.

## Enviar por WhatsApp (WhatsApp Cloud API da Meta)

`app/whatsapp.py` envia mensagens usando a WhatsApp Cloud API da Meta.
Passos manuais na [Meta for Developers](https://developers.facebook.com)
(não há como automatizar isto — é tudo feito na conta da Meta):

1. Cria uma conta de developer e uma App do tipo **Business**.
2. Na App, adiciona o produto **WhatsApp**. A Meta atribui logo um número
   de testes grátis.
3. Na página **"API Setup"** da App encontras o `Temporary access token`
   (24h) e o `Phone number ID` — copia-os para `WHATSAPP_TOKEN` e
   `WHATSAPP_PHONE_NUMBER_ID` no teu `.env`. Para um token que não expire,
   cria um **System User** em Business Settings → Users → System Users,
   com a permissão `whatsapp_business_messaging`.
4. Enquanto a app está em modo de testes, só consegues enviar para números
   que adicionares e verificares (por SMS) na secção "API Setup" → "To".
   Guarda esses números em `WHATSAPP_NUMERO_RITA` / `WHATSAPP_NUMERO_MARIDO`
   no `.env` (formato internacional, só dígitos: ex. `351912345678`).

### Texto livre vs. templates
- `enviar_mensagem(numero, texto)` manda texto livre, mas só é entregue se
  o destinatário te tiver escrito nas últimas 24h (a "janela de
  atendimento" da Meta). Serve para testar rapidamente:
  ```bash
  python3 -c "
  from app.config import WHATSAPP_NUMERO_RITA
  from app.whatsapp import enviar_mensagem
  print(enviar_mensagem(WHATSAPP_NUMERO_RITA, 'teste'))
  "
  ```
- Fora dessa janela (ex: enviar a lista sem a pessoa ter escrito primeiro),
  a Meta só entrega mensagens de **template pré-aprovado**. Temos três
  templates em revisão na Meta — `lista_mercado`, `lista_continente` e
  `lista_tarefas` — todos com uma única variável `{{1}}` no corpo, onde
  entra a lista em bullet points (um item por parágrafo). Os nomes vão
  para `WHATSAPP_TEMPLATE_LISTA_MERCADO` / `_CONTINENTE` / `_TAREFAS` no
  `.env`, e `WHATSAPP_TEMPLATE_LINGUA` (o mesmo para os três).
- `enviar_lista_mercado(numero, itens)`, `enviar_lista_continente(numero,
  itens)` e `enviar_lista_tarefas(numero, itens)` usam esses templates.
  **Não funcionam enquanto a Meta não aprovar os templates** — até lá, a
  chamada à API é recusada mesmo com o nome certo configurado. Por agora,
  os jobs do agendador usam texto livre (`enviar_mensagem`) em vez destas
  três — assim que os templates forem aprovados, `app/jobs.py` passa a
  usá-las (deixam de depender da janela de 24h).

## Próximos passos (fases seguintes)

- Fase 2: já tens o job de sexta-feira que escolhe as 5 receitas — falta ligar
  isto a uma fonte de receitas mais viva que o CSV (ex: Google Sheet), se
  fizer sentido no futuro.
- Fase 3 e Fase 4: **feitas** — o agendador (`app/scheduler.py` +
  `app/jobs.py`) já envia a lista de compras à sexta-feira e as
  prioridades da empregada à segunda/terça. Falta só a Meta aprovar os
  templates para trocar `enviar_mensagem` pelas funções de template.
- Deploy: Railway, Render ou Fly.io — basta ligar o repositório GitHub
  (lembra-te: um único worker, ver secção do Agendador acima).

## Estrutura

```
dondoca/
├── app/
│   ├── main.py        # rotas / webhooks / lifespan (arranca o agendador)
│   ├── scheduler.py    # agendamento dos jobs semanais (APScheduler)
│   ├── jobs.py          # lógica dos jobs (receitas, lista de compras, prioridades)
│   ├── ai.py           # filtros e decisões inteligentes (Claude)
│   ├── receitas.py     # leitura do CSV de receitas
│   ├── whatsapp.py     # envio de mensagens (WhatsApp Cloud API)
│   ├── database.py    # SQLite
│   └── config.py       # configurações e regras da casa
├── data/
│   └── receitas.csv    # livro de receitas da casa
├── requirements.txt
└── .env.example
```
