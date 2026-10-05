# 🚀 Deploy Loka-Kin ke Vercel + Render (Recommended)

> **Setup terbaik untuk production**: Frontend di Vercel (gratis, cepat, global CDN), Backend di Render (gratis, support Python/FastAPI). Total $0/bulan.

> **Catatan tentang sandbox**: Coding agent tidak bisa deploy langsung karena sandbox memblokir endpoint publik. Anda perlu deploy via dashboard Vercel & Render (proses ~5 menit total).

---

## 📋 Prasyarat

- Akun GitHub (Anda sudah punya, repo: `Hamsah-code/Loka-Kin`)
- Akun Vercel — sign up gratis di https://vercel.com pakai GitHub
- Akun Render — sign up gratis di https://render.com pakai GitHub

---

## Langkah 1: Deploy Backend (Render) — 3 menit

Backend harus live **dulu** karena frontend butuh URL backend.

1. Buka https://dashboard.render.com → klik **"New +"** → **"Blueprint"**
2. Klik **"Connect GitHub"** jika pertama kali, lalu cari repo **Hamsah-code/Loka-Kin**
3. Pilih branch `arena/01a109c3-loka-kin`
4. Render otomatis detect `render.yaml` dan tampilkan 2 service:
   - `loka-kin-api` (web service, Python)
   - `loka-kin-frontend` (static site) — **skip ini dulu**, kita deploy FE ke Vercel
5. Klik **"Apply"**. Tunggu ~5 menit sampai backend status **"Live"**
6. **Copy URL backend** — biasanya `https://loka-kin-api.onrender.com`
7. Buka `https://loka-kin-api.onrender.com/docs` untuk verifikasi API hidup

✅ **Backend live!** Simpan URL-nya.

---

## Langkah 2: Deploy Frontend (Vercel) — 2 menit

1. Buka https://vercel.com/new
2. **"Import Git Repository"** → cari **Hamsah-code/Loka-Kin**
3. Klik **"Import"** → di halaman setup:
   - **Project Name**: `loka-kin` (atau sesuai keinginan)
   - **Framework Preset**: `Create React App` (auto-detect)
   - **Root Directory**: klik "Edit" → isi `frontend`
   - **Build Command**: kosongkan (sudah di vercel.json)
   - **Output Directory**: kosongkan (sudah `build`)
4. Klik **"Environment Variables"** → tambah:
   - Key: `REACT_APP_BACKEND_URL`
   - Value: `https://loka-kin-api.onrender.com` (URL dari Langkah 1)
5. Klik **"Deploy"** → tunggu ~2-3 menit
6. Selesai! Anda dapat URL seperti `https://loka-kin.vercel.app`

✅ **Frontend live!** Coba buka di browser — aplikasi Loka-Kin sudah online untuk seluruh dunia.

---

## Langkah 3: Custom Domain (Opsional)

### Vercel custom domain
1. Di Vercel dashboard → Project → **Settings** → **Domains**
2. Masukkan domain Anda (misal `loka-kin.id`)
3. Ikuti instruksi DNS (tambah A/CNAME record di domain registrar)

### Render custom domain
1. Di Render dashboard → `loka-kin-api` → **Settings** → **Custom Domains**
2. Masukkan `api.loka-kin.id`
3. Ikuti instruksi DNS

---

## 🔄 Auto-Deploy (CI/CD)

Setelah setup di atas, setiap Anda push ke branch `arena/01a109c3-loka-kin`:
- Vercel otomatis rebuild & redeploy FE
- Render otomatis rebuild & redeploy BE

Tidak perlu deploy manual lagi! 🎉

---

## 🔒 WAJIB: Ganti Data Seed (untuk Production)

> ⚠️ **PERINGATAN PENTING**: Backend saat ini berisi **data internal rumah sakit asli**:
> - 78 nama staf (Layanan Medis, Sosial, Admin, dll)
> - 9 departemen spesifik instansi
> - Template tugas/absensi internal

**Sebelum go-live publik**, edit `backend/server.py` → cari `SEED_STAFF` dan ganti dengan dummy:

```python
SEED_STAFF = [
    ("Budi Santoso, A.Md.Kep", "Layanan Medis"),
    ("Siti Aminah, S.Kep", "Layanan Medis"),
    ("Andi Wijaya, S.Sos", "Layanan Sosial"),
    # ... dst dengan nama dummy
]
```

Atau tambahkan **autentikasi login** sebelum expose ke publik.

---

## 🗄️ Database Persistent (Opsional tapi Disarankan)

Default: data in-memory (mongomock) — **reset setiap backend restart**.

Untuk data persistent:
1. Buat akun gratis di https://www.mongodb.com/atlas
2. Buat cluster M0 (512 MB gratis selamanya)
3. Di Render dashboard → `loka-kin-api` → **Environment**:
   - Ubah `MONGO_URL` dari `mock` ke connection string MongoDB Anda
   - Format: `mongodb+srv://USER:PASS@cluster0.xxxx.mongodb.net`
4. Save → Render auto-restart dengan DB real

---

## 📁 File yang Ditambahkan

| File | Fungsi |
|---|---|
| `frontend/vercel.json` | Vercel config (build + SPA routing + cache) |
| `render.yaml` | Render Blueprint (auto-detect di dashboard) |
| `Dockerfile` | Universal container (alternatif deploy) |
| `Procfile`, `runtime.txt` | Heroku-style fallback |
| `railway.toml` | Alternatif Railway.app |
| `DEPLOYMENT.md` | File ini |

Patch minor:
- `frontend/craco.config.js` — `allowedHosts: 'all'` (untuk sandbox preview)
- `frontend/package.json` — hapus `@emergentbase/visual-edits` (dep opsional dari URL private)

---

## 🆘 Troubleshooting

**Q: Vercel build gagal dengan error "ajv"**
A: Sudah diatasi via `--legacy-peer-deps` di `installCommand` di vercel.json.

**Q: Frontend loading tapi data kosong**
A: Pastikan `REACT_APP_BACKEND_URL` di Vercel environment variables benar. Cek CORS di backend (sudah enabled default).

**Q: Backend di Render lambat (free plan)**
A: Free plan spin-down setelah 15 menit idle. First request ~30 detik. Upgrade ke $7/bulan untuk always-on.

**Q: Error 502 dari Render**
A: Cek logs di Render dashboard. Biasanya karena `requirements.txt` ada package yang gagal install. Lihat `DEPLOYMENT.md` (Opsi 1 note).

---

## 🔗 Link Cepat

- Repo: https://github.com/Hamsah-code/Loka-Kin
- Vercel: https://vercel.com/new
- Render: https://dashboard.render.com
- MongoDB Atlas: https://www.mongodb.com/atlas
- API Docs (setelah deploy): `https://loka-kin-api.onrender.com/docs`
