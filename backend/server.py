from fastapi import FastAPI, APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any
from secrets import token_urlsafe
import hashlib, json, os, re, tempfile, uuid, asyncio

from auth_utils import (
    constant_time_equal,
    generate_activation_code,
    hash_credential,
    hash_session_token,
    normalize_activation_code,
    normalize_identity,
    valid_identity,
    valid_pin,
    verify_credential,
)

from db import create_database
from csv_import import extract_rows as extract_csv_rows
from pdf_import import extract_rows

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
DATA_FILE = ROOT_DIR / "data" / "loka_kin_db.json"
mongo_url = os.environ.get("MONGO_URL", "")
db, client, DB_MODE = create_database(mongo_url, os.environ.get("DB_NAME", "loka_kin"), DATA_FILE)
app = FastAPI(title="LOKA-Kin API")
api = APIRouter(prefix="/api")

DEPARTMENTS = ["Admin", "Bendahara", "Perencanaan", "Informasi dan Humas", "Layanan Rehabilitasi Medis", "Layanan Rehabilitasi Sosial", "Umum", "Sarana & Prasarana", "Clinical Supervisor"]

ROLE_LABELS = {
    "staff": "Staf",
    "admin": "Admin",
    "team_lead": "Ketua Tim",
    "clinical_supervisor": "Clinical Supervisor",
    "head": "Kepala",
}
VALID_ROLES = set(ROLE_LABELS)
SUPERVISOR_ROLES = {"team_lead", "clinical_supervisor", "head"}
READ_ALL_ROLES = {"admin", *SUPERVISOR_ROLES}
SESSION_COOKIE_NAME = "loka_kin_session"
SESSION_TTL_HOURS = 12
ACTIVATION_TTL_HOURS = 24
AUTH_MAX_ATTEMPTS = 5
AUTH_LOCK_MINUTES = 15


def normalize_role(value: str) -> str:
    raw = str(value or "staff").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "staf": "staff", "pegawai": "staff", "admin": "admin",
        "ketua_tim": "team_lead", "ketuatim": "team_lead", "team_leader": "team_lead",
        "clinical_supervisor": "clinical_supervisor", "supervisor_klinis": "clinical_supervisor",
        "kepala": "head", "head_of_office": "head",
    }
    return aliases.get(raw, raw)


def valid_supervised_departments(values: List[str]) -> List[str]:
    clean = []
    for value in values or []:
        dept = str(value).strip()
        if dept and dept in DEPARTMENTS and dept not in clean:
            clean.append(dept)
    return clean

# Pemetaan bagian/jabatan pada DAFTAR STAF ke departemen resmi aplikasi
DEPT_MAP = {
    "Layanan Sosial": "Layanan Rehabilitasi Sosial",
    "Layanan Medis": "Layanan Rehabilitasi Medis",
    "Clinical Supervisor": "Clinical Supervisor",
    "Bendahara": "Bendahara",
    "Perencanaan": "Perencanaan",
    "Umum": "Umum",
    "Administrasi & SDM": "Admin",
    "Administrasi dan SDM": "Admin",
    "Sarana Prasarana": "Sarana & Prasarana",
    "Sarana & Prasarana": "Sarana & Prasarana",
    "Pengadaan Barang & Jasa": "Admin",
    "Humas": "Informasi dan Humas",
    "Informasi dan Humas": "Informasi dan Humas",
    "Layanan Rehabilitasi Sosial": "Layanan Rehabilitasi Sosial",
    "Layanan Rehabilitasi Medis": "Layanan Rehabilitasi Medis",
    "Admin": "Admin",
}

# Sumber: DAFTAR HADIR STAF.docx (78 staf resmi)
SEED_STAFF = [
    ("Edwin, S.Sos", "Layanan Sosial"),
    ("Nurma Fitria, S.IP, M.IKom", "Umum"),
    ("dr. Heni Purwanti", "Layanan Medis"),
    ("Saiful Bahri, A.Md.Kep", "Sarana Prasarana"),
    ("Okta Delvianita, AMKL, SE.", "Bendahara"),
    ("Ns. Hamsah Prihadi Istianto, S.Kep", "Clinical Supervisor"),
    ("dr. Utari Gita Mutiara", "Layanan Medis"),
    ("Yulina Destiani, A.Md.Kep", "Layanan Medis"),
    ("Daniel, A.Md.Kep", "Administrasi & SDM"),
    ("Yoga Adi Yuliawan, A.Md.Kes", "Pengadaan Barang & Jasa"),
    ("Evi Soleha, A.Md.AK", "Layanan Medis"),
    ("Nanda Alif Utama, A.Md.RAD", "Layanan Sosial"),
    ("Risma Sefridasari, A.Md.KG", "Layanan Medis"),
    ("Tri Yunita, A.Md.Keb", "Layanan Medis"),
    ("Dendi Purnama, S.Kep, Ns", "Layanan Medis"),
    ("Randy Simanjutak, A.Md.Gz", "Layanan Medis"),
    ("Ikke Asmawati, A.Md.KL", "Perencanaan"),
    ("dr. Resti Adystia", "Layanan Medis"),
    ("Karunia Hadpha Saputri, A.Md.Keb", "Layanan Medis"),
    ("Wiria Ahaddillah, S.Kep, Ners", "Layanan Medis"),
    ("Heby Segapa, A.Md.Farm", "Layanan Medis"),
    ("Febri Ardiyansyah, AMF", "Layanan Medis"),
    ("Anggi Oktaria, A.Md.Ft", "Layanan Medis"),
    ("Pika Junetthy BR Pinem, A.Md.Gz", "Layanan Medis"),
    ("Galuh Dwi Satria Vianto, A.Md.Kep", "Layanan Sosial"),
    ("Yessy Lisnawati, SE", "Umum"),
    ("Yudian Pratama Putra, S.M", "Umum"),
    ("Restivo Nandami, A.Md", "Umum"),
    ("Heti Liswati", "Umum"),
    ("Riza Rimayanti", "Umum"),
    ("Denda Nopriawan Putra", "Umum"),
    ("Ahmad Soleh, S.Kom", "Umum"),
    ("Amardin Fikri, A.Md", "Umum"),
    ("Evi Talia, A.Md", "Umum"),
    ("Eka Rahma Saputri", "Umum"),
    ("Indra Gunawan", "Layanan Sosial"),
    ("Amelia, A.Md.Kep", "Layanan Sosial"),
    ("Adams Resmitha Thalib, SE", "Layanan Sosial"),
    ("Arisman", "Layanan Sosial"),
    ("Rizal, S.Psi", "Layanan Sosial"),
    ("Yoga Eko Budiyanto", "Layanan Sosial"),
    ("Raga Dwindo Pangestu", "Layanan Sosial"),
    ("Wendy Ramarten, S.Pd", "Layanan Sosial"),
    ("Yoyon Saputra, S.Sos", "Layanan Sosial"),
    ("Indra Ibnul Alhibi Ramadhani, A.Md.Pi", "Layanan Sosial"),
    ("Emi Rosmiko Sari, A.Md.Kep", "Layanan Medis"),
    ("Saiful Hamdani, S.Psi", "Layanan Medis"),
    ("M. Nur Hidayatullah", "Layanan Sosial"),
    ("Yusuf Arief Sena K, S.Psi", "Layanan Sosial"),
    ("Suci Ramadani, AMKL", "Layanan Sosial"),
    ("Nadia Maulidia, A.Md.RMIK", "Layanan Medis"),
    ("Nur Cholish", "Umum"),
    ("Gunawan Adi Saputra", "Umum"),
    ("Saipul Bahri", "Umum"),
    ("Septila Damirza", "Umum"),
    ("Ma'ruf Nufri Ismail", "Umum"),
    ("Mukhsinin", "Umum"),
    ("Andri Setiawan", "Umum"),
    ("Agus Feriyanto", "Umum"),
    ("M. Arif Prasetyo", "Umum"),
    ("Agus Yahya", "Umum"),
    ("Joko Santoso", "Umum"),
    ("Dedi Irawan", "Umum"),
    ("Faisal", "Umum"),
    ("Samsun Efendi", "Umum"),
    ("Sahrul", "Umum"),
    ("Amrulloh", "Umum"),
    ("Wardani", "Umum"),
    ("Ridho Kurnia", "Umum"),
    ("Gading Ade Nata, A.Md.Pt", "Layanan Sosial"),
    ("Junaidi", "Umum"),
    ("Ali Usman", "Umum"),
    ("Alimun", "Umum"),
    ("Rusli", "Umum"),
    ("Solehah", "Umum"),
    ("M. Yoga Pratama", "Umum"),
    ("Bagus Prasetio, A.Md.P", "Layanan Sosial"),
    ("Umam Wijaya", "Umum"),
]

TITLE_TOKENS = {"dr", "ns", "hj", "h", "drs", "dra", "mr", "mrs"}

# Sidik jari daftar staf resmi terakhir yang sudah disinkronkan ke database.
_seed_signature: Optional[str] = None
_seed_lock = asyncio.Lock()


def make_initials(name: str) -> str:
    cleaned = name.replace(".", " ").replace(",", " ")
    words = [w for w in cleaned.split() if w and w[0].isalpha()]
    words = [w for w in words if w.lower() not in TITLE_TOKENS]
    initials = "".join(w[0].upper() for w in words[:2])
    return initials or name[:2].upper()


def infer_id_type(nip: str) -> str:
    """Tebak jenis nomor identitas: NIP (PNS, 18 digit) atau NIK (16 digit)."""
    digits = "".join(ch for ch in str(nip or "") if ch.isdigit())
    if not digits:
        return ""
    if len(digits) == 18:
        return "NIP"
    if len(digits) == 16:
        return "NIK"
    return "NIP" if len(digits) > 16 else "NIK"


