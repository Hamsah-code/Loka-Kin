from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, List
import os, uuid, asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="LOKA-Kin API")
api = APIRouter(prefix="/api")

DEPARTMENTS = ["Admin", "Bendahara", "Perencanaan", "Informasi dan Humas", "Layanan Rehabilitasi Medis", "Layanan Rehabilitasi Sosial"]
NAMES = ["Ari Pratama", "Bunga Lestari", "Cahyo Nugroho", "Dina Amalia", "Eko Saputra", "Fajar Ramadhan", "Gita Maharani", "Hana Putri", "Irfan Maulana", "Jihan Sari"]

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
    if await db.staff.count_documents({}) == 0:
        staff = []
        for i in range(85):
            name = f"{NAMES[i % len(NAMES)]} {i + 1:02d}"
            staff.append({"id": f"staff-{i+1}", "name": name, "department": DEPARTMENTS[i % len(DEPARTMENTS)], "initials": "".join(x[0] for x in name.split()[:2]), "active": True})
        await db.staff.insert_many(staff)
    else:
        existing = await db.staff.find({}, {"_id": 0}).to_list(100)
        for i, person in enumerate(existing):
            if person.get("department") not in DEPARTMENTS:
                await db.staff.update_one({"id": person["id"]}, {"$set": {"department": DEPARTMENTS[i % len(DEPARTMENTS)]}})
    if await db.tasks.count_documents({}) == 0:
        staff = await db.staff.find({}, {"_id": 0}).to_list(4)
        now = datetime.now(timezone.utc).isoformat()
        demo = [
            {"id": "task-1", "title": "Rekap laporan layanan harian", "staff_id": staff[0]["id"], "status": "plan", "target": "12 laporan", "priority": "Tinggi", "due_date": "Hari ini", "notes": "Pastikan semua unit terinput", "proof_link": "", "created_at": now},
            {"id": "task-2", "title": "Validasi data kehadiran", "staff_id": staff[1]["id"], "status": "doing", "target": "85 data", "priority": "Sedang", "due_date": "Hari ini", "notes": "Cek data yang belum sinkron", "proof_link": "", "created_at": now},
            {"id": "task-3", "title": "Kirim ringkasan mingguan", "staff_id": staff[2]["id"], "status": "finish", "target": "1 dokumen", "priority": "Rendah", "due_date": "Selesai", "notes": "Dikirim ke koordinator", "proof_link": "https://docs.google.com", "created_at": now},
            {"id": "task-4", "title": "Perbarui SOP meja layanan", "staff_id": staff[3]["id"], "status": "doing", "target": "3 bab", "priority": "Tinggi", "due_date": "Besok", "notes": "Review bersama tim", "proof_link": "", "created_at": now},
        ]
        await db.tasks.insert_many(demo)

@api.get("/")
async def root(): return {"message": "LOKA-Kin API aktif"}

@api.get("/staff", response_model=List[Staff])
async def get_staff():
    await seed_data()
    return await db.staff.find({}, {"_id": 0}).to_list(100)

@api.post("/staff", response_model=Staff)
async def create_staff(payload: StaffCreate):
    name = payload.name.strip()
    if not name: raise HTTPException(400, "Nama staf wajib diisi")
    doc = {"id": f"staff-{uuid.uuid4()}", "name": name, "department": payload.department, "initials": "".join(x[0] for x in name.split()[:2]), "active": True}
    await db.staff.insert_one(doc)
    return doc

@api.delete("/staff/{staff_id}")
async def delete_staff(staff_id: str):
    result = await db.staff.delete_one({"id": staff_id})
    if not result.deleted_count: raise HTTPException(404, "Staf tidak ditemukan")
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
    if not result: raise HTTPException(404, "Tugas tidak ditemukan")
    return result

@api.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    result = await db.tasks.delete_one({"id": task_id})
    if not result.deleted_count: raise HTTPException(404, "Tugas tidak ditemukan")
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
    staff_rows = await db.staff.find({}, {"_id": 0}).to_list(100)
    staff_departments = {person["id"]: person.get("department", "") for person in staff_rows}
    departments = [{"name": department, "total": sum(1 for t in tasks if staff_departments.get(t["staff_id"]) == department), "finish": sum(1 for t in tasks if staff_departments.get(t["staff_id"]) == department and t["status"] == "finish")} for department in DEPARTMENTS]
    return {"total_tasks": len(tasks), "counts": counts, "percentages": {k: round(v / total * 100) for k, v in counts.items()}, "completion_rate": round(counts["finish"] / total * 100), "trends": {"daily": daily, "weekly": weekly, "monthly": monthly}, "departments": departments}

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
    if hasattr(app.state, "export_scheduler"): app.state.export_scheduler.cancel()
    client.close()