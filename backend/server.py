from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any
import os, uuid, asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ.get("MONGO_URL", "mock")
if mongo_url == "mock" or not mongo_url:
    try:
        from mongomock_motor import AsyncMongoMockClient
        client = AsyncMongoMockClient()
    except ImportError:
        client = AsyncIOMotorClient("mongodb://localhost:27017")
else:
    client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get("DB_NAME", "loka_kin")]
app = FastAPI(title="LOKA-Kin API")
api = APIRouter(prefix="/api")

DEPARTMENTS = ["Admin", "Bendahara", "Perencanaan", "Informasi dan Humas", "Layanan Rehabilitasi Medis", "Layanan Rehabilitasi Sosial", "Umum", "Sarana & Prasarana", "Clinical Supervisor"]

# Pemetaan bagian pada DAFTAR HADIR STAF ke departemen resmi aplikasi
DEPT_MAP = {
    "Layanan Sosial": "Layanan Rehabilitasi Sosial",
    "Layanan Medis": "Layanan Rehabilitasi Medis",
    "Clinical Supervisor": "Clinical Supervisor",
    "Bendahara": "Bendahara",
    "Perencanaan": "Perencanaan",
    "Umum": "Umum",
    "Administrasi & SDM": "Admin",
    "Sarana Prasarana": "Sarana & Prasarana",
    "Pengadaan Barang & Jasa": "Admin",
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


def make_initials(name: str) -> str:
    cleaned = name.replace(".", " ").replace(",", " ")
    words = [w for w in cleaned.split() if w and w[0].isalpha()]
    words = [w for w in words if w.lower() not in TITLE_TOKENS]
    initials = "".join(w[0].upper() for w in words[:2])
    return initials or name[:2].upper()


def resolve_department(doc_dept: str) -> str:
    return DEPT_MAP.get(doc_dept, "Admin")


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


class StaffCreate(BaseModel):
    name: str
    department: str


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


async def seed_data():
    # Idempotent upsert staff-1..staff-78 dari SEED_STAFF (sumber DAFTAR HADIR STAF.docx)
    for i, (name, doc_dept) in enumerate(SEED_STAFF, start=1):
        await db.staff.update_one(
            {"id": f"staff-{i}"},
            {"$set": {
                "id": f"staff-{i}",
                "name": name,
                "department": resolve_department(doc_dept),
                "initials": make_initials(name),
                "active": True,
            }},
            upsert=True,
        )
    # Bersihkan staf lama staff-N (N > 78) yang tidak memiliki tugas
    stale_cursor = db.staff.find({"id": {"$regex": r"^staff-\d+$"}}, {"_id": 0, "id": 1})
    async for row in stale_cursor:
        tail = row["id"].split("-", 1)[1]
        if tail.isdigit() and int(tail) > 78:
            if await db.tasks.count_documents({"staff_id": row["id"]}) == 0:
                await db.staff.delete_one({"id": row["id"]})

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


@api.get("/")
async def root():
    return {"message": "LOKA-Kin API aktif"}


@api.get("/staff", response_model=List[Staff])
async def get_staff():
    await seed_data()
    rows = await db.staff.find({}, {"_id": 0}).to_list(500)
    rows.sort(key=staff_sort_key)
    return rows


@api.post("/staff", response_model=Staff)
async def create_staff(payload: StaffCreate):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Nama staf wajib diisi")
    if payload.department not in DEPARTMENTS:
        raise HTTPException(400, "Departemen tidak valid")
    doc = {"id": f"staff-{uuid.uuid4()}", "name": name, "department": payload.department, "initials": make_initials(name), "active": True}
    await db.staff.insert_one(doc)
    return doc


@api.delete("/staff/{staff_id}")
async def delete_staff(staff_id: str):
    result = await db.staff.delete_one({"id": staff_id})
    if not result.deleted_count:
        raise HTTPException(404, "Staf tidak ditemukan")
    return {"ok": True}


@api.get("/tasks", response_model=List[Task])
async def get_tasks():
    await seed_data()
    return await db.tasks.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/tasks", response_model=Task)
async def create_task(payload: TaskCreate):
    doc = payload.model_dump()
    status = doc.get("status", "todo")
    if status == "plan":
        status = "todo"
    
    # Validasi: Tugas baru wajib berstatus To Do List terlebih dahulu
    if status in ["doing", "finish"]:
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

    doc.update({"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat()})
    await db.tasks.insert_one(doc)
    return doc


@api.patch("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, payload: TaskCreate):
    existing = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Tugas tidak ditemukan")

    doc = payload.model_dump()
    new_status = doc.get("status", "todo")
    if new_status == "plan":
        new_status = "todo"
    doc["status"] = new_status

    old_status = existing.get("status", "todo")
    if old_status == "plan":
        old_status = "todo"

    # Validasi: Tugas tidak dapat diubah ke Doing atau Finish jika belum pernah diinputkan ke To Do List
    has_todo = bool(existing.get("todo_at")) or (existing.get("status") in ["todo", "plan"]) or bool(doc.get("todo_at"))
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
async def delete_task(task_id: str):
    result = await db.tasks.delete_one({"id": task_id})
    if not result.deleted_count:
        raise HTTPException(404, "Tugas tidak ditemukan")
    return {"ok": True}


@api.get("/analytics")
async def analytics():
    await seed_data()
    tasks = await db.tasks.find({}, {"_id": 0}).to_list(500)
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
    staff_rows = await db.staff.find({}, {"_id": 0}).to_list(500)
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
async def export_sheet():
    exported_at = datetime.now(ZoneInfo("Asia/Jakarta"))
    await db.export_logs.insert_one({"id": str(uuid.uuid4()), "mode": "manual", "status": "simulated", "exported_at": exported_at.isoformat(), "spreadsheet_id": "1RVliN0kwubvYBmAoCYWrIJhV6wgT2RvW4XcTAxF--1I"})
    return {"ok": True, "status": "simulated", "message": "Simulasi ekspor manual berhasil dicatat.", "exported_at": exported_at.isoformat(), "next_run": next_export_time().isoformat()}


def next_export_time():
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    target = now.replace(hour=21, minute=0, second=0, microsecond=0)
    return target + timedelta(days=1) if now >= target else target


@api.get("/export/status")
async def export_status():
    last = await db.export_logs.find_one({}, {"_id": 0}, sort=[("exported_at", -1)])
    return {"mode": "simulated", "schedule": "21:00", "timezone": "Asia/Jakarta", "spreadsheet_id": "1RVliN0kwubvYBmAoCYWrIJhV6wgT2RvW4XcTAxF--1I", "last_export": last, "next_run": next_export_time().isoformat()}


async def scheduled_export_loop():
    while True:
        wait_seconds = (next_export_time() - datetime.now(ZoneInfo("Asia/Jakarta"))).total_seconds()
        await asyncio.sleep(max(1, wait_seconds))
        exported_at = datetime.now(ZoneInfo("Asia/Jakarta"))
        await db.export_logs.insert_one({"id": str(uuid.uuid4()), "mode": "automatic", "status": "simulated", "exported_at": exported_at.isoformat(), "spreadsheet_id": "1RVliN0kwubvYBmAoCYWrIJhV6wgT2RvW4XcTAxF--1I"})


@app.on_event("startup")
async def start_scheduler():
    app.state.export_scheduler = asyncio.create_task(scheduled_export_loop())


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])


@app.on_event("shutdown")
async def shutdown_db_client():
    if hasattr(app.state, "export_scheduler"):
        app.state.export_scheduler.cancel()
    client.close()
