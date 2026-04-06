"""
ticket system/ticket_mailer.py
─────────────────────
Centralised email notification service for the ticket system.

Responsibilities:
  - ticket_assigned_notification  : sent to every assignee when a ticket is created / reassigned
  - ticket_status_notification    : sent to assignees on resolve / close / reopen
  - All emails are HTML + plain-text multipart with bilingual content (English + Hindi)
  - Attachments (TicketAttachment rows) are included inline on the creation mail
  - Errors are logged — they never crash the request cycle
"""

import logging
import mimetypes
from email.mime.base import MIMEBase
from email import encoders

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  COLOUR / STYLE TOKENS  (kept in Python so there's a single source of truth)
# ─────────────────────────────────────────────────────────────────────────────
_PRIORITY_COLOUR = {
    "low":      ("#166534", "#dcfce7"),   # text, bg
    "medium":   ("#854d0e", "#fef9c3"),
    "high":     ("#9a3412", "#ffedd5"),
    "critical": ("#991b1b", "#fee2e2"),
}
_STATUS_COLOUR = {
    "open":      ("#1e40af", "#dbeafe"),
    "pending":   ("#854d0e", "#fef9c3"),
    "resolved":  ("#166534", "#dcfce7"),
    "closed":    ("#475569", "#f1f5f9"),
    "escalated": ("#991b1b", "#fee2e2"),
}
_BRAND_DARK   = "#2C3547"
_BRAND_GREEN  = "#2F6B3F"
_BRAND_LIGHT  = "#A3B087"
_BRAND_CREAM  = "#FFF8D4"
_HINDI_COLOR  = "#b8860b"  # Golden brown for Hindi sections


# ─────────────────────────────────────────────────────────────────────────────
#  BILINGUAL TRANSLATION DICTIONARY
# ─────────────────────────────────────────────────────────────────────────────
_TRANSLATIONS = {
    # Email headers and labels
    "ticket_system": {
        "en": "Ticket System — Shwetdhara Dairy",
        "hi": "टिकट प्रणाली — श्वेतधारा डेयरी"
    },
    "ticket_system_short": {
        "en": "Ticket System",
        "hi": "टिकट प्रणाली"
    },
    "new_ticket_assigned": {
        "en": "New Ticket Assigned",
        "hi": "नया टिकट असाइन किया गया"
    },
    "ticket_assigned_to_you": {
        "en": "Hello, a new support ticket has been assigned to you",
        "hi": "नमस्ते, आपको एक नया सहायता टिकट असाइन किया गया है"
    },
    "ticket_details": {
        "en": "Ticket Details",
        "hi": "टिकट विवरण"
    },
    "caller_entity_info": {
        "en": "Caller / Entity Information",
        "hi": "कॉलर / संस्था जानकारी"
    },
    "issue_description": {
        "en": "Issue Description",
        "hi": "समस्या का विवरण"
    },
    "open_dashboard": {
        "en": "Open Ticket Website",
        "hi": "टिकट डैशबोर्ड खोलें"
    },
    "attachments_included": {
        "en": "attachment(s) included with this ticket",
        "hi": "अटैचमेंट इस टिकट के साथ शामिल हैं"
    },
    "ticket_resolved": {
        "en": "Ticket Resolved",
        "hi": "टिकट हल हो गया"
    },
    "ticket_closed": {
        "en": "Ticket Closed",
        "hi": "टिकट बंद हो गया"
    },
    "ticket_reopened": {
        "en": "Ticket Reopened",
        "hi": "टिकट पुनः खोला गया"
    },
    "ticket_escalated": {
        "en": "Ticket Escalated",
        "hi": "टिकट एस्केलेटेड (उच्च स्तर पर भेजा गया)"
    },
    "ticket_pending": {
        "en": "Ticket Pending",
        "hi": "टिकट लंबित है"
    },
    "ticket_updated": {
        "en": "Ticket Updated",
        "hi": "टिकट अपडेट किया गया"
    },
    "status_updated_by": {
        "en": "The following ticket status has been updated by",
        "hi": "निम्नलिखित टिकट की स्थिति द्वारा अपडेट की गई है"
    },
    "status_updated_to": {
        "en": "has been updated to",
        "hi": "अपडेट की गई है"
    },
    "new_status": {
        "en": "New status",
        "hi": "नई स्थिति"
    },
    "updated_at": {
        "en": "Updated at",
        "hi": "अपडेट किया गया"
    },
    "updated_by": {
        "en": "Updated by",
        "hi": "द्वारा अपडेट किया गया"
    },
    "removed_from_ticket": {
        "en": "Ticket Unassigned",
        "hi": "टिकट से हटाया गया"
    },
    "you_have_been_removed": {
        "en": "You have been removed from ticket",
        "hi": "आपको टिकट से हटा दिया गया है"
    },
    "no_further_action": {
        "en": "No further action is required from you",
        "hi": "आपसे किसी और कार्रवाई की आवश्यकता नहीं है"
    },
    "type": {
        "en": "Type",
        "hi": "प्रकार"
    },
    "priority": {
        "en": "Priority",
        "hi": "प्राथमिकता"
    },
    "status": {
        "en": "Status",
        "hi": "स्थिति"
    },
    "created": {
        "en": "Created",
        "hi": "बनाया गया"
    },
    "created_by": {
        "en": "Created by",
        "hi": "द्वारा बनाया गया"
    },
    "assigned_to": {
        "en": "Assigned to",
        "hi": "को असाइन किया गया"
    },
    "expected": {
        "en": "Expected",
        "hi": "अपेक्षित तिथि"
    },
    "entity_type": {
        "en": "Entity type",
        "hi": "संस्था का प्रकार"
    },
    "name": {
        "en": "Name",
        "hi": "नाम"
    },
    "location": {
        "en": "Location",
        "hi": "स्थान"
    },
    "mobile": {
        "en": "Mobile",
        "hi": "मोबाइल नंबर"
    },
    "ticket_id": {
        "en": "Ticket ID",
        "hi": "टिकट आईडी"
    },
    "caller": {
        "en": "Caller",
        "hi": "कॉलर"
    },
    "auto_notification": {
        "en": "This is an automated notification",
        "hi": "यह एक स्वचालित सूचना है"
    },
    "do_not_reply": {
        "en": "Please do not reply to this email. Log in to the dashboard to take action on this ticket.",
        "hi": "कृपया इस ईमेल का उत्तर न दें। इस टिकट पर कार्रवाई करने के लिए डैशबोर्ड में लॉग इन करें।"
    },
    "the_following_ticket": {
        "en": "The following ticket",
        "hi": "निम्नलिखित टिकट"
    },
    "has_been": {
        "en": "has been",
        "hi": "हो गया है"
    },
    "by": {
        "en": "by",
        "hi": "द्वारा"
    },
}


def _t(key: str, lang: str = "en") -> str:
    """Get translation for a key in specified language."""
    translations = _TRANSLATIONS.get(key, {})
    return translations.get(lang, translations.get("en", key))


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _priority_badge(priority: str) -> str:
    txt, bg = _PRIORITY_COLOUR.get(priority.lower(), ("#475569", "#f1f5f9"))
    label = priority.capitalize()
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:20px;'
        f'font-size:12px;font-weight:600;background:{bg};color:{txt}">'
        f'{label}</span>'
    )


