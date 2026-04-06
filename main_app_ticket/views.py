from django.http import JsonResponse
from django.shortcuts import render, redirect
import logging
import json
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.http import HttpResponseRedirect
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken          # ← moved to top
from rest_framework_simplejwt.exceptions import TokenError        # ← moved to top
from .farmer_bulk_upload      import process_farmers
from .sahayak_bulk_upload     import process_sahayaks
from .transporter_bulk_upload import process_transporters
from .employee_bulk_upload    import process_employees
from .jwt_utils import get_tokens_for_user, set_jwt_cookies, delete_jwt_cookies  # ← all three here
from .models import CustomUser

logger = logging.getLogger(__name__)


@csrf_protect
@never_cache
def loginView(request):
    """
    Production-grade login view.

    Routing after successful login:
      - Superuser / Staff (Admin)    →  /bulk_upload/
      - Customer Care Executive      →  /          (Caller Dashboard)
      - All other employees          →  /my_tickets/
    """

    print("=" * 60)
    print("LOGIN VIEW - START")
    print(f"Request method: {request.method}")
    print(f"User authenticated: {request.user.is_authenticated}")
    print(f"Session key: {request.session.session_key}")
    print("=" * 60)

    # Redirect already-authenticated users away from the login page
    if request.user.is_authenticated:
        print(f"User already authenticated: {request.user.email}")
        print(f"Is superuser: {request.user.is_superuser}")
        print(f"Is staff: {request.user.is_staff}")
        print(f"Employee title: {request.user.employee_title}")

        if request.user.is_superuser or request.user.is_staff:
            print("Redirecting to: bulk_upload (Admin)")
            return redirect('bulk_upload')

        if request.user.employee_title == CustomUser.EmployeeTitle.CUSTOMER_CARE_EXEC:
            print("Redirecting to: home (Caller Dashboard)")
            return redirect('home')

        print("Redirecting to: my_tickets")
        return redirect('my_tickets')

    if request.method == "POST":
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        print(f"\n--- POST LOGIN ATTEMPT ---")
        print(f"Email received: '{email}'")
        print(f"Password received: {'*' * len(password) if password else 'EMPTY'}")
        print(f"Password length: {len(password)}")

        # ── Basic field validation ──────────────────────────────
        if not email or not password:
            print(f"VALIDATION FAILED: email={bool(email)}, password={bool(password)}")
            messages.error(request, "Please enter both email and password.")
            return render(request, "login.html", {"email": email})

        try:
            validate_email(email)
            print(f"Email validation PASSED: {email}")
        except ValidationError as ve:
            print(f"Email validation FAILED: {ve}")
            messages.error(request, "Please enter a valid email address.")
            logger.warning(f"Invalid email format attempt: {email}")
            return render(request, "login.html", {"email": email})

        # ── Pre-auth account checks (better UX / specific errors) ──
        try:
            print(f"Looking up user in database: {email}")
            user_obj = CustomUser.objects.get(email=email)
            print(f"User found: ID={user_obj.id}, email={user_obj.email}")
            print(f"Is superuser: {user_obj.is_superuser}")
            print(f"Is staff: {user_obj.is_staff}")
            print(f"Account status: {user_obj.account_status}")
            print(f"Login status: {user_obj.login_status}")
            print(f"Employee code: {user_obj.employee_code}")
            print(f"Employee title: {user_obj.employee_title}")

            # Superusers and staff skip account-status checks entirely
            if not (user_obj.is_superuser or user_obj.is_staff):

                if user_obj.account_status == CustomUser.AccountStatus.INACTIVE:
                    print(f"ACCOUNT BLOCKED: Account status INACTIVE")
                    messages.error(request, "Your account is inactive. Please contact HR/Admin.")
                    logger.warning(f"Inactive account login attempt: {email}")
                    return render(request, "login.html", {"email": email})

                if user_obj.account_status == CustomUser.AccountStatus.YET_TO_CREATE:
                    print(f"ACCOUNT BLOCKED: Account status YET_TO_CREATE")
                    messages.error(request, "Account not fully set up. Please contact HR.")
                    logger.warning(f"Uninitialized account login attempt: {email}")
                    return render(request, "login.html", {"email": email})

                if not user_obj.login_status:
                    print(f"ACCOUNT BLOCKED: login_status = False")
                    messages.error(request, "Login is temporarily disabled for your account.")
                    logger.warning(f"Disabled login attempt: {email}")
                    return render(request, "login.html", {"email": email})

                if not user_obj.employee_code:
                    print(f"ACCOUNT BLOCKED: employee_code is missing/empty")
                    messages.error(request, "Employee record incomplete. Please contact HR.")
                    logger.warning(f"User missing employee code: {email}")
                    return render(request, "login.html", {"email": email})

            print("Pre-auth checks PASSED")

        except CustomUser.DoesNotExist:
            print(f"User NOT FOUND in database: {email}")
            # Let authenticate() handle it — avoids username-enumeration leaks
            pass
        except Exception as e:
            print(f"ERROR in pre-auth check: {type(e).__name__}: {e}")
            logger.error(f"Pre-auth check error for {email}: {e}")

        # ── Authenticate ────────────────────────────────────────
        try:
            print(f"\n--- Attempting authentication ---")
            print(f"Calling authenticate(email={email}, password=****)")
            user = authenticate(request, email=email, password=password)

            if user is None:
                print(f"AUTHENTICATION FAILED: No user returned from authenticate()")
                logger.warning(f"Failed login attempt: {email}")
                messages.error(request, "Invalid email or password.")
                return render(request, "login.html", {"email": email})

            print(f"AUTHENTICATION SUCCESS: User found")
            print(f"User ID: {user.id}")
            print(f"User email: {user.email}")
            print(f"User full name: {user.get_full_name()}")
            print(f"Is superuser: {user.is_superuser}")
            print(f"Is staff: {user.is_staff}")
            print(f"Account status: {user.account_status}")
            print(f"Login status: {user.login_status}")
            print(f"Employee code: {user.employee_code}")
            print(f"Employee title: {user.employee_title}")
            print(f"Department: {user.department}")

            # Post-auth guard — only for non-admin users
            if not (user.is_superuser or user.is_staff):

                if user.account_status == CustomUser.AccountStatus.INACTIVE:
                    print(f"POST-AUTH BLOCK: Account status INACTIVE")
                    messages.error(request, "Your account is inactive. Please contact HR/Admin.")
                    return render(request, "login.html", {"email": email})

                if user.account_status == CustomUser.AccountStatus.YET_TO_CREATE:
                    print(f"POST-AUTH BLOCK: Account status YET_TO_CREATE")
                    messages.error(request, "Account not fully set up. Please contact HR.")
                    return render(request, "login.html", {"email": email})

                if not user.login_status:
                    print(f"POST-AUTH BLOCK: login_status = False")
                    messages.error(request, "Login is temporarily disabled for your account.")
                    return render(request, "login.html", {"email": email})

                if not user.employee_code:
                    print(f"POST-AUTH BLOCK: employee_code is missing/empty")
                    messages.error(request, "Employee record incomplete. Please contact HR.")
                    return render(request, "login.html", {"email": email})

            # ── All checks passed — log the user in ──────────────────────────
            print(f"\n--- Logging in user ---")
            login(request, user)
            print(f"User logged in successfully")
            print(f"Session key after login: {request.session.session_key}")
            print(f"User.is_authenticated after login: {request.user.is_authenticated}")

            # ── Issue JWT token pair ──────────────────────────────────────────
            tokens = get_tokens_for_user(user)          # ← was wrongly make_token_pair()
            print(f"JWT tokens issued for: {user.email}")

            logger.info(
                f"Successful login: {email} | "
                f"Superuser: {user.is_superuser} | Staff: {user.is_staff} | "
                f"Title: {user.employee_title} | Dept: {user.department}"
            )
            messages.success(request, f"Welcome back, {user.get_full_name() or user.email}!")

            # ── Build redirect response first, THEN attach cookies ────────────
            print(f"Is superuser: {user.is_superuser} | Is staff: {user.is_staff}")
            print(f"Employee title: {user.employee_title}")

            next_url = request.GET.get('next', '').strip()
            print(f"Next URL parameter: '{next_url}'")

            if next_url and next_url.startswith('/'):
                print(f"Redirecting to next URL: {next_url}")
                response = HttpResponseRedirect(next_url)

            elif user.is_superuser or user.is_staff:
                print("Redirecting to: bulk_upload (Admin)")
                response = redirect('bulk_upload')

            elif user.employee_title == CustomUser.EmployeeTitle.CUSTOMER_CARE_EXEC:
                print("Redirecting to: home (Caller Dashboard)")
                response = redirect('home')

            else:
                print("Redirecting to: my_tickets")
                response = redirect('my_tickets')

            # Attach both JWT cookies to whichever redirect was built above
            set_jwt_cookies(response, tokens)
            print(f"JWT cookies set on response")
            return response

        except Exception as e:
            print(f"EXCEPTION in authentication block: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            logger.error(f"Authentication error for {email}: {e}")
            messages.error(request, "An error occurred during login. Please try again.")
            return render(request, "login.html", {"email": email})

    # GET — show login form
    print(f"\n--- GET request: Rendering login form ---")
    return render(request, "login.html")


def logoutView(request):
    # Blacklist the refresh token before clearing it
    refresh_token = request.COOKIES.get('refresh_token')
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            pass  # already expired or invalid — safe to ignore

    logout(request)                     # destroy Django session
    response = redirect('login')
    delete_jwt_cookies(response)        # clear both JWT cookies
    return response


def home(request):
    return render(request, "home.html")


def is_authenticated_view(request):
    return JsonResponse({"is_authenticated": request.user.is_authenticated})


def send_message(request):
    return JsonResponse({"status": "success", "message": "Message sent successfully!"})


# ══════════════════════════════════════════════════════════════════════════════
#  PASSWORD RESET  (Step 1 — request link)
# ══════════════════════════════════════════════════════════════════════════════

import json as _json
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.http import require_http_methods

_User = get_user_model()


def password_reset_view(request):
    """
    GET  → render the 'Forgot Password' form  (password_reset.html)
    POST → send reset e-mail, return JSON { success: true } or { error: "..." }
    """
    if request.method == "GET":
        # Show error banner if redirected here from an invalid token link
        error = request.GET.get("error", "")
        return render(request, "password_reset.html", {"link_error": error == "invalid_link"})

    # ── POST ──────────────────────────────────────────────────────────────────
    email = request.POST.get("email", "").strip()

    if not email:
        return JsonResponse({"success": False, "error": "Email address is required."}, status=400)

    # Always return success to avoid user enumeration
    try:
        user = _User.objects.get(email__iexact=email, is_active=True)
    except _User.DoesNotExist:
        return JsonResponse({
            "success": True,
            "message": "If that email is registered, a reset link has been sent.",
        })

    # Build reset URL  →  /reset-password/<uidb64>/<token>/
    uid   = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = request.build_absolute_uri(
        f"/reset-password/{uid}/{token}/"
    )

    # Send e-mail
    try:
        send_mail(
            subject="Password Reset – Ticket System",
            message=(
                f"Hi {user.get_full_name() or user.email},\n\n"
                f"Click the link below to reset your password:\n{reset_url}\n\n"
                "This link expires in 24 hours.\n\n"
                "If you did not request a password reset, please ignore this email."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error(f"[password_reset] mail error: {exc}")
        return JsonResponse(
            {"success": False, "error": "Failed to send email. Please try again later."},
            status=500,
        )

    return JsonResponse({
        "success": True,
        "message": "Password reset link has been sent to your email! Check your inbox.",
    })


# ══════════════════════════════════════════════════════════════════════════════
#  PASSWORD RESET  (Step 2 — set new password via token link)
# ══════════════════════════════════════════════════════════════════════════════

def password_reset_confirm_view(request, uidb64, token):
    """
    GET  → validate token, render the 'Set New Password' form
    POST → JSON body { password, confirm_password }
           returns  { success: true, message } or { error }
    """
    # ── Debug print statements ───────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"[DEBUG] password_reset_confirm_view called")
    print(f"[DEBUG] Method: {request.method}")
    print(f"[DEBUG] uidb64: {uidb64}")
    print(f"[DEBUG] token: {token}")
    print(f"[DEBUG] Request path: {request.path}")
    if request.method == "POST":
        print(f"[DEBUG] Request body: {request.body}")
    print(f"{'='*60}\n")

    # ── Validate token (shared by GET and POST) ───────────────────────────
    try:
        uid  = force_str(urlsafe_base64_decode(uidb64))
        user = _User.objects.get(pk=uid)
        print(f"[DEBUG] Decoded uid: {uid}")
        print(f"[DEBUG] Found user: {user.username if hasattr(user, 'username') else user.email}")
    except (TypeError, ValueError, OverflowError, _User.DoesNotExist) as e:
        user = None
        print(f"[DEBUG] Error decoding user: {type(e).__name__} - {str(e)}")

    token_valid = user is not None and default_token_generator.check_token(user, token)
    print(f"[DEBUG] User exists: {user is not None}")
    print(f"[DEBUG] Token valid: {token_valid}")

    # ── GET ──────────────────────────────────────────────────────────────────
    if request.method == "GET":
        print(f"[DEBUG] Processing GET request")
        if not token_valid:
            print(f"[DEBUG] Token invalid, redirecting to /reset-password/?error=invalid_link")
            return redirect("/reset-password/?error=invalid_link")
        print(f"[DEBUG] Rendering password_reset_confirm.html template")
        return render(request, "password_reset_confirm.html", {
            "uidb64": uidb64,
            "token":  token,
        })

    # ── POST (AJAX JSON) ──────────────────────────────────────────────────────
    print(f"[DEBUG] Processing POST request")

    if not token_valid:
        print(f"[DEBUG] Token invalid for POST request")
        return JsonResponse(
            {"success": False, "error": "This reset link is invalid or has expired. Please request a new one."},
            status=400,
        )

    try:
        body = _json.loads(request.body)
        print(f"[DEBUG] Successfully parsed JSON body: {body}")
    except (_json.JSONDecodeError, ValueError) as e:
        print(f"[DEBUG] JSON decode error: {type(e).__name__} - {str(e)}")
        return JsonResponse({"success": False, "error": "Invalid request format."}, status=400)

    password         = body.get("password", "")
    confirm_password = body.get("confirm_password", "")
    print(f"[DEBUG] Password length: {len(password)}")
    print(f"[DEBUG] Confirm password length: {len(confirm_password)}")
    print(f"[DEBUG] Passwords match: {password == confirm_password}")

    if not password:
        print(f"[DEBUG] Password is empty")
        return JsonResponse({"success": False, "error": "Password is required."}, status=400)

    if len(password) < 8:
        print(f"[DEBUG] Password too short: {len(password)} characters (minimum 8 required)")
        return JsonResponse(
            {"success": False, "error": "Password must be at least 8 characters long."}, status=400
        )

    if password != confirm_password:
        print(f"[DEBUG] Password mismatch: password='{password}', confirm='{confirm_password}'")
        return JsonResponse(
            {"success": False, "error": "Passwords do not match."}, status=400
        )

    print(f"[DEBUG] Setting new password for user: {user.username if hasattr(user, 'username') else user.email}")
    user.set_password(password)
    user.save()
    print(f"[DEBUG] Password successfully updated")

    print(f"[DEBUG] Returning success response")
    return JsonResponse({
        "success": True,
        "message": "Your password has been reset successfully! Redirecting to login…",
    })


# ══════════════════════════════════════════════════════════════════════════════
#  MY TICKETS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def my_tickets(request):
    tickets = (
        request.user.assigned_tickets
        .all()
        .select_related('farmer', 'mpp', 'transporter', 'created_by')
        .order_by('-created_at')
    )

    tickets_json = json.dumps(
        [
            {
                "id":          t.ticket_id,
                "entity":      t.entity_type,
                "caller":      t.caller_display_name,
                "location":    t.caller_location,
                "mobile": (
                    t.farmer.mobile_no        if t.farmer      else
                    t.mpp.mobile_number       if t.mpp         else
                    t.other_caller_mobile     or ""
                ),
                "type":        t.ticket_type,
                "priority":    t.priority,
                "assigned_by": t.created_by.get_full_name() if t.created_by else "System",
                "created":     t.created_at.strftime('%d %b %Y, %I:%M %p'),
                "expected":    t.expected_resolution_date.strftime('%d %b %Y')
                               if t.expected_resolution_date else "",
                "resolved":    t.resolved_at.strftime('%d %b %Y, %I:%M %p')
                               if t.resolved_at else "",
                "status":      t.status,
                "desc_en":     t.description_en or "",
                "desc_hi":     t.description_hi or "",
            }
            for t in tickets
        ],
        default=str,
    )

    context = {
    "tickets_json":    tickets_json,
    "open_count":      tickets.filter(status='open').count(),
    "pending_count":   tickets.filter(status='pending').count(),
    "reopened_count":  tickets.filter(status='reopened').count(),  # ← make sure this exists
    "resolved_count":  tickets.filter(status='resolved').count(),
    "closed_count":    tickets.filter(status='closed').count(),
    "escalated_count": tickets.filter(status='escalated').count(),
    "total_count":     tickets.count(),
    }
    return render(request, "my_tickets.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  BULK UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

import io
import traceback
import time
import uuid
from datetime import date, datetime

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.db import transaction
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

try:
    import openpyxl
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False


# ── Guard: only superuser / staff can access ──────────────────────────────────
def _is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


# ══════════════════════════════════════════════════════════════════════════════
#  SSE PROGRESS STREAM
# ══════════════════════════════════════════════════════════════════════════════

@login_required(login_url="login")
@user_passes_test(_is_admin, login_url="login")
def bulk_upload_progress(request):
    job_id = request.GET.get("job_id", "")
    if not job_id:
        return StreamingHttpResponse("data: {}\n\n", content_type="text/event-stream")

    def event_stream():
        last_idx = -1
        timeout  = 300
        start    = time.time()

        while time.time() - start < timeout:
            payload = cache.get(f"bu_progress_{job_id}")
            if payload is None:
                time.sleep(0.3)
                continue

            events = payload.get("events", [])
            for i in range(last_idx + 1, len(events)):
                evt = events[i]
                yield f"data: {json.dumps(evt)}\n\n"
                last_idx = i

            if payload.get("done"):
                break

            time.sleep(0.25)

        yield "data: {\"type\": \"done\"}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ══════════════════════════════════════════════════════════════════════════════
#  PROGRESS HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _push_event(job_id, event: dict):
    if not job_id:
        return
    key     = f"bu_progress_{job_id}"
    payload = cache.get(key) or {"events": [], "done": False}
    payload["events"].append(event)
    cache.set(key, payload, timeout=600)


def _push_progress(job_id, processed, total, message=""):
    _push_event(job_id, {
        "type":      "progress",
        "processed": processed,
        "total":     total,
        "pct":       round(processed / total * 100) if total else 0,
        "message":   message,
    })


def _push_done(job_id, summary, results):
    key     = f"bu_progress_{job_id}"
    payload = cache.get(key) or {"events": [], "done": False}
    payload["events"].append({
        "type":    "done",
        "summary": summary,
        "results": results,
    })
    payload["done"] = True
    cache.set(key, payload, timeout=600)


# ══════════════════════════════════════════════════════════════════════════════
#  BULK UPLOAD MAIN VIEW
# ══════════════════════════════════════════════════════════════════════════════

@login_required(login_url="login")
@user_passes_test(_is_admin, login_url="login")
def bulk_upload(request):
    from .models import Farmer, MPP, Transporter, Ticket

    context = {
        "db_counts":  _db_counts(),
        "active_tab": None,
        "summary":    None,
        "results":    [],
    }

    if request.method == "POST":
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        upload_type     = request.POST.get("upload_type", "farmer")
        update_existing = request.POST.get("update_existing") == "on"
        dry_run         = request.POST.get("dry_run") == "on"
        excel_file      = request.FILES.get("excel_file")
        job_id          = request.POST.get("job_id", "")

        context["active_tab"] = upload_type

        if not OPENPYXL_OK:
            err = "openpyxl is not installed. Run: pip install openpyxl"
            if is_ajax:
                return JsonResponse({"ok": False, "error": err})
            django_messages.error(request, err)
            return render(request, "bulk_upload.html", context)

        if not excel_file:
            err = "Please choose an Excel (.xlsx) file before submitting."
            if is_ajax:
                return JsonResponse({"ok": False, "error": err})
            django_messages.error(request, err)
            return render(request, "bulk_upload.html", context)

        if not excel_file.name.lower().endswith(".xlsx"):
            err = "Only .xlsx files are accepted."
            if is_ajax:
                return JsonResponse({"ok": False, "error": err})
            django_messages.error(request, err)
            return render(request, "bulk_upload.html", context)

        try:
            wb   = openpyxl.load_workbook(
                io.BytesIO(excel_file.read()), read_only=True, data_only=True
            )
            ws   = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as exc:
            err = f"Could not read the Excel file: {exc}"
            if is_ajax:
                return JsonResponse({"ok": False, "error": err})
            django_messages.error(request, err)
            return render(request, "bulk_upload.html", context)

        if len(rows) < 2:
            err = "The file appears to have no data rows (header only or empty)."
            if is_ajax:
                return JsonResponse({"ok": False, "error": err})
            django_messages.warning(request, err)
            return render(request, "bulk_upload.html", context)

        _HEADER_KEYS = {
            "employee code", "emp code",
            "form number",
            "vendor code",
            "mpp unique code",
        }

        header_row_idx = 0
        for i, row in enumerate(rows[:10]):
            if any(
                cell is not None
                and str(cell).strip().lower() in _HEADER_KEYS
                for cell in row
            ):
                header_row_idx = i
                break

        header_row = rows[header_row_idx]
        hmap = {
            str(cell).strip(): idx
            for idx, cell in enumerate(header_row)
            if cell is not None and str(cell).strip() != ""
        }
        data_rows = rows[header_row_idx + 1:]

        dispatch = {
            "farmer":      process_farmers,
            "sahayak":     process_sahayaks,
            "transporter": process_transporters,
            "employee":    process_employees,
        }
        processor = dispatch.get(upload_type)
        if not processor:
            err = f"Unknown upload type: '{upload_type}'"
            if is_ajax:
                return JsonResponse({"ok": False, "error": err})
            django_messages.error(request, err)
            return render(request, "bulk_upload.html", context)

        summary, results = processor(
            data_rows       = data_rows,
            hmap            = hmap,
            update_existing = update_existing,
            dry_run         = dry_run,
            performed_by    = request.user,
            job_id          = job_id,
        )
        summary["dry_run"] = dry_run
        context["db_counts"] = _db_counts()

        if is_ajax:
            return JsonResponse({
                "ok":      True,
                "summary": summary,
                "results": results,
            })

        context["summary"] = summary
        context["results"] = results
        level = django_messages.SUCCESS if summary["errors"] == 0 else django_messages.WARNING
        verb  = "previewed (dry run)" if dry_run else "imported"
        django_messages.add_message(
            request, level,
            f"{summary['total']} rows {verb} — "
            f"{summary['created']} created, {summary['updated']} updated, "
            f"{summary['errors']} errors, {summary['skipped']} skipped."
        )

    return render(request, "bulk_upload.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED VALUE EXTRACTORS
# ══════════════════════════════════════════════════════════════════════════════

_BLANK = {"", "none", "nan", "nat", "n/a", "null", "-", "--"}


def _v(row, hmap, *keys, default=None):
    for k in keys:
        idx = hmap.get(k)
        if idx is None:
            continue
        if idx >= len(row):
            continue
        val = row[idx]
        if val is None:
            continue
        s = str(val).strip()
        if s.lower() not in _BLANK:
            return s
    return default


def _i(row, hmap, *keys, default=0):
    for k in keys:
        idx = hmap.get(k)
        if idx is None:
            continue
        if idx >= len(row):
            continue
        val = row[idx]
        if val is None:
            continue
        try:
            return int(float(str(val).strip()))
        except (ValueError, TypeError):
            pass
    return default


def _d(row, hmap, *keys, default=None):
    FMTS = (
        "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d",
        "%d-%b-%Y", "%d %b %Y", "%m/%d/%Y",
        "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y",
    )
    for k in keys:
        idx = hmap.get(k)
        if idx is None:
            continue
        if idx >= len(row):
            continue
        val = row[idx]
        if val is None:
            continue
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        if isinstance(val, (int, float)) and 30000 < val < 60000:
            try:
                from openpyxl.utils.datetime import from_excel
                return from_excel(int(val)).date()
            except Exception:
                pass
        s = str(val).strip()
        if s.lower() in _BLANK:
            continue
        for fmt in FMTS:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    return default


def _db_counts():
    from .models import Farmer, MPP, Transporter, Ticket, CustomUser
    return {
        "farmers":      Farmer.objects.count(),
        "mpps":         MPP.objects.count(),
        "transporters": Transporter.objects.count(),
        "tickets":      Ticket.objects.count(),
        "employees":    CustomUser.objects.filter(
            account_status="Active"
        ).count(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  GEOGRAPHY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _state(name):
    from .models import State
    name = (name or "UTTAR PRADESH").strip().upper()
    obj, _ = State.objects.get_or_create(name=name)
    return obj


def _district(state, code, name):
    from .models import District
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    obj, created = District.objects.get_or_create(
        state=state, code=code, defaults={"name": name}
    )
    if not created and name != "UNKNOWN" and obj.name != name:
        obj.name = name
        obj.save(update_fields=["name"])
    return obj


def _tehsil(district, code, name):
    from .models import Tehsil
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    obj, created = Tehsil.objects.get_or_create(
        district=district, code=code, defaults={"name": name}
    )
    if not created and name != "UNKNOWN" and obj.name != name:
        obj.name = name
        obj.save(update_fields=["name"])
    return obj


def _village(tehsil, code, name):
    from .models import Village
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    obj, created = Village.objects.get_or_create(
        tehsil=tehsil, code=code, defaults={"name": name}
    )
    if not created and name != "UNKNOWN" and obj.name != name:
        obj.name = name
        obj.save(update_fields=["name"])
    return obj


def _hamlet(village, code, name):
    from .models import Hamlet
    if not code and not name:
        return None
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    obj, _ = Hamlet.objects.get_or_create(
        village=village, code=code, defaults={"name": name}
    )
    return obj


# ══════════════════════════════════════════════════════════════════════════════
#  FARMER PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

_FARMER_REQUIRED = [
    "form_number",
    "unique_member_code",
    "member_name",
    "gender",
    "state_name",
    "member_district_name",
    "member_tehshil_name",
    "member_village_name",
    "mpp_unique_code",
]

_MS = {
    "active":    "ACTIVE",
    "deactive":  "INACTIVE",
    "inactive":  "INACTIVE",
    "cancelled": "CANCELLED",
    "suspended": "SUSPENDED",
}

_QUAL = {
    "illiterate":    "Illiterate",
    "primary":       "Primary",
    "middle":        "Middle",
    "high school":   "High School",
    "secondary":     "High School",
    "intermediate":  "Intermediate",
    "graduate":      "Graduate",
    "post-graduate": "Post Graduate",
    "post graduate": "Post Graduate",
    "other":         "Other",
}

_REL = {
    "self":        "Self",
    "husband":     "Husband",
    "wife":        "Wife",
    "wife of":     "Wife",
    "father":      "Father",
    "father of":   "Father",
    "mother":      "Mother",
    "son":         "Son",
    "daughter of": "Other",
    "daughter":    "Other",
}


def _process_farmers(data_rows, hmap, update_existing, dry_run, performed_by, job_id=""):
    summary = {"total": 0, "created": 0, "updated": 0, "errors": 0, "skipped": 0}
    results = []

    missing = [c for c in _FARMER_REQUIRED if c not in hmap]
    if missing:
        err_result = [{
            "row": "—", "key": "—", "status": "error",
            "message": f"Missing required column(s): {', '.join(missing)}",
        }]
        _push_done(job_id, summary, err_result)
        return summary, err_result

    data_rows = [
        r for r in data_rows
        if not all(v is None or str(v).strip() == "" for v in r)
    ]
    total_rows = len(data_rows)

    if dry_run:
        for idx, raw in enumerate(data_rows, start=1):
            summary["total"] += 1
            g = lambda *k, **kw: _v(raw, hmap, *k, **kw)

            form_no = g("form_number")
            um_code = g("unique_member_code")
            name    = g("member_name")
            row_num = idx + 1

            if not form_no:
                summary["errors"] += 1
                results.append({"row": row_num, "key": "—", "status": "error",
                                 "message": "form_number is blank"})
            elif not um_code:
                summary["errors"] += 1
                results.append({"row": row_num, "key": form_no, "status": "error",
                                 "message": "unique_member_code is blank"})
            elif not name:
                summary["errors"] += 1
                results.append({"row": row_num, "key": form_no, "status": "error",
                                 "message": "member_name is blank"})
            else:
                mpp_code = g("mpp_unique_code")
                if mpp_code:
                    from .models import MPP
                    if not MPP.objects.filter(unique_code=mpp_code).exists():
                        summary["errors"] += 1
                        results.append({
                            "row": row_num, "key": form_no, "status": "error",
                            "message": (
                                f"MPP '{mpp_code}' not found. Upload Sahayak/MPP sheet first."
                            ),
                        })
                        _push_progress(job_id, idx, total_rows, f"Validating row {row_num}…")
                        continue
                summary["created"] += 1
                results.append({"row": row_num, "key": form_no, "status": "preview",
                                 "message": f"Would be imported — {name}"})

            _push_progress(job_id, idx, total_rows, f"Validating row {row_num}…")

        _push_done(job_id, summary, results)
        return summary, results

    # PASS 1: Validate
    validation_errors = []
    valid_rows        = []

    _push_event(job_id, {"type": "phase", "phase": "validate",
                          "message": "Validating all rows before import…"})

    for idx, raw in enumerate(data_rows, start=1):
        row_num = idx + 1
        g       = lambda *k, **kw: _v(raw, hmap, *k, **kw)

        form_no = g("form_number")
        um_code = g("unique_member_code")
        name    = g("member_name")

        if not form_no:
            validation_errors.append({
                "row": row_num, "key": "—", "status": "error",
                "message": "form_number is blank — row would be skipped",
            })
        elif not um_code:
            validation_errors.append({
                "row": row_num, "key": form_no, "status": "error",
                "message": "unique_member_code is blank",
            })
        elif not name:
            validation_errors.append({
                "row": row_num, "key": form_no, "status": "error",
                "message": "member_name is blank",
            })
        else:
            valid_rows.append((row_num, raw, form_no, um_code, name))

        if idx % 10 == 0 or idx == total_rows:
            _push_progress(
                job_id,
                processed=idx,
                total=total_rows * 2,
                message=f"Validating… row {row_num} of {total_rows + 1}",
            )

    if validation_errors:
        summary["total"]  = len(data_rows)
        summary["errors"] = len(validation_errors)
        _push_event(job_id, {
            "type":    "abort",
            "message": (
                f"Import aborted — {len(validation_errors)} validation error(s) found. "
                "No records were written. Fix the errors and re-upload."
            ),
        })
        _push_done(job_id, summary, validation_errors)
        return summary, validation_errors

    # PASS 2: Write
    _push_event(job_id, {
        "type":    "phase",
        "phase":   "write",
        "message": f"Validation passed ✓ — importing {len(valid_rows)} rows…",
    })

    write_results = []
    write_errors  = []

    try:
        with transaction.atomic():
            for write_idx, (row_num, raw, form_no, um_code, name) in enumerate(valid_rows, start=1):
                try:
                    action = _upsert_farmer(
                        raw, hmap, form_no, um_code, name,
                        update_existing, performed_by
                    )
                except Exception as exc:
                    write_errors.append({
                        "row": row_num, "key": form_no, "status": "error",
                        "message": f"DB error: {exc}",
                    })
                    logger.error("Farmer import DB error row %s (%s): %s",
                                 row_num, form_no, exc, exc_info=True)
                    raise

                if action == "created":
                    write_results.append({"row": row_num, "key": form_no,
                                           "status": "created", "message": f"Created — {name}"})
                elif action == "updated":
                    write_results.append({"row": row_num, "key": form_no,
                                           "status": "updated", "message": f"Updated — {name}"})
                else:
                    write_results.append({"row": row_num, "key": form_no,
                                           "status": "skipped",
                                           "message": "Already exists — skipped (update off)"})

                if write_idx % 10 == 0 or write_idx == len(valid_rows):
                    _push_progress(
                        job_id,
                        processed=total_rows + write_idx,
                        total=total_rows * 2,
                        message=f"Importing… {write_idx} of {len(valid_rows)}",
                    )

    except Exception:
        all_results = write_errors or [{
            "row": "—", "key": "—", "status": "error",
            "message": "Import failed and was fully rolled back. No records were saved.",
        }]
        summary["total"]  = len(data_rows)
        summary["errors"] = len(all_results)
        _push_event(job_id, {
            "type":    "rollback",
            "message": "An error occurred — the entire import was rolled back. No data was saved.",
        })
        _push_done(job_id, summary, all_results)
        return summary, all_results

    summary["total"]   = len(data_rows)
    summary["created"] = sum(1 for r in write_results if r["status"] == "created")
    summary["updated"] = sum(1 for r in write_results if r["status"] == "updated")
    summary["skipped"] = sum(1 for r in write_results if r["status"] == "skipped")
    summary["errors"]  = 0

    _push_done(job_id, summary, write_results)
    return summary, write_results


def _upsert_farmer(raw, hmap, form_no, um_code, name, update_existing, performed_by):
    from .models import (
        Farmer, MPP, Plant, BMC, MCC,
        State, District, Tehsil, Village, Hamlet, CustomUser,
    )

    g  = lambda *k, **kw: _v(raw, hmap, *k, **kw)
    gi = lambda *k, **kw: _i(raw, hmap, *k, **kw)
    gd = lambda *k, **kw: _d(raw, hmap, *k, **kw)

    state_obj    = _state(g("state_name"))
    district_obj = _district(state_obj,
                             g("member_district_code"),
                             g("member_district_name"))
    tehsil_obj   = _tehsil(district_obj,
                           g("member_tehshil_code"),
                           g("member_tehshil_name"))
    village_obj  = _village(tehsil_obj,
                            g("member_village_code"),
                            g("member_village_name"))
    hamlet_obj   = _hamlet(village_obj,
                           g("member_hamlet_code"),
                           g("member_hamlet_name"))

    mpp_code = g("mpp_unique_code")
    if not mpp_code:
        raise ValueError("mpp_unique_code is missing")

    mpp_obj = MPP.objects.filter(unique_code=mpp_code).first()
    if not mpp_obj:
        mpp_obj = _auto_create_mpp(raw, hmap, mpp_code, state_obj)

    gender_raw = (g("gender") or "").strip().capitalize()
    gender     = gender_raw if gender_raw in ("Male", "Female", "Other") else "Other"

    caste_raw = (g("caste_category") or "").strip()
    caste     = caste_raw if caste_raw in ("General", "OBC", "SC", "ST", "Other") else None

    qual_raw = (g("qualification") or "").strip().lower()
    qual     = _QUAL.get(qual_raw)

    rel_raw = (g("member_relation") or "").strip().lower()
    m_rel   = _REL.get(rel_raw, "Other")

    mtype_raw = (g("member_type") or "NONE").strip().upper()
    m_type    = mtype_raw if mtype_raw in ("NONE", "REGULAR", "PREMIUM") else "NONE"

    appr_raw = (g("approval_status") or "Pending").strip().capitalize()
    approval = appr_raw if appr_raw in ("Pending", "Approved", "Rejected") else "Pending"

    ms_raw   = (g("member_status") or "ACTIVE").strip().lower()
    m_status = _MS.get(ms_raw, "ACTIVE")

    pm_raw = (g("payment_mode") or "").strip().upper()
    p_mode = pm_raw if pm_raw in ("CASH", "DD", "CHEQUE", "ONLINE") else None

    accepted_by_user = None
    val = g("accepted_by", "user_id")
    if val:
        if val.lower() == "admin":
            accepted_by_user = CustomUser.objects.filter(is_superuser=True).first()
        elif "@" in val:
            accepted_by_user = CustomUser.objects.filter(email=val).first()

    defaults = {
        "member_name":     name,
        "father_name":     g("father_name"),
        "member_relation": m_rel,
        "gender":          gender,
        "age":             gi("age") or None,
        "birth_date":      gd("birth_date"),
        "caste_category":  caste,
        "qualification":   qual,
        "aadhar_no":       g("aadhar_no"),
        "mobile_no":       g("mobile_no"),
        "phone_no":        g("phone_no"),
        "house_no":        g("house_no"),
        "hamlet":          hamlet_obj,
        "village":         village_obj,
        "post_office":     g("post_office"),
        "tehsil":          tehsil_obj,
        "district":        district_obj,
        "state":           state_obj,
        "pincode":         g("pincode"),
        "mpp":             mpp_obj,
        "cow_heifer_no":       gi("Cow Herifer No"),
        "buffalo_heifer_no":   gi("Buffalo Herifer No"),
        "mix_heifer_no":       gi("Mix Herifer No"),
        "desi_cow_heifer_no":  gi("Desi Cow Herifer No"),
        "crossbred_heifer_no": gi("Crossbred Herifer No"),
        "cow_dry_no":          gi("Cow Dry No"),
        "buffalo_dry_no":      gi("Buffalo Dry No"),
        "mix_dry_no":          gi("Mix Dry No"),
        "desi_cow_dry_no":     gi("Desi Cow Dry No"),
        "crossbred_dry_no":    gi("Crossbred Dry No"),
        "cow_animal_nos":       gi("Cow Animal Nos"),
        "buffalo_animal_nos":   gi("Buffalo Animal Nos"),
        "mix_animal_nos":       gi("Mix Animal Nos"),
        "desi_cow_animal_nos":  gi("Desi Cow Animal Nos"),
        "crossbred_animal_nos": gi("Crossbred Animal Nos"),
        "lpd_no":                gi("lpd_no"),
        "household_consumption": gi("household_consumption"),
        "market_consumption":    gi("market_consumption"),
        "accountant_name":    g("accountant_name"),
        "bank_account_no":    g("bank_account_no"),
        "member_bank_name":   g("member_bank_name"),
        "member_branch_name": g("member_branch_name"),
        "ifsc":               g("ifsc"),
        "particular1_name":     g("particluar1_name"),
        "particular1_gender":   (g("particluar1_name_gender") or "").capitalize() or None,
        "particular1_age":      gi("particluar1_name_age") or None,
        "particular1_relation": g("particluar1_relation_name"),
        "nominee_name":     g("nominee_name"),
        "nominee_relation": g("relation"),
        "nominee_address":  g("nominee_address"),
        "guardian_name":     g("guardian_name"),
        "member_family_age": gi("member_family_age") or None,
        "member_type":   m_type,
        "admission_fee": gi("admission_fee"),
        "share_qty":     gi("share_qty"),
        "paid_amount":   gi("paid_amount"),
        "depositor_bank_name":   g("depositor_bank_name"),
        "depositor_branch_name": g("depositor_branch_name"),
        "dd_no":                 g("DD_no"),
        "transaction_date":      gd("transaction_date"),
        "payment_mode":          p_mode,
        "wef_date":              gd("wef_date"),
        "approval_status":      approval,
        "accepted_by":          accepted_by_user,
        "approval_date":        gd("approval_date"),
        "member_status":        m_status,
        "member_cancellation":  g("member_cancelation"),
        "enrollment_date":              gd("member Enrolment Date"),
        "first_board_approved_meeting": gd("first_board_approved_meeting"),
        "last_board_approved_meeting":  gd("last_board_approved_meeting"),
    }

    clean = {k: v for k, v in defaults.items() if v is not None}

    existing = Farmer.objects.filter(form_number=form_no).first()
    if existing:
        if not update_existing:
            return "skipped"
        for field, val in clean.items():
            setattr(existing, field, val)
        existing.unique_member_code = um_code
        existing.member_tr_code     = g("member_tr_code")
        existing.member_ex_code     = g("member_ex_code")
        existing.save()
        return "updated"
    else:
        Farmer.objects.create(
            form_number        = form_no,
            unique_member_code = um_code,
            member_tr_code     = g("member_tr_code"),
            member_ex_code     = g("member_ex_code"),
            created_by         = performed_by,
            **clean,
        )
        return "created"


def _auto_create_mpp(raw, hmap, mpp_code, state_obj):
    from .models import Plant, BMC, MCC, MPP

    g = lambda *k, **kw: _v(raw, hmap, *k, **kw)

    plant, _ = Plant.objects.get_or_create(
        code=g("mcc_tr_code", "bmc_tr_code") or "01001",
        defaults={"name": "SHWETDHARA MPCL"},
    )
    bmc_code = g("bmc_tr_code") or "01001"
    bmc_name = (g("bmc_name") or "UNKNOWN").upper()
    bmc, _ = BMC.objects.get_or_create(
        plant=plant, code=bmc_code, defaults={"name": bmc_name}
    )
    mcc_code = g("mcc_tr_code") or bmc_code
    mcc_name = (g("mcc_name") or bmc_name).upper()
    mcc, _ = MCC.objects.get_or_create(
        bmc=bmc, code=mcc_code, defaults={"name": mcc_name}
    )
    mpp_district = _district(state_obj,
                             g("mpp_district_code", "member_district_code"),
                             g("mpp_district_name", "member_district_name"))
    mpp_tehsil   = _tehsil(mpp_district,
                           g("mpp_tehshil_code", "member_tehshil_code"),
                           g("mpp_tehshil_name", "member_tehshil_name"))
    mpp_village  = _village(mpp_tehsil,
                            g("mpp_village_code", "member_village_code"),
                            g("mpp_village_name", "member_village_name"))
    mpp_hamlet   = _hamlet(mpp_village,
                           g("mpp_hamlet_code", "member_hamlet_code"),
                           g("mpp_hamlet_name", "member_hamlet_name"))

    mpp_name = (g("mpp_name") or mpp_code).upper()
    mpp, _ = MPP.objects.get_or_create(
        unique_code=mpp_code,
        defaults={
            "name": mpp_name, "transaction_code": g("mpp_tr_code"),
            "ex_code": g("mpp_ex_code"), "plant": plant, "mcc": mcc,
            "state": state_obj, "district": mpp_district,
            "tehsil": mpp_tehsil, "village": mpp_village,
            "hamlet": mpp_hamlet, "status": "Active",
        },
    )
    return mpp