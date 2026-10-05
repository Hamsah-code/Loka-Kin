# 🚀 Panduan Deploy Loka-Kin

> **Catatan sandbox:** Environment tempat saya (Coding Agent) bekerja tidak punya akses ke public tunnel (Cloudflare, ngrok, localtunnel semua diblokir). Jadi publikasi tidak bisa dilakukan dari sini — hanya dari mesin lokal Anda.

Ada **3 cara** deploy. Pilih salah satu:

---

## Opsi 1: ⭐ Render.com (Paling Mudah — Gratis)

Render.com support full-stack (backend + static frontend) via Blueprint.

### Langkah

1. **Push ke GitHub** (jika belum):
   ```bash
   cd Loka-Kin
   git add .
   git commit -m "Add deployment config"
   git push origin arena/01a109c3-loka-kin
   ```

2. **Buka https://render.com** → Sign up pakai akun GitHub Anda.

3. Klik **"New +" → "Blueprint"** → pilih repo `Hamsah-code/Loka-Kin`.

4. Render otomatis membaca `render.yaml` di root dan membuat 2 service:
   - `loka-kin-api` (backend FastAPI)
   - `loka-kin-frontend` (static site)

5. Tunggu build selesai (~5-10 menit). URL publik:
   - Frontend: `https://loka-kin-frontend.onrender.com`
   - Backend:  `https://loka-kin-api.onrender.com`
   - API Docs: `https://loka-kin-api.onrender.com/docs`

6. **Penting:** Setelah backend live, edit `render.yaml` → ubah
   `REACT_APP_BACKEND_URL` ke URL backend asli Anda, lalu push ulang.

### Catatan
- Free plan spin-down setelah 15 menit idle (build pertama ~5 menit)
- Data in-memory (mongomock) akan reset tiap restart. Untuk persistent: tambah MongoDB Atlas gratis

---

## Opsi 2: 🐳 Docker (Paling Universal)

### Lokal
```bash
docker build -t loka-kin .
docker run -p 8000:8000 loka-kin
# buka http://localhost:8000
```

### Deploy ke Railway / Fly.io / VPS
- **Railway**: `railway up` setelah `railway login`
- **Fly.io**: `fly launch` lalu `fly deploy`
- **VPS** (DigitalOcean, Linode, dll):
  ```bash
  scp -r . user@server:/app/
  ssh user@server "cd /app && docker build -t loka-kin . && docker run -d -p 80:8000 loka-kin"
  ```
  Lalu arahkan domain Anda ke IP server.

### Catatan
- Image ~300 MB (Python + Node build stages)
- Single container serve FE+BE di port 8000 (sudah di-patch di Dockerfile)

---

## Opsi 3: 🔀 Vercel (Frontend) + Railway/Render (Backend)

### Frontend → Vercel
```bash
cd frontend
npm install -g vercel
vercel --prod
# Vercel otomatis detect React; output di /build
# Set env var REACT_APP_BACKEND_URL=https://<backend-url>
```

### Backend → Railway
1. Buka https://railway.app → "New Project" → "Deploy from GitHub"
2. Pilih repo ini, set root directory: `backend`
3. Tambah env vars: `MONGO_URL=mock`, `DB_NAME=loka_kin`
4. Railway otomatis install `requirements.txt` dan start `uvicorn`

---

## 🗄️ Database (Opsional tapi Disarankan)

Default pakai `mongomock-motor` (in-memory, reset tiap restart).
Untuk data persistent:

1. Buat akun gratis di [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Buat cluster gratis (M0)
3. Set `MONGO_URL=mongodb+srv://USER:PASS@cluster0.xxxx.mongodb.net` di environment

Backend otomatis switch dari mock ke real MongoDB.

---

## 🔒 Keamanan & Data Pribadi

> ⚠️ **PERINGATAN**: Repository ini berisi **data internal rumah sakit**:
> - 78 nama staf asli
> - 9 departemen (termasuk struktur internal)
> - Template tugas/absensi spesifik instansi

**Sangat disarankan** sebelum deploy publik:
1. Ganti data seed di `backend/server.py` (`SEED_STAFF`) dengan dummy data
2. Tambahkan autentikasi (login page) sebelum expose ke internet
3. Atau deploy ke private network / VPN saja

---

## 📁 File yang Ditambahkan untuk Deploy

| File | Fungsi |
|---|---|
| `render.yaml` | Blueprint untuk Render.com (Opsi 1) |
| `railway.toml` | Config untuk Railway.app |
| `Dockerfile` | Universal container (Opsi 2) |
| `Procfile` | Heroku-style fallback |
| `runtime.txt` | Python version pin |
| `frontend/vercel.json` | SPA routing untuk Vercel |
| `DEPLOYMENT.md` | File ini |

Patch kecil di:
- `frontend/craco.config.js` — `allowedHosts: 'all'` untuk preview
- `frontend/package.json` — hapus `@emergentbase/visual-edits` (dep opsional dari URL private)
