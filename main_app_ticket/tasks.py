# main_app_ticket/tasks.py
"""
Celery tasks for KSTS escalation engine.
Thin wrappers — all logic lives in escalation_engine.py.

THREE scheduled tasks:
  1. overdue_auto_escalate  — every 15 min — auto-escalates overdue tickets + fires T1
  2. tier2_single           — on demand    — fires T2 for one ticket after delay
  3. tier2_sweep            — every 30 min — safety net for any missed T2
"""
import logging
from celery import shared_task

logger = logging.getLogger("ksts.escalation.tasks")


@shared_task(
    name="ksts.escalation.overdue_sweep",
    acks_late=True,
    max_retries=2,
    default_retry_delay=60,
)
def overdue_auto_escalate_sweep():
    """
    Runs every 15 minutes via Celery Beat.
    Detects tickets that are past their expected_resolution_date
    but not yet escalated, auto-escalates them, and fires Tier-1.
    THIS is the task that fixes the reported bug.
    """
    from .escalation_engine import run_overdue_auto_escalate_sweep
    logger.info("[OVERDUE-SWEEP] Starting overdue auto-escalate sweep")
    count = run_overdue_auto_escalate_sweep()
    logger.info("[OVERDUE-SWEEP] Done — %d tickets auto-escalated", count)
    return count


@shared_task(
    bind=True,
    name="ksts.escalation.tier1",
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_tier1_escalation(self, ticket_id: str,
                           is_auto_escalated: bool = False,
                           overdue_hrs: float = 0.0):
    """
    Send Tier-1 escalation email + Excel to reporting manager(s).
    Called immediately when a ticket is manually escalated via the dashboard.
    (Auto-escalated tickets call dispatch_tier1_for_ticket directly from
    the overdue sweep — this task is the manual-escalation entry point.)
    """
    from .escalation_engine import dispatch_tier1_for_ticket
    try:
        logger.info("[T1] Starting for %s (auto=%s, overdue=%.1f hrs)",
                    ticket_id, is_auto_escalated, overdue_hrs)
        dispatch_tier1_for_ticket(ticket_id,
                                   is_auto_escalated=is_auto_escalated,
                                   overdue_hrs=overdue_hrs)
        logger.info("[T1] Done for %s", ticket_id)
    except Exception as exc:
        logger.error("[T1] Error %s: %s — retry %d/3", ticket_id, exc, self.request.retries)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="ksts.escalation.tier2_single",
    max_retries=3,
    default_retry_delay=600,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_tier2_escalation(self, ticket_id: str,
                           is_auto_escalated: bool = False,
                           overdue_hrs: float = 0.0):
    """
    Send Tier-2 escalation to C.E. for one specific ticket.
    Scheduled by apply_async with countdown=TIER2_DELAY_HOURS*3600.
    Will no-op if ticket was resolved/closed in the meantime.
    """
    from .escalation_engine import dispatch_tier2_for_ticket
    try:
        logger.info("[T2] Starting for %s", ticket_id)
        dispatch_tier2_for_ticket(ticket_id,
                                   is_auto_escalated=is_auto_escalated,
                                   overdue_hrs=overdue_hrs)
        logger.info("[T2] Done for %s", ticket_id)
    except Exception as exc:
        logger.error("[T2] Error %s: %s — retry %d/3", ticket_id, exc, self.request.retries)
        raise self.retry(exc=exc)


@shared_task(
    name="ksts.escalation.tier2_sweep",
    acks_late=True,
)
def tier2_sweep():
    """
    Safety-net sweep (every 30 min).
    Catches escalated+unresolved tickets where T1 was sent
    TIER2_DELAY_HOURS+ ago but T2 hasn't fired yet.
    """
    from .escalation_engine import run_tier2_sweep
    logger.info("[T2-SWEEP] Starting")
    triggered = run_tier2_sweep()
    logger.info("[T2-SWEEP] Done — %d tickets", triggered)
    return triggered