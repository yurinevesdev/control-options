"""
Scheduler de tarefas de background para System.
Roda verificações diárias de opções próximas do vencimento e envia e-mails.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional

from system.ui.logger import get_logger
from system.config import SCHEDULER_HORA, EMAIL_NOTIFICACOES_ATIVAS
from system.notifications.email_notifier import criar_notificador
from system.core.db import Database

log = get_logger("scheduler")

_scheduler: Optional[BackgroundScheduler] = None


def _tarefa_verificar_opcoes_vencimento():
    try:
        log.info("Iniciando tarefa agendada: verificação de opções próximas do vencimento")

        db = Database(DB_PATH)
        notificador = criar_notificador()
        sucesso = notificador.enviar_notificacao(db)

        if sucesso:
            log.info("✓ Notificação enviada com sucesso")
        else:
            log.warning("⚠ Nenhuma opção próxima ao vencimento ou erro ao enviar")

        db.close()

    except Exception as e:
        log.error("✗ Erro na tarefa agendada: %s", e)
        
    except Exception as e:
        log.error("✗ Erro na tarefa agendada: %s", e)


def iniciar_scheduler():
    """Inicia o background scheduler."""
    global _scheduler
    
    if not EMAIL_NOTIFICACOES_ATIVAS:
        log.info("Notificações por e-mail desativadas (SYSTEM_EMAIL_NOTIF=0)")
        return
    
    if _scheduler is not None:
        log.warning("Scheduler já está em execução")
        return
    
    try:
        _scheduler = BackgroundScheduler()
        
        # Parse da hora (formato: "HH:MM", ex: "09:00")
        partes = SCHEDULER_HORA.split(":")
        hora = int(partes[0]) if len(partes) > 0 else 9
        minuto = int(partes[1]) if len(partes) > 1 else 0
        
        # Registrar tarefa diária
        _scheduler.add_job(
            _tarefa_verificar_opcoes_vencimento,
            CronTrigger(hour=hora, minute=minuto),
            id="verificar_opcoes_vencimento",
            name="Verificar opções próximas do vencimento",
            replace_existing=True,
            misfire_grace_time=30,  # Tolera até 30s de atraso
        )
        
        _scheduler.start()
        log.info("✓ Scheduler iniciado | Tarefa diária agendada para %s", SCHEDULER_HORA)
        
    except Exception as e:
        log.error("✗ Erro ao iniciar scheduler: %s", e)
        raise


def parar_scheduler():
    """Para o background scheduler."""
    global _scheduler
    
    if _scheduler is None:
        log.warning("Scheduler não está em execução")
        return
    
    try:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("✓ Scheduler parado")
    except Exception as e:
        log.error("✗ Erro ao parar scheduler: %s", e)


def obter_scheduler() -> Optional[BackgroundScheduler]:
    """Retorna a instância global do scheduler."""
    return _scheduler
