"""
farmer_bulk_upload.py
─────────────────────────────────────────────────────────────────────────────
Blazingly-fast farmer bulk import engine — model-aware edition.

WHY THE PREVIOUS VERSION HAD ERROR 1205
────────────────────────────────────────
  One outer transaction.atomic() wrapped ALL chunks.  MySQL held row locks on
  every written farmer row until the LAST chunk committed.  Any concurrent
  read/write on the farmers table (background jobs, another user) had to wait
  for the entire import — on large files that exceeds innodb_lock_wait_timeout
  (default 50 s) and MySQL raises error 1205.

KEY CHANGES IN THIS VERSION
────────────────────────────
  1.  PER-CHUNK TRANSACTIONS
      Each CHUNK_SIZE batch is committed in its own short transaction.
      Lock duration = time to insert 1000 rows ≈ 50–200 ms.
      No single transaction holds locks for the full file any more.

  2.  RAW-SQL INSERT … ON DUPLICATE KEY UPDATE  (true upsert)
      One SQL statement per chunk handles both INSERT (new rows) and UPDATE
      (existing rows) in a single server round-trip.  3-5× faster than
      Django's bulk_create + separate bulk_update pass.

      Duplicate key is triggered on `form_number` (UNIQUE) and
      `unique_member_code` (UNIQUE).  The ON DUPLICATE KEY clause updates
      all mutable columns so both constraints are handled correctly.

  3.  GEO get_or_create MOVED BEFORE WRITE TRANSACTIONS
      All _gc_* geography auto-creates happen during Pass 2 (prepare), which
      is completely outside any farmer write transaction.  This eliminates
      DDL-adjacent lock contention that can cause deadlocks.

  4.  accepted_by USERS BATCHED IN ONE QUERY
      Old code did a CustomUser query per row.  New code collects all unique
      values, resolves them in 1-2 queries, caches the results.

  5.  auto_now / auto_now_add FIELDS EXCLUDED FROM INSERT COLUMN LIST
      `created_at` (auto_now_add) and `updated_at` (auto_now) must NOT be
      in the INSERT column list — MySQL sets them via DEFAULT / ON UPDATE.
      Including them would override the auto value and cause silent bugs.

  6.  FK COLUMNS ARE `<field>_id`, NOT `<field>`
      Django stores ForeignKey values in columns named `<attname>` which is
      `<fieldname>_id` (e.g. `mpp_id`, `village_id`, `created_by_id`).
      We use field.attname to pull the correct integer PK from the in-memory
      Farmer object — not field.name (the Python attribute) or field.column
      (same as attname for FKs, but different for concrete non-FK fields).

  7.  RETRY WITH EXPONENTIAL BACK-OFF + SHORT SESSION LOCK TIMEOUT
      innodb_lock_wait_timeout is set to LOCK_TIMEOUT_SEC (5 s) for each
      chunk session so any unexpected stall fails fast.  Up to MAX_RETRIES
      retries with doubling back-off (0.3 s → 0.6 s → 1.2 s).

Architecture
────────────
  Pass 0  – Pre-warm caches (State/District/Tehsil/Village/Hamlet/MPP)
  Pass 1  – Validate all rows in Python (no DB writes)
  Pass 2  – Build all Farmer(**kwargs) objects; resolve all geo FKs
              (geo get_or_create happen here, outside write transactions)
              Batch-resolve accepted_by users in 1-2 queries
  Pass 3  – Chunked upsert: each chunk = one short transaction

Tuning knobs
────────────
  CHUNK_SIZE        rows per upsert call         (default 1000)
  PROGRESS_EVERY    SSE heartbeat every N rows    (default 200)
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
CHUNK_SIZE       = 1000
PROGRESS_EVERY   = 200
MAX_LIVELOG_ROWS = 200
LOCK_TIMEOUT_SEC = 5
MAX_RETRIES      = 3

# ── Blank-value sentinel ──────────────────────────────────────────────────────
_BLANK = {"", "none", "nan", "nat", "n/a", "null", "-", "--", "na"}

# ── Normalisation maps ────────────────────────────────────────────────────────
_MS_MAP: Dict[str, str] = {
    "active":    "ACTIVE",
    "deactive":  "INACTIVE",
    "inactive":  "INACTIVE",
    "cancelled": "CANCELLED",
    "suspended": "SUSPENDED",
}
_QUAL_MAP: Dict[str, str] = {
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
_REL_MAP: Dict[str, str] = {
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
_DATE_FMTS = (
    "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d",
    "%d-%b-%Y", "%d %b %Y", "%m/%d/%Y",
    "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y",
)
_PM_VALID    = {"CASH", "DD", "CHEQUE", "ONLINE"}
_CASTE_VALID = {"General", "OBC", "SC", "ST", "Other"}
_MTYPE_VALID = {"NONE", "REGULAR", "PREMIUM"}
_APPR_VALID  = {"Pending", "Approved", "Rejected"}

_FARMER_REQUIRED = [
    "form_number", "unique_member_code", "member_name", "gender",
    "state_name", "member_district_name", "member_tehshil_name",
    "member_village_name", "mpp_unique_code",
]

# ── Fields excluded from the INSERT column list ───────────────────────────────
# 'id'          → auto-increment, must be omitted so MySQL assigns it
# 'created_at'  → auto_now_add=True, MySQL DEFAULT handles it
# 'updated_at'  → auto_now=True,     MySQL ON UPDATE handles it
_SKIP_INSERT_COLUMNS = frozenset({"id", "created_at", "updated_at"})

# Fields never updated on DUPLICATE KEY conflict (identity + audit creation)
_SKIP_UPDATE_COLUMNS = frozenset({
    "id", "form_number", "created_at", "updated_at", "created_by_id",
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


def _i(row: tuple, hmap: dict, *keys: str, default: int = 0) -> int:
    for k in keys:
        idx = hmap.get(k)
        if idx is None or idx >= len(row):
            continue
        val = row[idx]
        if val is None:
            continue
        try:
            return int(float(str(val).strip()))
        except (ValueError, TypeError):
            pass
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
#  GEOGRAPHY CACHE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GeoCache:
    states:    Dict[str, Any] = field(default_factory=dict)
    districts: Dict[tuple, Any] = field(default_factory=dict)
    tehsils:   Dict[tuple, Any] = field(default_factory=dict)
    villages:  Dict[tuple, Any] = field(default_factory=dict)
    hamlets:   Dict[tuple, Any] = field(default_factory=dict)
    mpps:      Dict[str, Any] = field(default_factory=dict)
    plants:    Dict[str, Any] = field(default_factory=dict)
    bmcs:      Dict[tuple, Any] = field(default_factory=dict)
    mccs:      Dict[tuple, Any] = field(default_factory=dict)


def _warm_cache() -> GeoCache:
    from .models import State, District, Tehsil, Village, Hamlet, MPP, Plant, BMC, MCC
    c = GeoCache()
    for o in State.objects.all():
        c.states[o.name.upper()] = o
    for o in District.objects.all():
        c.districts[(o.state_id, o.code)] = o
    for o in Tehsil.objects.all():
        c.tehsils[(o.district_id, o.code)] = o
    for o in Village.objects.all():
        c.villages[(o.tehsil_id, o.code)] = o
    for o in Hamlet.objects.all():
        c.hamlets[(o.village_id, o.code)] = o
    for o in Plant.objects.all():
        c.plants[o.code] = o
    for o in BMC.objects.all():
        c.bmcs[(o.plant_id, o.code)] = o
    for o in MCC.objects.all():
        c.mccs[(o.bmc_id, o.code)] = o
    for o in MPP.objects.all():
        c.mpps[o.unique_code] = o
    logger.info(
        "GeoCache: %d states %d districts %d tehsils %d villages %d hamlets %d MPPs",
        len(c.states), len(c.districts), len(c.tehsils),
        len(c.villages), len(c.hamlets), len(c.mpps),
    )
    return c


# ── Geo get-or-create helpers ─────────────────────────────────────────────────

def _gc_state(geo: GeoCache, name: str):
    from .models import State
    key = (name or "UTTAR PRADESH").strip().upper()
    if key not in geo.states:
        obj, _ = State.objects.get_or_create(name=key)
        geo.states[key] = obj
    return geo.states[key]


def _gc_district(geo: GeoCache, state_obj, code: str, name: str):
    from .models import District
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    key  = (state_obj.pk, code)
    if key not in geo.districts:
        obj, created = District.objects.get_or_create(
            state=state_obj, code=code, defaults={"name": name})
        if not created and name != "UNKNOWN" and obj.name != name:
            obj.name = name
            obj.save(update_fields=["name"])
        geo.districts[key] = obj
    return geo.districts[key]


def _gc_tehsil(geo: GeoCache, district_obj, code: str, name: str):
    from .models import Tehsil
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    key  = (district_obj.pk, code)
    if key not in geo.tehsils:
        obj, created = Tehsil.objects.get_or_create(
            district=district_obj, code=code, defaults={"name": name})
        if not created and name != "UNKNOWN" and obj.name != name:
            obj.name = name
            obj.save(update_fields=["name"])
        geo.tehsils[key] = obj
    return geo.tehsils[key]


def _gc_village(geo: GeoCache, tehsil_obj, code: str, name: str):
    from .models import Village
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    key  = (tehsil_obj.pk, code)
    if key not in geo.villages:
        obj, created = Village.objects.get_or_create(
            tehsil=tehsil_obj, code=code, defaults={"name": name})
        if not created and name != "UNKNOWN" and obj.name != name:
            obj.name = name
            obj.save(update_fields=["name"])
        geo.villages[key] = obj
    return geo.villages[key]


def _gc_hamlet(geo: GeoCache, village_obj, code: str, name: str):
    from .models import Hamlet
    if not code and not name:
        return None
    code = (code or "00").strip()
    name = (name or "UNKNOWN").strip().upper()
    key  = (village_obj.pk, code)
    if key not in geo.hamlets:
        obj, _ = Hamlet.objects.get_or_create(
            village=village_obj, code=code, defaults={"name": name})
        geo.hamlets[key] = obj
    return geo.hamlets[key]


def _gc_mpp_autocreate(geo: GeoCache, raw: tuple, hmap: dict, mpp_code: str, state_obj):
    from .models import Plant, BMC, MCC, MPP
    g = lambda *k, **kw: _v(raw, hmap, *k, **kw)

    plant_code = g("mcc_tr_code", "bmc_tr_code") or "01001"
    if plant_code not in geo.plants:
        obj, _ = Plant.objects.get_or_create(
            code=plant_code, defaults={"name": "SHWETDHARA MPCL"})
        geo.plants[plant_code] = obj
    plant = geo.plants[plant_code]

    bmc_code = g("bmc_tr_code") or "01001"
    bmc_key  = (plant.pk, bmc_code)
    if bmc_key not in geo.bmcs:
        obj, _ = BMC.objects.get_or_create(
            plant=plant, code=bmc_code,
            defaults={"name": (g("bmc_name") or "UNKNOWN").upper()})
        geo.bmcs[bmc_key] = obj
    bmc = geo.bmcs[bmc_key]

    mcc_code = g("mcc_tr_code") or bmc_code
    mcc_key  = (bmc.pk, mcc_code)
    if mcc_key not in geo.mccs:
        obj, _ = MCC.objects.get_or_create(
            bmc=bmc, code=mcc_code,
            defaults={"name": (g("mcc_name") or bmc.name).upper()})
        geo.mccs[mcc_key] = obj
    mcc = geo.mccs[mcc_key]

    mpp_district = _gc_district(geo, state_obj,
        g("mpp_district_code", "member_district_code"),
        g("mpp_district_name", "member_district_name"))
    mpp_tehsil  = _gc_tehsil(geo, mpp_district,
        g("mpp_tehshil_code", "member_tehshil_code"),
        g("mpp_tehshil_name", "member_tehshil_name"))
    mpp_village = _gc_village(geo, mpp_tehsil,
        g("mpp_village_code", "member_village_code"),
        g("mpp_village_name", "member_village_name"))
    mpp_hamlet  = _gc_hamlet(geo, mpp_village,
        g("mpp_hamlet_code", "member_hamlet_code"),
        g("mpp_hamlet_name", "member_hamlet_name"))

    mpp, _ = MPP.objects.get_or_create(
        unique_code=mpp_code,
        defaults={
            "name":             (g("mpp_name") or mpp_code).upper(),
            "transaction_code": g("mpp_tr_code"),
            "ex_code":          g("mpp_ex_code"),
            "plant":            plant,
            "mcc":              mcc,
            "state":            state_obj,
            "district":         mpp_district,
            "tehsil":           mpp_tehsil,
            "village":          mpp_village,
            "hamlet":           mpp_hamlet,
            "status":           "Active",
        },
    )
    geo.mpps[mpp_code] = mpp
    return mpp


# ══════════════════════════════════════════════════════════════════════════════
#  ROW → Farmer kwargs  (pure Python after cache is warm)
# ══════════════════════════════════════════════════════════════════════════════

def _row_to_farmer_kwargs(
    raw: tuple, hmap: dict, geo: GeoCache,
    form_no: str, um_code: str, name: str,
    performed_by,
    accepted_by_cache: dict,
) -> dict:
    g  = lambda *k, **kw: _v(raw, hmap, *k, **kw)
    gi = lambda *k, **kw: _i(raw, hmap, *k, **kw)
    gd = lambda *k, **kw: _d(raw, hmap, *k, **kw)

    state_obj    = _gc_state(geo, g("state_name"))
    district_obj = _gc_district(geo, state_obj,
                                g("member_district_code"), g("member_district_name"))
    tehsil_obj   = _gc_tehsil(geo, district_obj,
                              g("member_tehshil_code"), g("member_tehshil_name"))
    village_obj  = _gc_village(geo, tehsil_obj,
                               g("member_village_code"), g("member_village_name"))
    hamlet_obj   = _gc_hamlet(geo, village_obj,
                              g("member_hamlet_code"), g("member_hamlet_name"))

    mpp_code = g("mpp_unique_code")
    mpp_obj  = geo.mpps.get(mpp_code) or _gc_mpp_autocreate(geo, raw, hmap, mpp_code, state_obj)

    gender   = (g("gender") or "").strip().capitalize()
    gender   = gender if gender in ("Male", "Female", "Other") else "Other"
    caste    = (g("caste_category") or "").strip()
    caste    = caste if caste in _CASTE_VALID else None
    qual     = _QUAL_MAP.get((g("qualification") or "").strip().lower())
    m_rel    = _REL_MAP.get((g("member_relation") or "").strip().lower(), "Other")
    m_type   = (g("member_type") or "NONE").strip().upper()
    m_type   = m_type if m_type in _MTYPE_VALID else "NONE"
    approval = (g("approval_status") or "Pending").strip().capitalize()
    approval = approval if approval in _APPR_VALID else "Pending"
    m_status = _MS_MAP.get((g("member_status") or "ACTIVE").strip().lower(), "ACTIVE")
    p_mode   = (g("payment_mode") or "").strip().upper()
    p_mode   = p_mode if p_mode in _PM_VALID else None

    accepted_by_val  = g("accepted_by", "user_id")
    accepted_by_user = accepted_by_cache.get(accepted_by_val) if accepted_by_val else None

    kwargs = {
        # ── Identity ──────────────────────────────────────────
        "form_number":        form_no,
        "unique_member_code": um_code,
        "member_tr_code":     g("member_tr_code"),
        "member_ex_code":     g("member_ex_code"),
        # ── Personal ─────────────────────────────────────────
        "member_name":        name,
        "father_name":        g("father_name"),
        "member_relation":    m_rel,
        "gender":             gender,
        "age":                gi("age") or None,
        "birth_date":         gd("birth_date"),
        "caste_category":     caste,
        "qualification":      qual,
        "aadhar_no":          g("aadhar_no"),
        "mobile_no":          g("mobile_no"),
        "phone_no":           g("phone_no"),
        # ── Address ──────────────────────────────────────────
        # NOTE: These are Django FK fields. Farmer(**kwargs) sets `.hamlet`,
        # `.village` etc. as Python objects.  When we later read
        # `getattr(obj, 'hamlet_id')` we get the integer PK — exactly what
        # the raw SQL INSERT needs for the `hamlet_id` column.
        "house_no":           g("house_no"),
        "hamlet":             hamlet_obj,
        "village":            village_obj,
        "post_office":        g("post_office"),
        "tehsil":             tehsil_obj,
        "district":           district_obj,
        "state":              state_obj,
        "pincode":            g("pincode"),
        "mpp":                mpp_obj,
        # ── Livestock — Heifer ───────────────────────────────
        "cow_heifer_no":       gi("Cow Herifer No"),
        "buffalo_heifer_no":   gi("Buffalo Herifer No"),
        "mix_heifer_no":       gi("Mix Herifer No"),
        "desi_cow_heifer_no":  gi("Desi Cow Herifer No"),
        "crossbred_heifer_no": gi("Crossbred Herifer No"),
        # ── Livestock — Dry ──────────────────────────────────
        "cow_dry_no":          gi("Cow Dry No"),
        "buffalo_dry_no":      gi("Buffalo Dry No"),
        "mix_dry_no":          gi("Mix Dry No"),
        "desi_cow_dry_no":     gi("Desi Cow Dry No"),
        "crossbred_dry_no":    gi("Crossbred Dry No"),
        # ── Livestock — Total ─────────────────────────────────
        "cow_animal_nos":          gi("Cow Animal Nos"),
        "buffalo_animal_nos":      gi("Buffalo Animal Nos"),
        "mix_animal_nos":          gi("Mix Animal Nos"),
        "desi_cow_animal_nos":     gi("Desi Cow Animal Nos"),
        "crossbred_animal_nos":    gi("Crossbred Animal Nos"),
        # ── Milk ─────────────────────────────────────────────
        "lpd_no":                 gi("lpd_no"),
        "household_consumption":  gi("household_consumption"),
        "market_consumption":     gi("market_consumption"),
        # ── Bank ─────────────────────────────────────────────
        "accountant_name":        g("accountant_name"),
        "bank_account_no":        g("bank_account_no"),
        "member_bank_name":       g("member_bank_name"),
        "member_branch_name":     g("member_branch_name"),
        "ifsc":                   g("ifsc"),
        # ── Nominee / Guardian ───────────────────────────────
        "particular1_name":       g("particluar1_name"),
        "particular1_gender":     (g("particluar1_name_gender") or "").capitalize() or None,
        "particular1_age":        gi("particluar1_name_age") or None,
        "particular1_relation":   g("particluar1_relation_name"),
        "nominee_name":           g("nominee_name"),
        "nominee_relation":       g("relation"),
        "nominee_address":        g("nominee_address"),
        "guardian_name":          g("guardian_name"),
        "member_family_age":      gi("member_family_age") or None,
        # ── Membership ───────────────────────────────────────
        "member_type":   m_type,
        "admission_fee": gi("admission_fee"),
        "share_qty":     gi("share_qty"),
        "paid_amount":   gi("paid_amount"),
        # ── Payment ──────────────────────────────────────────
        "depositor_bank_name":   g("depositor_bank_name"),
        "depositor_branch_name": g("depositor_branch_name"),
        "dd_no":                 g("DD_no"),
        "transaction_date":      gd("transaction_date"),
        "payment_mode":          p_mode,
        # ── Approval ─────────────────────────────────────────
        "wef_date":        gd("wef_date"),
        "approval_status": approval,
        "accepted_by":     accepted_by_user,   # FK → stored as accepted_by_id
        "approval_date":   gd("approval_date"),
        # ── Status ───────────────────────────────────────────
        "member_status":       m_status,
        "member_cancellation": g("member_cancelation"),
        # ── Dates ────────────────────────────────────────────
        "enrollment_date":              gd("member Enrolment Date"),
        "first_board_approved_meeting": gd("first_board_approved_meeting"),
        "last_board_approved_meeting":  gd("last_board_approved_meeting"),
        # ── Audit ────────────────────────────────────────────
        "created_by": performed_by,            # FK → stored as created_by_id
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
#  UPSERT ENGINE
# ══════════════════════════════════════════════════════════════════════════════

# Module-level cache — column metadata built once per process lifetime
_FARMER_INSERT_COLUMNS: Optional[List[str]] = None
_FARMER_ATTNAMES:       Optional[List[str]] = None


def _build_column_metadata(Farmer) -> Tuple[List[str], List[str]]:
    """
    Return (insert_columns, attnames) for the Farmer model.

    insert_columns  List[str]
        DB column names to include in the INSERT statement.
        Excludes 'id', 'created_at', 'updated_at' (auto-managed fields).

    attnames        List[str]
        Python attribute names on a Farmer instance that correspond to those
        columns — e.g. 'mpp_id' for the `mpp_id` DB column (Django FK attname).

        Using f.attname (not f.name) is CRITICAL:
          f.name  = 'mpp'     → the Python descriptor that returns an MPP object
          f.attname = 'mpp_id' → the integer PK stored on the instance
        getattr(obj, 'mpp_id') returns the integer we need for raw SQL.

    Result is cached at module level so it is computed only once.
    """
    global _FARMER_INSERT_COLUMNS, _FARMER_ATTNAMES
    if _FARMER_INSERT_COLUMNS is not None:
        return _FARMER_INSERT_COLUMNS, _FARMER_ATTNAMES

    cols, attrs = [], []
    for f in Farmer._meta.fields:
        if f.column in _SKIP_INSERT_COLUMNS:
            continue
        cols.append(f.column)
        attrs.append(f.attname)   # 'mpp_id', 'village_id', 'member_name', …

    _FARMER_INSERT_COLUMNS = cols
    _FARMER_ATTNAMES       = attrs
    return cols, attrs


def _build_upsert_sql(Farmer, update_existing: bool) -> str:
    """
    Build the INSERT … ON DUPLICATE KEY UPDATE SQL template string.
    Contains a {rows} placeholder that is filled per-chunk with the right
    number of (%s, %s, …) tuples.

    Called once per import run.
    """
    cols, _ = _build_column_metadata(Farmer)
    table    = Farmer._meta.db_table
    col_list = ", ".join(f"`{c}`" for c in cols)

    if update_existing:
        # Update every mutable column on conflict.
        # Columns in _SKIP_UPDATE_COLUMNS are intentionally preserved.
        update_clause = ", ".join(
            f"`{c}` = VALUES(`{c}`)"
            for c in cols
            if c not in _SKIP_UPDATE_COLUMNS
        )
    else:
        # No-op update: just touch form_number = form_number to satisfy the
        # ON DUPLICATE KEY UPDATE syntax without changing anything.
        update_clause = "`form_number` = `form_number`"

    return (
        f"INSERT INTO `{table}` ({col_list}) VALUES {{rows}} "
        f"ON DUPLICATE KEY UPDATE {update_clause}"
    )


def _upsert_chunk(
    Farmer,
    chunk_objs:     list,
    upsert_sql_tpl: str,
    attnames:       List[str],
) -> int:
    """
    Execute one INSERT … ON DUPLICATE KEY UPDATE for the chunk.
    Must be called inside an already-open transaction (see retry wrapper).
    Returns MySQL rowcount.
    """
    if not chunk_objs:
        return 0

    n_cols  = len(attnames)
    row_ph  = "(" + ", ".join(["%s"] * n_cols) + ")"
    rows_ph = ", ".join([row_ph] * len(chunk_objs))
    sql     = upsert_sql_tpl.format(rows=rows_ph)

    # Flatten: [row0_col0, row0_col1, …, rowN_colM]
    # getattr(obj, attname) returns the *value* Django has already set on the
    # instance.  For FK fields (e.g. attname='mpp_id') this is the integer PK.
    # For regular fields it's the Python value (str, int, date, None, …).
    params = [
        getattr(obj, attr, None)
        for obj in chunk_objs
        for attr in attnames
    ]

    with connection.cursor() as cur:
        # Short lock timeout — if MySQL can't acquire locks within 5 s it
        # raises 1205 immediately so the retry wrapper can back off and retry,
        # rather than blocking for the default 50 s.
        cur.execute(f"SET SESSION innodb_lock_wait_timeout = {LOCK_TIMEOUT_SEC}")
        cur.execute(sql, params)
        return cur.rowcount


def _upsert_chunk_with_retry(
    Farmer,
    chunk_objs:     list,
    upsert_sql_tpl: str,
    attnames:       List[str],
) -> int:
    """
    Wraps _upsert_chunk in its own short transaction with retry on lock error.
    Exponential back-off: 0.3 s → 0.6 s → 1.2 s.
    """
    from django.db import OperationalError
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with transaction.atomic():
                return _upsert_chunk(Farmer, chunk_objs, upsert_sql_tpl, attnames)
        except OperationalError as exc:
            last_exc = exc
            if "1205" in str(exc) or "lock wait timeout" in str(exc).lower():
                wait = 0.3 * (2 ** (attempt - 1))
                logger.warning(
                    "Lock timeout on chunk (attempt %d/%d), back-off %.1fs …",
                    attempt, MAX_RETRIES, wait,
                )
                time.sleep(wait)
            else:
                raise
    raise last_exc   # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def process_farmers(
    data_rows: list,
    hmap: dict,
    update_existing: bool,
    dry_run: bool,
    performed_by,
    job_id: str = "",
) -> Tuple[dict, list]:
    """
    Public entry point.  Drop-in replacement for the original _process_farmers.
    Returns (summary_dict, results_list).
    """
    t_start = time.perf_counter()
    summary = {"total": 0, "created": 0, "updated": 0, "errors": 0, "skipped": 0}
    results: list = []

    # ── Required columns check ────────────────────────────────────────────
    missing = [c for c in _FARMER_REQUIRED if c not in hmap]
    if missing:
        err = [{"row": "—", "key": "—", "status": "error",
                "message": f"Missing required column(s): {', '.join(missing)}"}]
        _push_done(job_id, summary, err)
        return summary, err

    data_rows = [r for r in data_rows
                 if not all(v is None or str(v).strip() == "" for v in r)]
    total_rows = len(data_rows)
    if total_rows == 0:
        err = [{"row": "—", "key": "—", "status": "error",
                "message": "No data rows found in file."}]
        _push_done(job_id, summary, err)
        return summary, err

    summary["total"] = total_rows

    # ── Pass 0: Warm geo cache ────────────────────────────────────────────
    _push_event(job_id, {"type": "phase", "phase": "cache",
                         "message": "Loading geography & MPP cache…"})
    geo = _warm_cache()

    if dry_run:
        return _dry_run(data_rows, hmap, geo, total_rows, summary, results, job_id)

    return _real_import(
        data_rows, hmap, geo, total_rows,
        update_existing, performed_by,
        summary, results, job_id, t_start,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  DRY RUN
# ══════════════════════════════════════════════════════════════════════════════

def _dry_run(data_rows, hmap, geo, total_rows, summary, results, job_id):
    _push_event(job_id, {"type": "phase", "phase": "validate",
                         "message": f"Dry run — validating {total_rows} rows…"})
    livelog_count = 0
    for idx, raw in enumerate(data_rows, start=1):
        row_num  = idx + 1
        g        = lambda *k, **kw: _v(raw, hmap, *k, **kw)
        form_no  = g("form_number")
        um_code  = g("unique_member_code")
        name     = g("member_name")
        mpp_code = g("mpp_unique_code")

        if not form_no:
            summary["errors"] += 1
            r = {"row": row_num, "key": "—", "status": "error",
                 "message": "form_number is blank"}
        elif not um_code:
            summary["errors"] += 1
            r = {"row": row_num, "key": form_no, "status": "error",
                 "message": "unique_member_code is blank"}
        elif not name:
            summary["errors"] += 1
            r = {"row": row_num, "key": form_no, "status": "error",
                 "message": "member_name is blank"}
        elif mpp_code and mpp_code not in geo.mpps:
            summary["errors"] += 1
            r = {"row": row_num, "key": form_no, "status": "error",
                 "message": f"MPP '{mpp_code}' not found — upload Sahayak/MPP sheet first."}
        else:
            summary["created"] += 1
            r = {"row": row_num, "key": form_no, "status": "preview",
                 "message": f"Would be imported — {name}"}

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
    data_rows, hmap, geo, total_rows,
    update_existing, performed_by,
    summary, results, job_id, t_start,
):
    from .models import Farmer

    # ──────────────────────────────────────────────────────────────────────
    # PASS 1 — VALIDATE (pure Python, zero DB writes)
    # ──────────────────────────────────────────────────────────────────────
    _push_event(job_id, {"type": "phase", "phase": "validate",
                         "message": f"Validating {total_rows} rows before import…"})

    validation_errors: List[dict]     = []
    valid_rows:        List[tuple]    = []
    seen_form_numbers: Dict[str, int] = {}

    for idx, raw in enumerate(data_rows, start=1):
        row_num  = idx + 1
        g        = lambda *k, **kw: _v(raw, hmap, *k, **kw)
        form_no  = g("form_number")
        um_code  = g("unique_member_code")
        name     = g("member_name")
        mpp_code = g("mpp_unique_code")

        err = None
        if not form_no:
            err = "form_number is blank"
        elif not um_code:
            err = "unique_member_code is blank"
        elif not name:
            err = "member_name is blank"
        elif not mpp_code:
            err = "mpp_unique_code is blank"
        elif form_no in seen_form_numbers:
            err = (f"Duplicate form_number in file — "
                   f"first seen at row {seen_form_numbers[form_no]}")
        else:
            seen_form_numbers[form_no] = row_num

        if err:
            validation_errors.append(
                {"row": row_num, "key": form_no or "—", "status": "error", "message": err})
        else:
            valid_rows.append((row_num, raw, form_no, um_code, name))

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

    # ──────────────────────────────────────────────────────────────────────
    # PRE-FETCH: batch-resolve all accepted_by users in 1–2 queries.
    # CustomUser uses email as USERNAME_FIELD (no username field).
    # ──────────────────────────────────────────────────────────────────────
    from .models import CustomUser

    raw_accepted_vals: set = set()
    for _, raw, *_ in valid_rows:
        val = _v(raw, hmap, "accepted_by", "user_id")
        if val:
            raw_accepted_vals.add(val)

    accepted_by_cache: Dict[str, Any] = {}
    if raw_accepted_vals:
        emails = {v for v in raw_accepted_vals if "@" in v}
        if emails:
            for u in CustomUser.objects.filter(email__in=emails).only("id", "email"):
                accepted_by_cache[u.email] = u
        if "admin" in raw_accepted_vals:
            su = CustomUser.objects.filter(is_superuser=True).only("id").first()
            if su:
                accepted_by_cache["admin"] = su

    # ──────────────────────────────────────────────────────────────────────
    # PASS 2 — PREPARE
    # Build all Farmer(**kwargs) objects in Python memory.
    # ALL geography get_or_create calls happen here — before any write
    # transaction so geo DDL never contends with farmer row locks.
    # ──────────────────────────────────────────────────────────────────────
    _push_event(job_id, {"type": "phase", "phase": "prepare",
                         "message": f"Preparing {len(valid_rows)} rows…"})

    farmer_objs:    List[Any]  = []
    farmer_metas:   List[dict] = []
    prepare_errors: List[dict] = []

    for idx, (row_num, raw, form_no, um_code, name) in enumerate(valid_rows, start=1):
        try:
            kwargs = _row_to_farmer_kwargs(
                raw, hmap, geo, form_no, um_code, name,
                performed_by, accepted_by_cache,
            )
            farmer_objs.append(Farmer(**kwargs))
            farmer_metas.append({"row_num": row_num, "form_no": form_no, "name": name})
        except Exception as exc:
            logger.error("Kwargs build error row %s (%s): %s", row_num, form_no, exc,
                         exc_info=True)
            prepare_errors.append({
                "row": row_num, "key": form_no, "status": "error",
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

    # ──────────────────────────────────────────────────────────────────────
    # PASS 3 — CHUNKED UPSERT
    #
    # THE FIX FOR ERROR 1205:
    # Each chunk runs in its OWN short transaction.  Lock hold time =
    # time to insert/update CHUNK_SIZE rows ≈ 50–200 ms per chunk.
    # The old design held locks for the ENTIRE file in one transaction.
    #
    # The upsert (INSERT … ON DUPLICATE KEY UPDATE) is idempotent:
    # if the process is killed mid-import and re-run, already-committed
    # chunks become no-op UPDATEs rather than duplicate-key errors.
    # ──────────────────────────────────────────────────────────────────────
    cols, attnames = _build_column_metadata(Farmer)
    upsert_sql_tpl = _build_upsert_sql(Farmer, update_existing)

    total_ops     = len(farmer_objs)
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
        chunk_objs = farmer_objs[chunk_start:chunk_end]
        chunk_meta = farmer_metas[chunk_start:chunk_end]

        try:
            _upsert_chunk_with_retry(Farmer, chunk_objs, upsert_sql_tpl, attnames)
        except Exception as exc:
            logger.critical(
                "Upsert chunk [%d:%d] failed permanently: %s",
                chunk_start, chunk_end, exc, exc_info=True,
            )
            for meta in chunk_meta:
                chunk_errors.append({
                    "row": meta["row_num"], "key": meta["form_no"],
                    "status": "error",
                    "message": f"Write error (chunk rolled back): {exc}",
                })
            summary["errors"] += len(chunk_meta)
            # Intentionally continue — other chunks are unaffected
            continue

        for meta in chunk_meta:
            write_results.append({
                "row":     meta["row_num"],
                "key":     meta["form_no"],
                "status":  "upserted",
                "message": f"Saved — {meta['name']}",
            })
            ops_done += 1
            if livelog_count < MAX_LIVELOG_ROWS:
                _push_event(job_id, {
                    "type": "row", "row": meta["row_num"],
                    "key":  meta["form_no"], "status": "upserted",
                    "message": f"Saved — {meta['name']}",
                })
                livelog_count += 1

        _push_progress(
            job_id,
            processed=total_rows * 2 + ops_done,
            total=total_rows * 3,
            message=f"Writing: {ops_done}/{total_ops}",
        )

    elapsed = time.perf_counter() - t_start
    summary["created"] = ops_done   # total saved (upsert doesn't distinguish)
    summary["updated"] = 0
    summary["skipped"] = 0

    logger.info(
        "Farmer import complete: %d rows in %.2fs — %d saved, %d errors",
        total_rows, elapsed, ops_done, summary["errors"],
    )

    all_results = write_results + chunk_errors
    _push_done(job_id, summary, all_results)
    return summary, all_results