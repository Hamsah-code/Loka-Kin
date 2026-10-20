# Deploy LOKA-Kin ke Netlify (Frontend) + Render (Backend)

Panduan ini membantu kamu memindahkan **frontend** LOKA-Kin dari GitHub Pages ke **Netlify**, sementara **backend** (FastAPI) tetap di **Render** (gratis, Docker). Arsitektur ini adalah yang paling stabil untuk production karena:

- Netlify = hosting statis tercepat + CDN global + deploy preview per PR
- Render = menjalankan container Python persisten (DB file / MongoDB Atlas)

```
Browser ──► https://loka-kin.netlify.app          (React build dari frontend/build)
        └──► https://loka-kin-api.onrender.com/api (FastAPI, CORS + cookie Secure)
```

> Jika deploy kamu **gagal terus**, langsung buka [`NETLIFY_FIX.md`](NETLIFY_FIX.md) — ada tabel error → solusi + setting UI yang benar.

> Alternatif: jika ingin **tanpa CORS** sama sekali, lihat bagian **E. Mode Proxy** di bawah.

---

## 1. Siapkan Backend (Render) — 5 menit

Backend LOKA-Kin sudah siap di `Dockerfile` + `render.yaml`. Kamu cukup:

1. **Render → New → Blueprint** → pilih repo `Hamsah-code/Loka-Kin` → Approve `render.yaml`
   - Region: **Singapore** (paling dekat ke ID)
   - Plan: **Free**
   - Health check: `/api/` (sudah diatur)
2. Tunggu deploy selesai, catat URL API, contoh: `https://loka-kin-api.onrender.com`
3. Buka **Render → Service → Environment** dan cek variabel ini (sudah ada di `render.yaml`, tapi kamu perlu **tambah Netlify** ke CORS):

| Variabel | Nilai | Wajib? |
|---|---|---|
| `AUTH_COOKIE_SAMESITE` | `none` | ✅ Untuk cross-origin Pages/Netlify |
| `AUTH_COOKIE_SECURE` | `true` | ✅ Wajib saat SameSite=None |
| `CORS_ORIGINS` | `https://loka-kin.netlify.app,https://hamsah-code.github.io` | ✅ Isi **semua origin frontend** dipisah koma. Tambah custom domain jika ada |
| `AUTH_SETUP_SECRET` | *(digenerate Render)* | ✅ Rahasia untuk buat Super Admin pertama — jangan commit |
| `MONGO_URL` | kosong atau `mongodb+srv://...` | Opsional: kosong = file JSON sementara (hilang saat restart), isi Atlas = data permanen |
| `DB_NAME` | `loka_kin` | ✅ |

**Penting:** Jika kamu punya 2 frontend (Pages + Netlify), isi keduanya di `CORS_ORIGINS` dipisah koma. Wildcard `*` **tidak boleh** untuk request berkredensial.

---

## 2. Siapkan Frontend di Netlify — 3 menit

### A. Via Dashboard (paling mudah, direkomendasikan)

