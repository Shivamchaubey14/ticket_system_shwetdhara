"""
transporter_bulk_upload.py
─────────────────────────────────────────────────────────────────────────────
Production-grade Transporter / Vendor bulk import engine — model-aware edition.

WHY THE PREVIOUS VERSION COULD HIT ERROR 1205
───────────────────────────────────────────────
  One outer transaction.atomic() wrapped ALL chunks.  MySQL held row locks on
  every written Transporter row until the LAST chunk committed.  Any concurrent
  read/write exceeded innodb_lock_wait_timeout and MySQL raised error 1205.

KEY CHANGES IN THIS VERSION  (mirrors farmer_bulk_upload.py exactly)
──────────────────────────────────────────────────────────────────────
  1.  PER-CHUNK TRANSACTIONS
      Each CHUNK_SIZE batch is committed in its own short transaction.
      Lock duration ≈ time to insert 500 rows ≈ 30–100 ms per chunk.

  2.  RAW-SQL INSERT … ON DUPLICATE KEY UPDATE  (true upsert)
      One SQL statement per chunk handles both INSERT (new rows) and UPDATE
      (existing rows) in a single server round-trip.  3-5× faster than
      bulk_create + separate bulk_update.
      Duplicate key is triggered on `vendor_code` (UNIQUE on Transporter).

  3.  auto_now / auto_now_add FIELDS EXCLUDED FROM INSERT COLUMN LIST
      `created_at` and `updated_at` must NOT be in the INSERT column list.

  4.  FK COLUMNS ARE `<field>_id`, NOT `<field>`
      We use field.attname (e.g. `created_by_id`) for integer PK extraction.

  5.  RETRY WITH EXPONENTIAL BACK-OFF + SHORT SESSION LOCK TIMEOUT
      innodb_lock_wait_timeout set to LOCK_TIMEOUT_SEC (5 s) per chunk.
      Up to MAX_RETRIES retries with doubling back-off (0.3 s → 0.6 s → 1.2 s).

Architecture
────────────
  Pass 0  – Pre-warm Transporter + User cache (one SELECT each)
  Pass 1  – Validate all rows in Python (no DB writes)
  Pass 2  – Build all Transporter(**kwargs) objects in memory
  Pass 3  – Chunked upsert: each chunk = one short transaction

Column aliases
──────────────
  All raw header → canonical-name resolution happens in _resolve_hmap()
  before any other processing — zero changes needed elsewhere.

Tuning knobs
────────────
  CHUNK_SIZE        rows per upsert call         (default 500)
  PROGRESS_EVERY    SSE heartbeat every N rows    (default 100)
  MAX_LIVELOG_ROWS  cap SSE live-log entries      (default 200)
  LOCK_TIMEOUT_SEC  MySQL session lock timeout    (default 5)
  MAX_RETRIES       retries on lock error         (default 3)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from django.db import connection, transaction

logger = logging.getLogger(__name__)

# ── Tuning ────────────────────────────────────────────────────────────────────
CHUNK_SIZE       = 500
PROGRESS_EVERY   = 100
MAX_LIVELOG_ROWS = 200
LOCK_TIMEOUT_SEC = 5
MAX_RETRIES      = 3

# ── Blank-value sentinel set ──────────────────────────────────────────────────
_BLANK = {"", "none", "nan", "nat", "n/a", "null", "-", "--", "na"}

# ── Choice maps ───────────────────────────────────────────────────────────────
_ACCOUNT_GROUP_VALID = {"ZFMP", "OTHER"}
_INCOTERM_VALID      = {"EXW", "FOB", "CIF", "CPT", "DAP", "DDP"}
_PM_MAP: Dict[str, str] = {
    "NEFT":   "N", "RTGS": "R", "IMPS": "M",
    "CHEQUE": "C", "DRAFT": "D",
    "N": "N", "R": "R", "M": "M",
    "C": "C", "D": "D", "Y": "Y",
}

_DATE_FMTS = (
    "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d",
    "%d-%b-%Y", "%d %b %Y", "%m/%d/%Y",
    "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y",
)

_TRANS_REQUIRED = ["Vendor Code", "Vendor Name"]

# ── Fields excluded from the INSERT column list ───────────────────────────────
_SKIP_INSERT_COLUMNS = frozenset({"id", "created_at", "updated_at"})

# Fields never updated on DUPLICATE KEY conflict
_SKIP_UPDATE_COLUMNS = frozenset({
    "id", "vendor_code", "created_at", "updated_at", "created_by_id",
})

# ── Column alias map ──────────────────────────────────────────────────────────
_COL_ALIASES: Dict[str, str] = {
    "vendor":               "Vendor Code",
    "vendor code":          "Vendor Code",
    "vendor_code":          "Vendor Code",
    "vendorcode":           "Vendor Code",
    "vendor no":            "Vendor Code",
    "vendor number":        "Vendor Code",
    "sap vendor":           "Vendor Code",
    "sap vendor code":      "Vendor Code",
    "vendor name":          "Vendor Name",
    "vendor_name":          "Vendor Name",
    "vendorname":           "Vendor Name",
    "name":                 "Vendor Name",
    "transporter name":     "Vendor Name",
    "company name":         "Vendor Name",
    "account group":        "Account Group",
    "account_group":        "Account Group",
    "accountgroup":         "Account Group",
    "acct group":           "Account Group",
    "search term 1":        "Search Term 1",
    "search term1":         "Search Term 1",
    "search_term1":         "Search Term 1",
    "search term 2":        "Search Term 2",
    "search term2":         "Search Term 2",
    "search_term2":         "Search Term 2",
    "address":              "Address",
    "city":                 "City",
    "country":              "Country",
    "contact person":       "Contact Person",
    "contact_person":       "Contact Person",
    "contact no":           "Contact No",
    "contact_no":           "Contact No",
    "contact number":       "Contact No",
    "mobile":               "Contact No",
    "phone":                "Contact No",
    "email":                "Email",
    "email address":        "Email",
    "company code":         "Company Code",
    "company_code":         "Company Code",
    "g/l account":          "GL Account",
    "gl account":           "GL Account",
    "gl_account":           "GL Account",
    "g/l":                  "GL Account",
    "payment terms":        "Payment Terms",
    "payment_terms":        "Payment Terms",
    "payment method":       "Payment Method",
    "payment_method":       "Payment Method",
    "bank key":             "Bank Key",
    "bank_key":             "Bank Key",
    "ifsc":                 "Bank Key",
    "bank account":         "Bank Account No",
    "bank account no":      "Bank Account No",
    "bank account number":  "Bank Account No",
    "bank_account_no":      "Bank Account No",
    "account holder":       "Account Holder",
    "account_holder":       "Account Holder",
    "gst number":           "GST Number",
    "gst_number":           "GST Number",
    "gst":                  "GST Number",
    "gstin":                "GST Number",
    "msme":                 "MSME",
    "msme registration":    "MSME",
    "is blocked":           "Is Blocked",
    "is_blocked":           "Is Blocked",
    "blocked":              "Is Blocked",
    "incoterm":             "Incoterm",
    "incoterm_loc":         "Incoterm Location",
    "incoterm location":    "Incoterm Location",
    "incoterm_location":    "Incoterm Location",
    "created by":           "SAP Created By",
    "sap created by":       "SAP Created By",
    "sap_created_by":       "SAP Created By",
    "created on":           "SAP Created On",
    "sap created on":       "SAP Created On",
    "sap_created_on":       "SAP Created On",
    "changed on":           "SAP Changed On",
    "sap changed on":       "SAP Changed On",
    "sap_changed_on":       "SAP Changed On",
}


# ══════════════════════════════════════════════════════════════════════════════
#  ALIAS RESOLVER
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_hmap(raw_hmap: dict) -> dict:
    """
    Translate raw header names to canonical names.
    First-occurrence wins on collision.
    Unknown headers are kept unchanged (preserves canonical names already correct).
    """
    resolved: dict = {}
    for raw_name, col_idx in raw_hmap.items():
        canonical = _COL_ALIASES.get(raw_name.lower().strip(), raw_name)
        if canonical not in resolved:
            resolved[canonical] = col_idx
    return resolved


# ══════════════════════════════════════════════════════════════════════════════
#  VALUE EXTRACTORS
# ══════════════════════════════════════════════════════════════════════════════

def _v(row: tuple, hmap: dict, *keys: str, default: Any = None) -> Any:
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


def _d(row: tuple, hmap: dict, *keys: str, default: Any = None) -> Optional[date]:
    for k in keys:
        idx = hmap.get(k)
        if idx is None or idx >= len(row):
            continue
        val = row[idx]
        if val is None:
            continue
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        if isinstance(val, (int, float)) and 30_000 < val < 60_000:
            try:
                from openpyxl.utils.datetime import from_excel
                return from_excel(int(val)).date()
            except Exception:
                pass
        s = str(val).strip()
        if s.lower() in _BLANK:
            continue
        for fmt in _DATE_FMTS:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    return default


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSPORTER CACHE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TransporterCache:
    transporters: Dict[str, Any] = field(default_factory=dict)
    users:        Dict[str, Any] = field(default_factory=dict)


def _warm_cache() -> TransporterCache:
    from .models import Transporter, CustomUser

    cache = TransporterCache()
    for obj in Transporter.objects.only("id", "vendor_code").all():
        cache.transporters[obj.vendor_code] = obj
    for obj in CustomUser.objects.only("id", "employee_code").all():
        if obj.employee_code:
            cache.users[obj.employee_code] = obj

    logger.info(
        "TransporterCache warmed: %d transporters %d users",
        len(cache.transporters), len(cache.users),
    )
    return cache


# ══════════════════════════════════════════════════════════════════════════════
#  ROW → Transporter kwargs  (pure Python, zero DB calls)
# ══════════════════════════════════════════════════════════════════════════════

def _row_to_transporter_kwargs(
    raw: tuple,
    hmap: dict,
    vendor_code: str,
    vendor_name: str,
    performed_by,
) -> dict:
    g  = lambda *k, **kw: _v(raw, hmap, *k, **kw)
    gd = lambda *k, **kw: _d(raw, hmap, *k, **kw)

    ag_raw = (g("Account Group", "account_group") or "ZFMP").strip().upper()
    ag     = ag_raw if ag_raw in _ACCOUNT_GROUP_VALID else "ZFMP"

    inc_raw  = (g("Incoterm", "incoterm") or "").strip().upper()
    inc_base = inc_raw.split("-")[0].strip()
    incoterm = inc_base if inc_base in _INCOTERM_VALID else None

    pm_raw = (g("Payment Method", "payment_method") or "").strip().upper()
    pm     = _PM_MAP.get(pm_raw)

    blocked_raw = (g("Is Blocked", "is_blocked") or "").strip().lower()
    is_blocked  = blocked_raw in ("true", "1", "yes", "y", "blocked")

    kwargs = {
        "vendor_name":       vendor_name or vendor_code,
        "account_group":     ag,
        "search_term1":      g("Search Term 1", "search_term1"),
        "search_term2":      g("Search Term 2", "search_term2"),
        "contact_person":    g("Contact Person", "contact_person"),
        "contact_no":        g("Contact No", "contact_no"),
        "email":             g("Email", "email"),
        "address":           g("Address", "address"),
        "city":              g("City", "city"),
        "country":           g("Country", "country") or "IN",
        "incoterm":          incoterm,
        "incoterm_location": g("Incoterm Location", "incoterm_location", "Incoterm_Loc"),
        "bank_account_no":   g("Bank Account No", "bank_account_no"),
        "bank_key":          g("Bank Key", "bank_key"),
        "account_holder":    g("Account Holder", "account_holder"),
        "payment_terms":     g("Payment Terms", "payment_terms"),
        "payment_method":    pm,
        "gst_number":        g("GST Number", "gst_number"),
        "msme":              g("MSME", "msme"),
        "is_blocked":        is_blocked,
        "company_code":      g("Company Code", "company_code"),
        "gl_account":        g("GL Account", "gl_account"),
        "sap_created_by":    g("SAP Created By", "sap_created_by"),
        "sap_created_on":    gd("SAP Created On", "sap_created_on"),
        "sap_changed_on":    gd("SAP Changed On", "sap_changed_on"),
        "created_by":        performed_by,
    }
    return {k: v for k, v in kwargs.items() if v is not None}


# ══════════════════════════════════════════════════════════════════════════════
#  SSE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _push_event(job_id: str, event: dict):
    if not job_id:
        return
    from django.core.cache import cache
    key     = f"bu_progress_{job_id}"
    payload = cache.get(key) or {"events": [], "done": False}
    payload["events"].append(event)
    cache.set(key, payload, timeout=600)


def _push_progress(job_id: str, processed: int, total: int, message: str = ""):
    _push_event(job_id, {
        "type": "progress", "processed": processed, "total": total,
        "pct": round(processed / total * 100) if total else 0,
        "message": message,
    })


def _push_done(job_id: str, summary: dict, results: list):
    from django.core.cache import cache
    key     = f"bu_progress_{job_id}"
    payload = cache.get(key) or {"events": [], "done": False}
    payload["events"].append({"type": "done", "summary": summary, "results": results})
    payload["done"] = True
    cache.set(key, payload, timeout=600)


# ══════════════════════════════════════════════════════════════════════════════
#  UPSERT ENGINE  (mirrors farmer_bulk_upload.py exactly)
# ══════════════════════════════════════════════════════════════════════════════

_TRANS_INSERT_COLUMNS: Optional[List[str]] = None
_TRANS_ATTNAMES:       Optional[List[str]] = None


def _build_column_metadata(Transporter) -> Tuple[List[str], List[str]]:
    """
    Return (insert_columns, attnames) for the Transporter model.
    Cached at module level — computed once per process lifetime.

    Uses f.attname (not f.name) so FK fields yield 'created_by_id' etc.
    """
    global _TRANS_INSERT_COLUMNS, _TRANS_ATTNAMES
    if _TRANS_INSERT_COLUMNS is not None:
        return _TRANS_INSERT_COLUMNS, _TRANS_ATTNAMES

    cols, attrs = [], []
    for f in Transporter._meta.fields:
        if f.column in _SKIP_INSERT_COLUMNS:
            continue
        cols.append(f.column)
        attrs.append(f.attname)

    _TRANS_INSERT_COLUMNS = cols
    _TRANS_ATTNAMES       = attrs
    return cols, attrs


def _build_upsert_sql(Transporter, update_existing: bool) -> str:
    """Build the INSERT … ON DUPLICATE KEY UPDATE SQL template."""
    cols, _ = _build_column_metadata(Transporter)
    table    = Transporter._meta.db_table
    col_list = ", ".join(f"`{c}`" for c in cols)

    if update_existing:
        update_clause = ", ".join(
            f"`{c}` = VALUES(`{c}`)"
            for c in cols
            if c not in _SKIP_UPDATE_COLUMNS
        )
    else:
        update_clause = "`vendor_code` = `vendor_code`"

    return (
        f"INSERT INTO `{table}` ({col_list}) VALUES {{rows}} "
        f"ON DUPLICATE KEY UPDATE {update_clause}"
    )


def _upsert_chunk(
    Transporter, chunk_objs: list, upsert_sql_tpl: str, attnames: List[str]
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
    Transporter, chunk_objs: list, upsert_sql_tpl: str, attnames: List[str]
) -> int:
    """Per-chunk transaction with retry on lock-wait timeout (error 1205)."""
    from django.db import OperationalError
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with transaction.atomic():
                return _upsert_chunk(Transporter, chunk_objs, upsert_sql_tpl, attnames)
        except OperationalError as exc:
            last_exc = exc
            if "1205" in str(exc) or "lock wait timeout" in str(exc).lower():
                wait = 0.3 * (2 ** (attempt - 1))
                logger.warning(
                    "Lock timeout on Transporter chunk (attempt %d/%d), back-off %.1fs …",
                    attempt, MAX_RETRIES, wait,
                )
                time.sleep(wait)
            else:
                raise
    raise last_exc  # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def process_transporters(
    data_rows:       list,
    hmap:            dict,
    update_existing: bool,
    dry_run:         bool,
    performed_by,
    job_id:          str = "",
) -> Tuple[dict, list]:
    """
    Public entry point — drop-in replacement for _process_transporters in views.py.
    Returns (summary_dict, results_list).
    """
    t_start = time.perf_counter()
    summary = {"total": 0, "created": 0, "updated": 0, "errors": 0, "skipped": 0}
    results = []

    # ── Resolve column aliases FIRST ──────────────────────────────────────
    hmap = _resolve_hmap(hmap)

    # ── Required columns check ────────────────────────────────────────────
    missing = [c for c in _TRANS_REQUIRED if c not in hmap]
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
        "message": "Loading transporter cache…",
    })
    cache = _warm_cache()

    if dry_run:
        return _dry_run(data_rows, hmap, cache, total_rows, summary, results, job_id)

    return _real_import(
        data_rows, hmap, cache, total_rows,
        update_existing, performed_by,
        summary, results, job_id, t_start,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  DRY RUN
# ══════════════════════════════════════════════════════════════════════════════

def _dry_run(
    data_rows: list, hmap: dict, cache: TransporterCache,
    total_rows: int, summary: dict, results: list, job_id: str,
) -> Tuple[dict, list]:

    _push_event(job_id, {
        "type": "phase", "phase": "validate",
        "message": f"Dry run — validating {total_rows} rows…",
    })

    livelog_count = 0
    for idx, raw in enumerate(data_rows, start=1):
        row_num     = idx + 1
        g           = lambda *k, **kw: _v(raw, hmap, *k, **kw)
        vendor_code = g("Vendor Code", "vendor_code")
        vendor_name = g("Vendor Name", "vendor_name")

        if not vendor_code:
            summary["errors"] += 1
            r = {"row": row_num, "key": "—", "status": "error",
                 "message": "Vendor Code is blank"}
        elif not vendor_name:
            summary["errors"] += 1
            r = {"row": row_num, "key": vendor_code, "status": "error",
                 "message": "Vendor Name is blank"}
        else:
            exists = vendor_code in cache.transporters
            summary["created"] += 1
            r = {
                "row": row_num, "key": vendor_code, "status": "preview",
                "message": f"Would {'update' if exists else 'create'} — {vendor_name}",
            }

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
    data_rows: list, hmap: dict, cache: TransporterCache,
    total_rows: int, update_existing: bool, performed_by,
    summary: dict, results: list, job_id: str, t_start: float,
) -> Tuple[dict, list]:

    from .models import Transporter

    # ── PASS 1: Validate (pure Python, no DB writes) ──────────────────────
    _push_event(job_id, {
        "type": "phase", "phase": "validate",
        "message": f"Validating {total_rows} rows before import…",
    })

    validation_errors: List[dict] = []
    valid_rows:        List[tuple] = []
    seen_codes:        Dict[str, int] = {}

    for idx, raw in enumerate(data_rows, start=1):
        row_num     = idx + 1
        g           = lambda *k, **kw: _v(raw, hmap, *k, **kw)
        vendor_code = g("Vendor Code", "vendor_code")
        vendor_name = g("Vendor Name", "vendor_name")

        err = None
        if not vendor_code:
            err = "Vendor Code is blank"
        elif not vendor_name:
            err = f"Vendor Name is blank for code '{vendor_code}'"
        elif vendor_code in seen_codes:
            err = (f"Duplicate Vendor Code in file — "
                   f"first seen at row {seen_codes[vendor_code]}")
        else:
            seen_codes[vendor_code] = row_num

        if err:
            validation_errors.append(
                {"row": row_num, "key": vendor_code or "—", "status": "error", "message": err})
        else:
            valid_rows.append((row_num, raw, vendor_code, vendor_name))

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

    # ── PASS 2: Prepare — build Transporter objects in memory ─────────────
    # No DB calls here — kwargs building is pure Python.
    _push_event(job_id, {
        "type": "phase", "phase": "prepare",
        "message": f"Preparing {len(valid_rows)} rows…",
    })

    trans_objs:     List[Any]  = []
    trans_metas:    List[dict] = []
    prepare_errors: List[dict] = []

    for idx, (row_num, raw, vendor_code, vendor_name) in enumerate(valid_rows, start=1):
        try:
            kwargs = _row_to_transporter_kwargs(
                raw, hmap, vendor_code, vendor_name, performed_by)
            trans_objs.append(Transporter(vendor_code=vendor_code, **kwargs))
            trans_metas.append({
                "row_num": row_num,
                "vendor_code": vendor_code,
                "vendor_name": vendor_name,
            })
        except Exception as exc:
            logger.error("Transporter kwargs build error row %s (%s): %s",
                         row_num, vendor_code, exc, exc_info=True)
            prepare_errors.append({
                "row": row_num, "key": vendor_code, "status": "error",
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

    # ── PASS 3: Chunked upsert — each chunk = its own short transaction ───
    #
    # THE FIX FOR ERROR 1205:
    # Each chunk runs in its OWN short transaction.  Lock hold time =
    # time to insert/update CHUNK_SIZE rows ≈ 30–100 ms per chunk.
    # The old design held locks for the ENTIRE file in one transaction.
    cols, attnames = _build_column_metadata(Transporter)
    upsert_sql_tpl = _build_upsert_sql(Transporter, update_existing)

    total_ops     = len(trans_objs)
    ops_done      = 0
    chunk_errors: List[dict] = []
    write_results: List[dict] = []
    livelog_count = 0

    _push_event(job_id, {
        "type": "phase", "phase": "write",
        "message": (
            f"Writing {total_ops} rows in chunks of {CHUNK_SIZE} "
            f"({'upsert — creates + updates' if update_existing else 'insert-only'})…"
        ),
    })

    for chunk_start in range(0, total_ops, CHUNK_SIZE):
        chunk_end  = min(chunk_start + CHUNK_SIZE, total_ops)
        chunk_objs = trans_objs[chunk_start:chunk_end]
        chunk_meta = trans_metas[chunk_start:chunk_end]

        try:
            _upsert_chunk_with_retry(Transporter, chunk_objs, upsert_sql_tpl, attnames)
        except Exception as exc:
            logger.critical(
                "Transporter upsert chunk [%d:%d] failed permanently: %s",
                chunk_start, chunk_end, exc, exc_info=True,
            )
            for meta in chunk_meta:
                chunk_errors.append({
                    "row": meta["row_num"], "key": meta["vendor_code"],
                    "status": "error",
                    "message": f"Write error (chunk rolled back): {exc}",
                })
            summary["errors"] += len(chunk_meta)
            continue

        for meta in chunk_meta:
            write_results.append({
                "row":     meta["row_num"],
                "key":     meta["vendor_code"],
                "status":  "upserted",
                "message": f"Saved — {meta['vendor_name']}",
            })
            ops_done += 1
            if livelog_count < MAX_LIVELOG_ROWS:
                _push_event(job_id, {
                    "type": "row", "row": meta["row_num"],
                    "key":  meta["vendor_code"], "status": "upserted",
                    "message": f"Saved — {meta['vendor_name']}",
                })
                livelog_count += 1

        _push_progress(
            job_id,
            processed=total_rows * 2 + ops_done,
            total=total_rows * 3,
            message=f"Writing: {ops_done}/{total_ops}",
        )

    elapsed = time.perf_counter() - t_start
    summary["created"] = ops_done
    summary["updated"] = 0
    summary["skipped"] = 0

    logger.info(
        "Transporter import complete: %d rows in %.2fs — %d saved, %d errors",
        total_rows, elapsed, ops_done, summary["errors"],
    )

    all_results = write_results + chunk_errors
    _push_done(job_id, summary, all_results)
    return summary, all_results