from fastapi import FastAPI, APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any
from secrets import token_urlsafe, randbelow
import hashlib, json, os, re, tempfile, uuid, asyncio, io

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
    "super_admin": "Super Admin",
    "team_lead": "Ketua Tim",
    "clinical_supervisor": "Clinical Supervisor",
    "head": "Kepala",
}
VALID_ROLES = set(ROLE_LABELS)
ADMIN_ROLES = {"admin", "super_admin"}
SUPERVISOR_ROLES = {"team_lead", "clinical_supervisor", "head"}
READ_ALL_ROLES = {*ADMIN_ROLES, *SUPERVISOR_ROLES}
SESSION_COOKIE_NAME = "loka_kin_session"
SESSION_TTL_HOURS = 12
ACTIVATION_TTL_HOURS = 24
LANDING_SETTINGS_KEY = "landing_page"
DEFAULT_LANDING_SETTINGS = {
    "brand_name": "Loka-Kin",
    "hero_kicker": "PLATFORM KINERJA TIM TERINTEGRASI",
    "hero_title": "Dorong Kinerja Tim",
    "hero_highlight": "Menjadi Lebih Optimal",
    "hero_description": "Platform kinerja karyawan yang memudahkan penetapan target, pelacakan kemajuan, dan pengakuan prestasi secara real-time.",
    "hero_cta": "Masuk",
    "assurance_one": "Pantau progres real-time",
    "assurance_two": "Laporan lebih terukur",
    "nav_home": "Home",
    "nav_features": "Fitur",
    "nav_how": "Cara kerja",
    "nav_about": "Tentang",
    "show_features": True,
    "features_title": "Kerja Tim Menjadi Lebih",
    "features_highlight": "Terarah",
    "features_description": "LOKA-Kin membantu tim menyusun target, menjalankan pekerjaan, dan melihat hasilnya dengan lebih jelas.",
    "show_how": True,
    "how_title": "Dari rencana menjadi hasil nyata.",
    "how_description": "Semua orang tahu apa yang dikerjakan, siapa penanggung jawabnya, dan sejauh mana progresnya.",
    "show_about": True,
    "about_title": "Bangun ritme kerja yang lebih baik bersama LOKA-Kin.",
    "about_description": "Satukan target, progres, dan capaian tim dalam satu tempat.",
    "footer_text": "© LOKA-Kin. Loka Rehabilitasi Narkotika Kalianda.",
    "accent_color": "#2458EC",
}
AUTH_MAX_ATTEMPTS = 5
AUTH_LOCK_MINUTES = 15


def normalize_role(value: str) -> str:
    raw = str(value or "staff").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "staf": "staff", "pegawai": "staff", "admin": "admin",
        "superadmin": "super_admin", "super_admin": "super_admin", "super_administrator": "super_admin",
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


class BootstrapSuperAdminRequest(BaseModel):
    setup_secret: str
    nip: str
    name: str = "Super Admin"


class ChangePinRequest(BaseModel):
    current_pin: str
    new_pin: str
    pin_confirmation: str


class LandingPageSettings(BaseModel):
    brand_name: str = Field(default=DEFAULT_LANDING_SETTINGS["brand_name"], max_length=80)
    hero_kicker: str = Field(default=DEFAULT_LANDING_SETTINGS["hero_kicker"], max_length=120)
    hero_title: str = Field(default=DEFAULT_LANDING_SETTINGS["hero_title"], max_length=100)
    hero_highlight: str = Field(default=DEFAULT_LANDING_SETTINGS["hero_highlight"], max_length=100)
    hero_description: str = Field(default=DEFAULT_LANDING_SETTINGS["hero_description"], max_length=500)
    hero_cta: str = Field(default=DEFAULT_LANDING_SETTINGS["hero_cta"], max_length=40)
    assurance_one: str = Field(default=DEFAULT_LANDING_SETTINGS["assurance_one"], max_length=80)
    assurance_two: str = Field(default=DEFAULT_LANDING_SETTINGS["assurance_two"], max_length=80)
    nav_home: str = Field(default=DEFAULT_LANDING_SETTINGS["nav_home"], max_length=30)
    nav_features: str = Field(default=DEFAULT_LANDING_SETTINGS["nav_features"], max_length=30)
    nav_how: str = Field(default=DEFAULT_LANDING_SETTINGS["nav_how"], max_length=30)
    nav_about: str = Field(default=DEFAULT_LANDING_SETTINGS["nav_about"], max_length=30)
    show_features: bool = DEFAULT_LANDING_SETTINGS["show_features"]
    features_title: str = Field(default=DEFAULT_LANDING_SETTINGS["features_title"], max_length=100)
    features_highlight: str = Field(default=DEFAULT_LANDING_SETTINGS["features_highlight"], max_length=80)
    features_description: str = Field(default=DEFAULT_LANDING_SETTINGS["features_description"], max_length=400)
    show_how: bool = DEFAULT_LANDING_SETTINGS["show_how"]
    how_title: str = Field(default=DEFAULT_LANDING_SETTINGS["how_title"], max_length=120)
    how_description: str = Field(default=DEFAULT_LANDING_SETTINGS["how_description"], max_length=400)
    show_about: bool = DEFAULT_LANDING_SETTINGS["show_about"]
    about_title: str = Field(default=DEFAULT_LANDING_SETTINGS["about_title"], max_length=120)
    about_description: str = Field(default=DEFAULT_LANDING_SETTINGS["about_description"], max_length=400)
    footer_text: str = Field(default=DEFAULT_LANDING_SETTINGS["footer_text"], max_length=120)
    accent_color: str = Field(default=DEFAULT_LANDING_SETTINGS["accent_color"], pattern=r"^#[0-9A-Fa-f]{6}$")


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


