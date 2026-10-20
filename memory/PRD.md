# PRD — LOKA-Kin

## Pernyataan Masalah
LOKA-Kin adalah website laporan kinerja harian untuk staf Loka Rehabilitasi Narkotika Kalianda dengan alur Plan, Doing, dan Finish. Sistem menampilkan grafik, persentase kinerja, ekspor Excel/PDF berperiode, dan simulasi ekspor Google Sheets pada pukul 21.00 WIB.

## Keputusan Arsitektur
- React + Tailwind-compatible CSS untuk dashboard responsif, dengan Lucide dan Sonner untuk interaksi.
- FastAPI + MongoDB untuk data staf, laporan, analitik, dan endpoint ekspor.
- Dashboard demo tanpa login; data awal 78 staf resmi dari `DAFTAR HADIR STAF.docx`.
- Ekspor Google Sheets otomatis pukul 21.00 WIB masih SIMULASI (belum ada OAuth).

## Persona
- Staf: mengisi dan memperbarui laporan pekerjaan harian.
- Admin: memantau semua staf, melihat analitik, mengelola staf, dan menyiapkan ekspor.

## Persyaratan Inti (Statis)
- Menu Plan, Doing, Finish.
- Data staf resmi dari DAFTAR HADIR STAF dengan enam departemen kantor.
- Laporan memiliki judul, penanggung jawab, status, target, prioritas, tenggat, catatan, bukti/link, dan foto kegiatan.
- Ringkasan, persentase workflow, completion rate, direktori staf, analitik departemen, dan ekspor Excel/PDF.

## Implementasi
### 2026-02-20
- API FastAPI (CRUD staf/tugas, analitik) dan seed 85 staf, template dashboard React.

### 2026-02-21
- Sinkronisasi 78 nama staf resmi dari `DAFTAR HADIR STAF.docx` (staff-1 = Edwin, S.Sos … staff-78 = Umam Wijaya). Mapping bagian → 6 departemen aplikasi. Tasks lama tetap terhubung karena staff_id `staff-1..staff-78` dipertahankan.
- Halaman Analitik:
  - Subtitle diganti menjadi "Data Analitik Kinerja Tim harian, mingguan dan bulanan."
  - Visual Completion Rate dirapikan: ring 150 px dengan angka persentase di pusat, legenda status berdampingan.
- Ekspor Excel/PDF berperiode:
  - Dialog ExportDialog memilih Harian, Mingguan, atau Bulanan dengan tanggal acuan.
  - Data laporan difilter berdasarkan `created_at` sesuai rentang periode; header dokumen mencantumkan judul periode dan rentang tanggal.
- Kontras dark mode disatukan lewat CSS variables (`--ink`, `--muted`, `--surface`, `--input-*`); teks tabel, form, badge, chart labels, empty state, task-menu, dan tombol ekspor kini kontras di dark mode.
- Testing agent iterasi 2 (backend-only) lulus 9/9 pytest (validasi 78 nama staf, CRUD, analytics shape, export status simulasi).

## Backlog Terprioritas
### P0
- Menghubungkan ekspor ke Google Sheets API/OAuth sungguhan.

### P1
- Login Google Workspace dan pembagian peran staf/admin.
- Drag-and-drop antar kolom Kanban.
- Riwayat perubahan laporan.

### P2
- Notifikasi tenggat dan ringkasan mingguan otomatis.
- Impor daftar staf dari spreadsheet.

## Tugas Berikutnya
1. Aktifkan sinkronisasi Google Sheets sungguhan (perlu OAuth Client ID/Secret dari user).
2. Tambahkan filter tanggal spesifik pada Kanban/laporan harian.
3. Pindahkan foto kegiatan ke object storage bila volume meningkat.

## Perubahan Lanjutan
- Menghapus label workspace statis dan menggantinya dengan hari/tanggal realtime.
- Menambahkan grafik tren harian, mingguan, bulanan, serta ringkasan per departemen.
- Scheduler ekspor otomatis pukul 21:00 WIB berjalan sebagai SIMULASI.

