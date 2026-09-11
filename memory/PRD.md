# PRD — LOKA-Kin

## Pernyataan Masalah
LOKA-Kin adalah website laporan kinerja harian untuk 85 staf kantor dengan alur Plan, Doing, dan Finish. Sistem menampilkan grafik serta persentase kinerja dan menyediakan ekspor laporan ke Google Sheets.

## Keputusan Arsitektur
- React + Tailwind-compatible CSS untuk dashboard responsif, dengan Lucide dan Sonner untuk interaksi.
- FastAPI + MongoDB untuk data staf, laporan, analitik, dan endpoint ekspor.
- Dashboard demo tanpa login; data awal otomatis menyiapkan 85 staf dan beberapa laporan contoh.
- Google Sheets disiapkan sebagai alur ekspor berikutnya; saat ini endpoint memberikan status siap ekspor.

## Persona
- Staf: mengisi dan memperbarui laporan pekerjaan harian.
- Admin Loka: memantau semua staf, melihat analitik, mengelola staf, dan menyiapkan ekspor.

## Persyaratan Inti (Statis)
- Menu Plan, Doing, Finish.
- 85 staf dapat dipilih dan dipantau.
- Laporan memiliki judul, penanggung jawab, status, target, prioritas, tenggat, catatan, serta bukti/link.
- Ringkasan, persentase workflow, completion rate, daftar staf, dan analitik.
- Ekspor Google Sheets.

## Implementasi
### 2026-02-20
- Membuat API FastAPI untuk staf, laporan CRUD, analitik, dan ekspor.
- Menambahkan seed data 85 staf serta laporan demo.
- Membuat dashboard LOKA-Kin dengan sidebar, ringkasan, Kanban, modal laporan, filter, pencarian, direktori staf, dan analitik.
- Menambahkan form admin untuk membuat staf dan navigasi mobile.
- Validasi build frontend dan smoke test API berhasil.

## Backlog Terprioritas
### P0
- Menghubungkan ekspor ke Google Sheets API/OAuth sungguhan.

### P1
- Login Google Workspace dan pembagian peran staf/admin.
- Drag-and-drop antar kolom Kanban.
- Riwayat perubahan dan laporan per tanggal.

### P2
- Notifikasi tenggat dan ringkasan mingguan otomatis.
- Impor daftar staf dari spreadsheet.
- Ekspor PDF laporan individu.

## Tugas Berikutnya
1. Pilih kredensial Google Workspace dan bentuk spreadsheet tujuan.
2. Tambahkan filter tanggal untuk dashboard dan analitik.
3. Aktifkan sinkronisasi Google Sheets sungguhan.

## Perubahan Lanjutan
- Menghapus label workspace statis dan menggantinya dengan hari/tanggal realtime berbahasa Indonesia.
- Mengganti departemen menjadi Admin, Bendahara, Perencanaan, Informasi dan Humas, Layanan Rehabilitasi Medis, dan Layanan Rehabilitasi Sosial.
- Menambahkan grafik harian, mingguan, bulanan, serta ringkasan aktivitas per departemen.
- Menambahkan scheduler ekspor otomatis pukul 21.00 Asia/Jakarta; karena mode simulasi dipilih, aktivitas dicatat sebagai simulasi dan belum mengunggah ke Google Sheets.

## Pembaruan Tampilan dan Administrasi
- Menambahkan pengalih tampilan Dashboard Dark/Light dengan preferensi tersimpan di browser.
- Menghapus identitas Admin Loka dari header dan mengganti sapaan menjadi “Tabik Pun Staf Loka Rehabilitasi Narkotika Kalianda”.
- Mengganti aksi ekspor tampilan menjadi unduh Excel dan dialog cetak untuk PDF.
- Menambahkan tombol Hapus Staf pada setiap baris daftar staf dan endpoint penghapusan staf.