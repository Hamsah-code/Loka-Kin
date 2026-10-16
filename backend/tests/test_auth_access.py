import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402
from auth_utils import hash_credential  # noqa: E402


ADMIN_NIP = "198501012010011001"
STAFF_NIP = "1600000000000002"
SUPERVISOR_NIP = "1600000000000003"
UMUM_STAFF_NIP = "1600000000000004"
OTHER_DEPT_NIP = "1600000000000005"
TEST_SETUP_SECRET = "owner-only-test-setup-secret"
TEST_PIN = "123456"
NEW_PIN = "654321"


def _task(task_id, staff_id, status="todo"):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": task_id,
        "title": f"Laporan {task_id}",
        "staff_id": staff_id,
        "status": status,
        "target": "1 berkas",
        "priority": "Sedang",
        "due_date": "",
        "notes": "",
        "proof_link": "",
        "photo_data": "",
        "photo_name": "",
        "todo_at": "2026-10-08 08:00",
        "doing_at": "2026-10-08 09:00" if status in {"doing", "finish"} else None,
        "finish_at": "2026-10-08 10:00" if status == "finish" else None,
        "status_updated_at": "2026-10-08 10:00" if status == "finish" else "2026-10-08 08:00",
        "target_history": [],
        "created_at": now,
    }


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_SETUP_SECRET", TEST_SETUP_SECRET)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)

    roster = [
        {"name": "Admin Test", "nip": ADMIN_NIP, "department": "Admin", "role": "admin"},
        {"name": "Staf Umum A", "nip": STAFF_NIP, "department": "Umum", "role": "staff"},
        {"name": "Ketua Umum", "nip": SUPERVISOR_NIP, "department": "Clinical Supervisor", "role": "team_lead", "supervised_departments": ["Umum"]},
        {"name": "Staf Umum B", "nip": UMUM_STAFF_NIP, "department": "Umum", "role": "staff"},
        {"name": "Staf Bendahara", "nip": OTHER_DEPT_NIP, "department": "Bendahara", "role": "staff"},
    ]
    staff = []
    for index, row in enumerate(roster, start=1):
        is_admin = row["role"] == "admin"
        staff.append({
            "id": f"staff-{index}",
            **row,
            "initials": row["name"][:2].upper(),
            "active": True,
            "id_type": "NIP" if len(row["nip"]) == 18 else "NIK",
            "keterangan": "",
            "position": "",
            "is_activated": not is_admin,
            "pin_hash": "" if is_admin else hash_credential(TEST_PIN),
        })

    data_file = tmp_path / "auth-test-db.json"
    data_file.write_text(json.dumps({
        "staff": staff,
        "tasks": [
            _task("task-own", "staff-2", "todo"),
            _task("task-finished-own", "staff-2", "finish"),
            _task("task-supervised", "staff-4", "todo"),
            _task("task-other-dept", "staff-5", "todo"),
        ],
        "settings": [{"key": "staff_roster", "rows": roster, "source": "roster test"}],
    }), encoding="utf-8")

    test_db, test_db_client, _mode = server.create_database("mock", data_file=data_file)
    monkeypatch.setattr(server, "db", test_db)
    monkeypatch.setattr(server, "client", test_db_client)
    server._seed_signature = None

    with TestClient(server.app) as client:
        yield client