## Pembaruan Tampilan
- Dark/Light dengan preferensi tersimpan di browser.
- Ekspor Excel dan PDF berbentuk dokumen berlayout A4 landscape (PDF), dengan header periode dan blok tanda tangan sejajar.
- Upload foto kegiatan pada tugas (batas 5 MB, preview).

### Pembaruan Alur Status & Timestamp (2026-09-30)
- **Perubahan Status Plan menjadi To Do List**: Kolom awal alur kerja kini resmi dinamakan **To Do List** (menggantikan Plan) dengan penyesuaian visual, metrik, legenda analitik, serta ekspor dokumen.
- **Aturan Input To Do List**: Seluruh laporan harian baru wajib masuk melalui **To Do List** terlebih dahulu dan tidak dapat dibuat langsung ke status Doing atau Finish. Tombol tambah di kolom Doing/Finish memberikan notifikasi panduan.
- **Pencatatan Tanggal & Jam Sebelum Simpan**: Setiap status memiliki kolom input tanggal & jam (`todo_at`, `doing_at`, `finish_at`) yang dapat diperiksa dan disesuaikan pengguna secara langsung di modal sebelum menekan tombol simpan tugas.
- **Badge Waktu Status pada Kartu**: Kartu tugas di Kanban menampilkan badge waktu status realtime (To Do, Doing, Finish).
- **Laporan Ekspor Komprehensif**: Dokumen Excel dan PDF memuat kolom waktu status lengkap (Waktu To Do, Waktu Doing, Waktu Selesai).
- **Laporan per Staf Penanggung Jawab (Excel & PDF)**: Dialog ekspor kini menyediakan pilihan filter **Staf Penanggung Jawab**:
  - Opsi **Staf Spesifik**: Menghasilkan dokumen laporan kinerja individu staf terpilih (dilengkapi kartu metadata, ringkasan capaian kinerja [Total, To Do, Doing, Finish, % Capaian], tabel tugas, dan tanda tangan staf pelapor).
  - Opsi **Semua Staf**: Mengelompokkan laporan secara terstruktur per staf penanggung jawab lengkap dengan ringkasan kinerja per orang baik untuk periode Harian, Mingguan, maupun Bulanan.
- **Perubahan Target Sesuai Kondisi Riil & Kewajiban Pengisian**:
  - Pada setiap perpindahan status (**To Do List ➔ Doing ➔ Finish**), staf **wajib mengisi kolom target** sesuai kondisi aktual/riil pekerjaan di lapangan.
  - Dialog konfirmasi khusus (**StatusTransitionModal**) otomatis muncul saat staf mengubah status tugas (melalui tombol aksi cepat pada kartu tugas maupun perubahan status di form edit tugas), memastikan target baru dan waktu transisi diinputkan sebelum status tersimpan.
  - **Penyimpanan Histori Target**: Target terbaru selalu menjadi nilai aktif pada tugas, sedangkan setiap riwayat target sebelumnya dicatat lengkap dalam `target_history` (status, nilai target, waktu transisi, dan catatan lapangan) untuk transparansi pengawasan pimpinan.
  - Tampilan kartu Kanban, modal pengeditan tugas, serta ekspor PDF dan Excel memuat linimasa riwayat target riil yang akuntabel.

### Pembaruan Modul KPI Analitik Kinerja & Standar Mutu (2026-09-30)
- **Dashboard KPI Lengkap per Bagian**: Menu **Analitik** kini dilengkapi bagian khusus **Key Performance Indicators (KPI)** yang menggambarkan kinerja dan mutu operasional:
  1. **Bagian Umum**: Tata Usaha, Administrasi & SDM, Keuangan/Bendahara, Perencanaan, Sarana Prasarana, dan Humas.
  2. **Layanan Rehabilitasi Medis**: Pelayanan Dokter, Asesmen Medis Awal, Detoksifikasi, Keperawatan, Farmasi Klinis, Status Gizi, dan Sanitasi Lingkungan.
  3. **Layanan Rehabilitasi Sosial**: Konseling Adiksi (CBT/MET), Therapeutic Community (TC), Pelatihan Keterampilan Vokasional, dan Evaluasi Perilaku/Reintegrasi.
