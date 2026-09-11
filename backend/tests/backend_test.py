import os
import uuid
from datetime import datetime

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    from pathlib import Path
    for line in (Path("/app/frontend/.env").read_text()).splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip()
            break
assert BASE_URL
BASE_URL = BASE_URL.rstrip("/")

VALID_DEPARTMENTS = {
    "Admin",
    "Bendahara",
    "Perencanaan",
    "Informasi dan Humas",
    "Layanan Rehabilitasi Medis",
    "Layanan Rehabilitasi Sosial",
}

SPREADSHEET_ID = "1RVliN0kwubvYBmAoCYWrIJhV6wgT2RvW4XcTAxF--1I"


@pytest.fixture
def client():
    with requests.Session() as session:
        session.headers.update({"Content-Type": "application/json"})
        yield session


# ---------- Staff endpoints ----------

def test_staff_sync_from_docx(client):
    r = client.get(f"{BASE_URL}/api/staff", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 78, f"Expected at least 78 staff, got {len(data)}"

    # never leak Mongo _id
    for row in data:
        assert "_id" not in row
        assert row["department"] in VALID_DEPARTMENTS, f"Invalid dept: {row['department']}"
        assert {"id", "name", "department", "initials", "active"}.issubset(row.keys())

    # Slot-based validation per SEED_STAFF ordering (staff-1..staff-78)
    by_id = {row["id"]: row for row in data}
    assert by_id["staff-1"]["name"] == "Edwin, S.Sos"
    assert by_id["staff-3"]["name"] == "dr. Heni Purwanti"
    assert by_id["staff-9"]["name"] == "Daniel, A.Md.Kep"
    assert by_id["staff-78"]["name"] == "Umam Wijaya"


def test_staff_create_valid_department(client):
    payload = {"name": f"TEST_{uuid.uuid4().hex[:6]}", "department": "Admin"}
    r = client.post(f"{BASE_URL}/api/staff", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "_id" not in body
    assert body["name"] == payload["name"]
    assert body["department"] == "Admin"
    assert body["initials"]
    # cleanup
    d = client.delete(f"{BASE_URL}/api/staff/{body['id']}", timeout=20)
    assert d.status_code == 200
    assert d.json()["ok"] is True


def test_staff_create_invalid_department(client):
    payload = {"name": "TEST_invalid", "department": "TidakAda"}
    r = client.post(f"{BASE_URL}/api/staff", json=payload, timeout=20)
    assert r.status_code == 400


def test_staff_delete_not_found(client):
    r = client.delete(f"{BASE_URL}/api/staff/does-not-exist-xyz", timeout=20)
    assert r.status_code == 404


# ---------- Task endpoints ----------

def test_task_crud_flow(client):
    staff = client.get(f"{BASE_URL}/api/staff", timeout=20).json()[0]
    payload = {
        "title": f"TEST_{uuid.uuid4().hex[:8]}",
        "staff_id": staff["id"],
        "status": "plan",
        "target": "1 laporan",
        "priority": "Tinggi",
        "due_date": "Besok",
        "notes": "regression",
        "proof_link": "",
        "photo_data": "",
        "photo_name": "",
    }
    created = client.post(f"{BASE_URL}/api/tasks", json=payload, timeout=20)
    assert created.status_code == 200
    task = created.json()
    assert "_id" not in task
    # created_at must be ISO parsable
    datetime.fromisoformat(task["created_at"])
    task_id = task["id"]
    try:
        patched_payload = {**payload, "status": "doing"}
        patched = client.patch(f"{BASE_URL}/api/tasks/{task_id}", json=patched_payload, timeout=20)
        assert patched.status_code == 200
        assert patched.json()["status"] == "doing"

        fetched = client.get(f"{BASE_URL}/api/tasks", timeout=20).json()
        for t in fetched:
            assert "_id" not in t
        assert any(t["id"] == task_id and t["status"] == "doing" for t in fetched)
    finally:
        deleted = client.delete(f"{BASE_URL}/api/tasks/{task_id}", timeout=20)
        assert deleted.status_code == 200
        # verify gone
        again = client.delete(f"{BASE_URL}/api/tasks/{task_id}", timeout=20)
        assert again.status_code == 404


def test_seed_tasks_reference_valid_staff(client):
    tasks = client.get(f"{BASE_URL}/api/tasks", timeout=20).json()
    staff_ids = {s["id"] for s in client.get(f"{BASE_URL}/api/staff", timeout=20).json()}
    seed_ids = [f"task-{i}" for i in range(1, 5)]
    seeded = [t for t in tasks if t["id"] in seed_ids]
    assert len(seeded) == 4, "Seed tasks task-1..task-4 must exist"
    for t in seeded:
        assert t["staff_id"] in staff_ids, f"{t['id']} refers to missing staff {t['staff_id']}"
        # Expected staff-1..staff-4 pinned
        idx = int(t["id"].split("-")[1])
        assert t["staff_id"] == f"staff-{idx}"


# ---------- Analytics ----------

def test_analytics_shape(client):
    r = client.get(f"{BASE_URL}/api/analytics", timeout=20)
    assert r.status_code == 200
    data = r.json()
    for k in ("total_tasks", "counts", "percentages", "completion_rate", "trends", "departments", "total_staff"):
        assert k in data, f"missing key {k}"
    assert set(data["counts"].keys()) == {"plan", "doing", "finish"}
    assert isinstance(data["trends"]["daily"], list) and len(data["trends"]["daily"]) > 0
    assert isinstance(data["trends"]["weekly"], list) and len(data["trends"]["weekly"]) > 0
    assert isinstance(data["trends"]["monthly"], list) and len(data["trends"]["monthly"]) > 0
    assert len(data["departments"]) == 6
    assert {d["name"] for d in data["departments"]} == VALID_DEPARTMENTS
    assert data["total_staff"] >= 78
    assert 0 <= data["completion_rate"] <= 100


# ---------- Export ----------

def test_export_status(client):
    r = client.get(f"{BASE_URL}/api/export/status", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "simulated"
    assert data["schedule"] == "21:00"
    assert data["timezone"] == "Asia/Jakarta"
    assert data["spreadsheet_id"] == SPREADSHEET_ID
    # next_run ISO
    datetime.fromisoformat(data["next_run"])


def test_export_post_logs_simulation(client):
    r = client.post(f"{BASE_URL}/api/export", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["status"] == "simulated"
    datetime.fromisoformat(data["exported_at"])
    datetime.fromisoformat(data["next_run"])

    # verify status endpoint reflects a last_export
    status = client.get(f"{BASE_URL}/api/export/status", timeout=20).json()
    assert status["last_export"] is not None
    assert "_id" not in status["last_export"]
    assert status["last_export"]["status"] == "simulated"
    assert status["last_export"]["spreadsheet_id"] == SPREADSHEET_ID
