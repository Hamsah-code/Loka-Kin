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
