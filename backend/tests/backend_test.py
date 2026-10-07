import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pdf_fixture  # noqa: E402  (helper pembuat PDF uji coba)


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    from pathlib import Path
    env_paths = [Path("/home/user/Loka-Kin/frontend/.env"), Path("/app/frontend/.env")]
    for p in env_paths:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip()
                    break
            if BASE_URL:
                break
    if not BASE_URL:
        BASE_URL = "http://localhost:8000"
assert BASE_URL
BASE_URL = BASE_URL.rstrip("/")

VALID_DEPARTMENTS = {
    "Admin",
    "Bendahara",
    "Perencanaan",
    "Informasi dan Humas",
    "Layanan Rehabilitasi Medis",
    "Layanan Rehabilitasi Sosial",
    "Umum",
    "Sarana & Prasarana",
    "Clinical Supervisor",
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
        # Nomor identitas (NIP/NIK) & keterangan selalu tersedia sebagai bagian data staf
        assert {"nip", "id_type", "keterangan"}.issubset(row.keys())
        assert isinstance(row["nip"], str)
        assert row["id_type"] in {"", "NIP", "NIK"}
        assert isinstance(row["keterangan"], str)

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


def test_staff_identity_and_keterangan_roundtrip(client):
    """NIP/NIK + keterangan harus bisa disimpan, dibaca ulang, dan diubah."""
    nip = "198501012010011001"  # 18 digit → NIP
    payload = {
        "name": f"TEST_{uuid.uuid4().hex[:6]}",
        "department": "Admin",
        "nip": nip,
        "keterangan": "Pengelola arsip kepegawaian",
    }
    r = client.post(f"{BASE_URL}/api/staff", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["nip"] == nip
    assert body["id_type"] == "NIP", "18 digit otomatis dikenali sebagai NIP"
    assert body["keterangan"] == "Pengelola arsip kepegawaian"
    staff_id = body["id"]

    try:
        # kembali dari daftar staf (persistensi)
        listed = {row["id"]: row for row in client.get(f"{BASE_URL}/api/staff", timeout=20).json()}
        assert listed[staff_id]["nip"] == nip
        assert listed[staff_id]["keterangan"] == "Pengelola arsip kepegawaian"

        # ubah NIP/NIK + keterangan + departemen lewat PUT
        upd = client.put(
            f"{BASE_URL}/api/staff/{staff_id}",
            json={"nip": "1600000000000001", "id_type": "NIK", "keterangan": "Staf kontrak", "department": "Umum"},
            timeout=20,
        )
        assert upd.status_code == 200, upd.text
        updated = upd.json()
        assert updated["nip"] == "1600000000000001"
        assert updated["id_type"] == "NIK"
        assert updated["keterangan"] == "Staf kontrak"
        assert updated["department"] == "Umum"

        # jenis nomor otomatis mengikuti panjang NIP/NIK ketika id_type tidak dikirim
        upd2 = client.put(f"{BASE_URL}/api/staff/{staff_id}", json={"nip": "198501012010011001"}, timeout=20)
        assert upd2.status_code == 200
        assert upd2.json()["id_type"] == "NIP"

        # nama kosong ditolak
        bad = client.put(f"{BASE_URL}/api/staff/{staff_id}", json={"name": "   "}, timeout=20)
        assert bad.status_code == 400
    finally:
        client.delete(f"{BASE_URL}/api/staff/{staff_id}", timeout=20)


def test_staff_update_not_found(client):
    r = client.put(f"{BASE_URL}/api/staff/does-not-exist-xyz", json={"nip": "1234567890123456"}, timeout=20)
    assert r.status_code == 404


def test_staff_import_merge_and_restore(client):
    """Impor daftar staf (nama + keterangan + NIP/NIK) tersimpan dan bisa dipulihkan."""
    snapshot = client.get(f"{BASE_URL}/api/staff/roster", timeout=20).json()
    assert snapshot["count"] >= 78

    new_name = f"TEST_IMPOR_{uuid.uuid4().hex[:6]}"
    nip = "1600000000000099"  # 16 digit → NIK
    r = client.post(
        f"{BASE_URL}/api/staff/import",
        json={
            "mode": "merge",
            "source": "pytest",
            "rows": [{"name": new_name, "bagian": "Verifikator Data", "nip": nip}],
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 1
    assert body["total_roster"] == snapshot["count"] + 1

    try:
        listed = client.get(f"{BASE_URL}/api/staff", timeout=20).json()
        imported = [s for s in listed if s["name"] == new_name]
        assert len(imported) == 1, "staf hasil impor harus muncul pada daftar staf"
        row = imported[0]
        assert row["nip"] == nip
        assert row["id_type"] == "NIK"
        assert row["keterangan"] == "Verifikator Data"
    finally:
        # Pulihkan daftar resmi seperti semula agar tidak mengotori data aplikasi.
        restore = client.post(
            f"{BASE_URL}/api/staff/import",
            json={"mode": "replace", "source": snapshot["source"], "rows": snapshot["rows"]},
            timeout=30,
        )
        assert restore.status_code == 200, restore.text
        assert restore.json()["total_roster"] == snapshot["count"]

    after = client.get(f"{BASE_URL}/api/staff", timeout=20).json()
    assert not [s for s in after if s["name"] == new_name], "impor uji coba harus dibersihkan"


def test_staff_import_rejects_empty_rows(client):
    r = client.post(f"{BASE_URL}/api/staff/import", json={"mode": "replace", "rows": [{"name": "   "}]}, timeout=20)
    assert r.status_code == 400


def test_staff_import_rejects_invalid_mode(client):
    r = client.post(
        f"{BASE_URL}/api/staff/import",
        json={"mode": "hapus-semua", "rows": [{"name": "TEST_mode"}]},
        timeout=20,
    )
    assert r.status_code == 400


def _pdf_bytes(builder, tmp_path, *args):
    path = tmp_path / f"staf-{uuid.uuid4().hex[:6]}.pdf"
    builder(path, *args)
    return path.read_bytes()


def test_parse_pdf_column_layout(client, tmp_path):
    """PDF kolom (nama | NIP | keterangan) harus terbaca lengkap dengan NIP/NIK."""
    payload = _pdf_bytes(
        pdf_fixture.build_text_pdf,
        tmp_path,
        [
            [(40, "DAFTAR STAF LOKA REHABILITASI NARKOTIKA KALIANDA")],
            [(40, "NO"), (75, "NAMA"), (250, "NIP/NIK"), (360, "JABATAN/KETERANGAN")],
            [(40, "1"), (75, "Edwin, S.Sos"), (250, "198501012010011001"), (360, "Penyuluh Sosial")],
            [(40, "2"), (75, "Nurma Fitria, S.IP, M.IKom"), (250, "1600000000000002"), (360, "Kepala Bagian Umum")],
        ],
    )
    r = client.post(
        f"{BASE_URL}/api/staff/parse-pdf",
        headers={"Content-Type": None},  # multipart, bukan JSON
        files={"file": ("data-staf.pdf", payload, "application/pdf")},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2, body
    assert body["with_nip"] == 2
    first, second = body["rows"]
    assert first["name"] == "Edwin, S.Sos"
    assert first["nip"] == "198501012010011001"
    assert first["bagian"] == "Penyuluh Sosial"
    assert second["name"] == "Nurma Fitria, S.IP, M.IKom"
    assert second["nip"] == "1600000000000002"


def test_parse_pdf_ruled_table(client, tmp_path):
    """PDF tabel bergaris tanpa judul di dalam grid tetap terbaca."""
    payload = _pdf_bytes(
        pdf_fixture.build_table_pdf,
        tmp_path,
        [(40, 30, "NO"), (75, 170, "NAMA STAF"), (250, 140, "NIP/NIK"), (395, 160, "JABATAN")],
        [
            ["1", "Okta Delvianita, AMKL, SE.", "198501012010011005", "Bendahara"],
            ["2", "Yulina Destiani, A.Md.Kep", "1600000000000006", "Perawat"],
        ],
    )
    r = client.post(
        f"{BASE_URL}/api/staff/parse-pdf",
        headers={"Content-Type": None},  # multipart, bukan JSON
        files={"file": ("data-staf-tabel.pdf", payload, "application/pdf")},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    names = {row["name"]: row for row in body["rows"]}
    assert "Okta Delvianita, AMKL, SE." in names
    assert names["Okta Delvianita, AMKL, SE."]["nip"] == "198501012010011005"
    assert names["Okta Delvianita, AMKL, SE."]["bagian"] == "Bendahara"
    assert names["Yulina Destiani, A.Md.Kep"]["nip"] == "1600000000000006"


def test_parse_pdf_without_text_layer_gives_guidance(client, tmp_path):
    payload = _pdf_bytes(pdf_fixture.build_empty_pdf, tmp_path)
    r = client.post(
        f"{BASE_URL}/api/staff/parse-pdf",
        headers={"Content-Type": None},  # multipart, bukan JSON
        files={"file": ("scan.pdf", payload, "application/pdf")},
        timeout=30,
    )
    assert r.status_code == 400
    assert "scan" in r.json()["detail"].lower()


def test_parse_pdf_rejects_non_pdf(client, tmp_path):
    r = client.post(
        f"{BASE_URL}/api/staff/parse-pdf",
        headers={"Content-Type": None},  # multipart, bukan JSON
        files={"file": ("daftar.txt", b"bukan pdf", "text/plain")},
        timeout=20,
    )
    assert r.status_code == 400
    assert "pdf" in r.json()["detail"].lower()


def test_import_pdf_replaces_whole_roster(client, tmp_path):
    """Unggah PDF langsung mengganti seluruh daftar staf beserta NIP/NIK-nya."""
    snapshot = client.get(f"{BASE_URL}/api/staff/roster", timeout=20).json()
    payload = _pdf_bytes(
        pdf_fixture.build_text_pdf,
        tmp_path,
        [
            [(40, "NO"), (75, "NAMA"), (250, "NIP/NIK"), (360, "JABATAN")],
            [(40, "1"), (75, "Uji Pdf Satu, S.Kep"), (250, "198001012006041001"), (360, "Perawat Uji")],
            [(40, "2"), (75, "Uji Pdf Dua, A.Md"), (250, "1600000000000123"), (360, "Administrasi Uji")],
        ],
    )
    r = client.post(
        f"{BASE_URL}/api/staff/import-pdf",
        headers={"Content-Type": None},  # multipart, bukan JSON
        files={"file": ("data-staf.pdf", payload, "application/pdf")},
        data={"mode": "replace", "source": "pytest pdf"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 2
    assert body["total_roster"] == 2
    assert body["with_nip"] == 2

    try:
        staff = client.get(f"{BASE_URL}/api/staff?include_inactive=false", timeout=20).json()
        assert len(staff) == 2, staff
        by_name = {row["name"]: row for row in staff}
        assert by_name["Uji Pdf Satu, S.Kep"]["nip"] == "198001012006041001"
        assert by_name["Uji Pdf Satu, S.Kep"]["id_type"] == "NIP"
        assert by_name["Uji Pdf Satu, S.Kep"]["keterangan"] == "Perawat Uji"
        assert by_name["Uji Pdf Dua, A.Md"]["nip"] == "1600000000000123"
        assert by_name["Uji Pdf Dua, A.Md"]["id_type"] == "NIK"

        # Staf lama yang masih memiliki laporan tidak dihapus, melainkan diarsipkan.
        everyone = client.get(f"{BASE_URL}/api/staff", timeout=20).json()
        archived = [row for row in everyone if not row["active"]]
        assert archived, "staf lama dengan laporan harus diarsipkan, bukan dibiarkan aktif"
    finally:
        restore = client.post(
            f"{BASE_URL}/api/staff/import",
            json={"mode": "replace", "source": snapshot["source"], "rows": snapshot["rows"]},
            timeout=30,
        )
        assert restore.status_code == 200
        assert restore.json()["total_roster"] == snapshot["count"]


def test_roster_reset_reactivates_default_staff(client):
    """Kembalikan daftar bawaan: seluruh staf daftar resmi aktif kembali."""
    r = client.delete(f"{BASE_URL}/api/staff/roster", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["roster_count"] >= 78
    assert body["total_staff"] == body["active_staff"], "tidak boleh ada staf resmi yang tertinggal nonaktif"

    staff = client.get(f"{BASE_URL}/api/staff?include_inactive=false", timeout=20).json()
    assert len(staff) >= 78
    assert all(row["active"] for row in staff)


def test_database_status_reports_persistence(client):
    r = client.get(f"{BASE_URL}/api/database/status", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] in {"mongodb", "local-json", "mongodb-local"}
    assert body["collections"]["staff"] >= 78
    assert body["total_documents"] >= body["collections"]["staff"]


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


def test_target_condition_and_history_workflow(client):
    staff = client.get(f"{BASE_URL}/api/staff", timeout=20).json()[0]
    payload = {
        "title": f"TEST_TARGET_{uuid.uuid4().hex[:8]}",
        "staff_id": staff["id"],
        "status": "todo",
        "target": "Target rencana 10 berkas",
        "priority": "Tinggi",
        "due_date": "Hari ini",
        "notes": "Testing target real condition",
    }
    created = client.post(f"{BASE_URL}/api/tasks", json=payload, timeout=20)
    assert created.status_code == 200
    t = created.json()
    task_id = t["id"]
    try:
        assert t["target"] == "Target rencana 10 berkas"
        assert len(t.get("target_history", [])) >= 1
        assert t["target_history"][0]["status"] == "todo"

        # Transisi ke Doing dengan target riil progres
        patch_doing = {
            **t,
            "status": "doing",
            "target": "Target riil: 5 berkas telah diverifikasi",
        }
        r_doing = client.patch(f"{BASE_URL}/api/tasks/{task_id}", json=patch_doing, timeout=20)
        assert r_doing.status_code == 200
        t_doing = r_doing.json()
        assert t_doing["status"] == "doing"
        assert t_doing["target"] == "Target riil: 5 berkas telah diverifikasi"
        assert len(t_doing["target_history"]) >= 2
        assert t_doing["target_history"][-1]["status"] == "doing"

        # Transisi ke Finish dengan target riil hasil akhir
        patch_finish = {
            **t_doing,
            "status": "finish",
            "target": "Target riil: 10 berkas 100% selesai dan diarsipkan",
        }
        r_finish = client.patch(f"{BASE_URL}/api/tasks/{task_id}", json=patch_finish, timeout=20)
        assert r_finish.status_code == 200
        t_finish = r_finish.json()
        assert t_finish["status"] == "finish"
        assert t_finish["target"] == "Target riil: 10 berkas 100% selesai dan diarsipkan"
        assert len(t_finish["target_history"]) >= 3
        assert t_finish["target_history"][-1]["status"] == "finish"
    finally:
        client.delete(f"{BASE_URL}/api/tasks/{task_id}", timeout=20)


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
    assert {"todo", "doing", "finish"}.issubset(set(data["counts"].keys()))
    assert isinstance(data["trends"]["daily"], list) and len(data["trends"]["daily"]) > 0
    assert isinstance(data["trends"]["weekly"], list) and len(data["trends"]["weekly"]) > 0
    assert isinstance(data["trends"]["monthly"], list) and len(data["trends"]["monthly"]) > 0
    assert len(data["departments"]) == len(VALID_DEPARTMENTS)
    assert {d["name"] for d in data["departments"]} == VALID_DEPARTMENTS
    assert data["total_staff"] >= 78
    assert 0 <= data["completion_rate"] <= 100

    # Validasi KPI (Key Performance Indicators) per bagian
    assert "kpi" in data and isinstance(data["kpi"], list)
    kpi_ids = {sec["id"] for sec in data["kpi"]}
    assert {"umum", "medis", "sosial"}.issubset(kpi_ids)
    for sec in data["kpi"]:
        assert {"id", "title", "overall_score", "indicators"}.issubset(sec.keys())
        assert len(sec["indicators"]) >= 4
        for ind in sec["indicators"]:
            assert {"code", "name", "target", "realization", "status"}.issubset(ind.keys())


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


def test_task_todo_requirement_and_status_timestamps(client):
    staff = client.get(f"{BASE_URL}/api/staff", timeout=20).json()[0]

    # 1. Direct creation in 'doing' or 'finish' must be rejected (400)
    for invalid_status in ["doing", "finish"]:
        resp = client.post(f"{BASE_URL}/api/tasks", json={
            "title": f"TEST_INVALID_{invalid_status}",
            "staff_id": staff["id"],
            "status": invalid_status,
        }, timeout=20)
        assert resp.status_code == 400, f"Expected 400 when creating task directly in {invalid_status}"

    # 2. Creating in 'todo' must succeed and have todo_at timestamp
    created = client.post(f"{BASE_URL}/api/tasks", json={
        "title": "TEST_VALID_TODO",
        "staff_id": staff["id"],
        "status": "todo",
        "todo_at": "2026-09-30 08:30",
    }, timeout=20)
    assert created.status_code == 200
    task = created.json()
    assert task["status"] == "todo"
    assert task["todo_at"] == "2026-09-30 08:30"
    task_id = task["id"]

    try:
        # 3. Transition to 'doing' requires date & time
        doing_resp = client.patch(f"{BASE_URL}/api/tasks/{task_id}", json={
            "title": "TEST_VALID_TODO",
            "staff_id": staff["id"],
            "status": "doing",
            "doing_at": "2026-09-30 09:15",
        }, timeout=20)
        assert doing_resp.status_code == 200
        doing_task = doing_resp.json()
        assert doing_task["status"] == "doing"
        assert doing_task["doing_at"] == "2026-09-30 09:15"
        assert doing_task["todo_at"] == "2026-09-30 08:30"

        # 4. Transition to 'finish' records finish_at timestamp
        finish_resp = client.patch(f"{BASE_URL}/api/tasks/{task_id}", json={
            "title": "TEST_VALID_TODO",
            "staff_id": staff["id"],
            "status": "finish",
            "finish_at": "2026-09-30 14:00",
        }, timeout=20)
        assert finish_resp.status_code == 200
        finish_task = finish_resp.json()
        assert finish_task["status"] == "finish"
        assert finish_task["finish_at"] == "2026-09-30 14:00"
    finally:
        client.delete(f"{BASE_URL}/api/tasks/{task_id}", timeout=20)