def _status_badge(status: str) -> str:
    txt, bg = _STATUS_COLOUR.get(status.lower(), ("#475569", "#f1f5f9"))
    label = status.capitalize()
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:20px;'
        f'font-size:12px;font-weight:600;background:{bg};color:{txt}">'
        f'{label}</span>'
    )


def _info_row_bilingual(label_en: str, label_hi: str, value: str) -> str:
    """Create a table row with bilingual label."""
    return f"""
     <tr>
        <td style="padding:8px 12px;font-size:13px;color:#64748b;white-space:nowrap;width:160px">
            <span lang="en">{label_en}</span><br>
            <span lang="hi" style="font-size:11px;color:#b8860b;">{label_hi}</span>
         </td>
        <td style="padding:8px 12px;font-size:13px;color:#1e293b;font-weight:500">{value or "—"}</td>
     </tr>
    """


def _info_row_single(label: str, value: str) -> str:
    """Single-language info row (for non-bilingual sections)."""
    return f"""
     <tr>
        <td style="padding:8px 12px;font-size:13px;color:#64748b;white-space:nowrap;width:160px">{label}</td>
        <td style="padding:8px 12px;font-size:13px;color:#1e293b;font-weight:500">{value or "—"}</td>
     </tr>
    """


def _base_html_bilingual(title_en: str, title_hi: str, body_html: str) -> str:
    """Wrap body_html in a clean, branded email shell with bilingual header."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title_en}</title>
<style>
  /* Language-specific styles */
  [lang="hi"] {{ font-family: 'Noto Sans Devanagari', 'Segoe UI', Arial, sans-serif; }}
  .bilingual-section {{ margin-bottom: 20px; }}
  .hindi-section {{ border-left: 3px solid #b8860b; background: #fef9e6; padding: 12px 16px; margin-top: 16px; border-radius: 0 8px 8px 0; }}
  .hindi-label {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #b8860b; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }}
  .hindi-text {{ font-size: 14px; color: #5c4500; line-height: 1.6; }}
</style>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0">
    <tr>
        <td align="center">
            <table width="600" cellpadding="0" cellspacing="0"
                   style="background:#ffffff;border-radius:12px;overflow:hidden;
                          box-shadow:0 4px 24px rgba(0,0,0,.08)">

                <!-- HEADER with bilingual title -->
                <tr>
                    <td style="background:{_BRAND_DARK};padding:24px 32px">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td>
                                    <p style="margin:0;font-size:11px;font-weight:600;letter-spacing:.12em;
                                               text-transform:uppercase;color:{_BRAND_LIGHT}">
                                        {_t('ticket_system', 'en')}
                                    </p>
                                    <p style="margin:4px 0 0;font-size:20px;font-weight:700;
                                               color:{_BRAND_CREAM}">
                                        {title_en}
                                    </p>
                                    <p style="margin:2px 0 0;font-size:14px;font-weight:500;
                                               color:{_HINDI_COLOR};font-family:'Noto Sans Devanagari',sans-serif">
                                        {title_hi}
                                    </p>
                                 </td>
                                <td align="right">
                                    <div style="width:44px;height:44px;border-radius:10px;
                                                 background:rgba(163,176,135,.18);
                                                 display:inline-flex;align-items:center;
                                                 justify-content:center;font-size:22px">🎫</div>
                                 </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <!-- BODY -->
                <tr>
                    <td style="padding:28px 32px">{body_html}</td>
                </tr>

                <!-- FOOTER (bilingual) -->
                <tr>
                    <td style="padding:16px 32px 24px;border-top:1px solid #e2e8f0">
                        <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.6">
                            <span lang="en">{_t('auto_notification', 'en')}.</span>
                            <span lang="hi" style="display:block;margin-top:4px;color:#b8860b;">{_t('auto_notification', 'hi')}.</span>
                            <br>
                            <span lang="en">{_t('do_not_reply', 'en')}</span>
                            <span lang="hi" style="display:block;margin-top:4px;font-size:11px;">{_t('do_not_reply', 'hi')}</span>
                        </p>
                    </td>
                </tr>

            </table>
            <p style="margin:16px 0 0;font-size:11px;color:#94a3b8">
                © {timezone.now().year} Shwetdhara Dairy Producer Company Limited
            </p>
        </td>
    </tr>
</table>
</body>
</html>"""


def _base_plain_bilingual(title: str, lines: list) -> str:
    """Create plain-text bilingual version."""
    header = (
        f"{'='*60}\n"
        f"{_t('ticket_system', 'en')} — {title}\n"
        f"{_t('ticket_system', 'hi')}\n"
        f"{'='*60}\n\n"
    )
    footer = (
        f"\n{'─'*60}\n"
        f"{_t('auto_notification', 'en')}. {_t('do_not_reply', 'en')}\n"
        f"{_t('auto_notification', 'hi')}. {_t('do_not_reply', 'hi')}\n"
        f"{'─'*60}"
    )
    return header + "\n".join(lines) + footer


def _safe_send(msg: EmailMultiAlternatives, context: str = "") -> bool:
    """Send an email; log and swallow any exception so the caller never crashes."""
    try:
        msg.send(fail_silently=False)
        logger.info("[Ticket mail] Sent '%s' → %s  [%s]",
                    msg.subject, msg.to, context)
        return True
    except Exception as exc:
        logger.error("[Ticket System mail] FAILED '%s' → %s  [%s]: %s",
                     msg.subject, msg.to, context, exc, exc_info=True)
        return False


