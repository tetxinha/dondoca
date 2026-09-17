"""
Agendador dos jobs semanais. A app já corre num único processo
long-running (uvicorn) — o APScheduler poupa-nos de precisar de um cron
externo só para estes dois jobs.

Importante: correr sempre com um único worker (--workers 1). Com mais do
que um, cada worker teria o seu próprio agendador e os jobs corriam em
duplicado.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.jobs import job_cardapio_e_lista_compras, job_prioridades_empregada

FUSO_HORARIO = "Europe/Lisbon"


def iniciar_agendador() -> BackgroundScheduler:
    """Regista os jobs e arranca o agendador. Chamar uma vez no arranque da app."""
    agendador = BackgroundScheduler(timezone=FUSO_HORARIO)
    agendador.add_job(
        job_cardapio_e_lista_compras,
        CronTrigger(day_of_week="fri", hour=20, minute=0),
        id="cardapio_e_lista_compras",
        replace_existing=True,
    )
    agendador.add_job(
        job_prioridades_empregada,
        CronTrigger(day_of_week="mon,tue", hour=20, minute=0),
        id="prioridades_empregada",
        replace_existing=True,
    )
    agendador.start()
    return agendador
