from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import List
import os, uuid, asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
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
    status: str = "plan"
    target: str = ""
    priority: str = "Sedang"
    due_date: str = ""
    notes: str = ""
    proof_link: str = ""
    photo_data: str = ""
    photo_name: str = ""


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

    if await db.tasks.count_documents({}) == 0:
        staff = await db.staff.find({}, {"_id": 0}).to_list(4)
        now = datetime.now(timezone.utc).isoformat()
        demo = [
            {"id": "task-1", "title": "Rekap laporan layanan harian", "staff_id": staff[0]["id"], "status": "plan", "target": "12 laporan", "priority": "Tinggi", "due_date": "Hari ini", "notes": "Pastikan semua unit terinput", "proof_link": "", "photo_data": "", "photo_name": "", "created_at": now},
            {"id": "task-2", "title": "Validasi data kehadiran", "staff_id": staff[1]["id"], "status": "doing", "target": "78 data", "priority": "Sedang", "due_date": "Hari ini", "notes": "Cek data yang belum sinkron", "proof_link": "", "photo_data": "", "photo_name": "", "created_at": now},
            {"id": "task-3", "title": "Kirim ringkasan mingguan", "staff_id": staff[2]["id"], "status": "finish", "target": "1 dokumen", "priority": "Rendah", "due_date": "Selesai", "notes": "Dikirim ke koordinator", "proof_link": "https://docs.google.com", "photo_data": "", "photo_name": "", "created_at": now},
            {"id": "task-4", "title": "Perbarui SOP meja layanan", "staff_id": staff[3]["id"], "status": "doing", "target": "3 bab", "priority": "Tinggi", "due_date": "Besok", "notes": "Review bersama tim", "proof_link": "", "photo_data": "", "photo_name": "", "created_at": now},
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
    doc.update({"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat()})
    await db.tasks.insert_one(doc)
    return doc


@api.patch("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, payload: TaskCreate):
    doc = payload.model_dump()
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
    counts = {status: sum(1 for t in tasks if t["status"] == status) for status in ["plan", "doing", "finish"]}
    total = max(len(tasks), 1)
    now = datetime.now(timezone.utc)
    daily = [{"label": (now - timedelta(days=i)).strftime("%d %b"), "total": max(1, len(tasks) - i % 3), "finish": max(0, counts["finish"] - i % 2)} for i in range(6, -1, -1)]
    weekly = [{"label": f"Minggu {i}", "total": max(1, len(tasks) + i), "finish": max(0, counts["finish"] + i % 2)} for i in range(1, 5)]
    monthly = [{"label": (now - timedelta(days=30 * i)).strftime("%b"), "total": max(1, len(tasks) + i * 2), "finish": max(0, counts["finish"] + i)} for i in range(5, -1, -1)]
    staff_rows = await db.staff.find({}, {"_id": 0}).to_list(500)
    staff_departments = {person["id"]: person.get("department", "") for person in staff_rows}
    departments = [{"name": department, "total": sum(1 for t in tasks if staff_departments.get(t["staff_id"]) == department), "finish": sum(1 for t in tasks if staff_departments.get(t["staff_id"]) == department and t["status"] == "finish")} for department in DEPARTMENTS]
    return {"total_tasks": len(tasks), "counts": counts, "percentages": {k: round(v / total * 100) for k, v in counts.items()}, "completion_rate": round(counts["finish"] / total * 100), "trends": {"daily": daily, "weekly": weekly, "monthly": monthly}, "departments": departments, "total_staff": len(staff_rows)}


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