1. Login ke [app.netlify.com](https://app.netlify.com) → **Add new site → Import an existing project**
2. Connect ke **GitHub** → pilih `Hamsah-code/Loka-Kin`
3. Netlify akan otomatis deteksi `netlify.toml` di root:
   - **Base directory:** `frontend`
   - **Build command:** `yarn install --frozen-lockfile --network-timeout 900000 && yarn build`
   - **Publish directory:** `frontend/build`
   - Jika tidak terdeteksi, isi manual sesuai di atas
4. Sebelum klik **Deploy**, masuk ke **Site configuration → Environment variables → Add variable**:

| Key | Value | Contoh |
|---|---|---|
| `REACT_APP_BACKEND_URL` | URL API Render kamu | `https://loka-kin-api.onrender.com` |
| `PUBLIC_URL` | `/` | `/` (wajib root, bukan `/Loka-Kin/` seperti GitHub Pages) |
| `CI` | `true` | `true` |
| `GENERATE_SOURCEMAP` | `false` | `false` |

> **Jangan set** `REACT_APP_PREVIEW_TOKEN_FALLBACK` di production! Itu hanya untuk iframe preview Arena.

5. Klik **Deploy site** → tunggu ~2 menit → situs jadi di `https://<random-name>.netlify.app`

6. (Opsional) Ganti domain: **Domain management → Add custom domain** → mis. `loka-kin.netlify.app` atau domain sendiri. Jika ganti domain, **update `CORS_ORIGINS` di Render** lagi.

### B. Via CLI (untuk yang suka terminal)

```bash
# Install CLI sekali
npm i -g netlify-cli

# Login (buka browser)
netlify login

# Dari root repo
netlify init
# → Team: pilih team kamu
# → Site: Create & configure a new site
# → Build command: yarn install --frozen-lockfile --network-timeout 900000 && yarn build
# → Publish: frontend/build
# → Base: frontend

# Set env var backend
netlify env:set REACT_APP_BACKEND_URL https://loka-kin-api.onrender.com
netlify env:set PUBLIC_URL "/"

# Deploy preview (cek dulu)
netlify deploy --build

# Jika OK, deploy production
netlify deploy --build --prod

# Cek log
netlify open:site
```

---

## 3. Konfigurasi Awal Super Admin (sekali saja)

1. Buka `https://loka-kin.netlify.app` → **Masuk → Penyiapan Super Admin pertama**
2. Tempel `AUTH_SETUP_SECRET` (ambil dari **Render → Environment**) + isi Nama + NIP/NIK resmi (16/18 digit)
3. Sistem beri **kode aktivasi 12 digit** (format `XXXX-XXXX-XXXX`, berlaku 24 jam, sekali pakai)
4. Pilih **Aktivasi akun / lupa PIN** → masukkan NIP/NIK + kode + PIN 6 digit baru
5. Login dengan NIP/NIK + PIN baru → kamu akan masuk sebagai **Super Admin**

Di menu **Pengaturan website** (khusus Super Admin) kamu bisa:
- Ubah judul, deskripsi, warna aksen landing page
- Kelola roster: impor CSV (`Nama`, `NIP/NIK`, `Departemen`, `Role`, `Departemen diawasi`)
- Rotasi PIN massal → unduh PDF kredensial (satu kali, tidak disimpan server)

---

## 4. Verifikasi Setelah Deploy

Jalankan di terminal kamu (ganti URL sesuai deploy kamu):

```bash
API=https://loka-kin-api.onrender.com
SITE=https://loka-kin.netlify.app

# API hidup?
curl -i $API/api/  # harus 200

# CORS preflight OK?
curl -i -H "Origin: $SITE" -X OPTIONS $API/api/auth/login \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
# harus 200 + header: access-control-allow-origin: https://loka-kin.netlify.app
# dan access-control-allow-credentials: true

# Landing settings bisa diakses cross-origin?
curl -i -H "Origin: $SITE" $API/api/public/landing-settings

# Cek di browser: buka SITE → Masuk → buat laporan To Do → Doing → Finish
# → tidak terlempar logout → cookie loka_kin_session muncul di DevTools → Application → Cookies
```

Jika login gagal dengan error CORS / cookie tidak set:
- Pastikan `CORS_ORIGINS` di Render mengandung **origin persis** Netlify (https + tanpa trailing slash)
- Pastikan `AUTH_COOKIE_SAMESITE=none` dan `AUTH_COOKIE_SECURE=true`
- Pastikan frontend `REACT_APP_BACKEND_URL` benar (tanpa `/api` di akhir, contoh `https://...onrender.com`)

---

## 5. Mode Proxy (Alternatif Tanpa CORS)

Jika kamu ingin **tidak mengurus CORS sama sekali**, Netlify bisa proxy-kan `/api/*` ke Render. Dengan ini frontend memanggil `/api` relatif (seperti preview satu-origin), sehingga:

- Tidak perlu `REACT_APP_BACKEND_URL` (kosongkan)
- Tidak perlu `CORS_ORIGINS` tambah Netlify
- Cookie bisa tetap `SameSite=lax` (lebih aman)

**Cara aktifkan:**
1. Buka `netlify.toml` → uncomment blok proxy:
   ```toml
   [[redirects]]
     from = "/api/*"
     to = "https://loka-kin-api.onrender.com/api/:splat"
     status = 200
     force = true
   ```
2. Di Netlify env, **kosongkan / hapus** `REACT_APP_BACKEND_URL` (atau set `""`)
3. Di Render env, kamu bisa set `AUTH_COOKIE_SAMESITE=lax` dan `AUTH_COOKIE_SECURE=true` (tetap true karena HTTPS)
4. Redeploy kedua sisi

**Trade-off proxy:** Setiap request API lewat CDN Netlify dulu (latency +1 hop), tapi setup lebih simpel.

---

## 6. Deploy Preview per Pull Request

Netlify otomatis buat **Deploy Preview** untuk tiap PR (jika GitHub integration aktif). Cocok untuk review:

- Setiap push ke branch → Netlify build preview di URL unik `https://deploy-preview-123--loka-kin.netlify.app`
- QA bisa test tanpa ganggu production

Untuk mengaktifkan: **Site configuration → Build & deploy → Deploy previews → Any pull request**.

---

## 7. CI/CD Alternatif: GitHub Actions → Netlify CLI

Jika kamu **tidak** pakai auto-deploy Netlify dari GitHub, kamu bisa pakai GitHub Actions:

File `.github/workflows/netlify.yml` sudah disiapkan (lihat repo). Cara pakai:

1. Di Netlify: **User settings → Applications → New access token** → copy token
2. Di Netlify: **Site → Site configuration → General → Site ID** → copy `Site ID`
3. Di GitHub: **Settings → Secrets and variables → Actions → New repository secret**:
   - `NETLIFY_AUTH_TOKEN` = token dari langkah 1
   - `NETLIFY_SITE_ID` = site ID dari langkah 2
   - `REACT_APP_BACKEND_URL` = URL Render (sebagai **Variable**, bukan Secret: Settings → Variables)
4. Push ke `main` → workflow akan build & deploy ke Netlify otomatis, plus menjalankan `yarn test`

---

## 8. Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| `REACT_APP_BACKEND_URL kosong - frontend akan memanggil /api` | Env var belum diset di Netlify | Site configuration → Environment variables → Add `REACT_APP_BACKEND_URL` → Clear cache and deploy |
| Login berhasil tapi langsung logout / 401 | Cookie terblok browser | Cek `AUTH_COOKIE_SAMESITE=none` + `AUTH_COOKIE_SECURE=true` di Render; pastikan kedua situs HTTPS |
| CORS error: `No 'Access-Control-Allow-Origin'` | Origin Netlify belum di `CORS_ORIGINS` | Tambah `https://<site>.netlify.app` ke `CORS_ORIGINS` (koma-separated), redeploy backend |
| 404 saat refresh `/dashboard` | SPA fallback tidak jalan | Pastikan `frontend/public/_redirects` ada (`/* /index.html 200`) dan `netlify.toml` punya `[[redirects]] from="/*"` |
| Build gagal `yarn: command not found` | Node/Yarn version mismatch | `netlify.toml` sudah set `NODE_VERSION=22`, `YARN_VERSION=1.22.22` — cek log build Netlify |
| Data hilang setelah redeploy Render | `MONGO_URL` kosong | Pasang MongoDB Atlas gratis → isi `MONGO_URL=mongodb+srv://...` di Render, data akan persisten |

---

## 9. Perbandingan Hosting

| Komponen | Opsi A (Rekomendasi) | Opsi B (Full Netlify) | Opsi C (Lama) |
|---|---|---|---|
| **Frontend** | Netlify | Netlify | GitHub Pages |
| **Backend** | Render (Docker) | Render / Fly.io / Railway (Netlify Functions tidak support FastAPI persisten) | Render |
| **Subpath** | `/` (root) | `/` | `/Loka-Kin/` |
| **CORS** | Perlu set `CORS_ORIGINS` | Perlu set `CORS_ORIGINS` | Perlu set `CORS_ORIGINS` |
| **Kelebihan** | Build cepat, preview PR, edge CDN | Sama, tapi backend tetap di luar Netlify | Gratis, tapi build lambat & subpath ribet |

> **Catatan:** Netlify **tidak** bisa menjalankan container Docker FastAPI secara persisten. Jangan coba deploy backend Python langsung ke Netlify. Gunakan Render/Fly/Railway untuk backend.

---

## 10. Checklist Go-Live

- [ ] Backend Render live & `curl $API/api/` 200
- [ ] `CORS_ORIGINS` berisi Netlify URL
- [ ] Netlify env `REACT_APP_BACKEND_URL` terisi
- [ ] Deploy Netlify sukses → buka `https://<site>.netlify.app` tidak 404
- [ ] Buat Super Admin via `AUTH_SETUP_SECRET` → login → buat 1 laporan test
- [ ] Impor roster CSV → cek role & departemen pengawasan
- [ ] Rotasi PIN → unduh PDF → bagikan manual (jangan upload ke repo!)
- [ ] Set custom domain (jika ada) → update `CORS_ORIGINS` lagi

Selamat! LOKA-Kin kamu sekarang live di Netlify 🚀

Butuh bantuan migrasi custom domain atau pasang MongoDB Atlas? Bilang aja, saya bantu sampai hijau semua.
