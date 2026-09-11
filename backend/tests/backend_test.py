import os
import uuid

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


@pytest.fixture
def client():
    with requests.Session() as session:
        session.headers.update({"Content-Type": "application/json"})
        yield session


def test_staff_directory_has_85_records(client):
    response = client.get(f"{BASE_URL}/api/staff", timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 85
    assert {"id", "name", "department", "active"}.issubset(data[0])


def test_tasks_and_analytics_are_consistent(client):
    tasks_response = client.get(f"{BASE_URL}/api/tasks", timeout=20)
    analytics_response = client.get(f"{BASE_URL}/api/analytics", timeout=20)
    assert tasks_response.status_code == 200
    assert analytics_response.status_code == 200
    tasks = tasks_response.json()
    analytics = analytics_response.json()
    assert analytics["total_tasks"] == len(tasks)
    assert sum(analytics["counts"].values()) == len(tasks)


def test_task_create_patch_get_delete_flow(client):
    staff = client.get(f"{BASE_URL}/api/staff", timeout=20).json()[0]
    payload = {
        "title": f"TEST_{uuid.uuid4().hex[:8]} laporan",
        "staff_id": staff["id"],
        "status": "plan",
        "target": "1 laporan",
        "priority": "Tinggi",
        "due_date": "Besok",
        "notes": "Regression test",
        "proof_link": "https://example.com/proof",
    }
    created = client.post(f"{BASE_URL}/api/tasks", json=payload, timeout=20)
    assert created.status_code == 200
    task = created.json()
    assert task["title"] == payload["title"]
    task_id = task["id"]
    try:
        patched_payload = {**payload, "status": "finish", "target": "2 laporan"}
        patched = client.patch(f"{BASE_URL}/api/tasks/{task_id}", json=patched_payload, timeout=20)
        assert patched.status_code == 200
        assert patched.json()["status"] == "finish"
        fetched = client.get(f"{BASE_URL}/api/tasks", timeout=20)
        assert fetched.status_code == 200
        persisted = next(item for item in fetched.json() if item["id"] == task_id)
        assert persisted["target"] == "2 laporan"
    finally:
        deleted = client.delete(f"{BASE_URL}/api/tasks/{task_id}", timeout=20)
        assert deleted.status_code == 200
        assert client.patch(f"{BASE_URL}/api/tasks/{task_id}", json=payload, timeout=20).status_code == 404


def test_export_reports_ready(client):
    response = client.post(f"{BASE_URL}/api/export", timeout=20)
    assert response.status_code == 200
    assert response.json()["status"] == "ready"