@pytest.fixture
def admin_client(api_client):
    preview = api_client.post(
        "/api/auth/initial-roster/preview",
        data={"setup_secret": TEST_SETUP_SECRET},
        files={"file": ("roster.csv", (
            "Nama,NIP/NIK,Departemen,Role,Departemen diawasi\n"
            f"Admin Test,{ADMIN_NIP},Admin,Admin,\n"
            f"Staf Umum,{STAFF_NIP},Umum,Staf,\n"
        ).encode(), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["rows"][0]["role"] == "Admin"

    bootstrap = api_client.post("/api/auth/bootstrap-admin", json={
        "setup_secret": TEST_SETUP_SECRET,
        "nip": ADMIN_NIP,
        "roster": preview.json()["rows"],
    })
    assert bootstrap.status_code == 200, bootstrap.text
    activation_code = bootstrap.json()["activation_code"]
    activate = api_client.post("/api/auth/activate", json={
        "nip": ADMIN_NIP,
        "activation_code": activation_code,
        "pin": TEST_PIN,
        "pin_confirmation": TEST_PIN,
    })
    assert activate.status_code == 200, activate.text
    login = api_client.post("/api/auth/login", json={"nip": ADMIN_NIP, "pin": TEST_PIN})
    assert login.status_code == 200, login.text
    return api_client


def _login(client, nip):
    response = client.post("/api/auth/login", json={"nip": nip, "pin": TEST_PIN})
    assert response.status_code == 200, response.text
    return response.json()["user"]


def test_preview_session_token_fallback_is_opt_in(api_client, monkeypatch):
    monkeypatch.setenv("AUTH_PREVIEW_TOKEN_FALLBACK", "true")
    login = api_client.post("/api/auth/login", json={"nip": STAFF_NIP, "pin": TEST_PIN})
    assert login.status_code == 200
    session_token = login.json().get("session_token")
    assert session_token
    assert "no-store" in login.headers.get("cache-control", "")

    api_client.cookies.clear()
    current_user = api_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {session_token}"}
    )
    assert current_user.status_code == 200
    assert current_user.json()["id"] == "staff-2"

    monkeypatch.delenv("AUTH_PREVIEW_TOKEN_FALLBACK")
    api_client.cookies.clear()
    regular_login = api_client.post("/api/auth/login", json={"nip": STAFF_NIP, "pin": TEST_PIN})
    assert regular_login.status_code == 200
    assert "session_token" not in regular_login.json()



def test_cookie_samesite_policy_for_split_origin_deployments(api_client, monkeypatch):
    """Frontend di GitHub Pages + API di host lain butuh SameSite=None; Secure.

    Default harus tetap ``lax`` supaya deployment satu-origin tidak berubah sikap;
    nilai di luar daftar tidak boleh menghasilkan cookie tanpa SameSite.
    """
    monkeypatch.delenv("AUTH_COOKIE_SAMESITE", raising=False)
    login = api_client.post("/api/auth/login", json={"nip": STAFF_NIP, "pin": TEST_PIN})
    assert login.status_code == 200
    assert "samesite=lax" in login.headers.get("set-cookie", "").lower()
    assert "secure" not in login.headers.get("set-cookie", "").lower()

    monkeypatch.setenv("AUTH_COOKIE_SAMESITE", "none")
    cross_site = api_client.post("/api/auth/login", json={"nip": STAFF_NIP, "pin": TEST_PIN})
    cookie = cross_site.headers.get("set-cookie", "").lower()
    assert "samesite=none" in cookie, cookie
    assert "secure" in cookie  # browser menolak cookie pihak ketiga tanpa Secure
    assert "httponly" in cookie

    logout = api_client.post("/api/auth/logout", headers={"Cookie": f"{server.SESSION_COOKIE_NAME}=whatever"})
    revoked = logout.headers.get("set-cookie", "").lower()
    assert "samesite=none" in revoked and "secure" in revoked, revoked

    monkeypatch.setenv("AUTH_COOKIE_SAMESITE", "tidak-valid")
    fallback = api_client.post("/api/auth/login", json={"nip": STAFF_NIP, "pin": TEST_PIN})
    assert "samesite=lax" in fallback.headers.get("set-cookie", "").lower()


def test_preview_query_token_channel_replaces_stripped_authorization_header(api_client, monkeypatch):
    """Gateway pratinjau dapat membuang header Authorization sekaligus memblokir cookie.

    Kanal ``?access_token=`` menutupi keduanya, tetapi hanya selama mode pratinjau
    dinyalakan sehingga deployment produksi tidak pernah menerima token di URL.
    """
    monkeypatch.setenv("AUTH_PREVIEW_TOKEN_FALLBACK", "true")
    login = api_client.post("/api/auth/login", json={"nip": STAFF_NIP, "pin": TEST_PIN})
    token = login.json()["session_token"]
    api_client.cookies.clear()

    for path in ("auth/me", "tasks", "analytics"):
        result = api_client.get(f"/api/{path}?access_token={token}")
        assert result.status_code == 200, (path, result.text)
    assert api_client.get("/api/auth/me").status_code == 401  # tanpa token: tetap anonim

    assert api_client.post(f"/api/auth/logout?access_token={token}").status_code == 200
    assert api_client.get(f"/api/auth/me?access_token={token}").status_code == 401

    monkeypatch.delenv("AUTH_PREVIEW_TOKEN_FALLBACK")
    assert api_client.get(f"/api/auth/me?access_token={token}").status_code == 401


def test_explicit_session_overrides_stale_cookie_and_logout_revokes_it(api_client, monkeypatch):
    monkeypatch.setenv("AUTH_PREVIEW_TOKEN_FALLBACK", "true")
    login = api_client.post("/api/auth/login", json={"nip": STAFF_NIP, "pin": TEST_PIN})
    token = login.json()["session_token"]
    api_client.cookies.clear()
    headers = {
        "Authorization": f"Bearer {token}",
        "Cookie": f"{server.SESSION_COOKIE_NAME}=expired-old-cookie",
    }
    for path in ("auth/me", "staff", "tasks", "analytics"):
        result = api_client.get(f"/api/{path}", headers=headers)
        assert result.status_code == 200, (path, result.text)

    assert api_client.post("/api/auth/logout", headers=headers).status_code == 200
    assert api_client.get("/api/auth/me", headers=headers).status_code == 401


def test_invalid_explicit_session_does_not_fall_back_to_cookie(api_client):
    _login(api_client, STAFF_NIP)
    assert api_client.get("/api/auth/me").status_code == 200
    assert api_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid-token"}
    ).status_code == 401

def _full_task(task_id, staff_id, *, title=None, status="todo"):
    return {
        "title": title or f"Laporan {task_id}",
        "staff_id": staff_id,
        "status": status,
        "target": "2 berkas",
        "priority": "Sedang",
        "due_date": "",
        "notes": "",
        "proof_link": "",
        "photo_data": "",
        "photo_name": "",
        "todo_at": "2026-10-08 08:00",
        "doing_at": "2026-10-08 09:00" if status in {"doing", "finish"} else None,
        "finish_at": "2026-10-08 10:00" if status == "finish" else None,
        "status_updated_at": "2026-10-08 10:00" if status == "finish" else "2026-10-08 08:00",
        "target_history": [],
    }


def test_bootstrap_requires_admin_roster_row_and_activates_first_admin(api_client):
    status = api_client.get("/api/auth/setup-status")
    assert status.status_code == 200
    assert status.json()["initial_admin_required"] is True

    missing = api_client.post("/api/auth/bootstrap-admin", json={"setup_secret": TEST_SETUP_SECRET, "nip": STAFF_NIP})
    assert missing.status_code == 404

    bootstrap = api_client.post("/api/auth/bootstrap-admin", json={"setup_secret": TEST_SETUP_SECRET, "nip": ADMIN_NIP})
    assert bootstrap.status_code == 200, bootstrap.text
    code = bootstrap.json()["activation_code"]
    assert len(code.replace("-", "")) == 12

    before_activation = api_client.post("/api/auth/login", json={"nip": ADMIN_NIP, "pin": TEST_PIN})
    assert before_activation.status_code == 401

    activated = api_client.post("/api/auth/activate", json={
        "nip": ADMIN_NIP, "activation_code": code, "pin": TEST_PIN, "pin_confirmation": TEST_PIN,
    })
    assert activated.status_code == 200, activated.text
    logged_in = api_client.post("/api/auth/login", json={"nip": ADMIN_NIP, "pin": TEST_PIN})
    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["role"] == "admin"
    assert api_client.get("/api/auth/me").json()["role"] == "admin"
    assert api_client.get("/api/auth/setup-status").json()["initial_admin_required"] is False

    reused = api_client.post("/api/auth/activate", json={
        "nip": ADMIN_NIP, "activation_code": code, "pin": NEW_PIN, "pin_confirmation": NEW_PIN,
    })
    assert reused.status_code == 400, "kode aktivasi harus sekali pakai"


def test_staff_is_scoped_to_own_reports_even_if_staff_id_is_forged(api_client):
    _login(api_client, STAFF_NIP)

    visible_tasks = api_client.get("/api/tasks").json()
    assert {task["id"] for task in visible_tasks} == {"task-own", "task-finished-own"}
    visible_staff = api_client.get("/api/staff").json()
    assert [row["id"] for row in visible_staff] == ["staff-2"]
    assert visible_staff[0]["nip"] == "", "NIP/NIK tidak bocor kepada pengguna non-Admin"
    assert api_client.get("/api/staff/roster").status_code == 403

    created = api_client.post("/api/tasks", json=_full_task("forged", "staff-5"))
    assert created.status_code == 200, created.text
    assert created.json()["staff_id"] == "staff-2", "API harus mengikat laporan Staf ke akun sendiri"

    foreign_update = api_client.patch("/api/tasks/task-supervised", json=_full_task("task-supervised", "staff-2", title="Tidak boleh"))
    assert foreign_update.status_code == 403
    finished_update = api_client.patch("/api/tasks/task-finished-own", json=_full_task("task-finished-own", "staff-2", status="doing"))
    assert finished_update.status_code == 403

    own_update = api_client.patch("/api/tasks/task-own", json=_full_task("task-own", "staff-5", title="Laporan saya diperbarui", status="doing"))
    assert own_update.status_code == 200, own_update.text
    assert own_update.json()["staff_id"] == "staff-2"

    analytics = api_client.get("/api/analytics").json()
    assert analytics["total_staff"] == 1
    assert analytics["total_tasks"] == 3, "analitik Staf hanya memuat laporan miliknya"


def test_supervisor_can_read_all_but_write_only_assigned_departments(api_client):
    _login(api_client, SUPERVISOR_NIP)

    visible_tasks = api_client.get("/api/tasks").json()
    assert {task["id"] for task in visible_tasks} == {"task-own", "task-finished-own", "task-supervised", "task-other-dept"}
    visible_staff = api_client.get("/api/staff").json()
    assert len(visible_staff) == 5
    assert all(row["nip"] == "" for row in visible_staff)

    allowed_create = api_client.post("/api/tasks", json=_full_task("supervisor-new", "staff-4"))
    assert allowed_create.status_code == 200, allowed_create.text
    denied_create = api_client.post("/api/tasks", json=_full_task("outside-new", "staff-5"))
    assert denied_create.status_code == 403

    allowed_update = api_client.patch("/api/tasks/task-supervised", json=_full_task("task-supervised", "staff-4", title="Perubahan Ketua", status="doing"))
    assert allowed_update.status_code == 200, allowed_update.text
    denied_update = api_client.patch("/api/tasks/task-other-dept", json=_full_task("task-other-dept", "staff-5", title="Tidak boleh"))
    assert denied_update.status_code == 403
    finished_update = api_client.patch("/api/tasks/task-finished-own", json=_full_task("task-finished-own", "staff-2", status="doing"))
    assert finished_update.status_code == 403
    assert api_client.delete("/api/tasks/task-finished-own").status_code == 403

    assert api_client.get("/api/analytics").json()["total_staff"] == 5


def test_admin_can_manage_roles_reset_pin_and_correct_finished_report(admin_client):
    created_staff = admin_client.post("/api/staff", json={
        "name": "Supervisor Baru",
        "department": "Clinical Supervisor",
        "nip": "1600000000000099",
        "role": "head",
        "supervised_departments": ["Umum", "Bendahara"],
    })
    assert created_staff.status_code == 200, created_staff.text
    assert created_staff.json()["role"] == "head"
    assert created_staff.json()["supervised_departments"] == ["Umum", "Bendahara"]
    assert "pin_hash" not in created_staff.json()
    assert "activation_code_hash" not in created_staff.json()

    corrected = admin_client.patch(
        "/api/tasks/task-finished-own",
        json=_full_task("task-finished-own", "staff-2", title="Koreksi Admin", status="finish"),
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["title"] == "Koreksi Admin"

    issued = admin_client.post(f"/api/auth/staff/staff-2/activation-code")
    assert issued.status_code == 200, issued.text
    code = issued.json()["activation_code"]
    assert api_login_fails(admin_client, STAFF_NIP, TEST_PIN)
    activation = admin_client.post("/api/auth/activate", json={
        "nip": STAFF_NIP,
        "activation_code": code,
        "pin": NEW_PIN,
        "pin_confirmation": NEW_PIN,
    })
    assert activation.status_code == 200, activation.text
    new_login = admin_client.post("/api/auth/login", json={"nip": STAFF_NIP, "pin": NEW_PIN})
    assert new_login.status_code == 200, new_login.text
    assert new_login.json()["user"]["role"] == "staff"


def api_login_fails(client, nip, pin):
    response = client.post("/api/auth/login", json={"nip": nip, "pin": pin})
    return response.status_code == 401


def test_admin_import_can_assign_roster_roles_but_never_imports_a_pin(admin_client):
    imported = admin_client.post("/api/staff/import", json={
        "mode": "merge",
        "source": "roster test",
        "rows": [{
            "name": "Clinical Supervisor Baru",
            "nip": "1600000000000098",
            "department": "Layanan Rehabilitasi Medis",
            "role": "Clinical Supervisor",
            "supervised_departments": ["Umum"],
            "pin": "112233",
        }],
    })
    assert imported.status_code == 200, imported.text
    rows = admin_client.get("/api/staff/roster").json()["rows"]
    roster_row = next(row for row in rows if row["name"] == "Clinical Supervisor Baru")
    assert roster_row["role"] == "clinical_supervisor"
    assert roster_row["supervised_departments"] == ["Umum"]
    assert "pin" not in roster_row
    assert "pin_hash" not in roster_row

    created = admin_client.get("/api/staff").json()
    account = next(row for row in created if row["name"] == "Clinical Supervisor Baru")
    assert account["is_activated"] is False
    assert account["nip"] == "1600000000000098"


def test_unauthenticated_requests_are_denied_and_logout_revokes_session(api_client):
    assert api_client.get("/api/tasks").status_code == 401
    assert api_client.get("/api/staff").status_code == 401
    assert api_client.get("/api/analytics").status_code == 401
    user = _login(api_client, STAFF_NIP)
    assert user["role"] == "staff"
    assert api_client.post("/api/auth/logout").status_code == 200
    assert api_client.get("/api/auth/me").status_code == 401


def _bootstrap_super_admin(client, nip="198602022012011002"):
    setup = client.post("/api/auth/bootstrap-super-admin", json={
        "setup_secret": TEST_SETUP_SECRET,
        "name": "Super Admin Test",
        "nip": nip,
    })
    assert setup.status_code == 200, setup.text
    code = setup.json()["activation_code"]
    activation = client.post("/api/auth/activate", json={
        "nip": nip,
        "activation_code": code,
        "pin": "864209",
        "pin_confirmation": "864209",
    })
    assert activation.status_code == 200, activation.text
    login = client.post("/api/auth/login", json={"nip": nip, "pin": "864209"})
    assert login.status_code == 200, login.text
    return login.json()["user"]


def test_super_admin_bootstrap_and_landing_page_controls(api_client):
    public_defaults = api_client.get("/api/public/landing-settings")
    assert public_defaults.status_code == 200
    assert public_defaults.json()["brand_name"] == "Loka-Kin"

    super_admin = _bootstrap_super_admin(api_client)
    assert super_admin["role"] == "super_admin"
    assert super_admin["role_label"] == "Super Admin"

    updated = api_client.put("/api/admin/landing-settings", json={
        **server.DEFAULT_LANDING_SETTINGS,
        "brand_name": "Loka Rehabilitasi Kalianda",
        "hero_title": "Kinerja layanan",
        "show_features": False,
        "accent_color": "#3366CC",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["brand_name"] == "Loka Rehabilitasi Kalianda"
    assert api_client.get("/api/public/landing-settings").json()["show_features"] is False
    assert api_client.get("/api/admin/credentials/status").status_code == 200


def test_regular_admin_cannot_access_super_admin_tools_or_assign_super_admin(admin_client):
    assert admin_client.get("/api/admin/credentials/status").status_code == 403
    assert admin_client.put("/api/admin/landing-settings", json=server.DEFAULT_LANDING_SETTINGS).status_code == 403
    created = admin_client.post("/api/staff", json={
        "name": "Percobaan Super Admin",
        "department": "Admin",
        "nip": "198602022012011009",
        "role": "super_admin",
    })
    assert created.status_code == 403


def test_credentials_pdf_rotates_staff_pins_once_and_forces_change(api_client, monkeypatch):
    _bootstrap_super_admin(api_client)
    generated = []

    def deterministic_pin(used):
        value = f"{900001 + len(used):06d}"
        used.add(value)
        generated.append(value)
        return value

    monkeypatch.setattr(server, "generate_temporary_pin", deterministic_pin)
    status = api_client.get("/api/admin/credentials/status")
    assert status.status_code == 200
    assert status.json()["ready_for_pin_pdf"] is True

    pdf = api_client.post("/api/admin/credentials/rotate-pdf", json={})
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")
    assert len(generated) == 5

    # staff-2 sorts second (after the Admin fixture account), and receives 900002.
    login = api_client.post("/api/auth/login", json={"nip": STAFF_NIP, "pin": "900002"})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["must_change_pin"] is True
    blocked = api_client.get("/api/tasks")
    assert blocked.status_code == 403

    changed = api_client.post("/api/auth/change-pin", json={
        "current_pin": "900002",
        "new_pin": NEW_PIN,
        "pin_confirmation": NEW_PIN,
    })
    assert changed.status_code == 200, changed.text
    assert api_client.get("/api/auth/me").json()["must_change_pin"] is False
    assert api_client.get("/api/tasks").status_code == 200


def test_credentials_pdf_blocks_missing_or_placeholder_official_ids(api_client):
    _bootstrap_super_admin(api_client)
    api_client.put(f"/api/staff/staff-2", json={
        "name": "Staf Umum A",
        "department": "Umum",
        "nip": "",
    })
    status = api_client.get("/api/admin/credentials/status")
    assert status.status_code == 200
    assert status.json()["ready_for_pin_pdf"] is False
    assert status.json()["missing_or_placeholder_identity"] >= 1
    response = api_client.post("/api/admin/credentials/rotate-pdf", json={})
    assert response.status_code == 409
    assert "NIP/NIK resmi" in response.json()["detail"]["message"]


def test_roster_replace_and_reset_do_not_disable_super_admin(api_client):
    user = _bootstrap_super_admin(api_client, nip=STAFF_NIP)
    replacement = api_client.post("/api/staff/import", json={
        "mode": "replace",
        "rows": [{"name": "Pegawai pengujian", "nip": UMUM_STAFF_NIP, "department": "Umum"}],
    })
    assert replacement.status_code == 200, replacement.text
    assert api_client.get("/api/auth/me").json()["id"] == user["id"]
    assert api_client.get("/api/admin/credentials/status").status_code == 200
    assert api_client.delete("/api/staff/roster").status_code == 200
    assert api_client.get("/api/auth/me").json()["role"] == "super_admin"


def test_roster_role_does_not_demote_system_super_admin(api_client):
    _bootstrap_super_admin(api_client, nip=STAFF_NIP)
    replacement = api_client.post("/api/staff/import", json={
        "mode": "replace",
        "rows": [{"name": "Staf Umum A", "nip": STAFF_NIP, "department": "Umum", "role": "staff"}],
    })
    assert replacement.status_code == 200, replacement.text
    assert api_client.get("/api/auth/me").json()["role"] == "super_admin"


def test_small_roster_with_no_reports_does_not_crash(api_client):
    _bootstrap_super_admin(api_client)
    api_client.portal.call(server.db.tasks.delete_many, {})
    replacement = api_client.post("/api/staff/import", json={
        "mode": "replace",
        "rows": [{"name": "Staf Umum A", "nip": STAFF_NIP, "department": "Umum"}],
    })
    assert replacement.status_code == 200, replacement.text
    assert api_client.get("/api/tasks").json() == []
    assert api_client.get("/api/analytics").status_code == 200