def parse_datetime(value: Any) -> Optional[datetime]:
    """Ubah nilai ISO menjadi datetime UTC; None bila kosong atau tidak valid.

    Nilai kosong harus ditangani di sini karena endpoint auth memakainya untuk
    memeriksa sesi/kunci: dokumen sesi yang sudah dicabut atau field waktu yang
    hilang harus berujung pada 401, bukan error 500.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


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
        "must_change_pin": bool(row.get("pin_change_required")),
    }


def preview_token_fallback_enabled() -> bool:
    """Hanya aktif pada proses pratinjau yang secara eksplisit mengizinkan alur token."""
    return os.environ.get("AUTH_PREVIEW_TOKEN_FALLBACK", "").lower() == "true"


def session_cookie_policy(request: Request) -> tuple[str, bool]:
    """Atribut cookie sesi untuk deployment satu-origin maupun beda-origin.

    Default tetap ``lax``. Bila frontend di-host di origin lain (mis. GitHub Pages)
    sementara API berjalan di host terpisah, atur ``AUTH_COOKIE_SAMESITE=none``;
    nilai ini otomatis memaksa ``Secure`` karena browser menolak cookie pihak
    ketiga tanpa atribut tersebut. ``CORS_ORIGINS`` wajib memuat origin frontend
    secara eksplisit (wildcard tidak diizinkan untuk request berkredensial).
    """
    samesite = os.environ.get("AUTH_COOKIE_SAMESITE", "lax").strip().lower()
    if samesite not in {"lax", "strict", "none"}:
        samesite = "lax"
    configured_secure = os.environ.get("AUTH_COOKIE_SECURE")
    if configured_secure is not None:
        secure = configured_secure.lower() == "true"
    else:
        secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"
    if samesite == "none":
        secure = True
    return samesite, secure


def request_session_token(request: Request) -> str:
    # An explicit per-tab session must override an older browser cookie.
    # Embedded previews can retain cookies while blocking login cookie updates.
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    # Gateway di depan preview dapat membuang header Authorization (gateway punya
    # autentikasi sendiri) sekaligus memblokir cookie pihak ketiga. Saluran ketiganya
    # yaitu parameter query, hanya diterima bila mode pratinjau eksplisit dinyalakan.
    if preview_token_fallback_enabled():
        query_token = str(request.query_params.get("access_token") or "").strip()
        if query_token:
            return query_token
    return request.cookies.get(SESSION_COOKIE_NAME, "")


async def get_current_user(request: Request) -> Dict[str, Any]:
    token = request_session_token(request)
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
    if user.get("pin_change_required") and request.url.path not in {
        "/api/auth/me", "/api/auth/change-pin",
    }:
        raise HTTPException(403, "PIN sementara harus diganti sebelum menggunakan aplikasi.")
    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(403, "Fitur ini hanya dapat digunakan Admin.")
    return user


async def require_super_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "super_admin":
        raise HTTPException(403, "Fitur ini hanya dapat digunakan Super Admin.")
    return user


def can_manage_staff_record(user: Dict[str, Any], staff_record: Dict[str, Any]) -> bool:
    role = user.get("role", "staff")
    if role in ADMIN_ROLES:
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
            "pin_change_required": False,
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

        role_text = (
            "super_admin" if existing and (existing.get("system_super_admin") or existing.get("role") == "super_admin")
            else row.get("role") or (existing or {}).get("role") or "staff"
        )
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
        # Super Admin is a system account, not tied to a staff roster import.
        {"seed_key": {"$exists": True}, "role": {"$ne": "super_admin"}, "system_super_admin": {"$ne": True}},
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

    if (
        await db.tasks.count_documents({}) == 0
        and await db.staff.count_documents({"active": {"$ne": False}}) >= 4
    ):
        staff = await db.staff.find({"active": {"$ne": False}}, {"_id": 0}).to_list(4)
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
    super_admin_count = await db.staff.count_documents({"role": "super_admin", "is_activated": True, "active": {"$ne": False}})
    return {
        "initial_admin_required": admin_count == 0,
        "initial_admin_setup_enabled": bool(os.environ.get("AUTH_SETUP_SECRET")),
        "initial_super_admin_required": super_admin_count == 0,
        "initial_super_admin_setup_enabled": bool(os.environ.get("AUTH_SETUP_SECRET")),
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


@api.post("/auth/bootstrap-super-admin")
async def bootstrap_super_admin(payload: BootstrapSuperAdminRequest):
    """Owner-only first-run setup for a Super Admin using an official NIP/NIK."""
    await seed_data()
    setup_secret = os.environ.get("AUTH_SETUP_SECRET", "")
    if not setup_secret:
        raise HTTPException(503, "Penyiapan Super Admin belum diaktifkan oleh pengelola sistem.")
    if not constant_time_equal(payload.setup_secret, setup_secret):
        raise HTTPException(403, "Kode penyiapan tidak cocok.")
    if await db.staff.count_documents({"role": "super_admin", "is_activated": True, "active": {"$ne": False}}):
        raise HTTPException(409, "Super Admin aktif sudah tersedia.")

    nip = normalize_identity(payload.nip)
    if not valid_identity(nip):
        raise HTTPException(400, "Masukkan NIP 18 digit atau NIK 16 digit yang valid.")
    name = str(payload.name or "").strip()
    if not name:
        raise HTTPException(400, "Nama Super Admin wajib diisi.")

    existing = await db.staff.find_one({"nip": nip}, {"_id": 0})
    if existing and existing.get("active", True) is False:
        raise HTTPException(400, "Akun dengan NIP/NIK tersebut sedang nonaktif.")
    if existing:
        # Pemilik sistem boleh mempromosikan akun roster yang identitasnya cocok.
        await db.staff.update_one({"id": existing["id"]}, {"$set": {
            "role": "super_admin", "system_super_admin": True, "supervised_departments": [],
        }})
        staff_id = existing["id"]
    else:
        staff_id = f"super-admin-{uuid.uuid4()}"
        doc = {
            "id": staff_id,
            "name": name,
            "department": "Admin",
            "initials": make_initials(name),
            "active": True,
            "nip": nip,
            "id_type": infer_id_type(nip),
            "keterangan": "Super Admin",
            "position": "Super Admin",
            "role": "super_admin",
            "supervised_departments": [],
            "is_activated": False,
            "pin_hash": "",
            "pin_change_required": False,
            "source": "owner_super_admin_setup",
            "system_super_admin": True,
        }
        await db.staff.insert_one(doc)

    fresh = await db.staff.find_one({"id": staff_id}, {"_id": 0})
    code_info = await issue_activation_code(fresh, "initial-super-admin-setup")
    return {
        "ok": True,
        "message": "Akun Super Admin disiapkan. Kode aktivasi hanya ditampilkan satu kali.",
        "staff_id": staff_id,
        "name": fresh.get("name"),
        "role": "super_admin",
        "activation_code": code_info["activation_code"],
        "expires_at": code_info["expires_at"],
    }


@api.get("/public/landing-settings")
async def get_landing_settings():
    stored = await db.settings.find_one({"key": LANDING_SETTINGS_KEY}, {"_id": 0})
    values = stored.get("values") if stored else None
    return {**DEFAULT_LANDING_SETTINGS, **(values or {})}


@api.put("/admin/landing-settings")
async def update_landing_settings(
    payload: LandingPageSettings,
    user: Dict[str, Any] = Depends(require_super_admin),
):
    values = payload.model_dump()
    for key, value in values.items():
        if isinstance(value, str):
            values[key] = value.strip()
    values["accent_color"] = values["accent_color"].upper()
    if not re.fullmatch(r"#[0-9A-F]{6}", values["accent_color"]):
        raise HTTPException(400, "Warna aksen harus berupa kode HEX, contoh #2458EC.")
    await db.settings.update_one(
        {"key": LANDING_SETTINGS_KEY},
        {"$set": {
            "key": LANDING_SETTINGS_KEY,
            "values": values,
            "updated_at": iso_utc(utc_now()),
            "updated_by": user["id"],
        }},
        upsert=True,
    )
    return values


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
                "pin_change_required": False,
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


@api.post("/auth/change-pin")
async def change_pin(payload: ChangePinRequest, user: Dict[str, Any] = Depends(get_current_user)):
    if not user.get("pin_change_required"):
        raise HTTPException(409, "Akun ini tidak memiliki PIN sementara yang perlu diganti.")
    if not valid_pin(payload.current_pin) or not verify_credential(payload.current_pin, user.get("pin_hash", "")):
        raise HTTPException(401, "PIN sementara tidak cocok.")
    if not valid_pin(payload.new_pin):
        raise HTTPException(400, "PIN baru harus terdiri dari tepat 6 angka.")
    if payload.new_pin in {"123456", "111111", "222222", "333333", "444444", "555555", "666666", "777777", "888888", "999999", "000000"}:
        raise HTTPException(400, "Pilih PIN enam digit yang tidak mudah ditebak.")
    if payload.new_pin == payload.current_pin:
        raise HTTPException(400, "PIN baru harus berbeda dari PIN sementara.")
    if payload.new_pin != payload.pin_confirmation:
        raise HTTPException(400, "Konfirmasi PIN baru tidak sama.")
    await db.staff.update_one({"id": user["id"]}, {"$set": {
        "pin_hash": hash_credential(payload.new_pin),
        "pin_change_required": False,
        "pin_last_changed_at": iso_utc(utc_now()),
    }})
    return {"ok": True, "message": "PIN baru berhasil disimpan."}


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
    samesite, secure_cookie = session_cookie_policy(request)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_TTL_HOURS * 60 * 60,
        httponly=True,
        secure=secure_cookie,
        samesite=samesite,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    result = {"ok": True, "user": user_profile(staff), "expires_at": iso_utc(expires)}
    # The embedded Arena preview may block partitioned cookies in its iframe.
    # Expose the short-lived session token only in the explicitly enabled preview
    # process; the frontend keeps it in sessionStorage and sends it as Bearer.
    if preview_token_fallback_enabled():
        result["session_token"] = token
    return result


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request_session_token(request)
    if token:
        await db.auth_sessions.delete_one({"token_hash": hash_session_token(token)})
    samesite, secure_cookie = session_cookie_policy(request)
    # Penghapusan cookie lintas-origin butuh atribut yang sama dengan saat menyetelnya.
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", httponly=True, secure=secure_cookie, samesite=samesite)
    return {"ok": True}


@api.get("/auth/me")
async def auth_me(user: Dict[str, Any] = Depends(get_current_user)):
    return user_profile(user)


@api.post("/auth/staff/{staff_id}/activation-code")
async def create_activation_code(staff_id: str, user: Dict[str, Any] = Depends(require_admin)):
    staff = await db.staff.find_one({"id": staff_id}, {"_id": 0})
    if not staff:
        raise HTTPException(404, "Staf tidak ditemukan.")
    if staff.get("role") == "super_admin" and user.get("role") != "super_admin":
        raise HTTPException(403, "Hanya Super Admin yang dapat menerbitkan ulang kredensial Super Admin.")
    if not valid_identity(staff.get("nip", "")):
        raise HTTPException(400, "Lengkapi NIP/NIK staf sebelum membuat kode aktivasi.")
    if not staff.get("active", True):
        raise HTTPException(400, "Aktifkan kembali data staf sebelum menerbitkan kode.")
    code_info = await issue_activation_code(staff, user["id"])
    return {"ok": True, "name": staff.get("name"), **code_info}


def is_demo_placeholder_identity(value: str, row: Optional[Dict[str, Any]] = None) -> bool:
    digits = normalize_identity(value)
    tagged = bool((row or {}).get("identity_is_placeholder")) or str((row or {}).get("credential_source") or "").startswith("demo")
    # Pattern historically emitted by scripts/preview.py for missing official IDs.
    return tagged or bool(re.fullmatch(r"1800000000\d{6}", digits))


def generate_temporary_pin(used: set[str]) -> str:
    weak = {"123456", "111111", "222222", "333333", "444444", "555555", "666666", "777777", "888888", "999999", "000000"}
    while True:
        value = f"{randbelow(1_000_000):06d}"
        if value not in used and value not in weak and len(set(value)) > 2:
            used.add(value)
            return value


def build_temporary_credentials_pdf(rows: List[Dict[str, Any]], generated_at: datetime) -> bytes:
    """Render a one-time in-memory PDF; plaintext PINs are never persisted."""
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        output, pagesize=page, rightMargin=12 * mm, leftMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=14 * mm,
        title="LOKA-Kin — PIN sementara pegawai",
        author="LOKA-Kin Super Admin",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("CredentialTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=colors.HexColor("#15345B"), alignment=TA_LEFT, spaceAfter=4)
    subtitle = ParagraphStyle("CredentialSubtitle", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#526174"), spaceAfter=5)
    warning = ParagraphStyle("CredentialWarning", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=colors.HexColor("#8A1C1C"), backColor=colors.HexColor("#FFF2F2"), borderColor=colors.HexColor("#F2B8B8"), borderWidth=0.6, borderPadding=7, spaceAfter=8)
    cell = ParagraphStyle("CredentialCell", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.4, leading=9, textColor=colors.HexColor("#172337"))
    pin_style = ParagraphStyle("CredentialPin", parent=cell, fontName="Helvetica-Bold", fontSize=9, alignment=TA_CENTER, textColor=colors.HexColor("#0B4BAA"))
    center = ParagraphStyle("CredentialCenter", parent=cell, alignment=TA_CENTER)

    story = [
        Paragraph("LOKA-Kin — Daftar NIP/NIK &amp; PIN Sementara", title),
        Paragraph(f"Loka Rehabilitasi Narkotika Kalianda · {len(rows)} pegawai · {generated_at.strftime('%d-%m-%Y %H:%M')} WIB", subtitle),
        Paragraph("RAHASIA — dibagikan secara pribadi kepada pegawai terkait. PIN pada dokumen ini baru saja diterbitkan/dirotasi, hanya ditampilkan sekali, dan wajib diganti setelah masuk. PIN sebelumnya tidak dapat dipulihkan karena hanya disimpan sebagai hash.", warning),
        Spacer(1, 2 * mm),
    ]
    data = [[Paragraph(f"<b>{escape(text)}</b>", center if index in {0, 5} else cell) for index, text in enumerate(("No", "Nama pegawai", "Departemen", "Peran", "NIP/NIK", "PIN sementara", "Status PIN"))]]
    for number, row in enumerate(rows, start=1):
        role_label = ROLE_LABELS.get(row.get("role", "staff"), "Staf")
        status = "PIN dirotasi" if row.get("was_activated") else "PIN awal diterbitkan"
        data.append([
            Paragraph(str(number), center),
            Paragraph(escape(str(row.get("name", ""))), cell),
            Paragraph(escape(str(row.get("department", "-"))), cell),
            Paragraph(escape(role_label), cell),
            Paragraph(escape(f"{row.get('id_type', 'NIP/NIK')} · {row.get('nip', '')}"), cell),
            Paragraph(escape(row["temporary_pin"]), pin_style),
            Paragraph(escape(status), cell),
        ])
    widths = [10 * mm, 49 * mm, 42 * mm, 34 * mm, 48 * mm, 27 * mm, 38 * mm]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173B72")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CAD4E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FB")]),
    ]))
    story.append(table)

    def footer(canvas, _document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(12 * mm, 7 * mm, "RAHASIA · Jangan unggah ke repositori atau kanal publik")
        canvas.drawRightString(page[0] - 12 * mm, 7 * mm, f"Halaman {_document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


@api.get("/admin/credentials/status")
async def credentials_status(user: Dict[str, Any] = Depends(require_super_admin)):
    records = await db.staff.find({"active": {"$ne": False}, "role": {"$ne": "super_admin"}}, {"_id": 0}).to_list(5000)
    records.sort(key=staff_sort_key)
    missing = [
        {"id": row.get("id"), "name": row.get("name", "Tanpa nama")}
        for row in records
        if not valid_identity(row.get("nip", "")) or is_demo_placeholder_identity(row.get("nip", ""), row)
    ]
    valid_count = len(records) - len(missing)
    return {
        "total_staff": len(records),
        "with_official_identity": valid_count,
        "missing_or_placeholder_identity": len(missing),
        "activated_accounts": sum(bool(row.get("is_activated") and row.get("pin_hash")) for row in records),
        "pending_accounts": sum(not bool(row.get("is_activated") and row.get("pin_hash")) for row in records),
        "ready_for_pin_pdf": bool(records) and not missing,
        "missing_staff": missing,
    }


@api.post("/admin/credentials/rotate-pdf")
async def rotate_credentials_and_download_pdf(user: Dict[str, Any] = Depends(require_super_admin)):
    """Rotate all eligible staff PINs and stream their temporary values once."""
    records = await db.staff.find({"active": {"$ne": False}, "role": {"$ne": "super_admin"}}, {"_id": 0}).to_list(5000)
    records.sort(key=staff_sort_key)
    if not records:
        raise HTTPException(400, "Belum ada pegawai aktif untuk diekspor.")
    missing = [row for row in records if not valid_identity(row.get("nip", "")) or is_demo_placeholder_identity(row.get("nip", ""), row)]
    if missing:
        raise HTTPException(status_code=409, detail={
            "message": "PDF PIN belum dapat dibuat. Lengkapi NIP/NIK resmi untuk semua pegawai aktif; nomor contoh tidak diterima.",
            "missing_staff": [{"id": row.get("id"), "name": row.get("name", "Tanpa nama")} for row in missing],
        })
    seen_ids = set()
    duplicates = []
    for row in records:
        nip = normalize_identity(row.get("nip", ""))
        if nip in seen_ids:
            duplicates.append(row.get("name", "Tanpa nama"))
        seen_ids.add(nip)
    if duplicates:
        raise HTTPException(409, detail={
            "message": "Ada NIP/NIK duplikat. Perbaiki roster sebelum menerbitkan PIN.",
            "duplicate_staff": duplicates,
        })

    issued_at = utc_now()
    used: set[str] = set()
    output_rows = []
    for row in records:
        temp_pin = generate_temporary_pin(used)
        output_rows.append({
            "id": row["id"],
            "name": row.get("name", ""),
            "department": row.get("department", ""),
            "role": row.get("role", "staff"),
            "nip": normalize_identity(row.get("nip", "")),
            "id_type": row.get("id_type") or infer_id_type(row.get("nip", "")),
            "temporary_pin": temp_pin,
            "was_activated": bool(row.get("is_activated") and row.get("pin_hash")),
        })
    # Render before committing any PIN change so a PDF generation failure does not lock accounts.
    pdf = build_temporary_credentials_pdf(output_rows, issued_at.astimezone(ZoneInfo("Asia/Jakarta")))
    changed = []
    try:
        for row, exported in zip(records, output_rows):
            await db.staff.update_one({"id": row["id"]}, {
                "$set": {
                    "pin_hash": hash_credential(exported["temporary_pin"]),
                    "is_activated": True,
                    "pin_change_required": True,
                    "temporary_pin_issued_at": iso_utc(issued_at),
                    "last_credential_issued_by": user["id"],
                    "login_failed_attempts": 0,
                    "login_locked_until": "",
                },
                "$unset": {
                    "activation_code_hash": "",
                    "activation_code_expires_at": "",
                    "activation_code_issued_by": "",
                },
            })
            changed.append(row)
            await db.auth_sessions.delete_many({"staff_id": row["id"]})
    except Exception:
        # Best-effort rollback if a later row fails during the multi-document update.
        for row in changed:
            restore = {key: row[key] for key in (
                "pin_hash", "is_activated", "pin_change_required", "temporary_pin_issued_at",
                "last_credential_issued_by", "login_failed_attempts", "login_locked_until",
                "activation_code_hash", "activation_code_expires_at", "activation_code_issued_by",
            ) if key in row}
            await db.staff.update_one({"id": row["id"]}, {"$set": restore})
        raise

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "event": "staff_temporary_pins_rotated_and_exported",
        "actor_id": user["id"],
        "staff_ids": [row["id"] for row in records],
        "count": len(records),
        "created_at": iso_utc(issued_at),
        "plaintext_persisted": False,
    })
    filename = f"loka-kin-kredensial-{issued_at.astimezone(ZoneInfo('Asia/Jakarta')).strftime('%Y%m%d-%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
        },
    )


@api.get("/admin/clustering/summary")
async def clustering_summary(user: Dict[str, Any] = Depends(require_super_admin)):
    """Ringkasan cluster peran x departemen untuk ditampilkan di aplikasi."""
    from clustering_export import summarize

    records = await db.staff.find({}, {"_id": 0}).to_list(5000)
    return summarize(records)


@api.post("/admin/clustering/apply")
async def clustering_apply(
    file: UploadFile = File(...),
    pin: str = Form("123456"),
    strict: bool = Form(False),
    user: Dict[str, Any] = Depends(require_super_admin),
):
    """Terapkan peran + PIN seragam dari berkas Excel/CSV yang diunggah Super Admin."""
    from clustering_apply import (
        TemplateError,
        apply_roles,
        read_upload,
        result_payload,
        upsert_separate_super_admin,
    )
    from clustering_export import summarize

    payload = await file.read()
    try:
        entries, separate = read_upload(file.filename or "unggahan.xlsx", payload)
    except TemplateError as exc:
        raise HTTPException(400, str(exc))

    records = await db.staff.find({}, {"_id": 0}).to_list(5000)
    try:
        result = apply_roles(records, entries, pin, strict=strict)
    except TemplateError as exc:
        raise HTTPException(400, str(exc))
    if result["problems"]:
        raise HTTPException(400, {
            "message": "Peran tidak diterapkan karena berkas isian belum konsisten.",
            "problems": result["problems"],
        })

    super_admin = upsert_separate_super_admin(records, separate, pin=pin)
    by_id = {str(row.get("id")): row for row in records}
    for row in records:
        await db.staff.update_one({"id": row["id"]}, {"$set": row})
    await db.auth_sessions.delete_many({})
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "event": "clustering_roles_applied",
        "actor_id": user["id"],
        "file": file.filename,
        "processed": result["processed"],
        "role_changes": len(result["role_changes"]),
        "pin_uniform": True,
        "created_at": iso_utc(utc_now()),
    })
    response = result_payload(result, super_admin)
    response["summary"] = summarize(list(by_id.values()))
    response["sessions_revoked"] = True
    return response


@api.get("/admin/clustering/template.xlsx")
async def clustering_template_xlsx(user: Dict[str, Any] = Depends(require_super_admin)):
    """Format clustering Excel (4 sheet) yang dibuat dari data akun terkini."""
    from clustering_export import DEFAULT_PIN, build_workbook

    records = await db.staff.find({}, {"_id": 0}).to_list(5000)
    workbook = build_workbook(records, pin=DEFAULT_PIN)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    stamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y%m%d")
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="Clustering-Akun-LokaKin-{stamp}.xlsx"',
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
        },
    )


@api.get("/admin/clustering/template.csv")
async def clustering_template_csv(user: Dict[str, Any] = Depends(require_super_admin)):
    """Tabel datar 78 akun (satu kolom per peran) untuk pandas/SPSS/Excel."""
    from clustering_export import DEFAULT_PIN, build_csv

    records = await db.staff.find({}, {"_id": 0}).to_list(5000)
    stamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y%m%d")
    return StreamingResponse(
        io.BytesIO(build_csv(records, pin=DEFAULT_PIN)),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="Clustering-Akun-LokaKin-{stamp}.csv"',
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
        },
    )


@api.get("/admin/clustering/template.pdf")
async def clustering_template_pdf(user: Dict[str, Any] = Depends(require_super_admin)):
    """PDF A4 lanskap (akun + matriks cluster) agar dapat langsung diunduh/dicetak."""
    from clustering_export import DEFAULT_PIN, build_pdf

    records = await db.staff.find({}, {"_id": 0}).to_list(5000)
    stamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y%m%d")
    return StreamingResponse(
        io.BytesIO(build_pdf(records, pin=DEFAULT_PIN)),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Clustering-Akun-LokaKin-{stamp}.pdf"',
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
        },
    )


@api.get("/admin/clustering/template.html")
async def clustering_template_html(user: Dict[str, Any] = Depends(require_super_admin)):
    """Tampilan siap cetak (A4 lanskap) sebagai alternatif PDF/Excel."""
    from clustering_export import DEFAULT_PIN, build_print_html

    records = await db.staff.find({}, {"_id": 0}).to_list(5000)
    return Response(
        content=build_print_html(records, pin=DEFAULT_PIN),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"},
    )


@api.get("/staff", response_model=List[Staff])
async def get_staff(include_inactive: bool = True, user: Dict[str, Any] = Depends(get_current_user)):
    """Staf only see themselves; supervisors can see all names; only Admin sees NIP/NIK."""
    await seed_data()
    if user.get("role") == "staff":
        query: Dict[str, Any] = {"id": user["id"]}
    elif user.get("role") in ADMIN_ROLES and include_inactive:
        query = {}
    elif user.get("role") in SUPERVISOR_ROLES and include_inactive:
        query = {}
    else:
        query = {"active": True}
    rows = await db.staff.find(query, {"_id": 0}).to_list(500)
    rows.sort(key=staff_sort_key)
    reveal_identity = user.get("role") in ADMIN_ROLES
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
    if role == "super_admin" and user.get("role") != "super_admin":
        raise HTTPException(403, "Hanya Super Admin yang dapat menetapkan role Super Admin.")
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
        if role == "super_admin" and user.get("role") != "super_admin":
            raise HTTPException(403, "Hanya Super Admin yang dapat menetapkan role Super Admin.")
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
    if existing.get("role") == "super_admin" and user.get("role") != "super_admin":
        raise HTTPException(403, "Hanya Super Admin yang dapat mengubah akun Super Admin.")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    requested_role = normalize_role(changes.get("role", existing.get("role", "staff")))
    if requested_role == "super_admin" and user.get("role") != "super_admin":
        raise HTTPException(403, "Hanya Super Admin yang dapat menetapkan role Super Admin.")
    if existing.get("role") == "admin" and existing.get("active", True) and (
        requested_role != "admin" or changes.get("active") is False
    ) and await db.staff.count_documents({"role": "admin", "active": {"$ne": False}, "is_activated": True}) <= 1:
        raise HTTPException(400, "Promosikan atau aktifkan Admin lain sebelum menonaktifkan role Admin terakhir.")
    if existing.get("role") == "super_admin" and existing.get("active", True) and (
        requested_role != "super_admin" or changes.get("active") is False
    ) and await db.staff.count_documents({"role": "super_admin", "active": {"$ne": False}, "is_activated": True}) <= 1:
        raise HTTPException(400, "Super Admin aktif terakhir tidak dapat dinonaktifkan atau diturunkan perannya.")
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
        if role == "super_admin" and user.get("role") != "super_admin":
            raise HTTPException(403, "Hanya Super Admin yang dapat menetapkan role Super Admin.")
        changes["role"] = role
        if role != "super_admin" and existing.get("system_super_admin"):
            changes["system_super_admin"] = False
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
    if staff.get("role") == "super_admin" and user.get("role") != "super_admin":
        raise HTTPException(403, "Hanya Super Admin yang dapat menghapus akun Super Admin.")
    if staff.get("role") == "admin" and staff.get("active", True) and staff.get("is_activated") and await db.staff.count_documents({"role": "admin", "active": {"$ne": False}, "is_activated": True}) <= 1:
        raise HTTPException(400, "Admin aktif terakhir tidak dapat dihapus atau dinonaktifkan.")
    if staff.get("role") == "super_admin" and staff.get("active", True) and staff.get("is_activated") and await db.staff.count_documents({"role": "super_admin", "active": {"$ne": False}, "is_activated": True}) <= 1:
        raise HTTPException(400, "Super Admin aktif terakhir tidak dapat dihapus atau dinonaktifkan.")
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
    if normalize_task_status(existing.get("status")) == "finish" and user.get("role") not in ADMIN_ROLES:
        raise HTTPException(403, "Laporan Finish terkunci. Hubungi Admin untuk koreksi.")

    doc = payload.model_dump()
    # Hanya Admin yang boleh memindahkan laporan ke staf lain. Pengguna lain
    # tetap terikat pada pemilik laporan yang sudah tersimpan di server.
    if user.get("role") not in ADMIN_ROLES:
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
    if normalize_task_status(task.get("status")) == "finish" and user.get("role") not in ADMIN_ROLES:
        raise HTTPException(403, "Laporan Finish terkunci. Hubungi Admin untuk koreksi.")
    result = await db.tasks.delete_one({"id": task_id})
    if not result.deleted_count:
        raise HTTPException(404, "Tugas tidak ditemukan")
    return {"ok": True}


ANALYTICS_SECTIONS = [
    {
        "id": "umum",
        "title": "Bagian Umum",
        "short": "Umum",
        "tagline": "Tata usaha, keuangan, SDM, perencanaan, humas & sarana prasarana",
        "departments": ["Umum", "Admin", "Bendahara", "Perencanaan", "Informasi dan Humas", "Sarana & Prasarana"],
        "icon": "Building2",
        "color": "blue",
        "code_prefix": "UM",
    },
    {
        "id": "medis",
        "title": "Layanan Rehabilitasi Medis",
        "short": "Medis",
        "tagline": "Dokter, keperawatan, farmasi klinis, gizi, sanitasi & fisioterapi",
        "departments": ["Layanan Rehabilitasi Medis"],
        "icon": "Stethoscope",
        "color": "emerald",
        "code_prefix": "MED",
    },
    {
        "id": "sosial",
        "title": "Layanan Rehabilitasi Sosial",
        "short": "Sosial",
        "tagline": "Asesmen sosial, bimbingan, pelatihan vokasional & reintegrasi",
        "departments": ["Layanan Rehabilitasi Sosial"],
        "icon": "HeartHandshake",
        "color": "amber",
        "code_prefix": "SOS",
    },
]

# Standar mutu seragam untuk ketiga indikator ringkas.
ANALYTICS_INDICATOR_TARGET = 95.0
JAKARTA_TZ = ZoneInfo("Asia/Jakarta")


def parse_local_datetime(value: Any) -> Optional[datetime]:
    """Baca timestamp laporan; nilai tanpa zona dianggap waktu Asia/Jakarta."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=JAKARTA_TZ) if parsed.tzinfo is None else parsed.astimezone(JAKARTA_TZ)


