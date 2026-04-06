"""
escalation_monitor.py
=====================
Production-grade two-tier escalation monitor for KSTS ticket system.

Tier-1  → Notify the ticket's reporting manager (manager of `escalated_to`)
          Triggered when a ticket has been in ESCALATED status for
          TIER1_GRACE_HOURS without resolution.

Tier-2  → Notify the C.E. (Chief Executive / top-level user)
          Triggered when a ticket has been in ESCALATED status for
          TIER2_GRACE_HOURS (> TIER1_GRACE_HOURS) without resolution,
          AND a Tier-1 mail was already dispatched.

State is tracked via EscalationNotification rows so re-runs are idempotent.

Usage
-----
    # Called by Django management command / Celery beat / cron
    from escalation_monitor import EscalationMonitor
    EscalationMonitor().run()
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("ksts.escalation")

# ── Grace periods ──────────────────────────────────────────────────────────────
# Override in settings.py:
#   ESCALATION_TIER1_GRACE_HOURS = 4
#   ESCALATION_TIER2_GRACE_HOURS = 24
TIER1_GRACE_HOURS: int = getattr(settings, "ESCALATION_TIER1_GRACE_HOURS", 4)
TIER2_GRACE_HOURS: int = getattr(settings, "ESCALATION_TIER2_GRACE_HOURS", 24)


class EscalationMonitor:
    """
    Stateless monitor — safe to call multiple times (idempotent per ticket).
    """

    def __init__(self):
        # Import here to avoid circular imports at module load time
        from main_app_ticket.models import Ticket, EscalationNotification  # noqa: F401 – aliased below
        self.Ticket = Ticket
        self.EscalationNotification = EscalationNotification

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self) -> dict:
        """
        Scan all ESCALATED tickets and send tier-1 / tier-2 mails as needed.
        Returns a summary dict for logging / admin display.
        """
        now = timezone.now()
        tier1_cutoff = now - timedelta(hours=TIER1_GRACE_HOURS)
        tier2_cutoff = now - timedelta(hours=TIER2_GRACE_HOURS)

        escalated_qs = (
            self.Ticket.objects
            .filter(status=self.Ticket.Status.ESCALATED)
            .select_related(
                "escalated_to",
                "escalated_to__manager",   # reporting manager of assignee
                "farmer", "mpp", "transporter",
                "created_by",
            )
            .prefetch_related("assigned_to")
        )

        summary = {"tier1_sent": 0, "tier2_sent": 0, "skipped": 0, "errors": 0}

        for ticket in escalated_qs:
            try:
                result = self._process_ticket(ticket, tier1_cutoff, tier2_cutoff, now)
                summary[result] = summary.get(result, 0) + 1
            except Exception as exc:
                logger.exception("EscalationMonitor error on %s: %s", ticket.ticket_id, exc)
                summary["errors"] += 1

        logger.info(
            "EscalationMonitor run complete | tier1=%d tier2=%d skipped=%d errors=%d",
            summary["tier1_sent"], summary["tier2_sent"],
            summary["skipped"], summary["errors"],
        )
        return summary

    # ------------------------------------------------------------------
    # Per-ticket logic
    # ------------------------------------------------------------------
    def _process_ticket(self, ticket, tier1_cutoff, tier2_cutoff, now) -> str:
        """
        Returns one of: 'tier1_sent', 'tier2_sent', 'skipped'
        """
        notif = self._get_or_init_notif(ticket)

        escalated_at = ticket.escalated_at or ticket.updated_at

        # ── Tier-2 check (evaluated first so we don't send tier-1 again) ──
        if escalated_at <= tier2_cutoff and notif.tier1_sent_at and not notif.tier2_sent_at:
            ce_email = self._get_ce_email()
            if ce_email:
                self._send_tier2(ticket, notif, ce_email, now)
                return "tier2_sent"

        # ── Tier-1 check ──────────────────────────────────────────────────
        if escalated_at <= tier1_cutoff and not notif.tier1_sent_at:
            manager_email = self._get_manager_email(ticket)
            if manager_email:
                self._send_tier1(ticket, notif, manager_email, now)
                return "tier1_sent"

        return "skipped"

    # ------------------------------------------------------------------
    # Notification state helpers
    # ------------------------------------------------------------------
    def _get_or_init_notif(self, ticket):
        notif, _ = self.EscalationNotification.objects.get_or_create(ticket=ticket)
        return notif

    # ------------------------------------------------------------------
    # Email recipients
    # ------------------------------------------------------------------
    def _get_manager_email(self, ticket) -> Optional[str]:
        """
        Returns email of the *reporting manager* of the person the ticket
        was escalated to.  Falls back to the manager of the first assignee.
        """
        # Primary: manager of escalated_to
        if ticket.escalated_to and ticket.escalated_to.manager:
            mgr = ticket.escalated_to.manager
            if mgr.email:
                return mgr.email

        # Fallback: manager of first assigned employee
        for assignee in ticket.assigned_to.all():
            if assignee.manager and assignee.manager.email:
                return assignee.manager.email

        # Last resort: escalated_to themselves if no manager set
        if ticket.escalated_to and ticket.escalated_to.email:
            logger.warning(
                "Ticket %s: no manager found for escalated_to=%s; "
                "sending tier-1 to escalated_to directly.",
                ticket.ticket_id, ticket.escalated_to.email,
            )
            return ticket.escalated_to.email

        logger.warning("Ticket %s: no tier-1 recipient found.", ticket.ticket_id)
        return None

    def _get_ce_email(self) -> Optional[str]:
        """
        Returns the C.E. email from settings.ESCALATION_CE_EMAIL or the
        first superuser with is_active=True.
        """
        ce_email = getattr(settings, "ESCALATION_CE_EMAIL", None)
        if ce_email:
            return ce_email

        # Auto-discover: first active superuser
        from main_app_ticket.models import CustomUser  # noqa
        su = (
            CustomUser.objects
            .filter(is_superuser=True, is_active=True)
            .order_by("employee_code")
            .first()
        )
        if su and su.email:
            return su.email

        logger.error("No C.E. email configured and no active superuser found.")
        return None

    # ------------------------------------------------------------------
    # Send helpers
    # ------------------------------------------------------------------
    @transaction.atomic
    def _send_tier1(self, ticket, notif, manager_email: str, now) -> None:
        from .escalation_mailer import EscalationMailer  # noqa
        mailer = EscalationMailer()
        mailer.send_tier1(ticket=ticket, recipient_email=manager_email)

        notif.tier1_sent_at = now
        notif.tier1_recipient = manager_email
        notif.save(update_fields=["tier1_sent_at", "tier1_recipient"])

        logger.info(
            "Tier-1 escalation mail sent | ticket=%s → %s",
            ticket.ticket_id, manager_email,
        )

    @transaction.atomic
    def _send_tier2(self, ticket, notif, ce_email: str, now) -> None:
        from .escalation_mailer import EscalationMailer  # noqa
        mailer = EscalationMailer()
        mailer.send_tier2(ticket=ticket, recipient_email=ce_email)

        notif.tier2_sent_at = now
        notif.tier2_recipient = ce_email
        notif.save(update_fields=["tier2_sent_at", "tier2_recipient"])

        logger.info(
            "Tier-2 escalation mail sent | ticket=%s → %s (CE)",
            ticket.ticket_id, ce_email,
        )