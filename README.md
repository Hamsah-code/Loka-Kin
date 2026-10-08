# LOKA-Kin

LOKA-Kin adalah aplikasi laporan kinerja harian dengan autentikasi NIP/NIK + PIN, pembagian akses berdasarkan role, dan pemetaan departemen pimpinan.

## Menjalankan aplikasi

Untuk preview lokal, jalankan dari root repository:

```bash
./preview.sh
```

Dashboard memakai `/api` relatif dan proxy development React meneruskan permintaan ke FastAPI. Backend menyimpan data lokal ke `backend/data/loka_kin_db.json` jika `MONGO_URL` tidak dikonfigurasi.

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
- Admin mengelola roster, role, pemetaan departemen, aktivasi/reset, dan seluruh laporan.

Tes otorisasi terisolasi tersedia di `backend/tests/test_auth_access.py`. Tes API integrasi terhadap server aktif pada `backend/tests/backend_test.py` memerlukan `LOKA_TEST_ADMIN_NIP` dan `LOKA_TEST_ADMIN_PIN`.