def parse_due_date(value: Any) -> Optional[date]:
    """Baca tenggat laporan (tanggal, 'Hari ini', atau dd/mm/yyyy)."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    lowered = text.lower()
    today = datetime.now(JAKARTA_TZ).date()
    if lowered in {"hari ini", "today"}:
        return today
    if lowered in {"besok", "tomorrow"}:
        return today + timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def task_finish_datetime(task: Dict[str, Any]) -> Optional[datetime]:
    for key in ("finish_at", "status_updated_at", "doing_at", "todo_at", "created_at"):
        parsed = parse_local_datetime(task.get(key))
        if parsed:
            return parsed
    return None


def task_created_date(task: Dict[str, Any]) -> Optional[date]:
    parsed = parse_local_datetime(task.get("created_at")) or parse_local_datetime(task.get("todo_at"))
    return parsed.date() if parsed else None


def build_trends(tasks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Tren produktivitas nyata: jumlah laporan masuk & selesai per periode."""
    today = datetime.now(JAKARTA_TZ).date()
    created = [(task_created_date(t), t) for t in tasks]
    finished = [(task_finish_datetime(t), t) for t in tasks]

    daily: List[Dict[str, Any]] = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        daily.append({
            "label": day.strftime("%d %b"),
            "total": sum(1 for created_at, _ in created if created_at == day),
            "finish": sum(1 for finished_at, t in finished
                          if finished_at and finished_at.date() == day and normalize_task_status(t.get("status")) == "finish"),
        })

    weekly: List[Dict[str, Any]] = []
    monday = today - timedelta(days=(today.weekday()))
    for offset in range(3, -1, -1):
        start = monday - timedelta(weeks=offset)
        end = start + timedelta(days=6)
        weekly.append({
            "label": f"Minggu {4 - offset}",
            "range": f"{start.strftime('%d/%m')}–{end.strftime('%d/%m')}",
            "total": sum(1 for created_at, _ in created if created_at and start <= created_at <= end),
            "finish": sum(1 for finished_at, t in finished
                          if finished_at and start <= finished_at.date() <= end and normalize_task_status(t.get("status")) == "finish"),
        })

    monthly: List[Dict[str, Any]] = []
    for offset in range(5, -1, -1):
        month = (today.replace(day=1) - timedelta(days=1)) if offset == 0 else None
        year = today.year
        month_index = today.month - offset
        while month_index <= 0:
            month_index += 12
            year -= 1
        label = datetime(year, month_index, 1).strftime("%b")
        monthly.append({
            "label": label,
            "total": sum(1 for created_at, _ in created
                         if created_at and created_at.year == year and created_at.month == month_index),
            "finish": sum(1 for finished_at, t in finished
                          if finished_at and finished_at.year == year and finished_at.month == month_index
                          and normalize_task_status(t.get("status")) == "finish"),
        })

    return {"daily": daily, "weekly": weekly, "monthly": monthly}


