"""
management/commands/run_escalation_monitor.py
=============================================
Django management command — invoke via:

    python manage.py run_escalation_monitor

Schedule with cron (every 30 minutes recommended):
    */30 * * * * /path/to/venv/bin/python /path/to/manage.py run_escalation_monitor >> /var/log/ksts_escalation.log 2>&1

Or with Celery beat (celery_config.py example at bottom of this file).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Scans all ESCALATED tickets and dispatches tier-1 (manager) "
        "and tier-2 (C.E.) notification emails with Excel attachments."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate run without sending any emails.",
        )
        parser.add_argument(
            "--ticket",
            type=str,
            default=None,
            help="Run monitor for a single ticket ID only (useful for testing).",
        )

    def handle(self, *args, **options):
        dry_run   = options["dry_run"]
        ticket_id = options.get("ticket")

        self.stdout.write(
            self.style.NOTICE(
                f"\n[{timezone.now():%Y-%m-%d %H:%M:%S}] "
                f"EscalationMonitor starting"
                f"{' (DRY RUN)' if dry_run else ''}"
                f"{f' for ticket {ticket_id}' if ticket_id else ''} …"
            )
        )

        if dry_run:
            self._run_dry(ticket_id)
            return

        from main_app_ticket.escalation_monitor import EscalationMonitor  # noqa
        monitor = EscalationMonitor()

        if ticket_id:
            # Single-ticket mode — useful for manual testing
            try:
                from main_app_ticket.models import Ticket  # noqa
                ticket = Ticket.objects.get(ticket_id=ticket_id)
            except Ticket.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Ticket {ticket_id} not found."))
                return

            if ticket.status != ticket.Status.ESCALATED:
                self.stdout.write(
                    self.style.WARNING(
                        f"Ticket {ticket_id} is not in ESCALATED status "
                        f"(current: {ticket.get_status_display()}). Skipping."
                    )
                )
                return

            from django.utils import timezone as tz
            from datetime import timedelta
            # Force both cutoffs to now so the ticket is always in scope
            summary = {"tier1_sent": 0, "tier2_sent": 0, "skipped": 0, "errors": 0}
            now = tz.now()
            try:
                notif = monitor._get_or_init_notif(ticket)
                mgr_email = monitor._get_manager_email(ticket)
                ce_email  = monitor._get_ce_email()
                if not notif.tier1_sent_at and mgr_email:
                    monitor._send_tier1(ticket, notif, mgr_email, now)
                    summary["tier1_sent"] += 1
                elif not notif.tier2_sent_at and notif.tier1_sent_at and ce_email:
                    monitor._send_tier2(ticket, notif, ce_email, now)
                    summary["tier2_sent"] += 1
                else:
                    summary["skipped"] += 1
            except Exception as exc:
                summary["errors"] += 1
                self.stderr.write(self.style.ERROR(f"Error: {exc}"))
        else:
            summary = monitor.run()

        # Print summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("  ✔ Run complete"))
        self.stdout.write(f"    Tier-1 (manager) mails sent : {summary.get('tier1_sent', 0)}")
        self.stdout.write(f"    Tier-2 (C.E.)    mails sent : {summary.get('tier2_sent', 0)}")
        self.stdout.write(f"    Skipped (already notified)  : {summary.get('skipped', 0)}")
        if summary.get("errors"):
            self.stdout.write(
                self.style.ERROR(f"    Errors                      : {summary['errors']}")
            )
        self.stdout.write("")

    # ── Dry-run ───────────────────────────────────────────────────────────────
    def _run_dry(self, ticket_id=None):
        from main_app_ticket.models import Ticket  # noqa
        from main_app_ticket.escalation_monitor import (  # noqa
            TIER1_GRACE_HOURS, TIER2_GRACE_HOURS,
        )
        from django.utils import timezone as tz
        from datetime import timedelta

        now = tz.now()
        qs = Ticket.objects.filter(status=Ticket.Status.ESCALATED)
        if ticket_id:
            qs = qs.filter(ticket_id=ticket_id)

        self.stdout.write(f"\n  Tier-1 grace: {TIER1_GRACE_HOURS}h | Tier-2 grace: {TIER2_GRACE_HOURS}h\n")
        self.stdout.write(f"  {'Ticket ID':<20} {'Escalated At':<22} {'Hours':<8} {'Action'}")
        self.stdout.write("  " + "─" * 70)

        for ticket in qs.select_related("escalated_to", "escalated_to__manager"):
            try:
                notif = ticket.escalation_notification
            except Exception:
                notif = None

            escalated_at = ticket.escalated_at or ticket.updated_at
            hours = (now - escalated_at).total_seconds() / 3600 if escalated_at else 0

            t1_done = notif.tier1_sent_at if notif else None
            t2_done = notif.tier2_sent_at if notif else None

            if hours >= TIER2_GRACE_HOURS and t1_done and not t2_done:
                action = self.style.ERROR("→ WOULD SEND TIER-2 (C.E.)")
            elif hours >= TIER1_GRACE_HOURS and not t1_done:
                action = self.style.WARNING("→ WOULD SEND TIER-1 (Manager)")
            else:
                action = "  skipped"

            esc_str = escalated_at.strftime("%d %b %Y %H:%M") if escalated_at else "—"
            self.stdout.write(f"  {ticket.ticket_id:<20} {esc_str:<22} {hours:<8.1f} {action}")

        self.stdout.write("")


# ════════════════════════════════════════════════════════════════════════════════
# CELERY BEAT CONFIG EXAMPLE
# Add to your celery.py / celery_config.py
# ════════════════════════════════════════════════════════════════════════════════
#
# from celery.schedules import crontab
#
# app.conf.beat_schedule = {
#     "ksts-escalation-monitor": {
#         "task": "main_app_ticket.tasks.run_escalation_monitor",
#         "schedule": crontab(minute="*/30"),   # every 30 minutes
#     },
# }
#
# And in tasks.py:
#
# from celery import shared_task
# from .escalation_monitor import EscalationMonitor
#
# @shared_task(name="main_app_ticket.tasks.run_escalation_monitor", bind=True, max_retries=3)
# def run_escalation_monitor(self):
#     try:
#         return EscalationMonitor().run()
#     except Exception as exc:
#         raise self.retry(exc=exc, countdown=60)