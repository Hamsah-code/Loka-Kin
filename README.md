# LOKA-Kin

LOKA-Kin adalah aplikasi laporan kinerja harian dengan autentikasi NIP/NIK + PIN, pembagian akses berdasarkan role, dan pemetaan departemen pimpinan.

## Menjalankan aplikasi

Untuk preview lokal, jalankan dari root repository:

```bash
./preview.sh
```

Dashboard memakai `/api` relatif dan proxy development React meneruskan permintaan ke FastAPI. Backend menyimpan data lokal ke `backend/data/loka_kin_db.json` jika `MONGO_URL` tidak dikonfigurasi.

## Publikasi demo

Landing page dan dashboard dapat diterbitkan sebagai situs publik (frontend di GitHub
Pages, API di Render) dan konfigurasi siap pakainya sudah ada di repo: lihat
[`DEPLOYMENT.md`](DEPLOYMENT.md) untuk `Dockerfile`, `render.yaml`, workflow
`.github/workflows/pages.yml`, pasangan variabel yang wajib disetel
(`CORS_ORIGINS`, `AUTH_COOKIE_SAMESITE`, `REACT_APP_BACKEND_URL`), serta pemeriksaan
setelah publik.

## Aktivasi Admin pertama

Admin pertama harus sudah tercantum di roster, dengan role `Admin`, NIP/NIK yang valid, dan departemen. Pemilik sistem menerbitkan kode aktivasi awal melalui alur penyiapan yang dilindungi `AUTH_SETUP_SECRET`:

1. Buat secret penyiapan di lingkungan server (jangan commit atau membagikannya):
   ```bash
   export AUTH_SETUP_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
   ```
2. Buka aplikasi, pilih **Masuk → Penyiapan Admin pertama**. Masukkan secret tersebut dan NIP/NIK Admin.
3. Bila roster belum dimuat, unggah CSV dengan kolom `Nama`, `NIP/NIK`, `Departemen`, `Role`, dan `Departemen diawasi` (opsional untuk staf biasa). Pastikan baris Admin memakai role `Admin`. Nilai role yang didukung: `Staf`, `Admin`, `Ketua Tim`, `Clinical Supervisor`, dan `Kepala`. Beberapa departemen pengawasan dapat dipisahkan dengan titik koma.
4. Serahkan kode aktivasi sekali pakai yang ditampilkan langsung kepada Admin. Admin memilih **Aktivasi akun / lupa PIN**, lalu membuat PIN enam digit sendiri dan masuk.

Jangan masukkan PIN ke spreadsheet. Kode aktivasi berlaku 24 jam dan hanya ditampilkan saat diterbitkan. Penerbitan ulang kode akan mencabut sesi dan PIN sebelumnya. PIN disimpan sebagai hash PBKDF2 dan tidak dapat dibaca Admin. Untuk deployment HTTPS di belakang proxy, cookie sesi secara otomatis memakai `Secure` berdasarkan skema request; atur `AUTH_COOKIE_SECURE=true` bila konfigurasi proxy Anda memerlukannya. Jika frontend dan API berada pada origin berbeda, isi `CORS_ORIGINS` dengan daftar origin frontend yang tepat (dipisahkan koma); wildcard tidak diizinkan untuk request berkredensial.

## Akses laporan

- Staf hanya dapat membaca dan mengelola laporan akun sendiri; API mengikat `staff_id` ke sesi pengguna.
- Ketua Tim, Clinical Supervisor, dan Kepala dapat membaca seluruh laporan, tetapi hanya dapat membuat atau mengubah laporan di departemen yang ditetapkan Admin.
- Laporan `Finish` terkunci untuk Staf dan pimpinan. Admin dapat melakukan koreksi.
- Ekspor PDF/Excel mengikuti peran: Staf langsung diekspor untuk laporan akunnya sendiri tanpa memilih staf, sedangkan Admin, Ketua Tim, Clinical Supervisor, dan Kepala dapat memilih seluruh staf atau satu staf untuk pemantauan.
- Admin mengelola roster, role, pemetaan departemen, aktivasi/reset, dan seluruh laporan.

