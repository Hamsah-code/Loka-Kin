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

## Analitik kinerja per bagian

Menu **Analitik** diringkas menjadi tiga bagian: **Umum**, **Medis**, dan **Sosial**
(tab per bagian). Setiap bagian menampilkan *Completion Rate*, *Workflow
Breakdown*, *Tren Produktivitas* (harian/mingguan/bulanan), dan *Indikator Kinerja
& Standar Mutu* yang kini hanya berisi tiga indikator berbasis data laporan nyata:

| Kode | Indikator | Realisasi |
|---|---|---|
| KPI-xx-01 | Laporan Kinerja Harian | staf yang mengisi laporan ÷ staf aktif unit |
| KPI-xx-02 | Status Penyelesaian Laporan | laporan `Finish` ÷ seluruh laporan unit |
| KPI-xx-03 | Ketepatan Tenggat Waktu | selesai ≤ tenggat (dan laporan belum selesai yang sudah lewat tenggat dihitung terlambat) |

Standar mutu ketiga indikator: **95%** (dapat diubah lewat `ANALYTICS_INDICATOR_TARGET`
di `backend/server.py`). Indikator tanpa data ditampilkan sebagai *Belum Ada Data*
dan tidak menurunkan skor bagian (bobot dinormalisasi).

Pemetaan sebagian: **Umum** = Umum, Admin, Bendahara, Perencanaan, Informasi dan
Humas, Sarana & Prasarana; **Medis** = Layanan Rehabilitasi Medis; **Sosial** =
Layanan Rehabilitasi Sosial. Departemen *Clinical Supervisor* tidak ditampilkan
pada analitik (tetap ada di roster dan pengelolaan staf). Kunci `departments`
pada `/api/analytics` tetap dikirim (9 departemen) untuk kompatibilitas, sedangkan
UI memakai `sections`/`unit_groups`.

## Clustering akun & penyeragaman PIN

### Memperbarui roster staf dari berkas clustering

Berkas "Isi Peran" yang sudah diperbarui dapat dipakai untuk **mengganti seluruh
daftar staf resmi** tanpa mengubah kode:

```bash
# server pratinjau harus berjalan (endpoint /api/admin/clustering/sync-roster)
python scripts/clustering.py sync Clustering-Akun-LokaKin.xlsx --dry-run   # pratinjau
python scripts/clustering.py sync Clustering-Akun-LokaKin.xlsx             # terapkan
```

Alur di server: berkas dibaca (`.xlsx`/`.csv`, pemisah `;` atau `,`, pengodean
Windows-1252/UTF-8) → peran diterjemahkan (Kepala Loka/Clinical Supervisor/Ketua
Tim/Staf) → departemen dinormalisasi (mis. "Layanan Umum" → `Umum`) → roster
resmi diimpor mode `replace` → seluruh akun roster diaktifkan dengan PIN seragam
`123456`. **Akun Super Admin terpisah tidak pernah diubah.** Staf yang tidak ada
pada berkas diarsipkan (bukan dihapus) agar riwayat laporan tetap terhubung, dan
NIP/NIK yang bukan 16/18 digit disimpan kosong serta dilaporkan agar dibetulkan
(akun tetap ada, hanya belum bisa login).


`scripts/clustering.py` menyiapkan data akun untuk clustering peran (Staf, Ketua
Tim, Clinical Supervisor, Kepala Loka, Super Admin) sekaligus menyeragamkan PIN
pratinjau. Semua perintah membaca/menulis snapshot mode `local-json`
(`backend/data/loka_kin_db.json`), jadi hentikan server lebih dulu.

```bash
# 1. Buat berkas isian peran (78 akun + blok Super Admin terpisah)
python scripts/clustering.py template          # -> Clustering-Akun-LokaKin.xlsx

# 2. Seragamkan PIN + aktifkan seluruh akun roster (peran tidak berubah)
python scripts/clustering.py pin --pin 123456

# 3. Terapkan peran hasil pengisian berkas Excel (+ PIN seragam)
python scripts/clustering.py apply Clustering-Akun-LokaKin.xlsx

# 4. Periksa matriks cluster peran x departemen
python scripts/clustering.py report
```

Format yang sama juga dapat diunduh langsung dari aplikasi tanpa terminal: masuk
sebagai Super Admin lalu buka **Pengaturan website → Clustering akun**. Tombol
Tombol *Unduh Excel*, *Unduh CSV*, *Unduh PDF*, dan *Cetak / HTML* memakai
endpoint terproteksi
`/api/admin/clustering/{summary,template.xlsx,template.csv,template.pdf,template.html}`
sehingga isinya selalu mengikuti data akun terbaru. PDF dan halaman cetak
memakai tata letak A4 lanskap (akun + matriks cluster); halaman HTML dapat
disimpan sebagai PDF dari dialog cetak peramban.

Berkas yang sudah diisi dapat **diunggah kembali dari aplikasi**: tab *Clustering
akun* → tombol **Terapkan berkas** (menerima `.xlsx`/`.xlsm`/`.csv`). Endpoint
`POST /api/admin/clustering/apply` memvalidasi isi berkas lebih dulu; bila ada
baris dengan dua peran, NIP/NIK tidak valid, atau NIP/NIK duplikat, tidak ada
perubahan yang disimpan dan daftar masalah dikembalikan ke layar. Bila valid,
peran + NIP/NIK + departemen diawasi + PIN seragam diterapkan, seluruh sesi
login dicabut, dan ringkasan perubahan dicatat di `audit_logs`
(`event: clustering_roles_applied`, tanpa nilai PIN).

Berkas Excel berisi empat sheet: **Isi Peran** (satu kolom per peran, diisi angka
`1`; kolom peran sudah terisi otomatis dari database), **Snapshot Database**,
**Matriks Cluster**, dan **Panduan** (kode peran, hak akses, daftar departemen
resmi). Blok *Super Admin terpisah* di bawah tabel membuat akun `super-admin`
yang tidak termasuk 78 akun roster; identitas awalnya ditandai placeholder agar
tidak dipakai pada PDF kredensial.

Ketentuan yang divalidasi sebelum menulis: tepat satu peran per baris,
NIP/NIK 16 atau 18 digit dan tidak duplikat, serta departemen diawasi untuk peran
pimpinan. Setiap `pin`/`apply` mencadangkan snapshot ke
`loka_kin_db.backup-<waktu>.json` dan mencabut sesi login lama. Login memakai
NIP/NIK, sehingga akun tanpa NIP/NIK tetap belum dapat dipakai clustering —
lengkapi kolom D pada sheet *Isi Peran*.

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
