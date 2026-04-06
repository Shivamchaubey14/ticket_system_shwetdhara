"""
escalation_api_views.py
=======================
Add these two views to api_views.py  (or keep as a separate file and
include in urls.py).

Endpoints:

  POST  /api/escalation/trigger/
        Manually trigger the monitor (staff-only).
        Body (optional JSON): { "ticket_id": "TKT-2026-000042" }
        Returns: { "status": "ok", "summary": {...} }

  GET   /api/escalation/status/
        Returns escalation notification state for all ESCALATED tickets.
        Staff-only.

  POST  /api/tickets/<ticket_id>/escalate/  (already exists — hook shown below)
        Existing view — just ensure it calls `_trigger_immediate_tier1` 
        after saving so the manager gets an instant notification on manual 
        escalation too (optional fast-path, not required).
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger("ksts.escalation_api")


# ── Guard: staff only ─────────────────────────────────────────────────────────
def _staff_required(view_fn):
    """Simple decorator — reuse your project's existing permission pattern."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({"error": "Staff access required."}, status=403)
        return view_fn(request, *args, **kwargs)
    wrapper.__name__ = view_fn.__name__
    return wrapper


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/escalation/trigger/
# ═══════════════════════════════════════════════════════════════════════════════

@_staff_required
@require_http_methods(["POST"])
def escalation_trigger(request):
    """
    Manually run the escalation monitor.
    Optionally scope to a single ticket via JSON body: {"ticket_id": "TKT-…"}
    """
    ticket_id = None
    try:
        body = json.loads(request.body or "{}")
        ticket_id = body.get("ticket_id")
    except (json.JSONDecodeError, AttributeError):
        pass

    from main_app_ticket.escalation_monitor import EscalationMonitor  # noqa
    from main_app_ticket.models import Ticket  # noqa

    monitor = EscalationMonitor()

    if ticket_id:
        try:
            ticket = Ticket.objects.get(ticket_id=ticket_id)
        except Ticket.DoesNotExist:
            return JsonResponse({"error": f"Ticket {ticket_id} not found."}, status=404)

        if ticket.status != Ticket.Status.ESCALATED:
            return JsonResponse(
                {
                    "error": (
                        f"Ticket {ticket_id} is not in ESCALATED status "
                        f"(current: {ticket.get_status_display()})."
                    )
                },
                status=400,
            )

        now = timezone.now()
        summary = {"tier1_sent": 0, "tier2_sent": 0, "skipped": 0, "errors": 0}
        try:
            notif     = monitor._get_or_init_notif(ticket)
            mgr_email = monitor._get_manager_email(ticket)
            ce_email  = monitor._get_ce_email()

            if not notif.tier1_sent_at and mgr_email:
                monitor._send_tier1(ticket, notif, mgr_email, now)
                summary["tier1_sent"] += 1
            elif notif.tier1_sent_at and not notif.tier2_sent_at and ce_email:
                monitor._send_tier2(ticket, notif, ce_email, now)
                summary["tier2_sent"] += 1
            else:
                summary["skipped"] += 1
        except Exception as exc:
            logger.exception("escalation_trigger error for %s: %s", ticket_id, exc)
            summary["errors"] += 1

    else:
        try:
            summary = monitor.run()
        except Exception as exc:
            logger.exception("escalation_trigger full run error: %s", exc)
            return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(
        {
            "status": "ok",
            "triggered_at": timezone.now().isoformat(),
            "scope": ticket_id or "all_escalated",
            "summary": summary,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/escalation/status/
# ═══════════════════════════════════════════════════════════════════════════════

@_staff_required
@require_http_methods(["GET"])
def escalation_status(request):
    """
    Returns the escalation notification state for all ESCALATED tickets.
    Useful for the admin dashboard or a monitoring widget.
    """
    from main_app_ticket.models import Ticket, EscalationNotification  # noqa
    from main_app_ticket.escalation_monitor import TIER1_GRACE_HOURS, TIER2_GRACE_HOURS  # noqa

    now = timezone.now()
    tickets = (
        Ticket.objects
        .filter(status=Ticket.Status.ESCALATED)
        .select_related("escalated_to", "escalated_to__manager")
        .prefetch_related("assigned_to")
        .order_by("-escalated_at")
    )

    rows = []
    for t in tickets:
        try:
            notif = t.escalation_notification
        except Exception:
            notif = None

        escalated_at = t.escalated_at or t.updated_at
        hours_open   = (now - escalated_at).total_seconds() / 3600 if escalated_at else 0

        mgr_name  = "—"
        mgr_email = "—"
        if t.escalated_to and t.escalated_to.manager:
            mgr = t.escalated_to.manager
            mgr_name  = mgr.get_full_name()
            mgr_email = mgr.email

        rows.append(
            {
                "ticket_id":         t.ticket_id,
                "ticket_type":       t.get_ticket_type_display(),
                "priority":          t.priority,
                "caller":            t.caller_display_name,
                "escalated_at":      escalated_at.isoformat() if escalated_at else None,
                "hours_open":        round(hours_open, 1),
                "manager_name":      mgr_name,
                "manager_email":     mgr_email,
                "escalation_reason": t.escalation_reason or "",
                "tier1_sent_at":     notif.tier1_sent_at.isoformat() if notif and notif.tier1_sent_at else None,
                "tier1_recipient":   notif.tier1_recipient if notif else None,
                "tier2_sent_at":     notif.tier2_sent_at.isoformat() if notif and notif.tier2_sent_at else None,
                "tier2_recipient":   notif.tier2_recipient if notif else None,
                "next_action":       _next_action(hours_open, notif, TIER1_GRACE_HOURS, TIER2_GRACE_HOURS),
            }
        )

    return JsonResponse(
        {
            "count":            len(rows),
            "tier1_grace_hours": TIER1_GRACE_HOURS,
            "tier2_grace_hours": TIER2_GRACE_HOURS,
            "tickets":          rows,
        }
    )


def _next_action(hours_open: float, notif, t1: int, t2: int) -> str:
    t1_done = notif.tier1_sent_at if notif else None
    t2_done = notif.tier2_sent_at if notif else None

    if t2_done:
        return "all_notifications_sent"
    if t1_done and hours_open >= t2:
        return "tier2_due_now"
    if t1_done:
        remaining = t2 - hours_open
        return f"tier2_in_{remaining:.1f}h"
    if hours_open >= t1:
        return "tier1_due_now"
    remaining = t1 - hours_open
    return f"tier1_in_{remaining:.1f}h"