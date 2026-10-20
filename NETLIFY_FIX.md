# FIX: Deploy Netlify Gagal — Solusi Lengkap

Dokumen ini khusus untuk kasus **"saya coba deploy sendiri selalu gagal"**. Ikuti 3 langkah di bawah — 95% gagal netlify karena salah satu dari ini.

---

## Langkah 0: Cek Error Sebenarnya (1 menit)

Buka **Netlify → Site → Deploys → klik deploy yang gagal → Deploy log**. Copy 20 baris terakhir yang merah. Cocokkan dengan tabel di bawah:

| Pesan error di log | Penyebab | Solusi |
|---|---|---|
| `Failed during stage 'building site': Build script returned non-zero exit code: 2` + `yarn: command not found` | Node/Yarn version tidak diset | Sudah di-fix di `netlify.toml` baru kami (`NODE_VERSION=22`, `YARN_VERSION=1.22.22`). Pastikan di Netlify UI kamu **tidak override** Node version ke 16/18. |
| `error Your lockfile needs to be updated` atau `frozen-lockfile` | `yarn.lock` tidak cocok dengan `package.json` | Di Netlify UI → Build → Build command → ubah jadi `yarn install --network-timeout 900000 && yarn build` (tanpa `--frozen-lockfile`) **sementara**, deploy sekali, lalu kembalikan. Atau jalankan `cd frontend && yarn install` lokal & commit `yarn.lock` baru. |
| `Treating warnings as errors because process.env.CI = true` + eslint fail | CI=true membuat warning jadi error | Di `netlify.toml` sudah ada `CI=true` tapi build lokal kami **lolos**. Jika kamu tetap gagal, di Netlify UI → Env vars → set `CI` = `false` sementara, deploy, lalu fix warning di kode. |
| `JavaScript heap out of memory` | Netlify free kehabisan RAM saat build CRA | Sudah di-fix: `NODE_OPTIONS=--max-old-space-size=4096` di `netlify.toml` baru. |
| `Publish directory does not exist: "build"` atau `frontend/build` | Salah set Base/Publish directory di UI | Lihat Langkah 1 di bawah — harus **Base: `frontend`**, **Publish: `build`** (bukan `frontend/build` jika base sudah `frontend`). |
| `Page not found` setelah deploy sukses (bukan build gagal) | SPA fallback belum | Pastikan `frontend/public/_redirects` ada (sudah kami tambahkan). Redeploy. |
| `Failed to load config "react-app" to extend from` | Cache Netlify usang | Netlify → Deploys → **Trigger deploy → Clear cache and deploy site** |

> Jika tidak ada di tabel, copy log-mu ke saya — saya baca dan fix langsung.

---

## Langkah 1: Setting UI Netlify yang Benar (WAJIB sesuai, jangan asal)

Masuk **Netlify → Site configuration → Build & deploy → Continuous deployment → Build settings → Edit configuration**

Isi **persis** ini (jangan pakai NPM, jangan pakai pnpm):

- **Base directory:** `frontend`
- **Build command:** `yarn install --frozen-lockfile --network-timeout 900000 && yarn build`
  - Jika masih gagal dengan frozen-lockfile, ganti jadi `yarn install --network-timeout 900000 && yarn build`
- **Publish directory:** `build`
  - **SALAH:** `frontend/build` (akan jadi `frontend/frontend/build`)
  - **SALAH:** `dist` / `public`
  - **BENAR:** `build` (karena Base sudah `frontend`)

**Biarkan kosong** (jangan override) jika kamu sudah pakai `netlify.toml` dari repo — Netlify akan otomatis pakai setting dari file. Cek **"Build settings from netlify.toml"** muncul di log.

Klik **Save**.

---

## Langkah 2: Environment Variables (jangan skip)

**Site configuration → Environment variables → Add variable**

| Key | Value | Catatan |
|---|---|---|
| `REACT_APP_BACKEND_URL` | `https://loka-kin-api.onrender.com` | Ganti dengan URL Render kamu. **Tanpa** `/api` di akhir. Jika backend belum siap, isi `https://loka-kin-api.onrender.com` placeholder dulu — build tetap sukses. |
| `PUBLIC_URL` | `/` | Wajib `/` (Netlify root). Bukan `/Loka-Kin/` (itu untuk GitHub Pages) |
| `NODE_VERSION` | `22` | Atau biarkan, sudah di `netlify.toml` |
| `YARN_VERSION` | `1.22.22` | Atau biarkan |

**Jangan set:**
- `REACT_APP_PREVIEW_TOKEN_FALLBACK` → harus kosong di production
- `AUTH_PREVIEW_TOKEN_FALLBACK` → hanya untuk preview lokal

Klik **Save** → **Trigger deploy → Clear cache and deploy site**

---

## Langkah 3: Backend CORS (biar login tidak gagal setelah deploy sukses)

Frontend Netlify & backend Render beda origin, jadi backend harus izinkan Netlify:

**Render → Service → Environment → Add:**

```
CORS_ORIGINS=https://<nama-site>.netlify.app
AUTH_COOKIE_SAMESITE=none
AUTH_COOKIE_SECURE=true
```

Jika kamu punya 2 frontend (Pages + Netlify):

```
CORS_ORIGINS=https://hamsah-code.github.io,https://loka-kin.netlify.app
```

Redeploy backend (Render auto-redeploy saat env berubah).

Verifikasi:

```bash
API=https://loka-kin-api.onrender.com
SITE=https://loka-kin.netlify.app

curl -i -H "Origin: $SITE" -X OPTIONS $API/api/auth/login \
  -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type"
# harus 200 + access-control-allow-origin: https://loka-kin.netlify.app
```

---

## Alternatif: Deploy Tanpa Netlify UI (CLI, 100% work)

Jika UI terus gagal, pakai CLI dari laptop kamu (lebih stabil):

```bash
npm i -g netlify-cli
netlify login                    # buka browser, login

cd /path/to/Loka-Kin
netlify init                     # pilih Create & configure new site → Team → Site name
netlify env:set REACT_APP_BACKEND_URL https://loka-kin-api.onrender.com
netlify env:set PUBLIC_URL "/"

netlify deploy --build           # preview di https://<random>--<site>.netlify.app
# cek preview OK?

netlify deploy --build --prod    # publish ke https://<site>.netlify.app
```

---

## Tes Lokal Meniru Netlify (sebelum push)

Jalankan di repo kamu:

```bash
./scripts/netlify-build.sh
# atau manual:
cd frontend
CI=true GENERATE_SOURCEMAP=false PUBLIC_URL="/" REACT_APP_BACKEND_URL="https://loka-kin-api.onrender.com" yarn build
```

Harus **Compiled successfully** seperti ini:

```
File sizes after gzip:
  127.25 kB  build/static/js/main.087b8905.js
  24.99 kB   build/static/css/main.6fbc733e.css
Done in 8-12s.
```

Jika lokal lolos tapi Netlify gagal → pasti setting UI salah (Langkah 1).

---

## Bantuan Cepat

1. **Screenshot / copy 20 baris log merah** Netlify kamu → paste ke chat → saya kasih fix exact line
2. **Sebutkan:** Deploy via GitHub connect atau drag-and-drop?
3. **Sebutkan:** Base / Build / Publish yang kamu isi di UI

Saya akan update repo & netlify.toml sampai deploy kamu hijau.