Tes otorisasi terisolasi tersedia di `backend/tests/test_auth_access.py`. Tes API integrasi terhadap server aktif pada `backend/tests/backend_test.py` memerlukan `LOKA_TEST_ADMIN_NIP` dan `LOKA_TEST_ADMIN_PIN`.

## Super Admin dan pengelolaan website

- Siapkan `AUTH_SETUP_SECRET` hanya di environment server (gunakan nilai acak kuat; jangan commit atau bagikan lewat kanal umum).
- Pada halaman Masuk pilih **Penyiapan Super Admin pertama**, lalu masukkan nama, **NIP/NIK resmi**, dan secret tersebut. Sistem menerbitkan kode aktivasi satu kali; pemilik akun menggunakannya untuk menetapkan PIN pribadi.
- Super Admin mendapat menu **Pengaturan website** untuk mengubah judul, teks, navigasi, visibilitas bagian landing page, dan warna aksen. Perubahan tersimpan di database dan langsung digunakan oleh landing page.
- Akun staf tetap dapat masuk untuk laporan sesuai perannya. Hanya role **Super Admin** yang dapat mengubah landing page atau mengunduh daftar PIN sementara.

## PDF kredensial pegawai

Sebelum menerbitkan PDF, impor roster berisi **NIP/NIK resmi** melalui menu **Daftar staf**. Aplikasi tidak mengarang nomor pemerintah; NIP/NIK yang kosong, duplikat, atau placeholder demo akan memblokir penerbitan.

Di **Pengaturan website → Kredensial pegawai**, tombol **Rotasi & unduh PDF** menerbitkan PIN sementara acak untuk semua pegawai aktif (kecuali akun Super Admin), mencabut sesi lama, lalu mengunduh PDF satu kali yang memuat NIP/NIK, PIN sementara, dan status akun. Operasi ini **mereset seluruh PIN pegawai**; PIN lama tidak dapat ditampilkan karena hanya tersimpan sebagai hash. Pegawai wajib mengganti PIN sementara saat login pertama. PDF tidak disimpan ulang di server dan harus dibagikan secara pribadi.

## Sesi pada preview iframe

`./preview.sh` mengaktifkan `AUTH_PREVIEW_TOKEN_FALLBACK=true` untuk API dan
`REACT_APP_PREVIEW_TOKEN_FALLBACK=true` untuk kedua frontend preview (port 3000
serta build statis di port 8000). Token disimpan per tab, bukan sebagai sesi
bersama di server. Token Bearer yang dikirim eksplisit mengungguli cookie lama;
logout mencabut token tersebut. Bila penyimpanan iframe diblokir, sesi dapat
berjalan di memori tab tetapi perlu login ulang setelah reload.

Karena gateway di depan preview dapat membuang header `Authorization` sekaligus
menolak cookie pihak ketiga, klien juga mengirim token yang sama sebagai
`?access_token=` pada permintaan `/api`. Saluran ini hanya diterima API selama
`AUTH_PREVIEW_TOKEN_FALLBACK=true`; token query yang tidak valid tidak jatuh
balik ke cookie (gagal tertutup). Respons dengan token di URL selalu diberi
`Cache-Control: no-store`, log akses uvicorn dimatikan pada `serve`, dan
`.preview/requests.log` hanya mencatat keberadaan token, tidak pernah nilainya.

**Jangan aktifkan kedua flag ini pada deployment produksi.** Build produksi
biasa menggunakan cookie HttpOnly dan tidak menerima token dalam respons login.
Setelah pembaruan preview, tutup tab lama dan buka ulang preview untuk memuat
bundle terbaru. Tidak perlu mengubah PIN atau mengaktifkan ulang Super Admin.

Pemeriksaan regresi:

```bash
./.venv/bin/python -m pytest backend/tests/test_auth_access.py -q
(cd frontend && CI=true yarn test --watchAll=false --runInBand)
```

Tes integrasi `backend/tests/backend_test.py` mengubah roster dan laporan.
Jalankan **hanya terhadap server dengan database pengujian terpisah**, bukan
preview berisi data pegawai asli. Akun Super Admin tidak boleh dinonaktifkan
atau diturunkan perannya oleh impor/reset roster; perubahan akun dilakukan
melalui pengelolaan akun dengan pemeriksaan hak akses.