def status_counts(tasks: List[Dict[str, Any]]) -> Dict[str, int]:
    statuses = [normalize_task_status(t.get("status")) or "todo" for t in tasks]
    counts = {
        "todo": sum(1 for status in statuses if status == "todo"),
        "doing": sum(1 for status in statuses if status == "doing"),
        "finish": sum(1 for status in statuses if status == "finish"),
    }
    counts["plan"] = counts["todo"]  # alias kompatibilitas
    return counts


def percentage_split(counts: Dict[str, int]) -> Dict[str, int]:
    total = max(counts["todo"] + counts["doing"] + counts["finish"], 1)
    return {key: round(counts[key] / total * 100) for key in ("todo", "doing", "finish", "plan")}


def deadline_adherence(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Hitung ketepatan tenggat: selesai ≤ akhir hari tenggat."""
    today = datetime.now(JAKARTA_TZ).date()
    evaluated = 0
    on_time = 0
    late = 0
    for task in tasks:
        due = parse_due_date(task.get("due_date"))
        if not due:
            continue
        status = normalize_task_status(task.get("status")) or "todo"
        finished_at = task_finish_datetime(task)
        if status == "finish" and finished_at:
            evaluated += 1
            if finished_at.date() <= due:
                on_time += 1
            else:
                late += 1
        elif status != "finish" and due < today:
            # Belum selesai padahal tenggat sudah lewat = terlambat.
            evaluated += 1
            late += 1
    rate = round(on_time / evaluated * 100, 1) if evaluated else 0.0
    return {"evaluated": evaluated, "on_time": on_time, "late": late, "rate": rate}


def quality_status(realization: float, target: float, has_data: bool) -> tuple[str, str]:
    if not has_data:
        return "Belum Ada Data", "blue"
    if realization >= target:
        return "Target Tercapai", "green"
    if realization >= target * 0.9:
        return "Mendekati Target", "amber"
    return "Perlu Perhatian", "red"


def compute_section_metrics(tasks: List[Dict[str, Any]], staff_rows: List[Dict[str, Any]],
                            section: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan satu bagian: laporan harian, status penyelesaian, dan tenggat waktu."""
    departments_in_section = set(section["departments"])
    staff_in_section = [s for s in staff_rows if (s.get("department") or "") in departments_in_section]
    staff_ids = {s["id"] for s in staff_in_section}
    section_tasks = [t for t in tasks if t.get("staff_id") in staff_ids]

    counts = status_counts(section_tasks)
    total = counts["todo"] + counts["doing"] + counts["finish"]
    completion_rate = round(counts["finish"] / total * 100, 1) if total else 0.0

    # Indikator 1: disiplin laporan harian = staf yang melaporkan / staf aktif unit.
    reporting_staff = {t.get("staff_id") for t in section_tasks if t.get("staff_id")}
    reporting_rate = round(len(reporting_staff) / len(staff_in_section) * 100, 1) if staff_in_section else 0.0

    adherence = deadline_adherence(section_tasks)
    has_deadline_data = adherence["evaluated"] > 0

    target = ANALYTICS_INDICATOR_TARGET
    raw_indicators = [
        {
            "code": f"KPI-{section.get('code_prefix', section['id'][:3].upper())}-01",
            "name": "Laporan Kinerja Harian",
            "desc": (
                f"{len(reporting_staff)} dari {len(staff_in_section)} staf unit mengisi laporan kinerja harian "
                f"({total} laporan tercatat pada periode analitik)."
            ),
            "target": target,
            "realization": reporting_rate,
            "weight": 34,
            "data_points": len(reporting_staff),
            "has_data": bool(staff_in_section),
        },
        {
            "code": f"KPI-{section.get('code_prefix', section['id'][:3].upper())}-02",
            "name": "Status Penyelesaian Laporan",
            "desc": (
                f"{counts['finish']} laporan Finish, {counts['doing']} Doing, dan {counts['todo']} To Do List "
                f"dari {total} laporan unit."
            ),
            "target": target,
            "realization": completion_rate,
            "weight": 33,
            "data_points": total,
            "has_data": total > 0,
        },
        {
            "code": f"KPI-{section.get('code_prefix', section['id'][:3].upper())}-03",
            "name": "Ketepatan Tenggat Waktu Penyelesaian",
            "desc": (
                f"{adherence['on_time']} dari {adherence['evaluated']} laporan bertenggat selesai tepat waktu; "
                f"{adherence['late']} terlambat."
                if has_deadline_data else
                "Belum ada laporan dengan tenggat waktu yang dapat dievaluasi."
            ),
            "target": target,
            "realization": adherence["rate"],
            "weight": 33,
            "data_points": adherence["evaluated"],
            "has_data": has_deadline_data,
        },
    ]

    indicators = []
    weighted_sum = 0.0
    active_weight = 0.0
    for raw in raw_indicators:
        status_label, tone = quality_status(raw["realization"], raw["target"], raw["has_data"])
        achievement = round((raw["realization"] / raw["target"]) * 100, 1) if raw["has_data"] else 0.0
        indicators.append({
            "code": raw["code"],
            "name": raw["name"],
            "desc": raw["desc"],
            "target": raw["target"],
            "realization": raw["realization"],
            "unit": "%",
            "achievement_rate": min(achievement, 200.0),
            "weight": raw["weight"],
            "status": status_label,
            "status_tone": tone,
            "data_points": raw["data_points"],
            "has_data": raw["has_data"],
        })
        if raw["has_data"]:
            weighted_sum += raw["realization"] * raw["weight"]
            active_weight += raw["weight"]

    # Indikator yang belum punya data tidak menurunkan skor bagian.
    section_score = round(weighted_sum / active_weight, 1) if active_weight else 0.0
    achievement_rate = round((section_score / target) * 100, 1) if target else 0.0
    if not total and not staff_in_section:
        overall_badge, overall_tone = "Belum Ada Data", "blue"
    elif achievement_rate >= 100:
        overall_badge, overall_tone = "Sangat Baik (A)", "green"
    elif achievement_rate >= 90:
        overall_badge, overall_tone = "Baik (B)", "blue"
    elif achievement_rate >= 75:
        overall_badge, overall_tone = "Cukup (C)", "amber"
    else:
        overall_badge, overall_tone = "Perlu Peningkatan", "red"

    department_breakdown = []
    for department in section["departments"]:
        dept_tasks = [t for t in section_tasks
                      if next((s for s in staff_in_section if s["id"] == t.get("staff_id")), {}).get("department") == department]
        dept_counts = status_counts(dept_tasks)
        department_breakdown.append({
            "name": department,
            "total": len(dept_tasks),
            "finish": dept_counts["finish"],
            "doing": dept_counts["doing"],
            "todo": dept_counts["todo"],
        })

    return {
        "id": section["id"],
        "title": section["title"],
        "short": section["short"],
        "tagline": section["tagline"],
        "icon": section["icon"],
        "color": section["color"],
        "departments": section["departments"],
        "staff_count": len(staff_in_section),
        "reporting_staff": len(reporting_staff),
        "total_tasks": total,
        "counts": counts,
        "percentages": percentage_split(counts),
        "completion_rate": completion_rate,
        "deadline": adherence,
        "trends": build_trends(section_tasks),
        "departments_breakdown": department_breakdown,
        "overall_score": section_score,
        "target_avg": target,
        "achievement_rate": achievement_rate,
        "overall_badge": overall_badge,
        "overall_tone": overall_tone,
        "indicators": indicators,
    }


@api.get("/analytics")
async def analytics(user: Dict[str, Any] = Depends(get_current_user)):
    """Analitik ringkas: laporan harian, status, dan tenggat per bagian Umum/Medis/Sosial."""
    await seed_data()
    task_query = {} if is_report_manager(user) else {"staff_id": user["id"]}
    tasks = await db.tasks.find(task_query, {"_id": 0}).to_list(500)
    for task in tasks:
        if task.get("status") == "plan":
            task["status"] = "todo"

    counts = status_counts(tasks)
    total = max(counts["todo"] + counts["doing"] + counts["finish"], 1)
    percentages = percentage_split(counts)

    staff_query = {} if is_report_manager(user) else {"id": user["id"]}
    staff_rows = await db.staff.find(staff_query, {"_id": 0}).to_list(500)

    sections = [compute_section_metrics(tasks, staff_rows, section) for section in ANALYTICS_SECTIONS]

    # Kompatibilitas: daftar departemen lengkap tetap dikirim untuk konsumen lama.
    staff_departments = {person["id"]: person.get("department", "") for person in staff_rows}
    departments = [
        {
            "name": department,
            "total": sum(1 for t in tasks if staff_departments.get(t["staff_id"]) == department),
            "finish": sum(1 for t in tasks if staff_departments.get(t["staff_id"]) == department
                          and normalize_task_status(t.get("status")) == "finish"),
        }
        for department in DEPARTMENTS
    ]

    return {
        "total_tasks": len(tasks),
        "counts": counts,
        "percentages": percentages,
        "completion_rate": round(counts["finish"] / total * 100),
        "trends": build_trends(tasks),
        "departments": departments,
        "total_staff": len(staff_rows),
        "kpi": sections,
        "sections": sections,
        "unit_groups": [
            {
                "id": section["id"],
                "name": section["title"],
                "short": section["short"],
                "total": section["total_tasks"],
                "finish": section["counts"]["finish"],
                "doing": section["counts"]["doing"],
                "todo": section["counts"]["todo"],
                "completion_rate": section["completion_rate"],
                "staff_count": section["staff_count"],
            }
            for section in sections
        ],
        "indicator_target": ANALYTICS_INDICATOR_TARGET,
    }


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
