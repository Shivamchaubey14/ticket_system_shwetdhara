"""
sahayak_bulk_upload.py
─────────────────────────────────────────────────────────────────────────────
Production-grade Sahayak / MPP bulk import engine — model-aware edition.

WHY THE PREVIOUS VERSION COULD HIT ERROR 1205
───────────────────────────────────────────────
  One outer transaction.atomic() wrapped ALL chunks.  MySQL held row locks on
  every written MPP row until the LAST chunk committed.  Any concurrent
  read/write on the MPP table had to wait for the entire import — on large
  files that exceeds innodb_lock_wait_timeout (default 50 s) and MySQL
  raises error 1205.

KEY CHANGES IN THIS VERSION  (mirrors farmer_bulk_upload.py exactly)
──────────────────────────────────────────────────────────────────────
  1.  PER-CHUNK TRANSACTIONS
      Each CHUNK_SIZE batch is committed in its own short transaction.
      Lock duration ≈ time to insert 500 rows ≈ 30–100 ms per chunk.

  2.  RAW-SQL INSERT … ON DUPLICATE KEY UPDATE  (true upsert)
      One SQL statement per chunk handles both INSERT (new rows) and UPDATE
      (existing rows) in a single server round-trip.  3-5× faster than
      bulk_create + separate bulk_update.
      Duplicate key is triggered on `unique_code` (UNIQUE on MPP).

  3.  GEO get_or_create MOVED BEFORE WRITE TRANSACTIONS
      All _gc_* geography auto-creates happen during Pass 2 (prepare),
      completely outside any MPP write transaction.

  4.  auto_now / auto_now_add FIELDS EXCLUDED FROM INSERT COLUMN LIST
      `created_at` (auto_now_add) and `updated_at` (auto_now) must NOT be
      in the INSERT column list — MySQL sets them via DEFAULT / ON UPDATE.

  5.  FK COLUMNS ARE `<field>_id`, NOT `<field>`
      We use field.attname (e.g. `plant_id`, `mcc_id`, `district_id`) to
      pull the correct integer PK from the in-memory MPP object.

  6.  RETRY WITH EXPONENTIAL BACK-OFF + SHORT SESSION LOCK TIMEOUT
      innodb_lock_wait_timeout is set to LOCK_TIMEOUT_SEC (5 s) per chunk.
      Up to MAX_RETRIES retries with doubling back-off (0.3 s → 0.6 s → 1.2 s).

Architecture
────────────
  Pass 0  – Pre-warm caches (State/District/Tehsil/Village/Hamlet/Plant/BMC/MCC/MPP)
  Pass 1  – Validate all rows in Python (no DB writes)
  Pass 2  – Build all MPP(**kwargs) objects; resolve all geo FKs
              (geo get_or_create happen here, outside write transactions)
  Pass 3  – Chunked upsert: each chunk = one short transaction

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

# ── Valid choices ─────────────────────────────────────────────────────────────
_STATUS_VALID = {"Active", "Inactive", "Closed"}

# ── Required header columns (alias-aware) ─────────────────────────────────────
# Each tuple = (canonical label, list-of-acceptable-hmap-keys)
_SAHAYAK_REQUIRED_ALIASES = [
    ("MPP Unique Code", ["mpp_code",      "MPP Unique Code", "mpp_unique_code"]),
    ("MPP Name",        ["mpp_name",       "MPP Name"]),
    ("Plant Name",      ["plant_name",     "Plant Name"]),
    ("MCC Name",        ["mcc_name",       "MCC Name"]),
    ("BMC Name",        ["bmc_name",       "BMC Name"]),
    ("State Name",      ["state_name",     "State Name"]),
    ("District Name",   ["district_name",  "District Name"]),
    ("Tehsil Name",     ["tehshil_name",   "tehsil_name",   "Tehsil Name"]),
    ("Village Name",    ["village_name",   "Village Name"]),
]

_SAHAYAK_REQUIRED = [label for label, _ in _SAHAYAK_REQUIRED_ALIASES]

_DATE_FMTS = (
    "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d",
    "%d-%b-%Y", "%d %b %Y", "%m/%d/%Y",
    "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y",
)

# ── Fields excluded from the INSERT column list ───────────────────────────────
# 'id'         → auto-increment, MySQL assigns it
# 'created_at' → auto_now_add=True, MySQL DEFAULT handles it
# 'updated_at' → auto_now=True,     MySQL ON UPDATE handles it
_SKIP_INSERT_COLUMNS = frozenset({"id", "created_at", "updated_at"})

# Fields never updated on DUPLICATE KEY conflict (identity + audit creation)
_SKIP_UPDATE_COLUMNS = frozenset({
    "id", "unique_code", "created_at", "updated_at",
})


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
#  GEO / HIERARCHY CACHE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SahayakCache:
    states:    Dict[str, Any] = field(default_factory=dict)
    districts: Dict[tuple, Any] = field(default_factory=dict)
    tehsils:   Dict[tuple, Any] = field(default_factory=dict)
    villages:  Dict[tuple, Any] = field(default_factory=dict)
    hamlets:   Dict[tuple, Any] = field(default_factory=dict)
    plants:    Dict[str, Any]   = field(default_factory=dict)
    bmcs:      Dict[tuple, Any] = field(default_factory=dict)
    mccs:      Dict[tuple, Any] = field(default_factory=dict)
    mpps:      Dict[str, Any]   = field(default_factory=dict)
    users:     Dict[str, Any]   = field(default_factory=dict)


def _warm_cache() -> SahayakCache:
    from .models import State, District, Tehsil, Village, Hamlet, Plant, BMC, MCC, MPP, CustomUser

    cache = SahayakCache()
    for obj in State.objects.all():
        cache.states[obj.name.upper()] = obj
    for obj in District.objects.select_related("state").all():
        cache.districts[(obj.state_id, obj.code)] = obj
    for obj in Tehsil.objects.select_related("district").all():
        cache.tehsils[(obj.district_id, obj.code)] = obj
    for obj in Village.objects.select_related("tehsil").all():
        cache.villages[(obj.tehsil_id, obj.code)] = obj
    for obj in Hamlet.objects.select_related("village").all():
        cache.hamlets[(obj.village_id, obj.code)] = obj
    for obj in Plant.objects.all():
        cache.plants[obj.code] = obj
    for obj in BMC.objects.select_related("plant").all():
        cache.bmcs[(obj.plant_id, obj.code)] = obj
    for obj in MCC.objects.select_related("bmc").all():
        cache.mccs[(obj.bmc_id, obj.code)] = obj
    for obj in MPP.objects.all():
        cache.mpps[obj.unique_code] = obj
    for obj in CustomUser.objects.all():
        if obj.employee_code:
            cache.users[obj.employee_code] = obj

    logger.info(
        "SahayakCache warmed: %d states %d districts %d tehsils "
        "%d villages %d hamlets %d plants %d BMCs %d MCCs %d MPPs %d users",
        len(cache.states), len(cache.districts), len(cache.tehsils),
        len(cache.villages), len(cache.hamlets), len(cache.plants),
        len(cache.bmcs), len(cache.mccs), len(cache.mpps), len(cache.users),
    )
    return cache


# ── Cached get-or-create helpers ─────────────────────────────────────────────

def _gc_state(cache: SahayakCache, name: str):
    from .models import State
    key = (name or "UTTAR PRADESH").strip().upper()
    if key not in cache.states:
        obj, _ = State.objects.get_or_create(name=key)
        cache.states[key] = obj
    return cache.states[key]


def _gc_district(cache: SahayakCache, state_obj, code: str, name: str):
    from .models import District
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    key  = (state_obj.pk, code)
    if key not in cache.districts:
        obj, created = District.objects.get_or_create(
            state=state_obj, code=code, defaults={"name": name})
        if not created and name != "UNKNOWN" and obj.name != name:
            obj.name = name
            obj.save(update_fields=["name"])
        cache.districts[key] = obj
    return cache.districts[key]


def _gc_tehsil(cache: SahayakCache, district_obj, code: str, name: str):
    from .models import Tehsil
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    key  = (district_obj.pk, code)
    if key not in cache.tehsils:
        obj, created = Tehsil.objects.get_or_create(
            district=district_obj, code=code, defaults={"name": name})
        if not created and name != "UNKNOWN" and obj.name != name:
            obj.name = name
            obj.save(update_fields=["name"])
        cache.tehsils[key] = obj
    return cache.tehsils[key]


def _gc_village(cache: SahayakCache, tehsil_obj, code: str, name: str):
    from .models import Village
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    key  = (tehsil_obj.pk, code)
    if key not in cache.villages:
        obj, created = Village.objects.get_or_create(
            tehsil=tehsil_obj, code=code, defaults={"name": name})
        if not created and name != "UNKNOWN" and obj.name != name:
            obj.name = name
            obj.save(update_fields=["name"])
        cache.villages[key] = obj
    return cache.villages[key]


def _gc_hamlet(cache: SahayakCache, village_obj, code: str, name: str):
    from .models import Hamlet
    if not code and not name:
        return None
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    key  = (village_obj.pk, code)
    if key not in cache.hamlets:
        obj, _ = Hamlet.objects.get_or_create(
            village=village_obj, code=code, defaults={"name": name})
        cache.hamlets[key] = obj
    return cache.hamlets[key]


def _gc_plant(cache: SahayakCache, code: str, name: str):
    from .models import Plant
    code = (code or "01001").strip()
    name = (name or "SHWETDHARA MPCL").strip().upper()
    if code not in cache.plants:
        obj, _ = Plant.objects.get_or_create(code=code, defaults={"name": name})
        cache.plants[code] = obj
    return cache.plants[code]


def _gc_bmc(cache: SahayakCache, plant_obj, code: str, name: str):
    from .models import BMC
    code = (code or "01001").strip()
    name = (name or "UNKNOWN").strip().upper()
    key  = (plant_obj.pk, code)
    if key not in cache.bmcs:
        obj, _ = BMC.objects.get_or_create(
            plant=plant_obj, code=code, defaults={"name": name})
        cache.bmcs[key] = obj
    return cache.bmcs[key]


def _gc_mcc(cache: SahayakCache, bmc_obj, code: str, name: str):
    from .models import MCC
    code = (code or bmc_obj.code).strip()
    name = (name or bmc_obj.name).strip().upper()
    key  = (bmc_obj.pk, code)
    if key not in cache.mccs:
        obj, _ = MCC.objects.get_or_create(
            bmc=bmc_obj, code=code, defaults={"name": name})
        cache.mccs[key] = obj
    return cache.mccs[key]


# ══════════════════════════════════════════════════════════════════════════════
#  ROW → MPP kwargs  (pure Python after cache is warm)
# ══════════════════════════════════════════════════════════════════════════════

def _row_to_mpp_kwargs(
    raw: tuple,
    hmap: dict,
    cache: SahayakCache,
    mpp_code: str,
    mpp_name: str,
) -> dict:
    g  = lambda *k, **kw: _v(raw, hmap, *k, **kw)
    gd = lambda *k, **kw: _d(raw, hmap, *k, **kw)

    # ── Dairy hierarchy ───────────────────────────────────────────────────
    plant_code = g("plant_code",  "Plant Code")  or "01001"
    plant_name = g("plant_name",  "Plant Name")  or "SHWETDHARA MPCL"
    plant_obj  = _gc_plant(cache, plant_code, plant_name)

    bmc_code = g("bmc_code", "bmc_transaction_code", "BMC Code", "bmc_tr_code") or "01001"
    bmc_name = g("bmc_name", "BMC Name") or mpp_code
    bmc_obj  = _gc_bmc(cache, plant_obj, bmc_code, bmc_name)

    mcc_code = g("mcc_code", "mcc_transaction_code", "MCC Code", "mcc_tr_code") or bmc_code
    mcc_name = g("mcc_name", "MCC Name") or bmc_name
    mcc_obj  = _gc_mcc(cache, bmc_obj, mcc_code, mcc_name)

    # ── Geography ─────────────────────────────────────────────────────────
    state_obj    = _gc_state(cache, g("state_name", "State Name"))
    district_obj = _gc_district(cache, state_obj,
        g("district_code",  "District Code"),
        g("district_name",  "District Name"))
    tehsil_obj   = _gc_tehsil(cache, district_obj,
        g("tehshil_code",   "tehsil_code",  "Tehsil Code"),
        g("tehshil_name",   "tehsil_name",  "Tehsil Name"))
    village_obj  = _gc_village(cache, tehsil_obj,
        g("village_code",   "Village Code"),
        g("village_name",   "Village Name"))
    hamlet_obj   = _gc_hamlet(cache, village_obj,
        g("hamlet_code",    "Hamlet Code"),
        g("hamlet_name",    "Hamlet Name"))

    # ── Status ────────────────────────────────────────────────────────────
    status_raw = (g("status", "Status") or "Active").strip().capitalize()
    status     = status_raw if status_raw in _STATUS_VALID else "Active"

    # ── Assigned Sahayak (optional) ───────────────────────────────────────
    sahayak_obj  = None
    sahayak_code = g("Sahayak Code", "assigned_sahayak_code", "facilitator_code")
    if sahayak_code and sahayak_code in cache.users:
        sahayak_obj = cache.users[sahayak_code]

    kwargs = {
        "name":             (mpp_name or mpp_code).upper(),
        "transaction_code": g("mpp_transaction_code", "MPP Transaction Code", "mpp_tr_code"),
        "ex_code":          g("mpp_ex_code",          "MPP Ex Code"),
        "short_name":       g("mpp_short_name",       "MPP Short Name"),
        "route_name":       g("route_name",           "Route Name"),
        "route_ex_code":    g("route_ex_code",        "Route Ex Code"),
        "dpu_station_code": g("dpu_station_code",     "DPU Station Code"),
        "dpu_vendor_code":  g("DPU_Vendor_Code",      "dpu_vendor_code", "DPU Vendor Code"),
        # FK objects — Farmer(**kwargs) sets them as Python objects;
        # getattr(obj, 'plant_id') returns the integer PK for raw SQL.
        "plant":            plant_obj,
        "mcc":              mcc_obj,
        "state":            state_obj,
        "district":         district_obj,
        "tehsil":           tehsil_obj,
        "village":          village_obj,
        "hamlet":           hamlet_obj,
        "pincode":          g("pincode",           "Pincode"),
        "mobile_number":    g("mob_no",            "Mobile No", "mobile_number"),
        "opening_date":     gd("mpp_opening_date", "Opening Date", "opening_date"),
        "closing_date":     gd("mpp_closing_date", "Closing Date", "closing_date"),
        "status":           status,
        "assigned_sahayak": sahayak_obj,
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

_MPP_INSERT_COLUMNS: Optional[List[str]] = None
_MPP_ATTNAMES:       Optional[List[str]] = None


def _build_column_metadata(MPP) -> Tuple[List[str], List[str]]:
    """
    Return (insert_columns, attnames) for the MPP model.
    Result is cached at module level so it is computed only once.

    attnames uses f.attname (not f.name) so FK fields yield e.g. 'plant_id'
    (the integer column) rather than 'plant' (the Python descriptor).
    """
    global _MPP_INSERT_COLUMNS, _MPP_ATTNAMES
    if _MPP_INSERT_COLUMNS is not None:
        return _MPP_INSERT_COLUMNS, _MPP_ATTNAMES

    cols, attrs = [], []
    for f in MPP._meta.fields:
        if f.column in _SKIP_INSERT_COLUMNS:
            continue
        cols.append(f.column)
        attrs.append(f.attname)

    _MPP_INSERT_COLUMNS = cols
    _MPP_ATTNAMES       = attrs
    return cols, attrs


def _build_upsert_sql(MPP, update_existing: bool) -> str:
    """Build the INSERT … ON DUPLICATE KEY UPDATE SQL template."""
    cols, _ = _build_column_metadata(MPP)
    table    = MPP._meta.db_table
    col_list = ", ".join(f"`{c}`" for c in cols)

    if update_existing:
        update_clause = ", ".join(
            f"`{c}` = VALUES(`{c}`)"
            for c in cols
            if c not in _SKIP_UPDATE_COLUMNS
        )
    else:
        # No-op: satisfy syntax without changing anything on conflict
        update_clause = "`unique_code` = `unique_code`"

    return (
        f"INSERT INTO `{table}` ({col_list}) VALUES {{rows}} "
        f"ON DUPLICATE KEY UPDATE {update_clause}"
    )


def _upsert_chunk(MPP, chunk_objs: list, upsert_sql_tpl: str, attnames: List[str]) -> int:
    """Execute one INSERT … ON DUPLICATE KEY UPDATE for the chunk."""
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
    MPP, chunk_objs: list, upsert_sql_tpl: str, attnames: List[str]
) -> int:
    """Per-chunk transaction with retry on lock-wait timeout (error 1205)."""
    from django.db import OperationalError
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with transaction.atomic():
                return _upsert_chunk(MPP, chunk_objs, upsert_sql_tpl, attnames)
        except OperationalError as exc:
            last_exc = exc
            if "1205" in str(exc) or "lock wait timeout" in str(exc).lower():
                wait = 0.3 * (2 ** (attempt - 1))
                logger.warning(
                    "Lock timeout on MPP chunk (attempt %d/%d), back-off %.1fs …",
                    attempt, MAX_RETRIES, wait,
                )
                time.sleep(wait)
            else:
                raise
    raise last_exc  # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def process_sahayaks(
    data_rows:       list,
    hmap:            dict,
    update_existing: bool,
    dry_run:         bool,
    performed_by,
    job_id:          str = "",
) -> Tuple[dict, list]:
    """
    Public entry point — drop-in replacement for _process_sahayaks in views.py.
    Returns (summary_dict, results_list).
    """
    t_start = time.perf_counter()
    summary = {"total": 0, "created": 0, "updated": 0, "errors": 0, "skipped": 0}
    results = []

    # ── Required columns check (alias-aware) ─────────────────────────────
    missing = [
        label
        for label, aliases in _SAHAYAK_REQUIRED_ALIASES
        if not any(a in hmap for a in aliases)
    ]
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

    # ── Pass 0: Warm cache ────────────────────────────────────────────────
    _push_event(job_id, {
        "type": "phase", "phase": "cache",
        "message": "Loading geography & hierarchy cache…",
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
    data_rows: list, hmap: dict, cache: SahayakCache,
    total_rows: int, summary: dict, results: list, job_id: str,
) -> Tuple[dict, list]:

    _push_event(job_id, {
        "type": "phase", "phase": "validate",
        "message": f"Dry run — validating {total_rows} rows…",
    })

    livelog_count = 0
    for idx, raw in enumerate(data_rows, start=1):
        row_num  = idx + 1
        g        = lambda *k, **kw: _v(raw, hmap, *k, **kw)
        mpp_code = g("mpp_code", "MPP Unique Code", "mpp_unique_code")
        mpp_name = g("mpp_name", "MPP Name")

        if not mpp_code:
            summary["errors"] += 1
            r = {"row": row_num, "key": "—", "status": "error",
                 "message": "MPP Unique Code is blank"}
        elif not mpp_name:
            summary["errors"] += 1
            r = {"row": row_num, "key": mpp_code, "status": "error",
                 "message": "MPP Name is blank"}
        else:
            exists = mpp_code in cache.mpps
            summary["created"] += 1
            r = {
                "row": row_num, "key": mpp_code, "status": "preview",
                "message": f"Would {'update' if exists else 'create'} — {mpp_name}",
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
    data_rows: list, hmap: dict, cache: SahayakCache,
    total_rows: int, update_existing: bool, performed_by,
    summary: dict, results: list, job_id: str, t_start: float,
) -> Tuple[dict, list]:

    from .models import MPP

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
        mpp_code = g("mpp_code", "MPP Unique Code", "mpp_unique_code")
        mpp_name = g("mpp_name", "MPP Name")

        err = None
        if not mpp_code:
            err = "MPP Unique Code is blank"
        elif not mpp_name:
            err = f"MPP Name is blank for code '{mpp_code}'"
        elif mpp_code in seen_codes:
            err = (f"Duplicate MPP Unique Code in file — "
                   f"first seen at row {seen_codes[mpp_code]}")
        else:
            seen_codes[mpp_code] = row_num

        if err:
            validation_errors.append(
                {"row": row_num, "key": mpp_code or "—", "status": "error", "message": err})
        else:
            valid_rows.append((row_num, raw, mpp_code, mpp_name))

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

    # ── PASS 2: Prepare — build MPP objects, resolve geo FKs ─────────────
    # All get_or_create calls happen HERE, before any MPP write transaction.
    # This prevents geo DDL from contending with MPP row locks.
    _push_event(job_id, {
        "type": "phase", "phase": "prepare",
        "message": f"Preparing {len(valid_rows)} rows…",
    })

    mpp_objs:       List[Any]  = []
    mpp_metas:      List[dict] = []
    prepare_errors: List[dict] = []

    for idx, (row_num, raw, mpp_code, mpp_name) in enumerate(valid_rows, start=1):
        try:
            kwargs = _row_to_mpp_kwargs(raw, hmap, cache, mpp_code, mpp_name)
            mpp_objs.append(MPP(unique_code=mpp_code, **kwargs))
            mpp_metas.append({"row_num": row_num, "mpp_code": mpp_code, "mpp_name": mpp_name})
        except Exception as exc:
            logger.error("MPP kwargs build error row %s (%s): %s", row_num, mpp_code, exc,
                         exc_info=True)
            prepare_errors.append({
                "row": row_num, "key": mpp_code, "status": "error",
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
    #
    # The upsert is idempotent: if the process is killed and re-run,
    # already-committed chunks become no-op UPDATEs.
    cols, attnames = _build_column_metadata(MPP)
    upsert_sql_tpl = _build_upsert_sql(MPP, update_existing)

    total_ops     = len(mpp_objs)
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
        chunk_objs = mpp_objs[chunk_start:chunk_end]
        chunk_meta = mpp_metas[chunk_start:chunk_end]

        try:
            _upsert_chunk_with_retry(MPP, chunk_objs, upsert_sql_tpl, attnames)
        except Exception as exc:
            logger.critical(
                "MPP upsert chunk [%d:%d] failed permanently: %s",
                chunk_start, chunk_end, exc, exc_info=True,
            )
            for meta in chunk_meta:
                chunk_errors.append({
                    "row": meta["row_num"], "key": meta["mpp_code"],
                    "status": "error",
                    "message": f"Write error (chunk rolled back): {exc}",
                })
            summary["errors"] += len(chunk_meta)
            continue  # other chunks are unaffected

        for meta in chunk_meta:
            write_results.append({
                "row":     meta["row_num"],
                "key":     meta["mpp_code"],
                "status":  "upserted",
                "message": f"Saved — {meta['mpp_name']}",
            })
            ops_done += 1
            if livelog_count < MAX_LIVELOG_ROWS:
                _push_event(job_id, {
                    "type": "row", "row": meta["row_num"],
                    "key":  meta["mpp_code"], "status": "upserted",
                    "message": f"Saved — {meta['mpp_name']}",
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
        "MPP import complete: %d rows in %.2fs — %d saved, %d errors",
        total_rows, elapsed, ops_done, summary["errors"],
    )

    all_results = write_results + chunk_errors
    _push_done(job_id, summary, all_results)
    return summary, all_results