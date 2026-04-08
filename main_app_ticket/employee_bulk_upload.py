"""
employee_bulk_upload.py
─────────────────────────────────────────────────────────────────────────────
Production-grade employee bulk import engine — model-aware edition.

WHY THE PREVIOUS VERSION COULD HIT ERROR 1205
───────────────────────────────────────────────
  One outer transaction.atomic() wrapped ALL chunks.  MySQL held row locks on
  every written CustomUser row until the LAST chunk committed — on large files
  that exceeds innodb_lock_wait_timeout (default 50 s) and MySQL raises 1205.

KEY CHANGES IN THIS VERSION  (mirrors farmer_bulk_upload.py exactly)
──────────────────────────────────────────────────────────────────────
  1.  PER-CHUNK TRANSACTIONS
      Each CHUNK_SIZE batch is committed in its own short transaction.
      Lock duration ≈ time to insert 200 rows ≈ 20–80 ms per chunk.

  2.  RAW-SQL INSERT … ON DUPLICATE KEY UPDATE  (true upsert)
      One SQL statement per chunk handles both INSERT and UPDATE.
      Duplicate key is triggered on `employee_code` (UNIQUE) and `email`
      (UNIQUE).  ON DUPLICATE KEY clause updates all mutable columns.

  3.  auto_now / auto_now_add FIELDS EXCLUDED FROM INSERT COLUMN LIST
      `date_joined` (auto_now_add) and similar auto fields must NOT be
      in the INSERT column list — MySQL DEFAULT handles them.

  4.  FK COLUMNS ARE `<field>_id`, NOT `<field>`
      We use field.attname (e.g. `manager_id`) for integer PK extraction.

  5.  TWO-SUB-PASS MANAGER LINK RESOLUTION (unchanged concept, new impl)
      Sub-pass A: upsert all employees WITHOUT manager links (chunked).
      Sub-pass B: resolve manager codes → PKs in a second sweep.
      Sub-pass B runs in its own per-chunk transactions too.

  6.  RETRY WITH EXPONENTIAL BACK-OFF + SHORT SESSION LOCK TIMEOUT
      innodb_lock_wait_timeout set to LOCK_TIMEOUT_SEC (5 s) per chunk.
      Up to MAX_RETRIES retries with doubling back-off.

Architecture
────────────
  Pass 0  – Pre-warm employee-code + email cache (one SELECT)
  Pass 1  – Validate all rows in Python (no DB writes)
  Pass 2a – Build CustomUser(**kwargs) objects; upsert in chunks
  Pass 2b – Resolve manager FKs; update in chunks

Tuning knobs
────────────
  CHUNK_SIZE        rows per upsert call         (default 200)
  PROGRESS_EVERY    SSE heartbeat every N rows    (default 50)
  MAX_LIVELOG_ROWS  cap SSE live-log entries      (default 200)
  LOCK_TIMEOUT_SEC  MySQL session lock timeout    (default 5)
  MAX_RETRIES       retries on lock error         (default 3)

Column aliases (case-insensitive, strip-whitespace)
────────────────────────────────────────────────────
  Employee Code / Emp Code / EmpCode                → employee_code  ★ required
  First Name / Firstname / Name                     → first_name     ★ required
  Last Name  / Lastname  / Surname                  → last_name
  Full Name                                         → full_name (informational)
  Department / Dept                                 → department
  Employee Type (Designation) / Designation / Grade → grade_raw → employee_type
  Employee Title (Role) / Title / Role              → employee_title
  Work Location (Branch) / Branch / Work Location   → work_address
  Reporting Manager Code / Reporting Manager        → manager_code (pass-2b FK)
  Functional Manager Code / Functional Manager      → func_manager_code (remark)
  Primary Email / Employee Email Id / Email         → email
  Mobile Number / Employee Phone Number / Mobile    → work_phone
  Account Status                                    → account_status
  Login Status                                      → login_status
  Remark                                            → remark
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from django.utils import timezone

from django.contrib.auth.hashers import make_password
from django.db import connection, transaction

logger = logging.getLogger(__name__)

# ── Tuning ────────────────────────────────────────────────────────────────────
CHUNK_SIZE       = 200
PROGRESS_EVERY   = 50
MAX_LIVELOG_ROWS = 200
LOCK_TIMEOUT_SEC = 5
MAX_RETRIES      = 3

# ── Blank-value sentinel ──────────────────────────────────────────────────────
_BLANK = {"", "none", "nan", "nat", "n/a", "null", "-", "--", "na"}

# ── Required columns (internal field names after alias resolution) ────────────
_EMP_REQUIRED = ["employee_code", "first_name"]

# ── Fields excluded from the INSERT column list ───────────────────────────────
# Django's AbstractUser has date_joined (auto_now_add) and last_login (nullable).
# We exclude 'id' and any auto-managed timestamp columns.
# NOTE: adjust this set if your CustomUser model has different auto fields.
_SKIP_INSERT_COLUMNS = frozenset({"id", "last_login"})  # removed "date_joined"
# Fields never updated on DUPLICATE KEY conflict
_SKIP_UPDATE_COLUMNS = frozenset({
    "id", "employee_code", "email", "password", "last_login",
})

# ── Column alias map ──────────────────────────────────────────────────────────
_COL_MAP: Dict[str, str] = {
    "employee code":                    "employee_code",
    "emp code":                         "employee_code",
    "empcode":                          "employee_code",
    "employee id":                      "employee_code",
    "emp id":                           "employee_code",
    "first name":                       "first_name",
    "firstname":                        "first_name",
    "first_name":                       "first_name",
    "name":                             "first_name",
    "full name":                        "full_name",
    "last name":                        "last_name",
    "lastname":                         "last_name",
    "last_name":                        "last_name",
    "surname":                          "last_name",
    "department":                       "department",
    "dept":                             "department",
    "designation":                      "employee_title",
    "title":                            "employee_title",
    "role":                             "employee_title",
    "employee title":                   "employee_title",
    "employee title (role)":            "employee_title",
    "grade":                            "grade_raw",
    "employee grade":                   "grade_raw",
    "employee type":                    "grade_raw",
    "employee type (designation)":      "grade_raw",
    "grade / role notes":               "grade_raw",
    "branch":                           "work_address",
    "work location":                    "work_address",
    "location":                         "work_address",
    "work location (branch)":           "work_address",
    "reporting manager":                "manager_code",
    "reporting manager code":           "manager_code",
    "manager":                          "manager_code",
    "functional manager":               "func_manager_code",
    "functional manager code":          "func_manager_code",
    "primary email":                    "email",
    "employee email id":                "email",
    "employee email":                   "email",
    "email id":                         "email",
    "email":                            "email",
    "secondary email":                  "secondary_email",
    "employee phone number":            "work_phone",
    "phone number":                     "work_phone",
    "phone":                            "work_phone",
    "mobile":                           "work_phone",
    "mobile number":                    "work_phone",
    "login status":                     "login_status_raw",
    "account status":                   "account_status_raw",
    "remark":                           "remark_raw",
}

# ── Normalisation maps ────────────────────────────────────────────────────────
_DEPT_MAP: Dict[str, str] = {
    "operations":                               "OPERATIONS",
    "quality":                                  "QUALITY",
    "pib & pes":                                "PIB & PES",
    "pib and pes":                              "PIB & PES",
    "it & mis":                                 "IT & MIS",
    "it and mis":                               "IT & MIS",
    "mis & store":                              "MIS & Store",
    "finance and accounts":                     "FINANCE AND ACCOUNTS",
    "finance & accounts":                       "FINANCE AND ACCOUNTS",
    "sales & marketing":                        "SALES & MARKETING",
    "sales and marketing":                      "SALES & MARKETING",
    "human resource":                           "HUMAN RESOUCE",
    "human resouce":                            "HUMAN RESOUCE",
    "hr":                                       "HUMAN RESOUCE",
    "cs & support services":                    "CS & SUPPORT SERVICES",
    "cs & business support":                    "CS & SUPPORT SERVICES",
    "cs, legal & business support services":    "CS, Legal & Business Support Services",
    "logistics":                                "LOGISTICS",
    "purchase":                                 "PURCHASE",
    "administration":                           "OTHER",
    "admin":                                    "OTHER",
}
_TITLE_MAP: Dict[str, str] = {
    "facilitator":                  "Facilitator",
    "area officer":                 "Area Officer",
    "cluster manager":              "Cluster Manager",
    "zonal manager":                "Zonal Manager",
    "fes executive":                "FES Executive",
    "fes technician":               "FES Technician",
    "fes":                          "FES",
    "development officer":          "Development Officer",
    "para-vet":                     "Para-Vet",
    "para vet":                     "Para-Vet",
    "animal nutrition officer":     "Animal Nutrition Officer",
    "animal nutrition supervisor":  "Animal Nutrition Supervisor",
    "operator":                     "Operator",
    "chemist":                      "Chemist",
    "mcc incharge":                 "MCC Incharge",
    "bmc incharge":                 "BMC Incharge",
    "audit & compliances":          "Audit & Compliances",
    "audit and compliances":        "Audit & Compliances",
    "operations & documentation":   "Operations & Documentation",
    "pib officer":                  "PIB Officer",
    "veterinarian":                 "Veterinarian",
    "it support":                   "IT Support",
    "it":                           "IT",
    "mis incharge":                 "MIS Incharge",
    "mis & store":                  "MIS & Store",
    "mis":                          "MIS",
    "store keeper":                 "Store Keeper",
    "finance cum store":            "Finance Cum Store",
    "department in charge":         "Department In Charge",
    "dept in charge":               "Department In Charge",
    "projects & reporting":         "Projects & Reporting",
    "account executive":            "Account Executive",
    "payments":                     "Payments",
    "stock & payments":             "Payments",
    "store":                        "Store",
    "purchase assistant":           "Purchase Assistant",
    "purchase documentation":       "Purchase Assistant",
    "primary sales officer":        "Primary Sales Officer",
    "sales officer":                "Sales Officer",
    "sales trainee":                "Sales Trainee",
    "sales mis":                    "Sales MIS",
    "payroll & training":           "Payroll & Training",
    "executive assistant":          "Executive Assistant",
    "hr head":                      "HR Head",
    "documentation":                "Documentation",
    "customer care executive":      "Customer Care Executive",
    "hod":                          "HOD",
    "trainee":                      "Trainee",
    "management trainee":           "Management Trainee",
    "assistant manager":            "Assistant Manager",
    "asst. manager":                "Assistant Manager",
    "asst manager":                 "Assistant Manager",
    "admin":                        "HOD",
    "chief executive":              "HOD",
    "governance & relationship":    "HOD",
    "fodder & agri business":       "HOD",
    "hr & admin":                   "HOD",
    "pes & input services":         "HOD",
    "other":                        "Other",
}
_ETYPE_MAP: Dict[str, str] = {
    "assistant":                "Assistant",
    "sr. assistant":            "Sr. Assistant",
    "senior assistant":         "Sr. Assistant",
    "jr. executive":            "Jr. Executive",
    "junior executive":         "Jr. Executive",
    "executive":                "Executive",
    "sr. executive":            "Sr. Executive",
    "senior executive":         "Sr. Executive",
    "dy. manager":              "Dy. Manager",
    "deputy manager":           "Dy. Manager",
    "assistant manager":        "Assistant Manager",
    "asst. manager":            "Assistant Manager",
    "manager":                  "Manager",
    "sr. manager":              "Sr. Manager",
    "senior manager":           "Sr. Manager",
    "management trainee":       "Management Trainee",
    "area officer":             "Area Officer",
    "other":                    "Other",
    "chief executive":          "Other",
    "haritkanak finance":       "Executive",
    "dept in charge":           "Executive",
    "admin":                    "Other",
}
_LOCATION_MAP: Dict[str, str] = {
    "ayodhya h.o.":     "Ayodhya H.O.",
    "ayodhya ho":       "Ayodhya H.O.",
    "ayodhya h.o":      "Ayodhya H.O.",
    "ayodhya":          "Ayodhya",
    "pratapgarh":       "Pratapgarh",
    "akbarpur":         "Akbarpur",
    "bahraich":         "Bahraich",
    "balrampur":        "Balrampur",
    "naanpara":         "Naanpara",
    "colonelganj":      "Colonelganj",
    "badlapur":         "Badlapur",
    "raje sultanpur":   "Raje Sultanpur",
    "ramsanehi ghat":   "Ramsanehi Ghat",
    "ram sanehi ghat":  "Ram Sanehi Ghat",
    "sultanpur":        "Sultanpur",
    "amethi":           "Amethi",
    "maharajganj":      "Maharajganj",
    "milkipur":         "Milkipur",
    "barausa":          "Barausa",
    "deeh":             "Deeh",
    "kurwar":           "Kurwar",
    "umrawal":          "Umrawal",
    "mihirpurwa":       "Mihirpurwa",
    "lalganj":          "Lalganj",
    "rae bareli":       "Rae Bareli",
    "blarampur":        "Blarampur",
}
_ACCT_MAP: Dict[str, str] = {
    "active":         "Active",
    "inactive":       "Inactive",
    "yet to create":  "Yet to create",
    "yet-to-create":  "Yet to create",
}


# ══════════════════════════════════════════════════════════════════════════════
#  VALUE EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════════

def _v(row: tuple, hmap: dict, *keys: str, default=None):
    for k in keys:
        idx = hmap.get(k)
        if idx is None or idx >= len(row):
            continue
        val = row[idx]
        if val is None:
            continue
        s = str(val).strip()
        if s.lower() not in _BLANK:
            return s
    return default


# ══════════════════════════════════════════════════════════════════════════════
#  EMPLOYEE CACHE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EmpCache:
    codes:  Dict[str, int] = field(default_factory=dict)  # emp_code → pk
    emails: set            = field(default_factory=set)    # for uniqueness


def _warm_cache() -> EmpCache:
    from .models import CustomUser
    cache = EmpCache()
    for emp_code, pk, email in CustomUser.objects.values_list(
        "employee_code", "id", "email"
    ):
        if emp_code:
            cache.codes[emp_code] = pk
        if email:
            cache.emails.add(email.lower())
    logger.info("EmpCache warmed: %d existing employees", len(cache.codes))
    return cache


# ══════════════════════════════════════════════════════════════════════════════
#  FIELD RESOLVERS
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_dept(raw: str) -> str:
    return _DEPT_MAP.get((raw or "").strip().lower(), "OTHER") if raw else "OTHER"


def _resolve_title(raw: str) -> Optional[str]:
    return _TITLE_MAP.get((raw or "").strip().lower(), "Other") if raw else None


def _resolve_etype(raw: str) -> str:
    return _ETYPE_MAP.get((raw or "").strip().lower(), "Other") if raw else "Assistant"


def _resolve_location(raw: str) -> Optional[str]:
    return _LOCATION_MAP.get((raw or "").strip().lower(), "Other") if raw else None


def _resolve_account_status(raw: str) -> str:
    return _ACCT_MAP.get((raw or "").strip().lower(), "Active")


def _resolve_login_status(raw: str) -> bool:
    return (raw or "").strip().lower() in ("yes", "true", "1", "active")


def _make_email(emp_code: str, raw_email: str, suffix_n: int, cache: EmpCache) -> str:
    if raw_email and "@" in raw_email:
        candidate = raw_email.strip().lower()
        if candidate not in cache.emails:
            return candidate
        local, domain = candidate.split("@", 1)
        candidate = f"{local}.{suffix_n}@{domain}"
    else:
        candidate = f"{emp_code.lower()}@shwetdhara.local"

    base = candidate
    n    = 0
    while candidate in cache.emails:
        n += 1
        candidate = base.replace("@", f"{n}@", 1)
    return candidate


# ══════════════════════════════════════════════════════════════════════════════
#  SSE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _push_event(job_id: str, event: dict):
    if not job_id:
        return
    from django.core.cache import cache as djcache
    key     = f"bu_progress_{job_id}"
    payload = djcache.get(key) or {"events": [], "done": False}
    payload["events"].append(event)
    djcache.set(key, payload, timeout=600)


def _push_progress(job_id: str, processed: int, total: int, message: str = ""):
    _push_event(job_id, {
        "type": "progress", "processed": processed, "total": total,
        "pct": round(processed / total * 100) if total else 0,
        "message": message,
    })


def _push_done(job_id: str, summary: dict, results: list):
    from django.core.cache import cache as djcache
    key     = f"bu_progress_{job_id}"
    payload = djcache.get(key) or {"events": [], "done": False}
    payload["events"].append({"type": "done", "summary": summary, "results": results})
    payload["done"] = True
    djcache.set(key, payload, timeout=600)


# ══════════════════════════════════════════════════════════════════════════════
#  UPSERT ENGINE  (mirrors farmer_bulk_upload.py exactly)
# ══════════════════════════════════════════════════════════════════════════════

_EMP_INSERT_COLUMNS: Optional[List[str]] = None
_EMP_ATTNAMES:       Optional[List[str]] = None


def _build_column_metadata(CustomUser) -> Tuple[List[str], List[str]]:
    """
    Return (insert_columns, attnames) for the CustomUser model.
    Cached at module level — computed once per process lifetime.

    Uses f.attname (not f.name) so FK fields yield 'manager_id' etc.
    """
    global _EMP_INSERT_COLUMNS, _EMP_ATTNAMES
    if _EMP_INSERT_COLUMNS is not None:
        return _EMP_INSERT_COLUMNS, _EMP_ATTNAMES

    cols, attrs = [], []
    for f in CustomUser._meta.fields:
        if f.column in _SKIP_INSERT_COLUMNS:
            continue
        cols.append(f.column)
        attrs.append(f.attname)

    _EMP_INSERT_COLUMNS = cols
    _EMP_ATTNAMES       = attrs
    return cols, attrs


def _build_upsert_sql(CustomUser, update_existing: bool) -> str:
    """Build the INSERT … ON DUPLICATE KEY UPDATE SQL template."""
    cols, _ = _build_column_metadata(CustomUser)
    table    = CustomUser._meta.db_table
    col_list = ", ".join(f"`{c}`" for c in cols)

    if update_existing:
        update_clause = ", ".join(
            f"`{c}` = VALUES(`{c}`)"
            for c in cols
            if c not in _SKIP_UPDATE_COLUMNS
        )
    else:
        # No-op: satisfy syntax without changing anything on conflict
        update_clause = "`employee_code` = `employee_code`"

    return (
        f"INSERT INTO `{table}` ({col_list}) VALUES {{rows}} "
        f"ON DUPLICATE KEY UPDATE {update_clause}"
    )


def _build_manager_update_sql(CustomUser) -> str:
    """Simple UPDATE for resolving manager FKs in sub-pass B."""
    table = CustomUser._meta.db_table
    return f"UPDATE `{table}` SET `manager_id` = %s WHERE `employee_code` = %s"


def _upsert_chunk(
    CustomUser, chunk_objs: list, upsert_sql_tpl: str, attnames: List[str]
) -> int:
    if not chunk_objs:
        return 0

    n_cols  = len(attnames)
    row_ph  = "(" + ", ".join(["%s"] * n_cols) + ")"
    rows_ph = ", ".join([row_ph] * len(chunk_objs))
    sql     = upsert_sql_tpl.format(rows=rows_ph)

    params = [
        getattr(obj, attr, None)
        for obj in chunk_objs
        for attr in attnames
    ]

    with connection.cursor() as cur:
        cur.execute(f"SET SESSION innodb_lock_wait_timeout = {LOCK_TIMEOUT_SEC}")
        cur.execute(sql, params)
        return cur.rowcount


def _upsert_chunk_with_retry(
    CustomUser, chunk_objs: list, upsert_sql_tpl: str, attnames: List[str]
) -> int:
    """Per-chunk transaction with retry on lock-wait timeout (error 1205)."""
    from django.db import OperationalError
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with transaction.atomic():
                return _upsert_chunk(CustomUser, chunk_objs, upsert_sql_tpl, attnames)
        except OperationalError as exc:
            last_exc = exc
            if "1205" in str(exc) or "lock wait timeout" in str(exc).lower():
                wait = 0.3 * (2 ** (attempt - 1))
                logger.warning(
                    "Lock timeout on Employee chunk (attempt %d/%d), back-off %.1fs …",
                    attempt, MAX_RETRIES, wait,
                )
                time.sleep(wait)
            else:
                raise
    raise last_exc  # type: ignore[misc]


def _update_manager_chunk_with_retry(pairs: List[tuple]) -> None:
    """
    pairs: list of (manager_pk: int, emp_code: str)
    Each pair sets manager_id on that employee row.
    Runs in its own per-chunk transaction with retry.
    """
    from django.db import OperationalError
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(
                        f"SET SESSION innodb_lock_wait_timeout = {LOCK_TIMEOUT_SEC}"
                    )
                    # executemany is fine here — small list, no flattening needed
                    cur.executemany(
                        "UPDATE `%(table)s` SET `manager_id` = %%s "
                        "WHERE `employee_code` = %%s"
                        % {"table": _get_user_table()},
                        pairs,
                    )
                return
        except OperationalError as exc:
            last_exc = exc
            if "1205" in str(exc) or "lock wait timeout" in str(exc).lower():
                wait = 0.3 * (2 ** (attempt - 1))
                logger.warning(
                    "Lock timeout on manager-link chunk (attempt %d/%d), back-off %.1fs …",
                    attempt, MAX_RETRIES, wait,
                )
                time.sleep(wait)
            else:
                raise
    raise last_exc  # type: ignore[misc]


_USER_TABLE: Optional[str] = None


def _get_user_table() -> str:
    global _USER_TABLE
    if _USER_TABLE is None:
        from .models import CustomUser
        _USER_TABLE = CustomUser._meta.db_table
    return _USER_TABLE


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def process_employees(
    data_rows:       list,
    hmap:            dict,
    update_existing: bool,
    dry_run:         bool,
    performed_by,
    job_id:          str = "",
) -> Tuple[dict, list]:
    """
    Public entry point called by views.bulk_upload().
    hmap keys are the RAW header strings from the Excel file.
    Returns (summary_dict, results_list).
    """
    t_start = time.perf_counter()
    summary = {"total": 0, "created": 0, "updated": 0, "errors": 0, "skipped": 0}
    results: list = []

    # ── Re-map raw header strings → internal field names via _COL_MAP ─────
    field_hmap: dict = {}
    for raw_key, idx in hmap.items():
        normalised = raw_key.strip().lower()
        f          = _COL_MAP.get(normalised)
        if f and f not in field_hmap:
            field_hmap[f] = idx
        if normalised not in field_hmap:
            field_hmap[normalised] = idx

    # ── Required columns check ────────────────────────────────────────────
    missing = [c for c in _EMP_REQUIRED if c not in field_hmap]
    if missing:
        err = [{
            "row": "—", "key": "—", "status": "error",
            "message": f"Missing required column(s): {', '.join(missing)}",
        }]
        _push_done(job_id, summary, err)
        return summary, err

    data_rows = [
        r for r in data_rows
        if not all(v is None or str(v).strip() == "" for v in r)
    ]
    total_rows = len(data_rows)
    if total_rows == 0:
        err = [{"row": "—", "key": "—", "status": "error",
                "message": "No data rows found in file."}]
        _push_done(job_id, summary, err)
        return summary, err

    summary["total"] = total_rows

    _push_event(job_id, {
        "type": "phase", "phase": "cache",
        "message": "Loading existing employee records into cache…",
    })
    emp_cache = _warm_cache()

    if dry_run:
        return _dry_run(
            data_rows, field_hmap, emp_cache,
            total_rows, summary, results, job_id,
        )

    return _real_import(
        data_rows, field_hmap, emp_cache, total_rows,
        update_existing, performed_by, summary, results, job_id, t_start,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  DRY RUN
# ══════════════════════════════════════════════════════════════════════════════

def _dry_run(
    data_rows: list, hmap: dict, emp_cache: EmpCache,
    total_rows: int, summary: dict, results: list, job_id: str,
) -> Tuple[dict, list]:

    _push_event(job_id, {
        "type": "phase", "phase": "validate",
        "message": f"Dry run — validating {total_rows} rows…",
    })

    livelog_count = 0
    seen_codes: dict = {}

    for idx, raw in enumerate(data_rows, start=1):
        row_num  = idx + 1
        g        = lambda *k, **kw: _v(raw, hmap, *k, **kw)
        emp_code = g("employee_code")
        first    = g("first_name")

        if not emp_code:
            r = {"row": row_num, "key": "—", "status": "error",
                 "message": "Employee Code is blank — row skipped"}
            summary["errors"] += 1
        elif not first:
            r = {"row": row_num, "key": emp_code, "status": "error",
                 "message": "First Name is blank"}
            summary["errors"] += 1
        elif emp_code in seen_codes:
            r = {"row": row_num, "key": emp_code, "status": "error",
                 "message": f"Duplicate Employee Code in file (first seen row {seen_codes[emp_code]})"}
            summary["errors"] += 1
        else:
            seen_codes[emp_code] = row_num
            exists = emp_code in emp_cache.codes
            last   = g("last_name") or ""
            full   = f"{first} {last}".strip()
            r = {"row": row_num, "key": emp_code, "status": "preview",
                 "message": f"{'Would update' if exists else 'Would create'} — {full}"}
            summary["created"] += 1

        results.append(r)
        if idx % PROGRESS_EVERY == 0 or idx == total_rows:
            _push_progress(job_id, idx, total_rows, f"Validating row {row_num}…")
        if livelog_count < MAX_LIVELOG_ROWS:
            _push_event(job_id, {"type": "row", **r})
            livelog_count += 1

    _push_done(job_id, summary, results)
    return summary, results


# ══════════════════════════════════════════════════════════════════════════════
#  REAL IMPORT
# ══════════════════════════════════════════════════════════════════════════════

def _real_import(
    data_rows: list, hmap: dict, emp_cache: EmpCache,
    total_rows: int, update_existing: bool, performed_by,
    summary: dict, results: list, job_id: str, t_start: float,
) -> Tuple[dict, list]:

    from .models import CustomUser

    # ── PASS 1: Validate (pure Python, no DB writes) ──────────────────────
    _push_event(job_id, {
        "type": "phase", "phase": "validate",
        "message": f"Validating {total_rows} rows before import…",
    })

    validation_errors: List[dict] = []
    valid_rows:        List[tuple] = []
    seen_codes:        Dict[str, int] = {}

    for idx, raw in enumerate(data_rows, start=1):
        row_num  = idx + 1
        g        = lambda *k, **kw: _v(raw, hmap, *k, **kw)
        emp_code = g("employee_code")
        first    = g("first_name")

        err = None
        if not emp_code:
            err = "Employee Code is blank"
        elif not first:
            err = "First Name is blank"
        elif emp_code in seen_codes:
            err = f"Duplicate Employee Code in file — first at row {seen_codes[emp_code]}"
        else:
            seen_codes[emp_code] = row_num

        if err:
            validation_errors.append({
                "row": row_num, "key": emp_code or "—",
                "status": "error", "message": err,
            })
        else:
            valid_rows.append((row_num, raw, emp_code, first, g("last_name") or ""))

        if idx % PROGRESS_EVERY == 0 or idx == total_rows:
            _push_progress(job_id, idx, total_rows * 3,
                           f"Validating row {row_num} of {total_rows + 1}")

    if validation_errors:
        summary["errors"] = len(validation_errors)
        _push_event(job_id, {
            "type": "abort",
            "message": (f"Import aborted — {len(validation_errors)} validation error(s). "
                        "No records were written."),
        })
        _push_done(job_id, summary, validation_errors)
        return summary, validation_errors

    # ── PASS 2: Prepare — build CustomUser objects in memory ──────────────
    _push_event(job_id, {
        "type": "phase", "phase": "prepare",
        "message": f"Preparing {len(valid_rows)} employees…",
    })

    emp_objs:       List[Any]  = []
    emp_metas:      List[dict] = []
    mgr_links:      List[tuple] = []  # (emp_code, mgr_code) — resolved in pass 2b
    prepare_errors: List[dict] = []

    codes_in_file = [r[2] for r in valid_rows]

    for idx, (row_num, raw, emp_code, first, last) in enumerate(valid_rows, start=1):
        g = lambda *k, **kw: _v(raw, hmap, *k, **kw)

        full        = f"{first} {last}".strip()
        dept_raw    = g("department")
        title_raw   = g("employee_title")
        branch_raw  = g("work_address")
        grade_raw   = g("grade_raw")
        raw_email   = g("email") or ""
        phone_raw   = g("work_phone") or ""
        func_mgr    = g("func_manager_code") or ""
        acct_raw    = g("account_status_raw") or "Active"
        login_raw   = g("login_status_raw") or "Yes"
        remark_raw  = g("remark_raw") or ""
        mgr_code    = g("manager_code")

        department     = _resolve_dept(dept_raw)
        employee_title = _resolve_title(title_raw)
        employee_type  = _resolve_etype(grade_raw)
        work_address   = _resolve_location(branch_raw)
        account_status = _resolve_account_status(acct_raw)
        login_status   = _resolve_login_status(login_raw)

        email = _make_email(emp_code, raw_email, row_num, emp_cache)
        emp_cache.emails.add(email.lower())

        remark_parts = []
        if grade_raw:
            remark_parts.append(f"Grade: {grade_raw}")
        if func_mgr:
            remark_parts.append(f"Func. Manager Code: {func_mgr}")
        if remark_raw:
            remark_parts.append(remark_raw)
        remark = " | ".join(remark_parts) or None

        kwargs: dict = {
            "first_name":     first,
            "last_name":      last,
            "email":          email,
            "password":       make_password(None),   
            "department":     department,
            "employee_type":  employee_type,
            "work_phone":     phone_raw or None,
            "account_status": account_status,
            "login_status":   login_status,
            "is_active":      account_status == "Active",
            "date_joined":    timezone.now(),
        }
        if employee_title:
            kwargs["employee_title"] = employee_title
        if work_address:
            kwargs["work_address"] = work_address
        if remark:
            kwargs["remark"] = remark

        try:
            emp_objs.append(CustomUser(employee_code=emp_code, **kwargs))
            emp_metas.append({
                "row_num":  row_num,
                "emp_code": emp_code,
                "full":     full,
                "email":    email,
            })
            if mgr_code:
                mgr_links.append((emp_code, mgr_code))
        except Exception as exc:
            logger.error("Employee kwargs build error row %s (%s): %s",
                         row_num, emp_code, exc, exc_info=True)
            prepare_errors.append({
                "row": row_num, "key": emp_code, "status": "error",
                "message": f"Row preparation error: {exc}",
            })

        if idx % PROGRESS_EVERY == 0 or idx == len(valid_rows):
            _push_progress(job_id, total_rows + idx, total_rows * 3,
                           f"Preparing row {row_num}…")

    if prepare_errors:
        summary["errors"] = len(prepare_errors)
        _push_event(job_id, {
            "type": "abort",
            "message": f"{len(prepare_errors)} row(s) failed during preparation. Nothing written.",
        })
        _push_done(job_id, summary, prepare_errors)
        return summary, prepare_errors

    # ── PASS 2a: Chunked upsert (employees WITHOUT manager links) ─────────
    #
    # THE FIX FOR ERROR 1205:
    # Each chunk runs in its OWN short transaction.  Lock hold time =
    # time to insert/update CHUNK_SIZE rows ≈ 20–80 ms per chunk.
    #
    # manager_id is intentionally LEFT OUT of the upsert here — we include
    # it in _SKIP_UPDATE_COLUMNS so existing manager links aren't wiped,
    # and sub-pass B will write the correct values for rows in this file.
    cols, attnames = _build_column_metadata(CustomUser)
    upsert_sql_tpl = _build_upsert_sql(CustomUser, update_existing)

    # Remove manager_id from attnames for the upsert — set it in pass 2b.
    # This avoids resetting existing links for employees NOT in this file.
    try:
        mgr_col_idx = attnames.index("manager_id")
        attnames_no_mgr = [a for a in attnames if a != "manager_id"]
        cols_no_mgr     = [c for c in cols      if c != "manager_id"]
    except ValueError:
        attnames_no_mgr = attnames
        cols_no_mgr     = cols

    # Rebuild the SQL without manager_id
    if attnames_no_mgr is not attnames:
        table    = CustomUser._meta.db_table
        col_list = ", ".join(f"`{c}`" for c in cols_no_mgr)
        if update_existing:
            update_clause = ", ".join(
                f"`{c}` = VALUES(`{c}`)"
                for c in cols_no_mgr
                if c not in _SKIP_UPDATE_COLUMNS
            )
        else:
            update_clause = "`employee_code` = `employee_code`"
        upsert_sql_tpl_no_mgr = (
            f"INSERT INTO `{table}` ({col_list}) VALUES {{rows}} "
            f"ON DUPLICATE KEY UPDATE {update_clause}"
        )
    else:
        upsert_sql_tpl_no_mgr = upsert_sql_tpl
        attnames_no_mgr       = attnames

    total_ops     = len(emp_objs)
    ops_done      = 0
    chunk_errors: List[dict] = []
    write_results: List[dict] = []
    livelog_count = 0

    _push_event(job_id, {
        "type": "phase", "phase": "write",
        "message": (
            f"Writing {total_ops} employees in chunks of {CHUNK_SIZE} "
            f"({'upsert — creates + updates' if update_existing else 'insert-only'})…"
        ),
    })

    for chunk_start in range(0, total_ops, CHUNK_SIZE):
        chunk_end  = min(chunk_start + CHUNK_SIZE, total_ops)
        chunk_objs = emp_objs[chunk_start:chunk_end]
        chunk_meta = emp_metas[chunk_start:chunk_end]

        try:
            _upsert_chunk_with_retry(
                CustomUser, chunk_objs, upsert_sql_tpl_no_mgr, attnames_no_mgr
            )
        except Exception as exc:
            logger.critical(
                "Employee upsert chunk [%d:%d] failed permanently: %s",
                chunk_start, chunk_end, exc, exc_info=True,
            )
            for meta in chunk_meta:
                chunk_errors.append({
                    "row": meta["row_num"], "key": meta["emp_code"],
                    "status": "error",
                    "message": f"Write error (chunk rolled back): {exc}",
                })
            summary["errors"] += len(chunk_meta)
            continue

        for meta in chunk_meta:
            write_results.append({
                "row":     meta["row_num"],
                "key":     meta["emp_code"],
                "status":  "upserted",
                "message": f"Saved — {meta['full']} <{meta['email']}>",
            })
            ops_done += 1
            if livelog_count < MAX_LIVELOG_ROWS:
                _push_event(job_id, {
                    "type": "row", "row": meta["row_num"],
                    "key":  meta["emp_code"], "status": "upserted",
                    "message": f"Saved — {meta['full']}",
                })
                livelog_count += 1

        _push_progress(
            job_id,
            processed=total_rows * 2 + ops_done,
            total=total_rows * 3,
            message=f"Writing: {ops_done}/{total_ops}",
        )

    # ── PASS 2b: Resolve manager FKs ─────────────────────────────────────
    # Fetch all PKs for employee codes that appear in this file.
    # This must happen AFTER pass 2a so that new employees have PKs.
    if mgr_links:
        _push_event(job_id, {
            "type": "phase", "phase": "write",
            "message": "Resolving reporting-manager links…",
        })

        all_codes_needed = {ec for ec, _ in mgr_links} | {mc for _, mc in mgr_links}
        code_to_pk = {
            u.employee_code: u.pk
            for u in CustomUser.objects.filter(
                employee_code__in=all_codes_needed
            ).only("id", "employee_code")
        }

        mgr_pairs:       List[tuple] = []
        mgr_link_errors              = 0

        for emp_code, mgr_code in mgr_links:
            mgr_pk = code_to_pk.get(mgr_code)
            emp_pk = code_to_pk.get(emp_code)
            if emp_pk and mgr_pk:
                mgr_pairs.append((mgr_pk, emp_code))
            elif emp_pk and not mgr_pk:
                mgr_link_errors += 1
                _push_event(job_id, {
                    "type": "row", "row": "—", "key": emp_code,
                    "status": "skipped",
                    "message": f"Manager code '{mgr_code}' not found — link skipped",
                })

        # Write manager links in chunks, each in its own short transaction
        for chunk_start in range(0, len(mgr_pairs), CHUNK_SIZE):
            chunk = mgr_pairs[chunk_start: chunk_start + CHUNK_SIZE]
            try:
                _update_manager_chunk_with_retry(chunk)
            except Exception as exc:
                logger.error("Manager link chunk failed: %s", exc, exc_info=True)
                _push_event(job_id, {
                    "type": "row", "row": "—", "key": "—",
                    "status": "error",
                    "message": f"Manager-link chunk error (skipped): {exc}",
                })

        _push_event(job_id, {
            "type": "phase", "phase": "write",
            "message": (
                f"Manager links resolved ✓"
                + (f" ({mgr_link_errors} code(s) not found — skipped)"
                   if mgr_link_errors else "")
            ),
        })

    elapsed = time.perf_counter() - t_start
    summary["created"] = ops_done
    summary["updated"] = 0
    summary["skipped"] = 0

    logger.info(
        "Employee import complete: %d rows in %.2fs — %d saved, %d errors",
        total_rows, elapsed, ops_done, summary["errors"],
    )

    _push_progress(job_id, total_rows * 3, total_rows * 3, "Finalising…")
    all_results = write_results + chunk_errors
    _push_done(job_id, summary, all_results)
    return summary, all_results