def _attach_ticket_files(msg: EmailMultiAlternatives, ticket) -> int:
    """Attach every TicketAttachment row that belongs to ticket to the email."""
    count = 0
    try:
        for att in ticket.attachments.all():
            try:
                if not att.file:
                    continue
                file_data = att.file.read()
                mime = att.mime_type or mimetypes.guess_type(att.file_name)[0] or "application/octet-stream"
                main_type, sub_type = mime.split("/", 1)
                part = MIMEBase(main_type, sub_type)
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=att.file_name,
                )
                msg.attach(part)
                count += 1
                att.file.seek(0)
            except Exception as e:
                logger.warning("[Ticket System mail] Could not attach file '%s': %s",
                               att.file_name, e)
    except Exception as e:
        logger.warning("[Ticket System mail] Error iterating attachments: %s", e)
    return count


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def ticket_assigned_notification(ticket, assignees, created_by=None, include_attachments=True):
    """
    Send a bilingual 'ticket assigned to you' email to every user in assignees.
    """
    if not assignees:
        return

    # Build shared content once
    priority = ticket.priority or "medium"
    status = ticket.status or "open"
    creator = created_by.get_full_name() if created_by else "System"
    ticket_url = getattr(settings, "SITE_URL", "").rstrip("/")

    # Caller / entity info
    entity_label_en = ticket.entity_type.capitalize() if ticket.entity_type else "—"
    entity_label_hi = {
        "farmer": "किसान",
        "sahayak": "सहायक",
        "transporter": "ट्रांसपोर्टर",
        "other": "अन्य"
    }.get(ticket.entity_type, ticket.entity_type or "—")
    
    caller_name = ticket.caller_display_name or "—"
    caller_loc = ticket.caller_location or "—"
    caller_mob = ticket.caller_contact_mobile or "—"

    # Description snippet (200 chars)
    desc_snippet = ""
    if ticket.description_en:
        desc_snippet = ticket.description_en[:200]
        if len(ticket.description_en) > 200:
            desc_snippet += "…"

    # Assignee names for summary line
    all_assignee_names = ", ".join(u.get_full_name() for u in assignees)

    # Attachment count
    try:
        att_count = ticket.attachments.count()
    except Exception:
        att_count = 0

    # Subject (English only for email subject line)
    subject = f"[Ticket System] New Ticket Assigned — {ticket.ticket_id} ({ticket.ticket_type})"

    # HTML body with bilingual content
    att_note_html = ""
    if att_count:
        att_note_html = f"""
        <p style="margin:0 0 6px;font-size:13px;color:#64748b">
            <span lang="en"><strong>{att_count} {_t('attachments_included', 'en')}</strong></span>
            <span lang="hi" style="display:block;font-size:12px;"><strong>{att_count} {_t('attachments_included', 'hi')}</strong></span>
        </p>
        """

    desc_html = ""
    if desc_snippet:
        desc_html = f"""
        <div style="margin-top:16px;padding:14px 16px;background:#f8fafc;
                    border-left:4px solid {_BRAND_GREEN};border-radius:0 8px 8px 0">
            <p style="margin:0 0 4px;font-size:11px;font-weight:700;
                       text-transform:uppercase;letter-spacing:.08em;color:#64748b">
                <span lang="en">{_t('issue_description', 'en')}</span>
                <span lang="hi" style="margin-left:8px;">{_t('issue_description', 'hi')}</span>
            </p>
            <p style="margin:0;font-size:13px;color:#334155;line-height:1.6">{desc_snippet}</p>
        </div>
        """

    body_html = f"""
    <p style="margin:0 0 20px;font-size:15px;color:#334155;line-height:1.6">
        <span lang="en">{_t('ticket_assigned_to_you', 'en')}</span>
        <span lang="hi" style="display:block;margin-top:4px;font-size:14px;">{_t('ticket_assigned_to_you', 'hi')}</span>
    </p>

    <!-- Ticket Summary Card -->
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin-bottom:20px">
        <div style="background:{_BRAND_DARK};padding:12px 18px">
            <p style="margin:0;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{_BRAND_LIGHT}">
                <span lang="en">{_t('ticket_details', 'en')}</span>
                <span lang="hi" style="margin-left:8px;">{_t('ticket_details', 'hi')}</span>
            </p>
            <p style="margin:4px 0 0;font-size:18px;font-weight:700;color:{_BRAND_CREAM};font-family:monospace">{ticket.ticket_id}</p>
        </div>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
            {_info_row_bilingual(_t('type', 'en'), _t('type', 'hi'), ticket.ticket_type)}
            {_info_row_bilingual(_t('priority', 'en'), _t('priority', 'hi'), _priority_badge(priority))}
            {_info_row_bilingual(_t('status', 'en'), _t('status', 'hi'), _status_badge(status))}
            {_info_row_bilingual(_t('created', 'en'), _t('created', 'hi'), ticket.created_at.strftime("%d %b %Y, %I:%M %p"))}
            {_info_row_bilingual(_t('created_by', 'en'), _t('created_by', 'hi'), creator)}
            {_info_row_bilingual(_t('assigned_to', 'en'), _t('assigned_to', 'hi'), all_assignee_names)}
            {_info_row_bilingual(_t('expected', 'en'), _t('expected', 'hi'), str(ticket.expected_resolution_date) if ticket.expected_resolution_date else "—")}
        </table>
    </div>

    <!-- Caller / Entity Card (bilingual) -->
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin-bottom:20px">
        <div style="padding:10px 18px;background:rgba(47,107,63,.08);border-bottom:1px solid #e2e8f0">
            <p style="margin:0;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{_BRAND_GREEN}">
                <span lang="en">{_t('caller_entity_info', 'en')}</span>
                <span lang="hi" style="margin-left:8px;">{_t('caller_entity_info', 'hi')}</span>
            </p>
        </div>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
            <tr>
                <td style="padding:8px 12px;font-size:13px;color:#64748b;width:160px">
                    <span lang="en">{_t('entity_type', 'en')}</span><br>
                    <span lang="hi" style="font-size:11px;color:#b8860b;">{_t('entity_type', 'hi')}</span>
                </td>
                <td style="padding:8px 12px;font-size:13px;color:#1e293b">
                    <span lang="en">{entity_label_en}</span><br>
                    <span lang="hi" style="font-size:12px;color:#b8860b;">{entity_label_hi}</span>
                </td>
            </tr>
            {_info_row_bilingual(_t('name', 'en'), _t('name', 'hi'), caller_name)}
            {_info_row_bilingual(_t('location', 'en'), _t('location', 'hi'), caller_loc)}
            {_info_row_bilingual(_t('mobile', 'en'), _t('mobile', 'hi'), caller_mob)}
        </table>
    </div>

    {att_note_html}
    {desc_html}

    <div style="margin-top:24px;text-align:center">
        <a href="{ticket_url}/"
           style="display:inline-block;padding:12px 28px;background:{_BRAND_DARK};
                  color:#fff;font-size:14px;font-weight:600;text-decoration:none;
                  border-radius:8px;letter-spacing:.02em">
            🎫 <span lang="en">{_t('open_dashboard', 'en')}</span>
            <span lang="hi" style="display:none;">{_t('open_dashboard', 'hi')}</span>
        </a>
    </div>
    """

    # Plain-text bilingual version
    plain_lines = [
        f"{_t('ticket_assigned_to_you', 'en')}",
        f"{_t('ticket_assigned_to_you', 'hi')}",
        "",
        f"{_t('ticket_id', 'en')} / {_t('ticket_id', 'hi')} : {ticket.ticket_id}",
        f"{_t('type', 'en')} / {_t('type', 'hi')} : {ticket.ticket_type}",
        f"{_t('priority', 'en')} / {_t('priority', 'hi')} : {priority.upper()}",
        f"{_t('status', 'en')} / {_t('status', 'hi')} : {status.upper()}",
        f"{_t('created', 'en')} / {_t('created', 'hi')} : {ticket.created_at.strftime('%d %b %Y, %I:%M %p')}",
        f"{_t('created_by', 'en')} / {_t('created_by', 'hi')} : {creator}",
        f"{_t('assigned_to', 'en')} / {_t('assigned_to', 'hi')} : {all_assignee_names}",
        f"{_t('expected', 'en')} / {_t('expected', 'hi')} : {ticket.expected_resolution_date or 'Not set'}",
        "",
        f"{_t('caller_entity_info', 'en')} / {_t('caller_entity_info', 'hi')}",
        f"  {_t('entity_type', 'en')}/{_t('entity_type', 'hi')} : {entity_label_en} / {entity_label_hi}",
        f"  {_t('name', 'en')}/{_t('name', 'hi')} : {caller_name}",
        f"  {_t('location', 'en')}/{_t('location', 'hi')} : {caller_loc}",
        f"  {_t('mobile', 'en')}/{_t('mobile', 'hi')} : {caller_mob}",
    ]
    if desc_snippet:
        plain_lines += ["", f"{_t('issue_description', 'en')} / {_t('issue_description', 'hi')}", f"  {desc_snippet}"]
    if att_count:
        plain_lines += ["", f"{att_count} {_t('attachments_included', 'en')} / {_t('attachments_included', 'hi')}"]
    if ticket_url:
        plain_lines += ["", f"{_t('open_dashboard', 'en')} / {_t('open_dashboard', 'hi')} : {ticket_url}/"]

    # Send one email per assignee
    from_email = settings.DEFAULT_FROM_EMAIL

    for user in assignees:
        if not user.email:
            logger.warning("[Ticket System mail] Assignee %s has no email — skipping",
                           user.get_full_name())
            continue

        # Personalise greeting
        personal_html = body_html.replace(
            '<span lang="en">Hello, a new support ticket has been assigned to you</span>',
            f'<span lang="en">Hello {user.get_full_name() or user.email}, a new support ticket has been assigned to you</span>'
        )

        msg = EmailMultiAlternatives(
            subject=subject,
            body=_base_plain_bilingual(f"{_t('new_ticket_assigned', 'en')} — {ticket.ticket_id}", plain_lines),
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(
            _base_html_bilingual(
                f"{_t('new_ticket_assigned', 'en')}: {ticket.ticket_id}",
                f"{_t('new_ticket_assigned', 'hi')}: {ticket.ticket_id}",
                personal_html
            ),
            "text/html",
        )

        if include_attachments and att_count:
            _attach_ticket_files(msg, ticket)

        _safe_send(msg, context=f"{ticket.ticket_id} → {user.email}")


def ticket_status_notification(ticket, action: str, performed_by=None):
    """
    Notify all current assignees of a status change with bilingual content.
    
    Args:
        ticket: Ticket object
        action: 'resolved', 'closed', 'reopened', 'escalated', 'pending', etc.
        performed_by: User who performed the action
    """
    try:
        assignees = list(ticket.assigned_to.all())
    except Exception:
        assignees = []

    if not assignees:
        return

    actor = performed_by.get_full_name() if performed_by else "System"
    priority = ticket.priority or "medium"
    # Use the actual status from the ticket, not the action
    current_status = ticket.status or action
    ticket_url = getattr(settings, "SITE_URL", "").rstrip("/")

    # Define action mappings with proper icons, titles, and verbs
    action_mappings = {
        "resolved": {
            "icon": "✅",
            "title_en": _t('ticket_resolved', 'en'),
            "title_hi": _t('ticket_resolved', 'hi'),
            "verb_en": "has been resolved",
            "verb_hi": "हल कर दिया गया है",
            "email_action": "Resolved"
        },
        "closed": {
            "icon": "🔒",
            "title_en": _t('ticket_closed', 'en'),
            "title_hi": _t('ticket_closed', 'hi'),
            "verb_en": "has been closed",
            "verb_hi": "बंद कर दिया गया है",
            "email_action": "Closed"
        },
        "reopened": {
            "icon": "🔄",
            "title_en": _t('ticket_reopened', 'en'),
            "title_hi": _t('ticket_reopened', 'hi'),
            "verb_en": "has been reopened",
            "verb_hi": "पुनः खोल दिया गया है",
            "email_action": "Reopened"
        },
        "escalated": {
            "icon": "🔥",
            "title_en": _t('ticket_escalated', 'en'),
            "title_hi": _t('ticket_escalated', 'hi'),
            "verb_en": "has been escalated",
            "verb_hi": "एस्केलेटेड कर दिया गया है",
            "email_action": "Escalated"
        },
        "pending": {
            "icon": "⏳",
            "title_en": _t('ticket_pending', 'en'),
            "title_hi": _t('ticket_pending', 'hi'),
            "verb_en": "has been marked as pending",
            "verb_hi": "लंबित कर दिया गया है",
            "email_action": "Pending"
        },
    }
    
    # Default mapping for unknown actions
    default_mapping = {
        "icon": "📋",
        "title_en": _t('ticket_updated', 'en'),
        "title_hi": _t('ticket_updated', 'hi'),
        "verb_en": "has been updated",
        "verb_hi": "अपडेट कर दिया गया है",
        "email_action": "Updated"
    }
    
    mapping = action_mappings.get(action.lower(), default_mapping)
    icon = mapping["icon"]
    title_en = mapping["title_en"]
    title_hi = mapping["title_hi"]
    verb_en = mapping["verb_en"]
    verb_hi = mapping["verb_hi"]
    email_action = mapping["email_action"]

    # Create subject based on actual status
    subject = f"[Ticket System] {title_en} — {ticket.ticket_id} ({ticket.ticket_type})"

    # Build HTML body
    body_html = f"""
    <p style="margin:0 0 20px;font-size:15px;color:#334155;line-height:1.6">
        <span lang="en">{_t('the_following_ticket', 'en')} <strong>{verb_en}</strong> {_t('by', 'en')} <strong>{actor}</strong>.</span>
        <span lang="hi" style="display:block;margin-top:4px;">{_t('the_following_ticket', 'hi')} <strong>{verb_hi}</strong> {_t('by', 'hi')} <strong>{actor}</strong>.</span>
    </p>

    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin-bottom:20px">
        <div style="background:{_BRAND_DARK};padding:12px 18px">
            <p style="margin:0;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{_BRAND_LIGHT}">
                <span lang="en">{_t('ticket_details', 'en')}</span>
                <span lang="hi" style="margin-left:8px;">{_t('ticket_details', 'hi')}</span>
            </p>
            <p style="margin:4px 0 0;font-size:18px;font-weight:700;color:{_BRAND_CREAM};font-family:monospace">{ticket.ticket_id}</p>
        </div>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
            {_info_row_bilingual(_t('type', 'en'), _t('type', 'hi'), ticket.ticket_type)}
            {_info_row_bilingual(_t('priority', 'en'), _t('priority', 'hi'), _priority_badge(priority))}
            {_info_row_bilingual(_t('new_status', 'en'), _t('new_status', 'hi'), _status_badge(current_status))}
            {_info_row_bilingual(_t('updated_at', 'en'), _t('updated_at', 'hi'), timezone.now().strftime("%d %b %Y, %I:%M %p"))}
            {_info_row_bilingual(_t('updated_by', 'en'), _t('updated_by', 'hi'), actor)}
            {_info_row_bilingual(_t('caller', 'en'), _t('caller', 'hi'), ticket.caller_display_name or "—")}
            {_info_row_bilingual(_t('location', 'en'), _t('location', 'hi'), ticket.caller_location or "—")}
         </table>
    </div>

    <div style="margin-top:24px;text-align:center">
        <a href="{ticket_url}/"
           style="display:inline-block;padding:12px 28px;background:{_BRAND_DARK};
                  color:#fff;font-size:14px;font-weight:600;text-decoration:none;
                  border-radius:8px">
            {icon} <span lang="en">{_t('open_dashboard', 'en')}</span>
            <span lang="hi" style="display:none;">{_t('open_dashboard', 'hi')}</span>
        </a>
    </div>
    """

    # Plain text version
    plain_lines = [
        f"{title_en} / {title_hi}",
        "",
        f"{_t('the_following_ticket', 'en')} {verb_en} {_t('by', 'en')} {actor}",
        f"{_t('the_following_ticket', 'hi')} {verb_hi} {_t('by', 'hi')} {actor}",
        "",
        f"{_t('ticket_id', 'en')} / {_t('ticket_id', 'hi')} : {ticket.ticket_id}",
        f"{_t('type', 'en')} / {_t('type', 'hi')} : {ticket.ticket_type}",
        f"{_t('priority', 'en')} / {_t('priority', 'hi')} : {priority.upper()}",
        f"{_t('new_status', 'en')} / {_t('new_status', 'hi')} : {current_status.upper()}",
        f"{_t('updated_at', 'en')} / {_t('updated_at', 'hi')} : {timezone.now().strftime('%d %b %Y, %I:%M %p')}",
        f"{_t('updated_by', 'en')} / {_t('updated_by', 'hi')} : {actor}",
        f"{_t('caller', 'en')} / {_t('caller', 'hi')} : {ticket.caller_display_name or '—'}",
        f"{_t('location', 'en')} / {_t('location', 'hi')} : {ticket.caller_location or '—'}",
    ]
    
    if ticket_url:
        plain_lines += ["", f"{_t('open_dashboard', 'en')} / {_t('open_dashboard', 'hi')} : {ticket_url}/"]

    from_email = settings.DEFAULT_FROM_EMAIL

    # Send email to each assignee
    for user in assignees:
        if not user.email:
            continue

        # Personalize greeting
        personalized_html = body_html.replace(
            '<p style="margin:0 0 20px;font-size:15px;color:#334155;line-height:1.6">',
            f'<p style="margin:0 0 20px;font-size:15px;color:#334155;line-height:1.6">Hello {user.get_full_name() or user.email},<br><br>'
        )

        msg = EmailMultiAlternatives(
            subject=subject,
            body=_base_plain_bilingual(f"{title_en} — {ticket.ticket_id}", plain_lines),
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(
            _base_html_bilingual(
                f"{icon} {title_en}: {ticket.ticket_id}",
                f"{title_hi}: {ticket.ticket_id}",
                personalized_html
            ),
            "text/html",
        )
        _safe_send(msg, context=f"{ticket.ticket_id} → {user.email} [{email_action}]")


def ticket_reassign_notification(ticket, new_assignees, old_assignees=None, reassigned_by=None):
    """
    Notify newly added assignees that a ticket was reassigned to them.
    Optionally notify removed assignees that they are no longer on the ticket.
    Bilingual version.
    """
    # Notify new assignees
    if new_assignees:
        ticket_assigned_notification(
            ticket,
            assignees=new_assignees,
            created_by=reassigned_by,
            include_attachments=False,
        )

    # Notify removed assignees (bilingual)
    if old_assignees:
        actor = reassigned_by.get_full_name() if reassigned_by else "System"
        ticket_url = getattr(settings, "SITE_URL", "").rstrip("/")
        subject = f"[Ticket System] {_t('removed_from_ticket', 'en')} — {ticket.ticket_id}"

        body_html = f"""
        <p style="margin:0 0 16px;font-size:15px;color:#334155">
            <span lang="en">{_t('you_have_been_removed', 'en')} <strong>{ticket.ticket_id}</strong> by {actor}. {_t('no_further_action', 'en')}</span>
            <span lang="hi" style="display:block;margin-top:8px;">{_t('you_have_been_removed', 'hi')} <strong>{ticket.ticket_id}</strong> {actor} द्वारा। {_t('no_further_action', 'hi')}</span>
        </p>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin-bottom:20px">
            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
                {_info_row_bilingual(_t('ticket_id', 'en'), _t('ticket_id', 'hi'), ticket.ticket_id)}
                {_info_row_bilingual(_t('type', 'en'), _t('type', 'hi'), ticket.ticket_type)}
                {_info_row_bilingual(_t('caller', 'en'), _t('caller', 'hi'), ticket.caller_display_name or "—")}
              </table>
        </div>
        """

        plain_lines = [
            f"{_t('you_have_been_removed', 'en')} / {_t('you_have_been_removed', 'hi')}",
            f"{_t('ticket_id', 'en')} / {_t('ticket_id', 'hi')} : {ticket.ticket_id}",
            f"{_t('type', 'en')} / {_t('type', 'hi')} : {ticket.ticket_type}",
            f"{_t('caller', 'en')} / {_t('caller', 'hi')} : {ticket.caller_display_name or '—'}",
        ]

        from_email = settings.DEFAULT_FROM_EMAIL
        for user in old_assignees:
            if not user.email:
                continue
            msg = EmailMultiAlternatives(
                subject=subject,
                body=_base_plain_bilingual(f"{_t('removed_from_ticket', 'en')} — {ticket.ticket_id}", plain_lines),
                from_email=from_email,
                to=[user.email],
            )
            msg.attach_alternative(
                _base_html_bilingual(
                    f"{_t('removed_from_ticket', 'en')}: {ticket.ticket_id}",
                    f"{_t('removed_from_ticket', 'hi')}: {ticket.ticket_id}",
                    body_html
                ),
                "text/html",
            )
            _safe_send(msg, context=f"{ticket.ticket_id} unassign → {user.email}")
            
# ─────────────────────────────────────────────────────────────────────────────
#  ESCALATION NOTIFICATION
#  Sent to: all assignees + their reporting managers
# ─────────────────────────────────────────────────────────────────────────────

def ticket_escalation_notification(ticket, escalated_by=None, reason=""):
    """
    Send escalation alert to:
      1. All current assignees
      2. The reporting manager of each assignee (de-duplicated)
    """
    try:
        assignees = list(ticket.assigned_to.all())
    except Exception:
        assignees = []

    # Collect managers — de-duplicated, skip None, skip managers who are
    # already assignees (they'll get the assignee copy)
    assignee_pks = {u.pk for u in assignees}
    managers = []
    seen_manager_pks = set()
    for user in assignees:
        mgr = getattr(user, "manager", None)
        if mgr and mgr.pk not in seen_manager_pks and mgr.pk not in assignee_pks:
            managers.append(mgr)
            seen_manager_pks.add(mgr.pk)

    if not assignees and not managers:
        logger.warning(
            "[Ticket mail] Escalation: no recipients for %s", ticket.ticket_id
        )
        return

    actor      = escalated_by.get_full_name() if escalated_by else "System"
    priority   = ticket.priority or "critical"
    ticket_url = getattr(settings, "SITE_URL", "").rstrip("/")
    from_email = settings.DEFAULT_FROM_EMAIL

    subject = (
        f"[URGENT — Ticket Escalated] {ticket.ticket_id} "
        f"({ticket.ticket_type}) — Immediate Attention Required"
    )

    # Shared HTML block
    reason_html = ""
    if reason:
        reason_html = f"""
        <div style="margin:16px 0;padding:14px 16px;background:#fff3cd;
                    border-left:4px solid #e6a817;border-radius:0 8px 8px 0">
            <p style="margin:0 0 4px;font-size:11px;font-weight:700;
                       text-transform:uppercase;letter-spacing:.08em;color:#856404">
                Escalation Reason / एस्केलेशन का कारण
            </p>
            <p style="margin:0;font-size:13px;color:#533f03;line-height:1.6">{reason}</p>
        </div>
        """

    def _build_body(recipient_name, role_note):
        return f"""
        <!-- URGENT BANNER -->
        <div style="background:#991b1b;border-radius:8px;padding:12px 18px;
                    margin-bottom:20px;display:flex;align-items:center;gap:10px">
            <span style="font-size:22px">🔥</span>
            <div>
                <p style="margin:0;font-size:13px;font-weight:700;color:#fecaca;
                           text-transform:uppercase;letter-spacing:.08em">
                    Urgent Escalation Alert — तत्काल एस्केलेशन सूचना
                </p>
                <p style="margin:2px 0 0;font-size:12px;color:#fca5a5">{role_note}</p>
            </div>
        </div>

        <p style="margin:0 0 16px;font-size:15px;color:#334155;line-height:1.6">
            Hello <strong>{recipient_name}</strong>,<br><br>
            <span lang="en">
                Ticket <strong>{ticket.ticket_id}</strong> has been
                <strong style="color:#991b1b">escalated</strong> by
                <strong>{actor}</strong> and requires immediate attention.
            </span><br>
            <span lang="hi" style="font-size:14px;color:#b8860b">
                टिकट <strong>{ticket.ticket_id}</strong> को
                <strong style="color:#991b1b">एस्केलेट</strong> किया गया है।
                इस पर तत्काल ध्यान देना आवश्यक है।
            </span>
        </p>

        <!-- Ticket Detail Card -->
        <div style="background:#f8fafc;border:1px solid #e2e8f0;
                    border-radius:10px;overflow:hidden;margin-bottom:16px">
            <div style="background:#2C3547;padding:12px 18px">
                <p style="margin:0;font-size:11px;font-weight:700;letter-spacing:.1em;
                           text-transform:uppercase;color:#A3B087">
                    Ticket Details / टिकट विवरण
                </p>
                <p style="margin:4px 0 0;font-size:18px;font-weight:700;
                           color:#FFF8D4;font-family:monospace">{ticket.ticket_id}</p>
            </div>
            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
                {_info_row_bilingual('Type', 'प्रकार', ticket.ticket_type)}
                {_info_row_bilingual('Priority', 'प्राथमिकता', _priority_badge(priority))}
                {_info_row_bilingual('Status', 'स्थिति', _status_badge('escalated'))}
                {_info_row_bilingual('Escalated by', 'द्वारा एस्केलेट', actor)}
                {_info_row_bilingual('Caller', 'कॉलर', ticket.caller_display_name or '—')}
                {_info_row_bilingual('Location', 'स्थान', ticket.caller_location or '—')}
                {_info_row_bilingual('Mobile', 'मोबाइल', ticket.caller_contact_mobile or '—')}
                {_info_row_bilingual('Created', 'बनाया गया', ticket.created_at.strftime('%d %b %Y, %I:%M %p'))}
                {_info_row_bilingual('Expected', 'अपेक्षित तिथि', str(ticket.expected_resolution_date) if ticket.expected_resolution_date else '—')}
            </table>
        </div>

        {reason_html}

        <div style="margin-top:24px;text-align:center">
            <a href="{ticket_url}/"
               style="display:inline-block;padding:12px 28px;
                      background:#991b1b;color:#fff;font-size:14px;
                      font-weight:600;text-decoration:none;border-radius:8px">
                🔥 Open Ticket Dashboard / डैशबोर्ड खोलें
            </a>
        </div>
        """

    plain_lines_base = [
        "⚠️  URGENT ESCALATION ALERT / तत्काल एस्केलेशन सूचना",
        "",
        f"Ticket {ticket.ticket_id} has been ESCALATED by {actor}.",
        f"टिकट {ticket.ticket_id} को {actor} द्वारा एस्केलेट किया गया है।",
        "",
        f"Type / प्रकार           : {ticket.ticket_type}",
        f"Priority / प्राथमिकता   : {priority.upper()}",
        f"Caller / कॉलर           : {ticket.caller_display_name or '—'}",
        f"Location / स्थान        : {ticket.caller_location or '—'}",
        f"Mobile / मोबाइल         : {ticket.caller_contact_mobile or '—'}",
    ]
    if reason:
        plain_lines_base += [
            "",
            f"Escalation Reason / एस्केलेशन का कारण: {reason}",
        ]
    if ticket_url:
        plain_lines_base += ["", f"Dashboard: {ticket_url}/"]

    # ── Send to assignees ────────────────────────────────────────────────
    for user in assignees:
        if not user.email:
            continue
        role_note = "You are assigned to this ticket — immediate action required."
        msg = EmailMultiAlternatives(
            subject=subject,
            body=_base_plain_bilingual(
                f"🔥 Ticket Escalated: {ticket.ticket_id}", plain_lines_base
            ),
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(
            _base_html_bilingual(
                f"🔥 Ticket Escalated: {ticket.ticket_id}",
                f"टिकट एस्केलेटेड: {ticket.ticket_id}",
                _build_body(user.get_full_name() or user.email, role_note),
            ),
            "text/html",
        )
        _safe_send(msg, context=f"{ticket.ticket_id} escalation → assignee {user.email}")

    # ── Send to managers ─────────────────────────────────────────────────
    for mgr in managers:
        if not mgr.email:
            continue
        # Find which of their subordinates is assigned
        subordinate_names = ", ".join(
            u.get_full_name()
            for u in assignees
            if getattr(u, "manager", None) and u.manager.pk == mgr.pk
        )
        role_note = (
            f"Your team member(s) <strong>{subordinate_names}</strong> "
            f"are assigned to this escalated ticket."
        )
        role_note_plain = (
            f"Your team member(s) {subordinate_names} are assigned to this escalated ticket."
        )

        plain_lines_mgr = plain_lines_base + [
            "",
            f"Assigned team member(s): {subordinate_names}",
        ]

        msg = EmailMultiAlternatives(
            subject=f"[Manager Alert] {subject}",
            body=_base_plain_bilingual(
                f"🔥 Escalation Manager Alert: {ticket.ticket_id}",
                plain_lines_mgr,
            ),
            from_email=from_email,
            to=[mgr.email],
        )
        msg.attach_alternative(
            _base_html_bilingual(
                f"🔥 Escalation Alert: {ticket.ticket_id}",
                f"एस्केलेशन अलर्ट: {ticket.ticket_id}",
                _build_body(mgr.get_full_name() or mgr.email, role_note),
            ),
            "text/html",
        )
        _safe_send(
            msg,
            context=f"{ticket.ticket_id} escalation → manager {mgr.email}",
        )


# ─────────────────────────────────────────────────────────────────────────────
#  MANAGER AREA ALERT  —  sent when a new ticket is created
#  Sent to: the reporting manager(s) of the assigned employee(s)
# ─────────────────────────────────────────────────────────────────────────────

def ticket_manager_area_alert(ticket, assignees, created_by=None):
    """
    Notify each unique manager that a new ticket has been raised in their
    team's area.  One consolidated email per manager covering all their
    subordinates who were assigned.

    Called from ticket_create() after assignment is saved.
    """
    if not assignees:
        return

    # Build manager → [subordinates] map
    manager_map = {}   # {manager_pk: {"manager": user, "subordinates": [...]}}
    for user in assignees:
        mgr = getattr(user, "manager", None)
        if not mgr:
            continue
        if mgr.pk not in manager_map:
            manager_map[mgr.pk] = {"manager": mgr, "subordinates": []}
        manager_map[mgr.pk]["subordinates"].append(user)

    if not manager_map:
        logger.info(
            "[Ticket mail] Manager area alert: no managers found for %s",
            ticket.ticket_id,
        )
        return

    creator    = created_by.get_full_name() if created_by else "System"
    priority   = ticket.priority or "medium"
    ticket_url = getattr(settings, "SITE_URL", "").rstrip("/")
    from_email = settings.DEFAULT_FROM_EMAIL

    subject = (
        f"[Ticket Alert — Your Team's Area] {ticket.ticket_id} "
        f"| {ticket.ticket_type} | {priority.capitalize()} Priority"
    )

    # Description snippet
    desc_snippet = ""
    if ticket.description_en:
        desc_snippet = ticket.description_en[:200]
        if len(ticket.description_en) > 200:
            desc_snippet += "…"

    for entry in manager_map.values():
        mgr         = entry["manager"]
        subordinates = entry["subordinates"]
        if not mgr.email:
            continue

        sub_names   = ", ".join(u.get_full_name() for u in subordinates)
        sub_dept    = subordinates[0].department if subordinates else ""

        desc_html = ""
        if desc_snippet:
            desc_html = f"""
            <div style="margin:14px 0;padding:14px 16px;background:#f0fdf4;
                        border-left:4px solid #2F6B3F;border-radius:0 8px 8px 0">
                <p style="margin:0 0 4px;font-size:11px;font-weight:700;
                           text-transform:uppercase;letter-spacing:.08em;color:#166534">
                    Issue Description / समस्या विवरण
                </p>
                <p style="margin:0;font-size:13px;color:#14532d;line-height:1.6">
                    {desc_snippet}
                </p>
            </div>
            """

        body_html = f"""
        <!-- AREA ALERT BANNER -->
        <div style="background:linear-gradient(135deg,#1e2330,#2d3447);
                    border-radius:8px;padding:14px 18px;margin-bottom:20px">
            <p style="margin:0;font-size:12px;font-weight:700;color:#A3B087;
                       text-transform:uppercase;letter-spacing:.1em">
                📍 New Ticket in Your Team's Area
            </p>
            <p style="margin:4px 0 0;font-size:11px;color:rgba(255,255,255,.55)">
                नई टिकट — आपकी टीम के क्षेत्र में
            </p>
        </div>

        <p style="margin:0 0 18px;font-size:15px;color:#334155;line-height:1.7">
            Hello <strong>{mgr.get_full_name() or mgr.email}</strong>,<br><br>
            <span lang="en">
                A new support ticket has been created in your team's area and assigned
                to <strong>{sub_names}</strong> ({sub_dept}).
                This is an area notification for your awareness and oversight.
            </span><br><br>
            <span lang="hi" style="font-size:14px;color:#b8860b">
                आपकी टीम के क्षेत्र में एक नई सहायता टिकट बनाई गई है और
                <strong>{sub_names}</strong> को सौंपी गई है।
                यह आपकी जानकारी और निगरानी के लिए एक क्षेत्र सूचना है।
            </span>
        </p>

        <!-- Team Assignment Highlight -->
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;
                    padding:12px 16px;margin-bottom:16px;display:flex;
                    align-items:center;gap:12px">
            <span style="font-size:20px">👥</span>
            <div>
                <p style="margin:0;font-size:11px;font-weight:700;color:#166534;
                           text-transform:uppercase;letter-spacing:.06em">
                    Assigned To / असाइन किया गया
                </p>
                <p style="margin:2px 0 0;font-size:13px;font-weight:600;color:#14532d">
                    {sub_names}
                </p>
                <p style="margin:1px 0 0;font-size:11px;color:#4ade80">{sub_dept}</p>
            </div>
        </div>

        <!-- Ticket Detail Card -->
        <div style="background:#f8fafc;border:1px solid #e2e8f0;
                    border-radius:10px;overflow:hidden;margin-bottom:16px">
            <div style="background:#2C3547;padding:12px 18px">
                <p style="margin:0;font-size:11px;font-weight:700;letter-spacing:.1em;
                           text-transform:uppercase;color:#A3B087">
                    Ticket Details / टिकट विवरण
                </p>
                <p style="margin:4px 0 0;font-size:18px;font-weight:700;
                           color:#FFF8D4;font-family:monospace">{ticket.ticket_id}</p>
            </div>
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border-collapse:collapse">
                {_info_row_bilingual('Type', 'प्रकार', ticket.ticket_type)}
                {_info_row_bilingual('Priority', 'प्राथमिकता', _priority_badge(priority))}
                {_info_row_bilingual('Status', 'स्थिति', _status_badge('open'))}
                {_info_row_bilingual('Created by', 'द्वारा बनाया गया', creator)}
                {_info_row_bilingual('Caller', 'कॉलर', ticket.caller_display_name or '—')}
                {_info_row_bilingual('Location', 'स्थान', ticket.caller_location or '—')}
                {_info_row_bilingual('Mobile', 'मोबाइल', ticket.caller_contact_mobile or '—')}
                {_info_row_bilingual('Expected', 'अपेक्षित', str(ticket.expected_resolution_date) if ticket.expected_resolution_date else '—')}
            </table>
        </div>

        {desc_html}

        <p style="margin:12px 0;font-size:12px;color:#64748b;font-style:italic">
            <span lang="en">
                ℹ️ This is an informational alert. You do not need to take direct
                action unless escalation is required.
            </span><br>
            <span lang="hi">
                ℹ️ यह एक सूचनात्मक अलर्ट है। जब तक एस्केलेशन आवश्यक न हो,
                आपको सीधे कार्रवाई करने की आवश्यकता नहीं है।
            </span>
        </p>

        <div style="margin-top:24px;text-align:center">
            <a href="{ticket_url}/"
               style="display:inline-block;padding:12px 28px;background:#2C3547;
                      color:#fff;font-size:14px;font-weight:600;
                      text-decoration:none;border-radius:8px">
                📋 View on Dashboard / डैशबोर्ड पर देखें
            </a>
        </div>
        """

        plain_lines = [
            "📍 NEW TICKET IN YOUR TEAM'S AREA / आपकी टीम के क्षेत्र में नई टिकट",
            "",
            f"Hello {mgr.get_full_name()},",
            f"A new ticket has been raised in your team's area.",
            "",
            f"Assigned to   : {sub_names} ({sub_dept})",
            f"Ticket ID     : {ticket.ticket_id}",
            f"Type          : {ticket.ticket_type}",
            f"Priority      : {priority.upper()}",
            f"Caller        : {ticket.caller_display_name or '—'}",
            f"Location      : {ticket.caller_location or '—'}",
            f"Mobile        : {ticket.caller_contact_mobile or '—'}",
            f"Created by    : {creator}",
            f"Expected      : {ticket.expected_resolution_date or 'Not set'}",
        ]
        if desc_snippet:
            plain_lines += ["", f"Issue: {desc_snippet}"]
        plain_lines += [
            "",
            "This is an informational alert for your awareness and oversight.",
        ]
        if ticket_url:
            plain_lines += ["", f"Dashboard: {ticket_url}/"]

        msg = EmailMultiAlternatives(
            subject=subject,
            body=_base_plain_bilingual(
                f"New Ticket Alert — {ticket.ticket_id}", plain_lines
            ),
            from_email=from_email,
            to=[mgr.email],
        )
        msg.attach_alternative(
            _base_html_bilingual(
                f"📍 Area Alert: {ticket.ticket_id}",
                f"क्षेत्र अलर्ट: {ticket.ticket_id}",
                body_html,
            ),
            "text/html",
        )
        _safe_send(
            msg,
            context=f"{ticket.ticket_id} area alert → manager {mgr.email}",
        )