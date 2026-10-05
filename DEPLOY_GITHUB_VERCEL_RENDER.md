# 🚀 Panduan Deploy Loka-Kin via GitHub (Vercel + Render)

Panduan step-by-step dari **nol sampai live** dalam **±10 menit**. Cocok untuk pemula.

> **TL;DR**: Code sudah di-push ke GitHub. Tinggal klik-klik di dashboard Vercel & Render → aplikasi langsung online.

---

## 📍 Peta Rute Deploy

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Source Code     │      │   GitHub Repo    │      │  Live URLs       │
│  (Loka-Kin)      │ ───▶ │  Hamsah-code/    │ ───▶ │  Vercel + Render │
│                  │ push │  Loka-Kin        │ auto │                  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
                                  ▲                         ▲
                                  │                         │
                            [sudah ✓]              deploy dari sini
```

✅ Code sudah di branch `arena/01a109c3-loka-kin` di GitHub
⬜ Anda tinggal setup deploy

---

## 🎯 Yang Akan Anda Dapat Setelah Selesai

| Service | Platform | URL | Fungsi |
|---|---|---|---|
| Frontend | Vercel | `https://loka-kin-xxxxx.vercel.app` | UI aplikasi |
| Backend | Render | `https://loka-kin-api.onrender.com` | API FastAPI |
| API Docs | Render | `https://loka-kin-api.onrender.com/docs` | Swagger UI |
| Database | (in-memory) | - | Reset tiap restart |

**Total biaya: $0/bulan** (free tier).

---

# 📋 LANGKAH 1: Deploy Backend ke Render (3-5 menit)

## 1.1 — Buka Halaman Deploy Render

Klik link ini (sudah pre-filled):

**→ https://dashboard.render.com/select-repo?type=blueprint**

Atau manual:
1. Buka https://render.com
2. Klik **"Get Started for Free"** atau **"Sign In"**
3. Sign in pakai **GitHub** (recommended)

## 1.2 — Hubungkan GitHub ke Render

Jika baru pertama kali:
1. Render akan minta izin akses GitHub
2. Klik **"Authorize Render"**
3. Pilih **"All repositories"** atau pilih repo `Hamsah-code/Loka-Kin` saja
4. Klik **"Install & Authorize"**

## 1.3 — Pilih Repo & Blueprint

1. Di dropdown repo, cari dan pilih **Hamsah-code/Loka-Kin**
2. Render otomatis detect `render.yaml` di root
3. Klik **"Apply"**

## 1.4 — Tunggu Build Selesai

- Render akan membuat 2 services:
  - `loka-kin-api` (Python web service) ← **yang kita butuhkan**
  - `loka-kin-frontend` (static site) ← **kita abaikan, deploy FE ke Vercel**
- Klik **"loka-kin-api"** untuk lihat progress build
- Build memakan waktu **±3-5 menit** (pertama kali, install dependencies)
- Status akan berubah: `Building` → `Live` (hijau)

## 1.5 — Salin URL Backend

Setelah status **"Live"** (hijau):
1. Copy URL di pojok kiri atas, biasanya: `https://loka-kin-api.onrender.com`
2. **SIMPAN URL INI** — dipakai untuk Step 2

## 1.6 — Test API Hidup

Buka di tab baru:
- `https://loka-kin-api.onrender.com/docs` → harusnya muncul halaman Swagger UI
- `https://loka-kin-api.onrender.com/api/staff` → harusnya muncul JSON list 78 staf

Kalau keduanya OK, **backend sudah live!** ✅ Lanjut Step 2.

### ❓ Troubleshooting Step 1

**Build gagal "ERROR: No matching distribution for emergentintegrations"**
→ Sudah diatasi: `emergentintegrations` tidak dipakai di server.py, sudah saya skip.

**Build gagal "Address already in use" atau "Port already allocated"**
→ Normal di free tier. Render otomatis retry. Tunggu sebentar.

**Status "Live" tapi `/docs` 404**
→ Tunggu 30 detik, kadang proxy butuh waktu propagate.

**Status stuck di "Building" > 10 menit**
→ Klik "Manual Deploy" → "Clear build cache & deploy".

---

# 📋 LANGKAH 2: Deploy Frontend ke Vercel (2-3 menit)

## 2.1 — Buka Halaman Import Vercel

Klik link ini (langsung ke import page):

**→ https://vercel.com/new**

Atau manual:
1. Buka https://vercel.com
2. Sign in pakai **GitHub** (recommended)
3. Klik **"Add New..."** → **"Project"**

## 2.2 — Pilih Repo

1. Cari dan klik **"Hamsah-code/Loka-Kin"** di list
2. Klik **"Import"**

## 2.3 — Konfigurasi Project

Di halaman setup, isi/ubah field berikut:

| Field | Isi |
|---|---|
| **Project Name** | `loka-kin` (atau nama lain) |
| **Framework Preset** | `Create React App` (auto-detect, jangan ubah) |
| **Root Directory** | klik "Edit" → ubah jadi `frontend` ← **PENTING!** |
| **Build Command** | (kosongkan, sudah di vercel.json) |
| **Output Directory** | (kosongkan, sudah `build`) |
| **Install Command** | (kosongkan, sudah di vercel.json) |

⚠️ **WAJIB**: `Root Directory` harus `frontend` (bukan root repo). Kalau lupa, build akan error "Cannot find package.json".

## 2.4 — Tambah Environment Variable

Klik section **"Environment Variables"**, lalu isi:

| Key | Value |
|---|---|
| `REACT_APP_BACKEND_URL` | `https://loka-kin-api.onrender.com` |

