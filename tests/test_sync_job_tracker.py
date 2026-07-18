"""Unit tests for scripts/sync_job_tracker.py — the pure logic, no DB / no xlsx.

Focus on the two things that are easy to get wrong and were called out
explicitly: the PATCH diff comparison, and date/float equality between xlsx
cells and the values the API echoes back.
"""
import datetime as dt

import sync_job_tracker as sj


# --------------------------------------------------------------------------- canon
def test_canon_dates_normalise_across_forms():
    iso = "2026-07-15"
    assert sj.canon("applied_date", dt.datetime(2026, 7, 15, 9, 30)) == iso
    assert sj.canon("applied_date", dt.date(2026, 7, 15)) == iso
    assert sj.canon("applied_date", "2026-07-15") == iso
    # what the API might echo for a date/time column
    assert sj.canon("applied_date", "2026-07-15T00:00:00") == iso
    assert sj.canon("applied_date", "07/15/2026") == iso


def test_canon_floats_normalise_money_forms():
    assert sj.canon("salary_min", 120000) == 120000.0
    assert sj.canon("salary_min", 120000.0) == 120000.0
    assert sj.canon("salary_min", "$120,000") == 120000.0
    assert sj.canon("salary_max", "150k") == 150000.0
    # API returns numeric(12,2) as a float — must compare equal to an int cell
    assert sj.canon("salary_min", 120000) == sj.canon("salary_min", 120000.00)


def test_canon_text_and_status():
    assert sj.canon("company", "  Acme  ") == "Acme"
    assert sj.canon("status", "Interview") == "interview"
    assert sj.canon("notes", "") is None
    assert sj.canon("role", None) is None


# --------------------------------------------------------------------------- headers
def test_map_headers_fuzzy():
    headers = ["Company", "Job Title", "Stage", "Min Salary", "Salary Max",
               "City", "Remote/Hybrid", "Via", "Link", "Date Applied", "Notes"]
    m = sj.map_headers(headers)
    fields = {m[i] for i in m}
    assert fields == set(sj.FIELDS)
    assert m[0] == "company"
    assert m[1] == "role"
    assert m[3] == "salary_min" and m[4] == "salary_max"
    assert m[9] == "applied_date"


def test_map_headers_first_column_wins_for_a_field():
    # two columns could both look like a salary; only one claims salary_min
    headers = ["Company", "Salary", "Comp"]
    m = sj.map_headers(headers)
    assert list(m.values()).count("salary_min") == 1


# --------------------------------------------------------------------------- diff / plan
def test_diff_only_changed_fields():
    existing = {"company": "Acme", "role": "SWE", "status": "applied",
                "salary_min": 120000.0, "applied_date": "2026-07-15"}
    desired = {"company": "Acme", "role": "SWE", "status": "interview",
               "salary_min": 120000.0, "applied_date": "2026-07-15"}
    assert sj.diff(desired, existing) == {"status": "interview"}


def test_diff_no_change_when_equal_after_canon():
    # int vs float salary, datetime vs iso date — must be seen as equal (no PATCH)
    existing = {"salary_min": 120000.0, "applied_date": "2026-07-15", "company": "Acme"}
    desired = {"salary_min": sj.canon("salary_min", 120000),
               "applied_date": sj.canon("applied_date", dt.datetime(2026, 7, 15)),
               "company": "Acme"}
    assert sj.diff(desired, existing) == {}


def test_diff_blank_desired_never_clears():
    existing = {"company": "Acme", "role": "SWE", "notes": "keep me"}
    desired = {"company": "Acme", "role": "SWE"}  # notes absent (blank cell dropped)
    assert sj.diff(desired, existing) == {}


def test_plan_splits_create_update_unchanged():
    api_rows = [
        {"id": "r1", "company": "Acme", "role": "SWE", "status": "applied"},
        {"id": "r2", "company": "Globex", "role": "PM", "status": "saved"},
    ]
    idx = sj.index_existing(api_rows)
    desired = [
        {"company": "Acme", "role": "SWE", "status": "interview"},   # update r1
        {"company": "Globex", "role": "PM", "status": "saved"},      # unchanged
        {"company": "Initech", "role": "QA", "status": "applied"},   # create
    ]
    creates, updates, unchanged = sj.plan(desired, idx)
    assert [c["company"] for c in creates] == ["Initech"]
    assert len(unchanged) == 1
    assert len(updates) == 1
    _id, _rec, changed = updates[0]
    assert _id == "r1" and changed == {"status": "interview"}


def test_index_matches_case_insensitively():
    idx = sj.index_existing([{"id": "r1", "company": "Acme Corp", "role": "SWE"}])
    desired = [{"company": "acme corp", "role": "swe", "status": "interview"}]
    creates, updates, _ = sj.plan(desired, idx)
    assert not creates and updates[0][0] == "r1"