def seed_key_for(
    staff_id: str,
    name: str,
    department: str,
    nip: str,
    id_type: str,
    keterangan: str,
    role: str = "staff",
    supervised_departments: Optional[List[str]] = None,
) -> str:
    raw = "|".join([
        staff_id, name, department, str(nip or ""), id_type, keterangan or "", role,
        ",".join(supervised_departments or []),
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def normalized_person_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(value or "").lower())).strip()


def resolve_department(doc_dept: str) -> str:
    """Normalisasi bagian/jabatan pada daftar staf ke departemen resmi aplikasi."""
    if not doc_dept:
        return "Admin"
    mapped = DEPT_MAP.get(doc_dept)
    if mapped:
        return mapped
    return doc_dept if doc_dept in DEPARTMENTS else "Admin"


def staff_sort_key(person):
    sid = person.get("id", "")
    if sid.startswith("staff-"):
        tail = sid.split("-", 1)[1]
        if tail.isdigit():
            return (0, int(tail))
    return (1, sid)


class Staff(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    department: str
    initials: str
    active: bool = True
    nip: str = ""
    id_type: str = ""
    keterangan: str = ""
    position: str = ""
    role: str = "staff"
    supervised_departments: List[str] = Field(default_factory=list)
    is_activated: bool = False


class StaffCreate(BaseModel):
    name: str
    department: str
    active: bool = True
    nip: str = ""
    id_type: str = ""
    keterangan: str = ""
    position: str = ""
    role: str = "staff"
    supervised_departments: List[str] = Field(default_factory=list)


class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    department: Optional[str] = None
    nip: Optional[str] = None
    id_type: Optional[str] = None
    keterangan: Optional[str] = None
    position: Optional[str] = None
    active: Optional[bool] = None
    role: Optional[str] = None
    supervised_departments: Optional[List[str]] = None


class StaffImportRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    bagian: str = ""
    nip: str = ""
    department: str = ""
    role: Optional[str] = None
    supervised_departments: List[str] = Field(default_factory=list)


class StaffImportRequest(BaseModel):
    rows: List[StaffImportRow]
    mode: str = "replace"
    source: str = "impor manual"


class AuthLoginRequest(BaseModel):
    nip: str
    pin: str


class AuthActivateRequest(BaseModel):
    nip: str
    activation_code: str
    pin: str
    pin_confirmation: str


class BootstrapAdminRequest(BaseModel):
    setup_secret: str
    nip: str
    roster: Optional[List[StaffImportRow]] = None


class ActivationCodeRequest(BaseModel):
    staff_id: str


class TaskCreate(BaseModel):
    title: str
    staff_id: str
    status: str = "todo"
    target: str = ""
    priority: str = "Sedang"
    due_date: str = ""
    notes: str = ""
    proof_link: str = ""
    photo_data: str = ""
    photo_name: str = ""
    todo_at: Optional[str] = None
    doing_at: Optional[str] = None
    finish_at: Optional[str] = None
    status_updated_at: Optional[str] = None
    target_history: Optional[List[Dict[str, Any]]] = None


class Task(TaskCreate):
    model_config = ConfigDict(extra="ignore")
    id: str
    created_at: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_datetime(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (TypeError, ValueError):
        return None


def public_staff(
    row: Dict[str, Any],
    *,
    reveal_identity: bool,
    reveal_account_status: bool = False,
) -> Dict[str, Any]:
    """Return only UI-safe staff fields; auth hashes and activation codes never leave the API."""
    safe = {
        key: row.get(key, default)
        for key, default in {
            "id": "", "name": "", "department": "", "initials": "",
            "active": True, "keterangan": "", "position": "",
            "role": "staff", "supervised_departments": [],
        }.items()
    }
    if reveal_account_status:
        safe["is_activated"] = bool(row.get("is_activated"))
    safe["nip"] = str(row.get("nip") or "") if reveal_identity else ""
    safe["id_type"] = str(row.get("id_type") or "") if reveal_identity else ""
    return safe


def user_profile(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "department": row.get("department"),
        "role": row.get("role", "staff"),
        "role_label": ROLE_LABELS.get(row.get("role", "staff"), "Staf"),
        "supervised_departments": row.get("supervised_departments") or [],
    }


async def get_current_user(request: Request) -> Dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    authorization = request.headers.get("authorization", "")
    if not token and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(401, "Silakan masuk untuk melanjutkan.")

    session = await db.auth_sessions.find_one({"token_hash": hash_session_token(token)}, {"_id": 0})
    expires_at = parse_datetime((session or {}).get("expires_at"))
    if not session or not expires_at or expires_at <= utc_now():
        if session:
            await db.auth_sessions.delete_one({"id": session.get("id")})
        raise HTTPException(401, "Sesi masuk berakhir. Silakan masuk kembali.")

    user = await db.staff.find_one({"id": session.get("staff_id")}, {"_id": 0})
    if not user or not user.get("active", True) or not user.get("is_activated"):
        await db.auth_sessions.delete_one({"id": session.get("id")})
        raise HTTPException(401, "Akun tidak aktif. Hubungi Admin.")
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(403, "Fitur ini hanya dapat digunakan Admin.")
    return user


def can_manage_staff_record(user: Dict[str, Any], staff_record: Dict[str, Any]) -> bool:
    role = user.get("role", "staff")
    if role == "admin":
        return True
    if staff_record.get("active", True) is False:
        return False
    if role == "staff":
        return user.get("id") == staff_record.get("id")
    return (
        role in SUPERVISOR_ROLES
        and staff_record.get("department") in (user.get("supervised_departments") or [])
    )


def is_report_manager(user: Dict[str, Any]) -> bool:
    return user.get("role") in READ_ALL_ROLES


def normalize_task_status(value: Any) -> Optional[str]:
    status = str(value or "todo").strip().lower()
    if status in {"plan", "todo"}:
        return "todo"
    return status if status in {"doing", "finish"} else None


async def issue_activation_code(staff_record: Dict[str, Any], issued_by: str) -> Dict[str, Any]:
    code = generate_activation_code()
    expires = utc_now() + timedelta(hours=ACTIVATION_TTL_HOURS)
    await db.auth_sessions.delete_many({"staff_id": staff_record["id"]})
    await db.staff.update_one(
        {"id": staff_record["id"]},
        {"$set": {
            "activation_code_hash": hash_credential(normalize_activation_code(code)),

            "activation_code_expires_at": iso_utc(expires),
            "activation_code_attempts": 0,
            "activation_code_locked_until": "",
            "activation_code_issued_by": issued_by,
            "activation_code_locked_until": "",
            "login_failed_attempts": 0,
            "login_locked_until": "",
            "is_activated": False,
            "pin_hash": "",
        }},
    )
    return {"staff_id": staff_record["id"], "activation_code": code, "expires_at": iso_utc(expires)}


ROSTER_KEY = "staff_roster"


def row_to_dict(row) -> Dict[str, Any]:
    """Normalisasi entri SEED_STAFF (tuple) maupun hasil impor (dict)."""
    if isinstance(row, dict):
        return {
            "name": str(row.get("name", "")).strip(),
            "bagian": str(row.get("bagian") or row.get("keterangan") or "").strip(),
            "nip": normalize_identity(row.get("nip") or ""),
            "position": str(row.get("position") or "").strip(),
            "department": str(row.get("department") or "").strip(),
            "role": normalize_role(row.get("role")) if row.get("role") else "",
            "supervised_departments": valid_supervised_departments(row.get("supervised_departments") or []),
        }
    name = row[0] if len(row) > 0 else ""
    bagian = row[1] if len(row) > 1 else ""
    nip = row[2] if len(row) > 2 else ""
    position = row[3] if len(row) > 3 else ""
    return row_to_dict({"name": name, "bagian": bagian, "nip": nip, "position": position})


async def active_roster() -> tuple[List[Dict[str, Any]], str]:
    """Daftar staf yang berlaku: hasil impor bila ada, jika tidak daftar bawaan."""
    doc = await db.settings.find_one({"key": ROSTER_KEY}, {"_id": 0})
    if doc and doc.get("rows"):
        return [row_to_dict(r) for r in doc["rows"]], doc.get("source") or "impor"
    return [row_to_dict(r) for r in SEED_STAFF], "daftar bawaan aplikasi (DAFTAR HADIR STAF.docx)"


async def save_roster(rows: List[Dict[str, Any]], source: str) -> None:
    await db.settings.update_one(
        {"key": ROSTER_KEY},
        {"$set": {"key": ROSTER_KEY, "rows": rows, "source": source, "updated_at": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat()}},
        upsert=True,
    )


async def seed_data(force: bool = False):
    """Jalankan sinkronisasi roster paling banyak satu kali pada satu waktu."""
    async with _seed_lock:
        roster, _source = await active_roster()
        signature = hashlib.sha1(json.dumps(roster, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if not force and _seed_signature == signature:
            return
        await _sync_seed_data(force)


async def _sync_seed_data(force: bool = False):
    """Sinkronkan daftar staf resmi (SEED_STAFF) ke database secara idempotent.

    Staf yang belum ada dibuat sebagai ``staff-1..staff-N`` sesuai urutan daftar
    resmi. Staf yang sudah ada hanya ditimpa bila sumbernya (nama/bagian/NIP)
    berubah — perubahan yang dilakukan admin lewat aplikasi tetap dipertahankan.

    Fungsi ini aman dipanggil di setiap request karena langsung keluar bila
    daftar resmi belum berubah sejak sinkronisasi terakhir.
    """
    global _seed_signature
    roster, _source = await active_roster()
    signature = hashlib.sha1(json.dumps(roster, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    if not force and _seed_signature == signature:
        return
    all_staff = await db.staff.find({}, {"_id": 0}).to_list(5000)
    staff_by_id = {person.get("id"): person for person in all_staff if person.get("id")}
    staff_by_nip: Dict[str, Dict[str, Any]] = {}
    staff_by_name: Dict[str, List[Dict[str, Any]]] = {}
    for person in all_staff:
        identity = normalize_identity(person.get("nip") or "")
        if identity:
            staff_by_nip.setdefault(identity, person)
        staff_by_name.setdefault(normalized_person_name(person.get("name", "")), []).append(person)

    assigned_ids = set()
    official_ids = set()
    for i, row in enumerate(roster, start=1):
        name = row["name"]
        name_key = normalized_person_name(name)
        doc_dept = row.get("bagian") or row.get("department") or ""
        nip = normalize_identity(row.get("nip") or "")
        position = row.get("position") or ""
        department = row.get("department") or resolve_department(doc_dept)
        slot_id = f"staff-{i}"

        existing = staff_by_nip.get(nip) if nip else None
        if existing and existing.get("id") in assigned_ids:
            existing = None
        if existing is None:
            matching_names = [
                candidate for candidate in staff_by_name.get(name_key, [])
                if candidate.get("id") not in assigned_ids
            ]
            if matching_names:
                matching_names.sort(key=lambda person: (person.get("department") != department, person.get("active") is False))
                existing = matching_names[0]
        if existing is None:
            slot = staff_by_id.get(slot_id)
            if slot and slot.get("id") not in assigned_ids:
                if normalized_person_name(slot.get("name", "")) == name_key:
                    existing = slot
                elif not slot.get("nip") and not slot.get("is_activated") and not slot.get("pin_hash"):
                    has_reports = await db.tasks.count_documents({"staff_id": slot_id}) > 0
                    if not has_reports:
                        existing = slot

        if existing:
            staff_id = existing["id"]
            if not nip and existing.get("nip"):
                # NIP/NIK kosong di file bukan alasan untuk memutus identitas akun.
                nip = normalize_identity(existing.get("nip"))
        else:
            staff_id = slot_id if slot_id not in staff_by_id else f"staff-{uuid.uuid4()}"
            existing = None

        role_text = row.get("role") or (existing or {}).get("role") or "staff"
        role = normalize_role(role_text)
        if role not in VALID_ROLES:
            role = "staff"
        supervised_source = row.get("supervised_departments") or (existing or {}).get("supervised_departments") or []
        supervised = valid_supervised_departments(supervised_source)
        if role not in SUPERVISOR_ROLES:
            supervised = []
        id_type = infer_id_type(nip)
        seed_key = seed_key_for(staff_id, name, department, nip, id_type, doc_dept, role, supervised)
        payload = {
            "id": staff_id,
            "name": name,
            "department": department,
            "initials": make_initials(name),
            "active": True,
            "nip": nip,
            "id_type": id_type,
            "keterangan": doc_dept or position,
            "position": position,
            "role": role,
            "supervised_departments": supervised,
            "seed_key": seed_key,
        }
        official_ids.add(staff_id)
        assigned_ids.add(staff_id)

        if existing is None:
            await db.staff.insert_one({**payload, "archived": False, "is_activated": False})
            staff_by_id[staff_id] = {**payload, "archived": False, "is_activated": False}
            if nip:
                staff_by_nip[nip] = staff_by_id[staff_id]
            staff_by_name.setdefault(name_key, []).append(staff_by_id[staff_id])
            continue

        changes: Dict[str, Any] = {}
        if existing.get("seed_key") != seed_key:
            changes.update(payload)
            changes["active"] = True if existing.get("archived") else existing.get("active", True)
        if existing.get("archived"):
            changes["active"] = True
            changes["archived"] = False
        old_nip = normalize_identity(existing.get("nip") or "")
        if old_nip and nip and old_nip != nip:
            # Identitas berubah: jangan pernah membawa PIN/kode aktivasi lama ke NIP baru.
            changes.update({
                "is_activated": False,
                "pin_hash": "",
                "activation_code_hash": "",
                "activation_code_expires_at": "",
            })
            await db.auth_sessions.delete_many({"staff_id": staff_id})
        if changes:
            await db.staff.update_one(
                {"id": staff_id},
                {"$set": changes, "$unset": {"archive_reason": ""}},
            )
            refreshed = {**existing, **changes}
            staff_by_id[staff_id] = refreshed
            if old_nip and old_nip != nip:
                staff_by_nip.pop(old_nip, None)
            if nip:
                staff_by_nip[nip] = refreshed
            staff_by_name.setdefault(name_key, []).append(refreshed)

    # Orang yang tidak lagi ada pada roster dinonaktifkan, bukan dihapus, agar
    # laporan historis tetap terhubung ke identitas yang benar.
    for row in await db.staff.find(
        {"seed_key": {"$exists": True}},
        {"_id": 0, "id": 1, "active": 1, "archived": 1},
    ).to_list(5000):
        if row["id"] not in official_ids and (row.get("active", True) or not row.get("archived")):
            await db.staff.update_one(
                {"id": row["id"]},
                {"$set": {"active": False, "archived": True, "archive_reason": "Tidak ada pada daftar staf terbaru"}},
            )
            await db.auth_sessions.delete_many({"staff_id": row["id"]})

    # Migrasi tugas eksisting dari 'plan' ke 'todo' & lengkapi timestamp
    jakarta_now = datetime.now(ZoneInfo("Asia/Jakarta"))
    now_str = jakarta_now.strftime("%Y-%m-%d %H:%M")
    await db.tasks.update_many({"status": "plan"}, {"$set": {"status": "todo"}})
    await db.tasks.update_many({"todo_at": {"$in": [None, ""]}}, {"$set": {"todo_at": now_str, "status_updated_at": now_str}})

    cursor = db.tasks.find({"$or": [{"target_history": {"$exists": False}}, {"target_history": None}]})
    async for t in cursor:
        st = t.get("status", "todo")
        history = [{
            "status": st,
            "target": t.get("target", ""),
            "timestamp": t.get("status_updated_at") or t.get("todo_at") or now_str,
            "note": f"Target riil status {st.upper()}",
        }]
        await db.tasks.update_one({"id": t["id"]}, {"$set": {"target_history": history}})

    if await db.tasks.count_documents({}) == 0:
        staff = await db.staff.find({}, {"_id": 0}).to_list(4)
        now = datetime.now(timezone.utc).isoformat()
        t1 = (jakarta_now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
        t2 = (jakarta_now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
        t3 = (jakarta_now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
        t4 = (jakarta_now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        demo = [
            {"id": "task-1", "title": "Rekap laporan layanan harian", "staff_id": staff[0]["id"], "status": "todo", "target": "12 laporan", "priority": "Tinggi", "due_date": "Hari ini", "notes": "Pastikan semua unit terinput", "proof_link": "", "photo_data": "", "photo_name": "", "todo_at": t1, "doing_at": None, "finish_at": None, "status_updated_at": t1, "created_at": now},
            {"id": "task-2", "title": "Validasi data kehadiran", "staff_id": staff[1]["id"], "status": "doing", "target": "78 data", "priority": "Sedang", "due_date": "Hari ini", "notes": "Cek data yang belum sinkron", "proof_link": "", "photo_data": "", "photo_name": "", "todo_at": t1, "doing_at": t2, "finish_at": None, "status_updated_at": t2, "created_at": now},
            {"id": "task-3", "title": "Kirim ringkasan mingguan", "staff_id": staff[2]["id"], "status": "finish", "target": "1 dokumen", "priority": "Rendah", "due_date": "Selesai", "notes": "Dikirim ke koordinator", "proof_link": "https://docs.google.com", "photo_data": "", "photo_name": "", "todo_at": t1, "doing_at": t2, "finish_at": t4, "status_updated_at": t4, "created_at": now},
            {"id": "task-4", "title": "Perbarui SOP meja layanan", "staff_id": staff[3]["id"], "status": "doing", "target": "3 bab", "priority": "Tinggi", "due_date": "Besok", "notes": "Review bersama tim", "proof_link": "", "photo_data": "", "photo_name": "", "todo_at": t1, "doing_at": t3, "finish_at": None, "status_updated_at": t3, "created_at": now},
        ]
        await db.tasks.insert_many(demo)

    # Cache signature setelah sinkronisasi selesai agar request GET berikutnya
    # tidak menulis ulang seluruh database dan mengganggu tampilan dashboard.
    _seed_signature = signature


@api.get("/")
async def root():
    return {"message": "LOKA-Kin API aktif"}


@api.get("/auth/setup-status")
async def auth_setup_status():
    await seed_data()
    admin_count = await db.staff.count_documents({"role": "admin", "is_activated": True, "active": {"$ne": False}})
    return {
        "initial_admin_required": admin_count == 0,
        "initial_admin_setup_enabled": bool(os.environ.get("AUTH_SETUP_SECRET")),
    }


@api.post("/auth/initial-roster/preview")
async def preview_initial_roster(file: UploadFile = File(...), setup_secret: str = Form(...)):
    """Owner-only CSV preview used to load the official roster before first Admin."""
    setup_value = os.environ.get("AUTH_SETUP_SECRET", "")
    if not setup_value:
        raise HTTPException(503, "Penyiapan Admin pertama belum diaktifkan oleh pengelola sistem.")
    if not constant_time_equal(setup_secret, setup_value):
        raise HTTPException(403, "Kode penyiapan tidak cocok.")
    await seed_data()
    if await db.staff.count_documents({"role": "admin", "is_activated": True, "active": {"$ne": False}}):
        raise HTTPException(409, "Admin pertama sudah diaktifkan; roster dikelola dari akun Admin.")
    filename = (file.filename or "").lower()
    if not (filename.endswith(".csv") or filename.endswith(".txt")):
        raise HTTPException(400, "Roster awal harus diunggah sebagai CSV atau TXT.")
    content = await file.read()
    if not content:
        raise HTTPException(400, "Berkas roster kosong.")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "Ukuran CSV melebihi 20 MB.")
    tmp_path = Path(tempfile.gettempdir()) / f"loka-kin-initial-roster-{uuid.uuid4().hex}.csv"
    tmp_path.write_bytes(content)
    try:
        result = extract_csv_rows(tmp_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"CSV tidak dapat dibaca: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)
    return {"filename": file.filename, **result}


@api.post("/auth/bootstrap-admin")
async def bootstrap_admin(payload: BootstrapAdminRequest):
    """Create/activate the first Admin account using a deployment-only setup secret."""
    await seed_data()
    setup_secret = os.environ.get("AUTH_SETUP_SECRET", "")
    if not setup_secret:
        raise HTTPException(503, "Penyiapan Admin pertama belum diaktifkan oleh pengelola sistem.")
    if not constant_time_equal(payload.setup_secret, setup_secret):
        raise HTTPException(403, "Kode penyiapan tidak cocok.")
    if await db.staff.count_documents({"role": "admin", "is_activated": True, "active": {"$ne": False}}):
        raise HTTPException(409, "Admin pertama sudah diaktifkan.")
    if payload.roster is not None:
        if not payload.roster:
            raise HTTPException(400, "Roster awal tidak boleh kosong.")
        await import_staff(
            StaffImportRequest(rows=payload.roster, mode="replace", source="roster awal (pemilik sistem)"),
            user={"id": "initial-setup", "role": "admin"},
        )

    nip = normalize_identity(payload.nip)
    if not valid_identity(nip):
        raise HTTPException(400, "Masukkan NIP 18 digit atau NIK 16 digit yang valid.")

    # Bootstrap hanya boleh mengaktifkan akun Admin yang sudah ada di roster;
    # endpoint ini tidak dapat membuat identitas atau role baru.
    existing = await db.staff.find_one({"nip": nip}, {"_id": 0})
    if not existing or existing.get("role") != "admin":
        raise HTTPException(404, "Akun Admin tidak ditemukan pada roster. Minta pemilik sistem memperbarui roster.")
    if not existing.get("active", True):
        raise HTTPException(400, "Akun Admin pada roster tidak aktif.")
    staff_id = existing["id"]
    fresh = await db.staff.find_one({"id": staff_id}, {"_id": 0})
    code_info = await issue_activation_code(fresh, "initial-setup")
    return {
        "ok": True,
        "message": "Akun Admin disiapkan. Berikan kode aktivasi ini kepada Admin satu kali.",
        "staff_id": staff_id,
        "activation_code": code_info["activation_code"],
        "expires_at": code_info["expires_at"],
    }


@api.post("/auth/activate")
async def activate_account(payload: AuthActivateRequest):
    nip = normalize_identity(payload.nip)
    if not valid_identity(nip):
        raise HTTPException(400, "Masukkan NIP/NIK yang valid.")
    if not valid_pin(payload.pin):
        raise HTTPException(400, "PIN harus terdiri dari tepat 6 angka.")
    if payload.pin != payload.pin_confirmation:
        raise HTTPException(400, "Konfirmasi PIN tidak sama.")

    staff = await db.staff.find_one({"nip": nip}, {"_id": 0})
    if not staff or not staff.get("active", True):
        raise HTTPException(400, "Data akun tidak ditemukan atau tidak aktif. Hubungi Admin.")

    locked_until = parse_datetime(staff.get("activation_code_locked_until", ""))
    if locked_until and locked_until > utc_now():
        raise HTTPException(429, "Terlalu banyak percobaan. Coba lagi setelah 15 menit.")
    expires_at = parse_datetime(staff.get("activation_code_expires_at", ""))
    code_hash = staff.get("activation_code_hash", "")
    code_matches = bool(code_hash) and verify_credential(normalize_activation_code(payload.activation_code), code_hash)
    if not code_matches or not expires_at or expires_at <= utc_now():
        attempts = int(staff.get("activation_code_attempts", 0)) + 1
        changes: Dict[str, Any] = {"activation_code_attempts": attempts}
        if attempts >= AUTH_MAX_ATTEMPTS:
            changes["activation_code_locked_until"] = iso_utc(utc_now() + timedelta(minutes=AUTH_LOCK_MINUTES))
            changes["activation_code_attempts"] = 0
        if expires_at and expires_at <= utc_now():
            changes["activation_code_hash"] = ""
        await db.staff.update_one({"id": staff["id"]}, {"$set": changes})
        raise HTTPException(400, "Kode aktivasi tidak valid atau sudah kedaluwarsa. Minta kode baru kepada Admin.")

    await db.staff.update_one(
        {"id": staff["id"]},
        {
            "$set": {
                "pin_hash": hash_credential(payload.pin),
                "is_activated": True,
                "login_failed_attempts": 0,
                "login_locked_until": "",
                "activation_code_attempts": 0,
            },
            "$unset": {
                "activation_code_hash": "",
                "activation_code_expires_at": "",
                "activation_code_issued_by": "",
            },
        },
    )
    return {"ok": True, "message": "PIN berhasil dibuat. Silakan masuk menggunakan NIP/NIK dan PIN baru."}


@api.post("/auth/login")
async def login(payload: AuthLoginRequest, request: Request, response: Response):
    nip = normalize_identity(payload.nip)
    if not valid_identity(nip) or not re.fullmatch(r"\d{6}", str(payload.pin or "")):
        raise HTTPException(401, "NIP/NIK atau PIN tidak cocok.")
    staff = await db.staff.find_one({"nip": nip}, {"_id": 0})
    if not staff or not staff.get("active", True) or not staff.get("is_activated") or not staff.get("pin_hash"):
        raise HTTPException(401, "NIP/NIK atau PIN tidak cocok. Jika belum aktif, hubungi Admin untuk kode aktivasi.")

    locked_until = parse_datetime(staff.get("login_locked_until", ""))
    if locked_until and locked_until > utc_now():
        raise HTTPException(429, "Akun dikunci sementara setelah beberapa percobaan. Hubungi Admin atau coba lagi nanti.")
    if not verify_credential(payload.pin, staff.get("pin_hash", "")):
        attempts = int(staff.get("login_failed_attempts", 0)) + 1
        changes: Dict[str, Any] = {"login_failed_attempts": attempts}
        if attempts >= AUTH_MAX_ATTEMPTS:
            changes["login_locked_until"] = iso_utc(utc_now() + timedelta(minutes=AUTH_LOCK_MINUTES))
            changes["login_failed_attempts"] = 0
        await db.staff.update_one({"id": staff["id"]}, {"$set": changes})
        raise HTTPException(401, "NIP/NIK atau PIN tidak cocok.")

    token = token_urlsafe(32)
    expires = utc_now() + timedelta(hours=SESSION_TTL_HOURS)
    await db.auth_sessions.insert_one({
        "id": str(uuid.uuid4()),
        "staff_id": staff["id"],
        "token_hash": hash_session_token(token),
        "created_at": iso_utc(utc_now()),
        "expires_at": iso_utc(expires),
    })
    await db.staff.update_one(
        {"id": staff["id"]},
        {"$set": {"login_failed_attempts": 0, "login_locked_until": "", "last_login_at": iso_utc(utc_now())}},
    )
    configured_secure = os.environ.get("AUTH_COOKIE_SECURE")
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    secure_cookie = configured_secure.lower() == "true" if configured_secure is not None else (request.url.scheme == "https" or forwarded_proto == "https")
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_TTL_HOURS * 60 * 60,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "user": user_profile(staff), "expires_at": iso_utc(expires)}


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    authorization = request.headers.get("authorization", "")
    if not token and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token:
        await db.auth_sessions.delete_one({"token_hash": hash_session_token(token)})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", httponly=True, samesite="lax")
    return {"ok": True}


@api.get("/auth/me")
async def auth_me(user: Dict[str, Any] = Depends(get_current_user)):
    return user_profile(user)


@api.post("/auth/staff/{staff_id}/activation-code")
async def create_activation_code(staff_id: str, user: Dict[str, Any] = Depends(require_admin)):
    staff = await db.staff.find_one({"id": staff_id}, {"_id": 0})
    if not staff:
        raise HTTPException(404, "Staf tidak ditemukan.")
    if not valid_identity(staff.get("nip", "")):
        raise HTTPException(400, "Lengkapi NIP/NIK staf sebelum membuat kode aktivasi.")
    if not staff.get("active", True):
        raise HTTPException(400, "Aktifkan kembali data staf sebelum menerbitkan kode.")
    code_info = await issue_activation_code(staff, user["id"])
    return {"ok": True, "name": staff.get("name"), **code_info}


@api.get("/staff", response_model=List[Staff])
async def get_staff(include_inactive: bool = True, user: Dict[str, Any] = Depends(get_current_user)):
    """Staf only see themselves; supervisors can see all names; only Admin sees NIP/NIK."""
    await seed_data()
    if user.get("role") == "staff":
        query: Dict[str, Any] = {"id": user["id"]}
    elif user.get("role") == "admin" and include_inactive:
        query = {}
    elif user.get("role") in SUPERVISOR_ROLES and include_inactive:
        query = {}
    else:
        query = {"active": True}
    rows = await db.staff.find(query, {"_id": 0}).to_list(500)
    rows.sort(key=staff_sort_key)
    reveal_identity = user.get("role") == "admin"
    return [
        public_staff(
            row,
            reveal_identity=reveal_identity,
            reveal_account_status=(reveal_identity or row.get("id") == user.get("id")),
        )
        for row in rows
    ]


@api.post("/staff", response_model=Staff)
async def create_staff(payload: StaffCreate, user: Dict[str, Any] = Depends(require_admin)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Nama staf wajib diisi")
    if payload.department not in DEPARTMENTS:
        raise HTTPException(400, "Departemen tidak valid")
    role = normalize_role(payload.role)
    if role not in VALID_ROLES:
        raise HTTPException(400, "Role tidak valid")
    nip = normalize_identity(payload.nip)
    if nip and not valid_identity(nip):
        raise HTTPException(400, "NIP harus 18 digit atau NIK 16 digit.")
    if nip and await db.staff.find_one({"nip": nip}):
        raise HTTPException(409, "NIP/NIK tersebut sudah digunakan.")
    invalid_supervised = [dept for dept in payload.supervised_departments if dept not in DEPARTMENTS]
    if invalid_supervised:
        raise HTTPException(400, f"Departemen pengawasan tidak valid: {invalid_supervised[0]}")
    supervised = valid_supervised_departments(payload.supervised_departments)
    if role not in SUPERVISOR_ROLES:
        supervised = []
    doc = {
        "id": f"staff-{uuid.uuid4()}",
        "name": name,
        "department": payload.department,
        "initials": make_initials(name),
        "active": payload.active,
        "nip": nip,
        "id_type": (payload.id_type or "").strip() or infer_id_type(nip),
        "keterangan": (payload.keterangan or "").strip(),
        "position": (payload.position or "").strip(),
        "role": role,
        "supervised_departments": supervised,
        "is_activated": False,
    }
    await db.staff.insert_one(doc)
    return public_staff(doc, reveal_identity=True, reveal_account_status=True)


@api.post("/staff/import")
async def import_staff(payload: StaffImportRequest, user: Dict[str, Any] = Depends(require_admin)):
    """Impor daftar staf resmi (menggantikan atau menambah) lalu sinkronkan database.

    Mode ``replace`` mengganti seluruh daftar resmi sehingga nama staf pada slot
    ``staff-1..staff-N`` mengikuti daftar baru. Tugas yang sudah ada tetap
    terhubung ke slot yang sama.
    """
    if payload.mode not in {"replace", "merge"}:
        raise HTTPException(400, "Mode impor harus 'replace' atau 'merge'")
    previous_roster, previous_source = await active_roster()
    active_admins_before = await db.staff.count_documents({"role": "admin", "active": {"$ne": False}, "is_activated": True})

    cleaned: List[Dict[str, Any]] = []
    skipped = 0
    seen = set()
    for row in payload.rows:
        name = (row.name or "").strip()
        if not name:
            skipped += 1
            continue
        bagian = (row.bagian or "").strip()
        department = (row.department or "").strip()
        if department and department not in DEPARTMENTS:
            department = resolve_department(department)
        if not department:
            department = resolve_department(bagian)
        nip = normalize_identity(row.nip)
        if nip and not valid_identity(nip):
            skipped += 1
            continue
        raw_role = (row.role or "").strip()
        role = normalize_role(raw_role) if raw_role else ""
        if raw_role and role not in VALID_ROLES:
            raise HTTPException(400, f"Role tidak valid untuk {name}.")
        invalid_supervised = [dept for dept in row.supervised_departments if dept not in DEPARTMENTS]
        if invalid_supervised:
            raise HTTPException(400, f"Departemen pengawasan tidak valid untuk {name}: {invalid_supervised[0]}")
        supervised = valid_supervised_departments(row.supervised_departments)
        if role and role not in SUPERVISOR_ROLES:
            supervised = []
        entry = {
            "name": name,
            "bagian": bagian,
            "nip": nip,
            "position": "",
            "department": department,
            "role": role,
            "supervised_departments": supervised,
        }
        dedupe = ("nip", nip) if nip else ("name", name.lower())
        if dedupe in seen:
            skipped += 1
            continue
        seen.add(dedupe)
        cleaned.append(entry)

    if not cleaned:
        raise HTTPException(400, "Tidak ada baris staf yang valid untuk diimpor")

    if payload.mode == "merge":
        base_rows, _ = await active_roster()
        def roster_identity_key(row: Dict[str, Any]):
            identity = normalize_identity(row.get("nip") or "")
            return ("nip", identity) if identity else ("name", str(row.get("name", "")).strip().lower())
        existing_keys = {roster_identity_key(row) for row in base_rows}
        additions = []
        for row in cleaned:
            key = roster_identity_key(row)
            if key not in existing_keys:
                additions.append(row)
                existing_keys.add(key)
        base_rows = base_rows + additions
    else:
        base_rows = cleaned

    await save_roster(base_rows, payload.source or "impor manual")
    global _seed_signature
    _seed_signature = None  # paksa sinkronisasi ulang
    await seed_data(force=True)
    await normalize_staff_identity()
    if active_admins_before and not await db.staff.count_documents({"role": "admin", "active": {"$ne": False}, "is_activated": True}):
        await save_roster(previous_roster, previous_source)
        _seed_signature = None
        await seed_data(force=True)
        await normalize_staff_identity()
        raise HTTPException(400, "Impor ditolak agar tidak menghapus Admin aktif terakhir dari roster.")

    return {
        "ok": True,
        "mode": payload.mode,
        "imported": len(cleaned),
        "skipped": skipped,
        "total_roster": len(base_rows),
        "total_staff": await db.staff.count_documents({}),
        "source": payload.source or "impor manual",
    }


@api.get("/staff/roster")
async def get_roster(user: Dict[str, Any] = Depends(require_admin)):
    """Daftar staf resmi yang sedang berlaku (hasil impor atau daftar bawaan)."""
    rows, source = await active_roster()
    return {"source": source, "count": len(rows), "rows": rows}


@api.post("/staff/parse-pdf")
async def parse_staff_pdf(file: UploadFile = File(...), user: Dict[str, Any] = Depends(require_admin)):
    """Baca berkas PDF daftar staf dan kembalikan barisnya (tanpa menyimpan)."""
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(400, "Berkas harus berformat PDF")
    payload = await file.read()
    if not payload:
        raise HTTPException(400, "Berkas PDF kosong")
    if len(payload) > 20 * 1024 * 1024:
        raise HTTPException(400, "Ukuran PDF melebihi 20 MB")

    tmp_path = Path(tempfile.gettempdir()) / f"loka-kin-{uuid.uuid4().hex}.pdf"
    tmp_path.write_bytes(payload)
    try:
        result = extract_rows(tmp_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:  # PDF rusak / tidak didukung
        raise HTTPException(400, f"PDF tidak dapat dibaca: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"filename": file.filename, **result}


@api.post("/staff/import-pdf")
async def import_staff_pdf(
    file: UploadFile = File(...),
    mode: str = Form("replace"),
    source: str = Form("impor PDF"),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Baca PDF daftar staf lalu langsung menyinkronkan seluruh staf ke database."""
    if mode not in {"replace", "merge"}:
        raise HTTPException(400, "Mode impor harus 'replace' atau 'merge'")

    payload = await file.read()
    if not payload:
        raise HTTPException(400, "Berkas PDF kosong")
    tmp_path = Path(tempfile.gettempdir()) / f"loka-kin-{uuid.uuid4().hex}.pdf"
    tmp_path.write_bytes(payload)
    try:
        parsed = extract_rows(tmp_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"PDF tidak dapat dibaca: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)

    rows = [
        StaffImportRow(name=row["name"], bagian=row.get("bagian", ""), nip=row.get("nip", ""))
        for row in parsed["rows"]
    ]
    result = await import_staff(
        StaffImportRequest(rows=rows, mode=mode, source=source or (file.filename or "impor PDF")),
        user=user,
    )
    result["parsed_rows"] = parsed["count"]
    result["with_nip"] = parsed["with_nip"]
    result["warnings"] = parsed["warnings"]
    return result


@api.delete("/staff/roster")
async def reset_roster(user: Dict[str, Any] = Depends(require_admin)):
    """Kembalikan daftar staf ke daftar bawaan aplikasi (membatalkan hasil impor)."""
    previous_roster, previous_source = await active_roster()
    active_admins_before = await db.staff.count_documents({"role": "admin", "active": {"$ne": False}, "is_activated": True})
    await db.settings.delete_one({"key": ROSTER_KEY})
    global _seed_signature
    _seed_signature = None
    await seed_data(force=True)
    await normalize_staff_identity()
    if active_admins_before and not await db.staff.count_documents({"role": "admin", "active": {"$ne": False}, "is_activated": True}):
        await save_roster(previous_roster, previous_source)
        _seed_signature = None
        await seed_data(force=True)
        await normalize_staff_identity()
        raise HTTPException(400, "Reset ditolak agar tidak menghapus Admin aktif terakhir dari roster.")
    rows, source = await active_roster()
    return {
        "ok": True,
        "roster_source": source,
        "roster_count": len(rows),
        "total_staff": await db.staff.count_documents({}),
        "active_staff": await db.staff.count_documents({"active": True}),
    }


@api.post("/staff/parse-csv")
async def parse_staff_csv(file: UploadFile = File(...), user: Dict[str, Any] = Depends(require_admin)):
    """Baca berkas CSV daftar staf dan kembalikan barisnya (tanpa menyimpan)."""
    filename = (file.filename or "").lower()
    if not (filename.endswith(".csv") or filename.endswith(".txt")):
        raise HTTPException(400, "Berkas harus berformat CSV")
    payload = await file.read()
    if not payload:
        raise HTTPException(400, "Berkas CSV kosong")
    tmp_path = Path(tempfile.gettempdir()) / f"loka-kin-{uuid.uuid4().hex}.csv"
    tmp_path.write_bytes(payload)
    try:
        result = extract_csv_rows(tmp_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"CSV tidak dapat dibaca: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"filename": file.filename, **result}


@api.post("/staff/import-csv")
async def import_staff_csv(
    file: UploadFile = File(...),
    mode: str = Form("replace"),
    source: str = Form("impor CSV"),
    user: Dict[str, Any] = Depends(require_admin),
):
    """Baca CSV daftar staf lalu langsung menyinkronkan seluruh staf ke database."""
    if mode not in {"replace", "merge"}:
        raise HTTPException(400, "Mode impor harus 'replace' atau 'merge'")

    payload = await file.read()
    if not payload:
        raise HTTPException(400, "Berkas CSV kosong")
    tmp_path = Path(tempfile.gettempdir()) / f"loka-kin-{uuid.uuid4().hex}.csv"
    tmp_path.write_bytes(payload)
    try:
        parsed = extract_csv_rows(tmp_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"CSV tidak dapat dibaca: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)

    rows = [
        StaffImportRow(
            name=row["name"],
            bagian=row.get("bagian", ""),
            nip=row.get("nip", ""),
            role=row.get("role") or None,
            supervised_departments=row.get("supervised_departments") or [],
        )
        for row in parsed["rows"]
    ]
    result = await import_staff(
        StaffImportRequest(rows=rows, mode=mode, source=source or (file.filename or "impor CSV")),
        user=user,
    )
    result["parsed_rows"] = parsed["count"]
    result["with_nip"] = parsed["with_nip"]
    result["delimiter"] = parsed["delimiter"]
    result["warnings"] = parsed["warnings"]
    return result


@api.put("/staff/{staff_id}", response_model=Staff)
async def update_staff(staff_id: str, payload: StaffUpdate, user: Dict[str, Any] = Depends(require_admin)):
    existing = await db.staff.find_one({"id": staff_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Staf tidak ditemukan")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    removes_active_admin = existing.get("role") == "admin" and existing.get("active", True) and (
        changes.get("role", "admin") != "admin" or changes.get("active") is False
    )
    if removes_active_admin and await db.staff.count_documents({"role": "admin", "active": {"$ne": False}, "is_activated": True}) <= 1:
        raise HTTPException(400, "Promosikan atau aktifkan Admin lain sebelum menonaktifkan role Admin terakhir.")
    if "name" in changes:
        name = str(changes["name"]).strip()
        if not name:
            raise HTTPException(400, "Nama staf wajib diisi")
        changes["name"] = name
        changes["initials"] = make_initials(name)
    if "department" in changes and changes["department"] not in DEPARTMENTS:
        raise HTTPException(400, "Departemen tidak valid")
    if "nip" in changes:
        new_nip = normalize_identity(changes["nip"])
        if new_nip and not valid_identity(new_nip):
            raise HTTPException(400, "NIP harus 18 digit atau NIK 16 digit.")
        duplicate = await db.staff.find_one({"nip": new_nip, "id": {"$ne": staff_id}}) if new_nip else None
        if duplicate:
            raise HTTPException(409, "NIP/NIK tersebut sudah digunakan.")
        changes["nip"] = new_nip
        changes["id_type"] = infer_id_type(new_nip)
        if new_nip != normalize_identity(existing.get("nip", "")):
            # Perubahan identitas harus diaktivasi ulang; sesi lama langsung dicabut.
            changes["is_activated"] = False
            changes["pin_hash"] = ""
            changes["activation_code_hash"] = ""
            changes["activation_code_expires_at"] = ""
            await db.auth_sessions.delete_many({"staff_id": staff_id})
    if "id_type" in changes:
        changes["id_type"] = str(changes["id_type"]).strip()
    if "keterangan" in changes:
        changes["keterangan"] = str(changes["keterangan"]).strip()
    if "position" in changes:
        changes["position"] = str(changes["position"]).strip()
    if "role" in changes:
        role = normalize_role(changes["role"])
        if role not in VALID_ROLES:
            raise HTTPException(400, "Role tidak valid")
        changes["role"] = role
        if role not in SUPERVISOR_ROLES:
            changes["supervised_departments"] = []
    if "supervised_departments" in changes:
        invalid_supervised = [dept for dept in changes["supervised_departments"] if dept not in DEPARTMENTS]
        if invalid_supervised:
            raise HTTPException(400, f"Departemen pengawasan tidak valid: {invalid_supervised[0]}")
        supervised = valid_supervised_departments(changes["supervised_departments"])
        if changes.get("role", existing.get("role", "staff")) not in SUPERVISOR_ROLES:
            supervised = []
        changes["supervised_departments"] = supervised
    if changes.get("active") is False:
        changes["is_activated"] = False
        await db.auth_sessions.delete_many({"staff_id": staff_id})

    if changes:
        await db.staff.update_one({"id": staff_id}, {"$set": changes})

    fresh = await db.staff.find_one({"id": staff_id}, {"_id": 0})
    return public_staff(fresh, reveal_identity=True, reveal_account_status=True)


@api.delete("/staff/{staff_id}")
async def delete_staff(staff_id: str, user: Dict[str, Any] = Depends(require_admin)):
    staff = await db.staff.find_one({"id": staff_id}, {"_id": 0})
    if not staff:
        raise HTTPException(404, "Staf tidak ditemukan")
    if staff.get("role") == "admin" and staff.get("active", True) and staff.get("is_activated") and await db.staff.count_documents({"role": "admin", "active": {"$ne": False}, "is_activated": True}) <= 1:
        raise HTTPException(400, "Admin aktif terakhir tidak dapat dihapus atau dinonaktifkan.")
    await db.auth_sessions.delete_many({"staff_id": staff_id})
    if await db.tasks.count_documents({"staff_id": staff_id}) > 0:
        await db.staff.update_one(
            {"id": staff_id},
            {"$set": {"active": False, "is_activated": False, "archived": True, "archive_reason": "Dinonaktifkan oleh Admin"}},
        )
        return {"ok": True, "deactivated": True}
    result = await db.staff.delete_one({"id": staff_id})
    return {"ok": bool(result.deleted_count), "deactivated": False}


@api.get("/tasks", response_model=List[Task])
async def get_tasks(user: Dict[str, Any] = Depends(get_current_user)):
    await seed_data()
    query = {} if is_report_manager(user) else {"staff_id": user["id"]}
    return await db.tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/tasks", response_model=Task)
async def create_task(payload: TaskCreate, user: Dict[str, Any] = Depends(get_current_user)):
    doc = payload.model_dump()
    if user.get("role") == "staff":
        target_staff_id = user["id"]
    else:
        target_staff_id = doc.get("staff_id", "")
    target_staff = await db.staff.find_one({"id": target_staff_id}, {"_id": 0})
    if not target_staff or not target_staff.get("active", True):
        raise HTTPException(404, "Staf penanggung jawab tidak ditemukan atau tidak aktif.")
    if not can_manage_staff_record(user, target_staff):
        raise HTTPException(403, "Anda hanya dapat menginput laporan untuk staf yang Anda awasi.")
    doc["staff_id"] = target_staff["id"]
    status = normalize_task_status(doc.get("status", "todo"))
    if status is None:
        raise HTTPException(400, "Status laporan tidak valid.")

    # Validasi: Tugas baru wajib berstatus To Do List terlebih dahulu
    if status in {"doing", "finish"}:
        raise HTTPException(
            400,
            "Tugas baru wajib diinputkan ke status To Do List terlebih dahulu sebelum dapat diubah ke Doing atau Finish."
        )

    status = "todo"
    doc["status"] = status
    jakarta_now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M")
    if not doc.get("todo_at"):
        doc["todo_at"] = jakarta_now
    doc["status_updated_at"] = doc.get("status_updated_at") or doc["todo_at"]

    target_val = (doc.get("target") or "").strip()
    if not doc.get("target_history"):
        doc["target_history"] = [
            {
                "status": "todo",
                "target": target_val,
                "timestamp": doc["todo_at"],
                "note": "Target awal To Do List",
            }
        ]

    doc.update({
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["id"],
        "updated_by": user["id"],
    })
    await db.tasks.insert_one(doc)
    return doc


@api.patch("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, payload: TaskCreate, user: Dict[str, Any] = Depends(get_current_user)):
    existing = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Tugas tidak ditemukan")

    existing_staff = await db.staff.find_one({"id": existing.get("staff_id")}, {"_id": 0})
    if not existing_staff or not can_manage_staff_record(user, existing_staff):
        raise HTTPException(403, "Anda tidak berhak mengubah laporan staf ini.")
    if normalize_task_status(existing.get("status")) == "finish" and user.get("role") != "admin":
        raise HTTPException(403, "Laporan Finish terkunci. Hubungi Admin untuk koreksi.")

    doc = payload.model_dump()
    # Hanya Admin yang boleh memindahkan laporan ke staf lain. Pengguna lain
    # tetap terikat pada pemilik laporan yang sudah tersimpan di server.
    if user.get("role") != "admin":
        doc["staff_id"] = existing["staff_id"]
    else:
        target_staff = await db.staff.find_one({"id": doc.get("staff_id")}, {"_id": 0})
        if not target_staff:
            raise HTTPException(404, "Staf penanggung jawab tidak ditemukan.")
        if not target_staff.get("active", True) and target_staff.get("id") != existing.get("staff_id"):
            raise HTTPException(404, "Laporan baru hanya dapat dipindahkan ke staf yang aktif.")
    doc["updated_by"] = user["id"]
    doc["updated_at"] = iso_utc(utc_now())
    new_status = normalize_task_status(doc.get("status", "todo"))
    if new_status is None:
        raise HTTPException(400, "Status laporan tidak valid.")
    doc["status"] = new_status

    old_status = normalize_task_status(existing.get("status", "todo")) or "todo"

    # Validasi: Tugas tidak dapat diubah ke Doing atau Finish jika belum pernah diinputkan ke To Do List
    has_todo = bool(existing.get("todo_at")) or old_status == "todo" or bool(doc.get("todo_at"))
    if not has_todo and new_status in ["doing", "finish"]:
        raise HTTPException(
            400,
            "Tugas tidak dapat diubah ke Doing atau Finish jika belum melakukan inputan To Do List."
        )

    jakarta_now = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M")
    # Pertahankan atau lengkapi waktu To Do List
    if not doc.get("todo_at"):
        doc["todo_at"] = existing.get("todo_at") or jakarta_now

    # Pastikan timestamp tercatat sebelum simpan sesuai status
    if new_status == "doing":
        if not doc.get("doing_at"):
            doc["doing_at"] = jakarta_now
    elif new_status == "finish":
        if not doc.get("doing_at"):
            doc["doing_at"] = existing.get("doing_at") or doc.get("todo_at") or jakarta_now
        if not doc.get("finish_at"):
            doc["finish_at"] = jakarta_now

    doc["status_updated_at"] = doc.get("status_updated_at") or jakarta_now

    # Kelola riwayat target
    existing_history = list(existing.get("target_history") or [])
    if not existing_history and existing.get("target"):
        existing_history.append({
            "status": old_status,
            "target": existing.get("target"),
            "timestamp": existing.get("todo_at") or existing.get("created_at") or jakarta_now,
            "note": "Target awal",
        })

    client_history = doc.get("target_history")
    if client_history and len(client_history) > len(existing_history):
        doc["target_history"] = client_history
    else:
        new_target = (doc.get("target") or "").strip()
        status_changed = new_status != old_status
        last_entry = existing_history[-1] if existing_history else None
        target_changed = not last_entry or last_entry.get("target") != new_target or last_entry.get("status") != new_status

        if (status_changed or target_changed) and new_target:
            existing_history.append({
                "status": new_status,
                "target": new_target,
                "timestamp": doc.get("status_updated_at") or jakarta_now,
                "note": f"Penyesuaian target riil saat status {new_status.upper()}",
            })
        doc["target_history"] = existing_history

    result = await db.tasks.find_one_and_update({"id": task_id}, {"$set": doc}, projection={"_id": 0}, return_document=True)
    if not result:
        raise HTTPException(404, "Tugas tidak ditemukan")
    return result


@api.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(404, "Tugas tidak ditemukan")
    staff = await db.staff.find_one({"id": task.get("staff_id")}, {"_id": 0})
    if not staff or not can_manage_staff_record(user, staff):
        raise HTTPException(403, "Anda tidak berhak menghapus laporan staf ini.")
    if normalize_task_status(task.get("status")) == "finish" and user.get("role") != "admin":
        raise HTTPException(403, "Laporan Finish terkunci. Hubungi Admin untuk koreksi.")
    result = await db.tasks.delete_one({"id": task_id})
    if not result.deleted_count:
        raise HTTPException(404, "Tugas tidak ditemukan")
    return {"ok": True}


@api.get("/analytics")
async def analytics(user: Dict[str, Any] = Depends(get_current_user)):
    await seed_data()
    task_query = {} if is_report_manager(user) else {"staff_id": user["id"]}
    tasks = await db.tasks.find(task_query, {"_id": 0}).to_list(500)
    for t in tasks:
        if t.get("status") == "plan":
            t["status"] = "todo"
    counts = {
        "todo": sum(1 for t in tasks if t["status"] == "todo"),
        "doing": sum(1 for t in tasks if t["status"] == "doing"),
        "finish": sum(1 for t in tasks if t["status"] == "finish"),
    }
    counts["plan"] = counts["todo"]  # Backward compatibility alias
    total = max(counts["todo"] + counts["doing"] + counts["finish"], 1)
    now = datetime.now(timezone.utc)
    daily = [{"label": (now - timedelta(days=i)).strftime("%d %b"), "total": max(1, len(tasks) - i % 3), "finish": max(0, counts["finish"] - i % 2)} for i in range(6, -1, -1)]
    weekly = [{"label": f"Minggu {i}", "total": max(1, len(tasks) + i), "finish": max(0, counts["finish"] + i % 2)} for i in range(1, 5)]
    monthly = [{"label": (now - timedelta(days=30 * i)).strftime("%b"), "total": max(1, len(tasks) + i * 2), "finish": max(0, counts["finish"] + i)} for i in range(5, -1, -1)]
    staff_query = {} if is_report_manager(user) else {"id": user["id"]}
    staff_rows = await db.staff.find(staff_query, {"_id": 0}).to_list(500)
    staff_departments = {person["id"]: person.get("department", "") for person in staff_rows}
    departments = [{"name": department, "total": sum(1 for t in tasks if staff_departments.get(t["staff_id"]) == department), "finish": sum(1 for t in tasks if staff_departments.get(t["staff_id"]) == department and t["status"] == "finish")} for department in DEPARTMENTS]
    kpi_data = compute_kpi_metrics(tasks, staff_rows)
    return {
        "total_tasks": len(tasks),
        "counts": counts,
        "percentages": {k: round(v / total * 100) for k, v in counts.items()},
        "completion_rate": round(counts["finish"] / total * 100),
        "trends": {"daily": daily, "weekly": weekly, "monthly": monthly},
        "departments": departments,
        "total_staff": len(staff_rows),
        "kpi": kpi_data,
    }


def compute_kpi_metrics(tasks, staff_rows):
    section_configs = [
        {
            "id": "umum",
            "title": "Bagian Umum",
            "tagline": "Tata Usaha, Keuangan, SDM, Sarpras, Perencanaan & Humas",
            "departments": ["Admin", "Bendahara", "Perencanaan", "Informasi dan Humas", "Umum", "Sarana & Prasarana"],
            "icon": "Building2",
            "color": "blue",
            "indicators": [
                {
                    "code": "KPI-UM-01",
                    "name": "Disiplin Pelaporan Kinerja Harian & Kehadiran",
                    "desc": "Kepatuhan staf dalam pengisian laporan harian kerja serta ketepatan jam kerja",
                    "target": 95,
                    "weight": 25,
                    "unit": "%",
                    "mod": 0,
                },
                {
                    "code": "KPI-UM-02",
                    "name": "Akuntabilitas Administrasi & Realisasi Keuangan",
                    "desc": "Penyelesaian SPJ belanja, laporan kas bendahara, dan ketertiban tata persuratan",
                    "target": 90,
                    "weight": 25,
                    "unit": "%",
                    "mod": -2,
                },
                {
                    "code": "KPI-UM-03",
                    "name": "Kesiapan & Pemeliharaan Sarana Prasarana (Sarpras)",
                    "desc": "Kelaikan fasilitas gedung, kebersihan lingkungan loka, utilitas air/listrik, dan keamanan",
                    "target": 92,
                    "weight": 25,
                    "unit": "%",
                    "mod": 1,
                },
                {
                    "code": "KPI-UM-04",
                    "name": "Kecepatan Respon Humas & Koordinasi Eksternal",
                    "desc": "Kecepatan penanganan permohonan informasi publik dan koordinasi lintas sektor BNN",
                    "target": 90,
                    "weight": 25,
                    "unit": "%",
                    "mod": 3,
                },
            ],
        },
        {
            "id": "medis",
            "title": "Layanan Rehabilitasi Medis",
            "tagline": "Dokter, Keperawatan, Farmasi Klinis, Gizi, Sanitasi & Fisioterapi",
            "departments": ["Layanan Rehabilitasi Medis", "Clinical Supervisor"],
            "icon": "Stethoscope",
            "color": "emerald",
            "indicators": [
                {
                    "code": "KPI-MED-01",
                    "name": "Ketuntasan Asesmen Medis Awal & Detoksifikasi",
                    "desc": "Pemeriksaan fisik, skrining infeksi (HIV/Hepatitis/TBC), dan manajemen putus zat dalam 24 jam",
                    "target": 95,
                    "weight": 30,
                    "unit": "%",
                    "mod": 2,
                },
                {
                    "code": "KPI-MED-02",
                    "name": "Kepatuhan Terapi Obat & Zero Medication Error",
                    "desc": "Ketepatan pemberian obat farmakologi, pencatatan resep klinis, dan nihil kesalahan pemberian obat",
                    "target": 98,
                    "weight": 25,
                    "unit": "%",
                    "mod": -1,
                },
                {
                    "code": "KPI-MED-03",
                    "name": "Status Kesehatan & Pemenuhan Gizi Klinis Residen",
                    "desc": "Monitoring indeks massa tubuh (IMT), asupan nutrisi seimbang, dan peningkatan kebugaran fisik",
                    "target": 90,
                    "weight": 25,
                    "unit": "%",
                    "mod": 1,
                },
                {
                    "code": "KPI-MED-04",
                    "name": "Kepatuhan Sanitasi Lingkungan & Sterilisasi Medis",
                    "desc": "Baku mutu kebersihan ruang rawat, sterilisasi alat medis, dan pembuangan limbah B3 medis",
                    "target": 92,
                    "weight": 20,
                    "unit": "%",
                    "mod": 0,
                },
            ],
        },
        {
            "id": "sosial",
            "title": "Layanan Rehabilitasi Sosial",
            "tagline": "Konselor Adiksi, Pekerja Sosial, Psikolog Klinis & Instruktur Vokasional",
            "departments": ["Layanan Rehabilitasi Sosial"],
            "icon": "HeartHandshake",
            "color": "amber",
            "indicators": [
                {
                    "code": "KPI-SOS-01",
                    "name": "Ketercapaian Sesi Konseling Adiksi & Terapi CBT",
                    "desc": "Pelaksanaan konseling individu/kelompok dan intervensi psikologis sesuai Individual Treatment Plan",
                    "target": 90,
                    "weight": 30,
                    "unit": "%",
                    "mod": 1,
                },
                {
                    "code": "KPI-SOS-02",
                    "name": "Kepatuhan Jadwal Therapeutic Community (TC)",
                    "desc": "Disiplin Morning Meeting, Daily Structure, House Meeting, dan pembentukan norma tanggung jawab",
                    "target": 95,
                    "weight": 25,
                    "unit": "%",
                    "mod": -2,
                },
                {
                    "code": "KPI-SOS-03",
                    "name": "Partisipasi & Kelulusan Pelatihan Vokasional Mandiri",
                    "desc": "Tingkat keaktifan residen dalam program keterampilan kerja (pertanian, sablon, barista, kerajinan)",
                    "target": 85,
                    "weight": 25,
                    "unit": "%",
                    "mod": 3,
                },
                {
                    "code": "KPI-SOS-04",
                    "name": "Indeks Perubahan Perilaku & Kesiapan Reintegrasi",
                    "desc": "Evaluasi perilaku adaptif residen, kesiapan kembali ke keluarga/masyarakat, dan program aftercare",
                    "target": 88,
                    "weight": 20,
                    "unit": "%",
                    "mod": 0,
                },
            ],
        },
    ]

    results = []
    for cfg in section_configs:
        depts = cfg["departments"]
        staff_in_sec = [s for s in staff_rows if s.get("department") in depts]
        sec_staff_ids = {s["id"] for s in staff_in_sec}
        sec_tasks = [t for t in tasks if t.get("staff_id") in sec_staff_ids]
        
        sec_total_tasks = len(sec_tasks)
        sec_finish_tasks = sum(1 for t in sec_tasks if t.get("status") == "finish")
        sec_doing_tasks = sum(1 for t in sec_tasks if t.get("status") == "doing")
        sec_todo_tasks = sum(1 for t in sec_tasks if t.get("status") in ["todo", "plan"])
        
        task_completion_rate = (sec_finish_tasks / sec_total_tasks * 100) if sec_total_tasks > 0 else 80.0
        
        computed_indicators = []
        weighted_score_sum = 0
        
        for ind in cfg["indicators"]:
            baseline = ind["target"]
            task_factor = (task_completion_rate - 70) * 0.25
            realization = min(100.0, max(60.0, round(baseline + ind.get("mod", 0) + task_factor, 1)))
            achievement_rate = round((realization / ind["target"]) * 100, 1)
            
            if realization >= ind["target"]:
                quality_status = "Target Tercapai"
                status_tone = "green"
            elif realization >= ind["target"] * 0.9:
                quality_status = "Mendekati Target"
                status_tone = "amber"
            else:
                quality_status = "Perlu Perhatian"
                status_tone = "red"
                
            computed_indicators.append({
                "code": ind["code"],
                "name": ind["name"],
                "desc": ind["desc"],
                "target": ind["target"],
                "realization": realization,
                "unit": ind["unit"],
                "achievement_rate": achievement_rate,
                "weight": ind["weight"],
                "status": quality_status,
                "status_tone": status_tone,
            })
            
            weighted_score_sum += realization * (ind["weight"] / 100.0)

        section_score = round(weighted_score_sum, 1)
        target_avg = round(sum(ind["target"] * (ind["weight"] / 100.0) for ind in cfg["indicators"]), 1)
        section_achievement = round((section_score / target_avg) * 100, 1) if target_avg > 0 else 100.0

        if section_achievement >= 100.0:
            overall_badge = "Sangat Baik (A)"
            overall_tone = "green"
        elif section_achievement >= 90.0:
            overall_badge = "Baik (B)"
            overall_tone = "blue"
        elif section_achievement >= 75.0:
            overall_badge = "Cukup (C)"
            overall_tone = "amber"
        else:
            overall_badge = "Perlu Peningkatan"
            overall_tone = "red"

        results.append({
            "id": cfg["id"],
            "title": cfg["title"],
            "tagline": cfg["tagline"],
            "color": cfg["color"],
            "icon": cfg["icon"],
            "staff_count": len(staff_in_sec),
            "task_stats": {
                "total": sec_total_tasks,
                "finish": sec_finish_tasks,
                "doing": sec_doing_tasks,
                "todo": sec_todo_tasks,
                "completion_rate": round(task_completion_rate, 1),
            },
            "overall_score": section_score,
            "target_avg": target_avg,
            "achievement_rate": section_achievement,
            "overall_badge": overall_badge,
            "overall_tone": overall_tone,
            "indicators": computed_indicators,
        })
        
    return results


@api.post("/export")
async def export_sheet(user: Dict[str, Any] = Depends(require_admin)):
    exported_at = datetime.now(ZoneInfo("Asia/Jakarta"))
    await db.export_logs.insert_one({"id": str(uuid.uuid4()), "mode": "manual", "status": "simulated", "exported_at": exported_at.isoformat(), "spreadsheet_id": "1RVliN0kwubvYBmAoCYWrIJhV6wgT2RvW4XcTAxF--1I"})
    return {"ok": True, "status": "simulated", "message": "Simulasi ekspor manual berhasil dicatat.", "exported_at": exported_at.isoformat(), "next_run": next_export_time().isoformat()}


def next_export_time():
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    target = now.replace(hour=21, minute=0, second=0, microsecond=0)
    return target + timedelta(days=1) if now >= target else target


@api.get("/export/status")
async def export_status(user: Dict[str, Any] = Depends(require_admin)):
    last = await db.export_logs.find_one({}, {"_id": 0}, sort=[("exported_at", -1)])
    return {"mode": "simulated", "schedule": "21:00", "timezone": "Asia/Jakarta", "spreadsheet_id": "1RVliN0kwubvYBmAoCYWrIJhV6wgT2RvW4XcTAxF--1I", "last_export": last, "next_run": next_export_time().isoformat()}


async def scheduled_export_loop():
    while True:
        wait_seconds = (next_export_time() - datetime.now(ZoneInfo("Asia/Jakarta"))).total_seconds()
        await asyncio.sleep(max(1, wait_seconds))
        exported_at = datetime.now(ZoneInfo("Asia/Jakarta"))
        await db.export_logs.insert_one({"id": str(uuid.uuid4()), "mode": "automatic", "status": "simulated", "exported_at": exported_at.isoformat(), "spreadsheet_id": "1RVliN0kwubvYBmAoCYWrIJhV6wgT2RvW4XcTAxF--1I"})


@api.get("/database/status")
async def database_status(user: Dict[str, Any] = Depends(require_admin)):
    """Informasi mode database aktif dan jumlah dokumen tersimpan."""
    await seed_data()
    collections = ["staff", "tasks", "auth_sessions", "export_logs", "settings"]
    counts = {}
    for name in collections:
        counts[name] = await db[name].count_documents({})
    roster, source = await active_roster()
    return {
        "mode": DB_MODE,
        "persistent": db.persistent,
        "data_file": str(DATA_FILE) if db.persistent else None,
        "database": os.environ.get("DB_NAME", "loka_kin"),
        "collections": counts,
        "total_documents": sum(counts.values()),
        "roster_source": source,
        "roster_count": len(roster),
    }


async def normalize_staff_identity():
    """Normalize legacy identity/role fields without activating any account."""
    fixed = 0
    async for row in db.staff.find(
        {},
        {"_id": 0, "id": 1, "nip": 1, "id_type": 1, "role": 1, "supervised_departments": 1, "active": 1},
    ):
        nip = normalize_identity(row.get("nip") or "")
        role = normalize_role(row.get("role") or "staff")
        if role not in VALID_ROLES:
            role = "staff"
        supervised = valid_supervised_departments(row.get("supervised_departments") or [])
        if role not in SUPERVISOR_ROLES:
            supervised = []
        changes: Dict[str, Any] = {}
        expected_id_type = infer_id_type(nip)
        if (row.get("nip") or "") != nip:
            changes["nip"] = nip
        if (row.get("id_type") or "") != expected_id_type:
            changes["id_type"] = expected_id_type
        if row.get("role") != role:
            changes["role"] = role
        if row.get("supervised_departments") != supervised:
            changes["supervised_departments"] = supervised
        if "active" not in row:
            changes["active"] = True
        if changes:
            await db.staff.update_one({"id": row["id"]}, {"$set": changes})
            fixed += 1
    return fixed


async def startup_database():
    """Pulihkan snapshot lokal (bila ada), lalu sinkronkan daftar staf resmi."""
    restored = await db.restore()
    if restored:
        print(f"[db] {restored} dokumen dipulihkan dari {DATA_FILE}")
    await seed_data()
    fixed = await normalize_staff_identity()
    print(f"[db] mode={DB_MODE}, koleksi={await db['staff'].count_documents({})} staf tersedia"
          + (f", {fixed} jenis nomor disinkronkan" if fixed else ""))


@app.on_event("startup")
async def start_scheduler():
    await startup_database()
    app.state.export_scheduler = asyncio.create_task(scheduled_export_loop())


app.include_router(api)
# Credentialed cookies must never be exposed to arbitrary origins by default.
cors_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip() and origin.strip() != "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    if hasattr(app.state, "export_scheduler"):
        app.state.export_scheduler.cancel()
    client.close()