⚠️ Ganti value dengan URL backend Anda yang Anda copy di Step 1.5.
- **JANGAN** tambahkan trailing slash
- **JANGAN** tambahkan `/api` di akhir (sudah ditambah otomatis di code)

## 2.5 — Klik Deploy

1. Klik tombol **"Deploy"** (besar, di bawah)
2. Tunggu **±2-3 menit** (build React production)
3. Lihat log real-time di panel
4. Kalau berhasil, akan muncul **"🎉 Congratulations!"** dengan confetti

## 2.6 — Salin URL Frontend

URL frontend akan muncul seperti:
- `https://loka-kin.vercel.app` atau
- `https://loka-kin-xxxxx.vercel.app`

**SIMPAN URL INI** — ini URL publik yang bisa dishare ke siapa saja! 🎉

## 2.7 — Test Aplikasi Live

Buka URL Vercel di browser:
- Halaman utama harus muncul dengan logo/navbar Loka-Kin
- Coba klik menu → seharusnya navigasi berfungsi
- Tab **"Staf"** → harusnya muncul 78 nama (data dari backend Render)
- Buka **DevTools → Network** → cek request ke `loka-kin-api.onrender.com` harusnya 200 OK

✅ **Aplikasi live untuk seluruh dunia!**

### ❓ Troubleshooting Step 2

**Build error "Cannot find module 'ajv/dist/compile/codegen'"**
→ Sudah diatasi: `ajv@8.20.0` di-install via vercel.json `installCommand` dengan `--legacy-peer-deps`.

**Build error "Module not found: Can't resolve '@/...'"**
→ Path alias `@/` di `craco.config.js` belum kompatibel. Hubungi agent untuk fix.

**Halaman Vercel loading tapi data kosong / "Network Error"**
→ Cek environment variable `REACT_APP_BACKEND_URL`:
  1. Vercel dashboard → Project → **Settings** → **Environment Variables**
  2. Pastikan value sama persis dengan URL Render
  3. Klik **"..."** → **"Redeploy"** (env vars tidak auto-apply ke deployment yang sudah running)

**CORS error di browser console**
→ Backend sudah enable CORS untuk `*`. Kalau masih error, share screenshot.

---

# 📋 LANGKAH 3 (Opsional): Setup Auto-Deploy

Setelah Step 1 & 2, setiap Anda push code ke branch `arena/01a109c3-loka-kin`:
- ✅ Vercel otomatis rebuild & redeploy FE
- ✅ Render otomatis rebuild & redeploy BE

Tidak perlu setup tambahan! Ini sudah otomatis begitu repo di-connect.

### Test Auto-Deploy

1. Edit file apapun di repo (misal README.md)
2. Commit & push ke branch
3. Cek Vercel dashboard → tab **"Deployments"** → akan muncul deployment baru otomatis
4. Cek Render dashboard → `loka-kin-api` → tab **"Events"** → akan muncul deploy baru

---

# 📋 LANGKAH 4 (Opsional): Custom Domain

## Custom Domain untuk Vercel (Frontend)

1. Beli domain di Namecheap / Cloudflare / Google Domains (contoh: `loka-kin.id`)
2. Di Vercel → Project → **Settings** → **Domains**
3. Masukkan domain Anda (misal `loka-kin.id` dan `www.loka-kin.id`)
4. Vercel akan kasih instruksi DNS. Tambahkan di domain registrar:
   ```
   Type: A
   Name: @
   Value: 76.76.21.21

   Type: CNAME
   Name: www
   Value: cname.vercel-dns.com
   ```
5. Tunggu 5-30 menit propagasi DNS
6. ✅ Aplikasi live di `https://loka-kin.id`

## Custom Domain untuk Render (Backend)

1. Render → `loka-kin-api` → **Settings** → **Custom Domains**
2. Masukkan `api.loka-kin.id`
3. Ikuti instruksi DNS (CNAME record)
4. Update env var di Vercel: `REACT_APP_BACKEND_URL` → `https://api.loka-kin.id`
5. Redeploy Vercel

---

# 📋 LANGKAH 5 (PENTING untuk Production): Ganti Data Seed

> ⚠️ **WAJIB sebelum share URL ke publik!**

Repository ini berisi **78 nama staf ASLI rumah sakit** + struktur departemen. Sebelum publish publik:

## Opsi A: Ganti dengan Data Dummy

Edit `backend/server.py` → cari `SEED_STAFF = [`:

```python
SEED_STAFF = [
    ("Budi Santoso, A.Md.Kep", "Layanan Medis"),
    ("Siti Aminah, S.Kep", "Layanan Sosial"),
    # ... (78 baris nama dummy)
]
```

Ganti dengan nama-nama dummy fiktif.

## Opsi B: Tambah Autentikasi

Tambah halaman login sebelum app bisa diakses. Butuh effort beberapa jam.

## Opsi C: Deploy ke Private Network Saja

Jangan share URL publik. Hanya untuk demo internal via VPN.

---

# 🆘 Bantuan Lebih Lanjut

Kalau stuck di langkah manapun, kasih tahu saya:
1. Di langkah berapa Anda stuck
2. Screenshot atau copy-paste error message
3. URL dashboard Vercel/Render Anda

Saya akan bantu troubleshoot.

---

# 🔗 Link Cepat (Bookmark)

| Tautan | Fungsi |
|---|---|
| https://github.com/Hamsah-code/Loka-Kin | Source code |
| https://vercel.com/new | Import project ke Vercel |
| https://dashboard.render.com | Manage Render services |
| https://loka-kin-api.onrender.com/docs | API docs (setelah deploy) |

---

**Estimasi total waktu: 5-10 menit**
**Biaya: $0/bulan (free tier)**
**Setelah selesai: Aplikasi Loka-Kin live untuk seluruh dunia! 🌍**