- **Mekanisme Otomatis & Terintegrasi**: Angka realisasi KPI dihitung secara otomatis dari agregasi data laporan harian staf (status tugas selesai, progres pengerjaan, dan pencapaian target riil per departemen) yang dipadukan dengan standar mutu Loka.
- **Fitur Tampilan**:
  - Tab navigasi filter bagian (`Semua Bagian`, `Umum`, `Medis`, `Sosial`).
  - Kartu eksekutif KPI per bagian dengan skor mutu keseluruhan (%), target standar, progres visual bar, jumlah staf aktif, dan badge kategori mutu (`Sangat Baik [A]`, `Baik [B]`, dll.).
  - Tabel rincian indikator mutu lengkap dengan kode indikator, bobot, target standar, realisasi laporan, tingkat ketercapaian, dan status mutu (`Target Tercapai`, `Mendekati Target`, `Perlu Perhatian`).

### Ekspor Otomatis per Akun & Monitoring Pimpinan (2026-10-12)
- **Ekspor PDF/Excel otomatis untuk Staf**: Saat role **Staf** membuka dialog ekspor, pemilih staf tidak lagi ditampilkan. Dokumen langsung dibuat untuk akun yang sedang masuk (kolom terkunci menampilkan nama & departemen staf tersebut), sehingga tidak ada lagi langkah "pilih laporan per staf".
- **Monitoring seluruh staf untuk pimpinan**: Role **Admin**, **Ketua Tim**, **Clinical Supervisor**, dan **Kepala** tetap memakai pemilih staf (opsi "Semua Staf (Laporan per Staf)" maupun staf tertentu) agar dapat memantau dan mencetak laporan seluruh staf.
- **Pengaman ganda**: `handleExportConfirm` memaksa `staff_id` ke akun pemilik sesi ketika role-nya Staf, dan API `/api/tasks` hanya mengembalikan laporan milik staf tersebut, sehingga dokumen tidak dapat memuat laporan staf lain.

### Perbaikan Sesi Tidak Dikenal & Distribusi Kredensial (2026-10-12)
- **Perbaikan bug 500 pada sesi kedaluwarsa/dicabut**: `parse_datetime` kini menangani nilai kosong/`None` sehingga cookie sesi yang sudah tidak ada di `auth_sessions` menghasilkan **401 "Silakan masuk untuk melanjutkan"**, bukan `AttributeError` yang berujung **500 Internal Server Error** (sebelumnya terpicu ketika sesi Admin dicabut akibat penerbitan kode aktivasi untuk akunnya sendiri).
- **Distribusi kredensial staf**: seluruh 78 staf kini memiliki username (NIP/NIK) + PIN yang diterbitkan lewat alur resmi (Admin menetapkan NIP → terbitkan kode aktivasi → `POST /api/auth/activate`). 74 staf memakai NIP/NIK contoh berpola `18xxxxxxxxxxxxxx` yang wajib diganti NIP resmi sebelum produksi. Daftar dibagikan sebagai dokumen Word di luar repositori karena memuat kredensial; PIN tetap hanya tersimpan sebagai hash PBKDF2 di server.

### Ekspor Kredensial Word & Excel (2026-10-12)
- `scripts/preview.py demo --accounts` kini menulis dua berkas kredensial sekaligus: dokumen Word (`Kredensial-Staf-LOKA-Kin.docx`) dan berkas Excel (`PIN-Staf-LOKA-Kin.xlsx`), keduanya di luar repositori karena memuat kredensial.
- Sub-perintah baru `scripts/preview.py ekspor [--kredensial .preview/kredensial.json] [--docx ...] [--xlsx ...]` menulis ulang kedua berkas dari rekaman kredensial tanpa menerbitkan ulang PIN.
- Berkas Excel memuat lembar **Kredensial Staf** (No, Nama, Departemen, Peran, Username NIP/NIK, PIN; header dibekukan, filter aktif, baris selang-seling) dan lembar **Cara Masuk** (panduan langkah). NIP/NIK dan PIN ditulis sebagai **teks** (`number_format '@'`) agar Excel tidak mengubahnya menjadi notasi ilmiah atau memangkas angka nol.
