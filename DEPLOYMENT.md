# Mempublikasikan demo LOKA-Kin

Dokumen ini menjelaskan cara memasang **demo yang bisa dibuka orang lain**:

- **frontend** (landing page + dashboard) di **GitHub Pages** — berkas `frontend/build`
  disajikan sebagai situs statis, diperbarui otomatis lewat `.github/workflows/pages.yml`;
- **backend** (FastAPI + otorisasi + penyimpanan) di **Render** — dibangun dari `Dockerfile`,
  konfigurasi siap pakai ada di `render.yaml`.

Keduanya terpisah, jadi ada satu hal yang wajib disetel agar login berhasil dari
origin lain: `CORS_ORIGINS` di API dan `REACT_APP_BACKEND_URL` di frontend.

```
Peramban ──► https://<pengguna>.github.io/Loka-Kin/   (halaman + aset statis)
        └──► https://loka-kin-api.onrender.com/api      (login, laporan, ekspor)
```

## A. GitHub Pages (frontend)

Workflow `Deploy frontend ke GitHub Pages` sudah disiapkan. Yang diperlukan di repo:

1. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. (Opsional) **Settings → Secrets and variables → Actions → Variables → New repository
   variable**, nama `REACT_APP_BACKEND_URL`, isi URL API dari langkah B (contoh
   `https://loka-kin-api.onrender.com`). Tanpa variabel ini, frontend memanggil `/api`
   pada origin-nya sendiri sehingga hanya cocok untuk pratinjau satu origin.
3. Jalankan **Actions → Deploy frontend ke GitHub Pages → Run workflow**.

Situs tampil di `https://<pemilik>.github.io/Loka-Kin/`. Berkas `build/404.html`
ikut dibuat agar tautan dalam tidak menghasilkan 404 khas Pages.

Perintah setara bila lebih suka baris perintah:

```bash
gh api -X POST repos/<pemilik>/<repo>/pages -f build_type=workflow
gh workflow run pages.yml --repo <pemilik>/<repo> --ref main
gh api repos/<pemilik>/<repo>/pages --jq .url
```

## B. API di Render

1. **Render → New → Blueprint**, pilih repo ini, lalu setujui `render.yaml`
   (wilayah Singapore, rencana gratis, `HealthCheckPath=/api/`).
2. Catat URL service, mis. `https://loka-kin-api.onrender.com`.
3. Isi **REACT_APP_BACKEND_URL** seperti di langkah A.2, lalu jalankan ulang workflow.

`render.yaml` menyetel hal yang dibutuhkan konfigurasi dua-origin ini:

| Variabel | Nilai | Alasan |
|---|---|---|
| `AUTH_COOKIE_SAMESITE` | `none` | cookie sesi dibuat di origin API tetapi dipakai dari Pages; tanpa `None` peramban membuang cookie saat login |
| `AUTH_COOKIE_SECURE` | `true` | `SameSite=None` mewajibkan `Secure`; di belakang proxy Render skema bisa terbaca `http` |
| `CORS_ORIGINS` | `https://<pemilik>.github.io` | request berkredensial menolak wildcard; isi daftar origin yang tepat, dipisah koma bila ada custom domain |
| `AUTH_SETUP_SECRET` | digenerasi Render | rahasia satu-kali untuk penyiapan Super Admin pertama; jangan pernah masuk ke repo |
| `MONGO_URL` | kosong / URI Atlas | kosong = snapshot JSON sementara (hilang saat restart/redeploy); isi MongoDB Atlas agar data laporan bertahan |
| `DB_NAME` | `loka_kin` | nama basis data MongoDB |

Alternatif lain: `fly deploy` dengan `Dockerfile` yang sama (jangan lupa menyetel
keenam variabel di atas lewat `fly secrets set` / `fly.toml`), atau VPS kecil dengan
nginx yang menyediakan TLS — `SameSite` boleh dikembalikan ke `lax` bila frontend dan
API disajikan pada domain yang sama.

## C. Menjalankan konfigurasi awal (sekali saja)

1. Buka demo, pilih **Masuk → Penyiapan Super Admin pertama**, tempel
   `AUTH_SETUP_SECRET` (lihat **Render → Service → Environment**) dan NIP/NIK resmi
   pengelola. Sistem menerbitkan kode aktivasi satu kali.
2. Serahkan kode itu ke pemilik akun, lalu gunakan **Aktivasi akun / lupa PIN** untuk
   membuat PIN enam digit.
3. Impor roster melalui **Daftar staf** (CSV berisi `Nama`, `NIP/NIK`, `Departemen`,
   `Role`, `Departemen diawasi`) supaya role, departemen pengawasan, dan penerbitan
   PDF kredensial dapat dipakai. Nomor pemerintah tidak pernah dikarang aplikasi:
   NIP/NIK yang kosong memblokir aktivasi akun dan penerbitan PDF.
4. Terbitkan PIN lewat **Pengaturan website → Kredensial pegawai → Rotasi & unduh
   PDF**, lalu bagikan PDF-nya secara pribadi. PDF tidak disimpan di server.

## D. Pemeriksaan setelah publik

```bash
API=https://loka-kin-api.onrender.com
SITE=https://<pemilik>.github.io

curl -i $API/api/                                            # 200, layanan hidup
curl -i -H "Origin: $SITE" -X OPTIONS $API/api/auth/login \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"          # 200 + allow-origin persis
curl -i -H "Origin: $SITE" $API/api/public/landing-settings  # allow-credentials: true
```

Lalu di peramban: buka situs, **Masuk** dengan akun hasil langkah C, buat satu laporan
(To Do → Doing → Finish), dan pastikan tidak terlempar keluar lagi. Panel
*Application → Cookies* harus menampilkan `loka_kin_session` untuk origin API.

## E. Catatan keamanan untuk demo publik

- Demo memakai roster berisi **nama pegawai nyata**; jangan bagikan PDF kredensial
  maupun tangkaran `AUTH_SETUP_SECRET` di kanal publik.
- **Jangan** menyalakan `AUTH_PREVIEW_TOKEN_FALLBACK` (API) atau
  `REACT_APP_PREVIEW_TOKEN_FALLBACK` (frontend) pada deployment publik. Keduanya
  membuka jalur token di URL/JSON yang hanya ditujukan untuk iframe pratinjau Arena;
  publik cukup cookie `HttpOnly`.
- Data pada rencana gratis Render tanpa `MONGO_URL` bersifat sementara: setiap
  restart/redeploy kembali ke roster bawaan. Untuk demo yang datanya bertahan,
  hubungkan MongoDB Atlas (tier gratis) lewat `MONGO_URL`.
- Perluas `CORS_ORIGINS` bila menambah custom domain, dan jaga HTTPS di kedua sisi
  karena cookie sesi bersifat `Secure`.
