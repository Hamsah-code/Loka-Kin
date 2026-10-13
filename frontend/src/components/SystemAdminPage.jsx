import { useEffect, useState } from "react";
import axios from "axios";
import { Download, Globe2, KeyRound, LoaderCircle, Palette, Save, ShieldAlert, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import "./SystemAdminPage.css";

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : "/api";

const textFields = [
  ["brand_name", "Nama brand", "text"],
  ["hero_kicker", "Label kecil di hero", "text"],
  ["hero_title", "Judul hero", "text"],
  ["hero_highlight", "Teks sorotan hero", "text"],
  ["hero_description", "Deskripsi hero", "textarea"],
  ["hero_cta", "Teks tombol utama", "text"],
  ["assurance_one", "Poin keunggulan 1", "text"],
  ["assurance_two", "Poin keunggulan 2", "text"],
  ["features_title", "Judul bagian fitur", "text"],
  ["features_highlight", "Teks sorotan fitur", "text"],
  ["features_description", "Deskripsi bagian fitur", "textarea"],
  ["how_title", "Judul cara kerja", "text"],
  ["how_description", "Deskripsi cara kerja", "textarea"],
  ["about_title", "Judul bagian tentang", "text"],
  ["about_description", "Deskripsi bagian tentang", "textarea"],
  ["footer_text", "Teks footer", "text"],
];
const menuFields = [
  ["nav_home", "Label menu Home", "home"],
  ["nav_features", "Label menu Fitur", "show_features"],
  ["nav_how", "Label menu Cara kerja", "show_how"],
  ["nav_about", "Label menu Tentang", "show_about"],
];

function errorMessage(error) {
  const data = error.response?.data;
  const fromDetail = (detail) => {
    if (typeof detail === "string") return detail;
    if (detail?.message) {
      const names = (detail.missing_staff || detail.duplicate_staff || [])
        .map((item) => typeof item === "string" ? item : item.name)
        .filter(Boolean);
      return names.length ? `${detail.message} (${names.slice(0, 5).join(", ")}${names.length > 5 ? ", …" : ""})` : detail.message;
    }
    return "Permintaan tidak dapat diproses.";
  };
  if (data instanceof Blob) {
    return data.text()
      .then((text) => {
        try { return fromDetail(JSON.parse(text).detail); } catch { return "Gagal mengunduh PDF kredensial."; }
      })
      .catch(() => "Gagal mengunduh PDF kredensial.");
  }
  return Promise.resolve(fromDetail(data?.detail));
}

export default function SystemAdminPage({ settings, onSaveSettings }) {
  const [form, setForm] = useState(settings || {});
  const [tab, setTab] = useState("website");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [statusBusy, setStatusBusy] = useState(false);
  const [downloadBusy, setDownloadBusy] = useState(false);

  useEffect(() => setForm(settings || {}), [settings]);

  const refreshCredentialStatus = async () => {
    setStatusBusy(true);
    try {
      const response = await axios.get(`${API}/admin/credentials/status`);
      setStatus(response.data);
    } catch (error) {
      if (error.response?.status === 401 || error.response?.status === 403) {
        toast.error(error.response?.data?.detail || "Akses Super Admin diperlukan.");
      } else {
        toast.error("Status kredensial belum dapat dimuat.");
      }
    } finally {
      setStatusBusy(false);
    }
  };

  useEffect(() => {
    if (tab === "credentials" && !status) refreshCredentialStatus();
    // Load the protected status only when its tab is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const updateField = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await onSaveSettings(form);
      toast.success("Pengaturan landing page berhasil disimpan.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Pengaturan tidak berhasil disimpan.");
    } finally {
      setSaving(false);
    }
  };

  const downloadCredentials = async () => {
    if (!window.confirm(
      "Tindakan ini akan menerbitkan PIN sementara baru untuk SEMUA pegawai aktif, mereset PIN lama, dan mencabut sesi mereka. PIN wajib diganti saat login pertama. Lanjutkan?"
    )) return;
    setDownloadBusy(true);
    try {
      const response = await axios.post(`${API}/admin/credentials/rotate-pdf`, {}, { responseType: "blob" });
      const file = new Blob([response.data], { type: "application/pdf" });
      const url = URL.createObjectURL(file);
      const link = document.createElement("a");
      link.href = url;
      link.download = `loka-kin-kredensial-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success("PDF PIN sementara berhasil diunduh. Bagikan secara pribadi kepada pegawai.");
      await refreshCredentialStatus();
    } catch (error) {
      toast.error(await errorMessage(error));
      await refreshCredentialStatus();
    } finally {
      setDownloadBusy(false);
    }
  };

  return (
    <section className="system-admin-page" data-testid="super-admin-page">
      <div className="system-admin-heading">
        <div>
          <span className="system-admin-eyebrow"><ShieldCheck size={14} /> KONSOL SUPER ADMIN</span>
          <h1>Pengelolaan website</h1>
          <p>Atur konten dan navigasi landing page, serta kelola distribusi PIN pegawai dengan alur sekali tampil.</p>
        </div>
        <span className="system-admin-secure"><ShieldCheck size={15} /> Hak akses Super Admin</span>
      </div>

      <div className="system-admin-tabs" role="tablist" aria-label="Menu pengelolaan Super Admin">
        <button type="button" role="tab" aria-selected={tab === "website"} className={tab === "website" ? "active" : ""} onClick={() => setTab("website")}>
          <Globe2 size={16} /> Landing page &amp; menu
        </button>
        <button type="button" role="tab" aria-selected={tab === "credentials"} className={tab === "credentials" ? "active" : ""} onClick={() => setTab("credentials")}>
          <KeyRound size={16} /> Kredensial pegawai
        </button>
      </div>

      {tab === "website" ? (
        <form className="system-admin-form" onSubmit={save}>
          <div className="system-admin-panel-head">
            <span className="system-admin-panel-icon"><Palette size={18} /></span>
            <div><h2>Konten landing page</h2><p>Perubahan tampil di halaman depan setelah disimpan.</p></div>
          </div>
          <div className="system-admin-grid">
            {textFields.map(([key, label, type]) => (
              <label className={type === "textarea" ? "system-admin-field wide" : "system-admin-field"} key={key}>
                <span>{label}</span>
                {type === "textarea" ? (
                  <textarea value={form[key] || ""} maxLength={500} rows={3} onChange={(event) => updateField(key, event.target.value)} />
                ) : (
                  <input value={form[key] || ""} maxLength={key === "brand_name" ? 80 : 120} onChange={(event) => updateField(key, event.target.value)} />
                )}
              </label>
            ))}
          </div>

          <div className="system-admin-subhead"><h3>Menu dan tampilan</h3><p>Ubah label navigasi, tampil/sembunyikan bagian, serta warna utama.</p></div>
          <div className="system-admin-grid system-admin-menu-grid">
            {menuFields.map(([key, label, toggleKey]) => (
              <label className="system-admin-field" key={key}>
                <span>{label}</span>
                <input value={form[key] || ""} maxLength={30} onChange={(event) => updateField(key, event.target.value)} />
                {toggleKey !== "home" && (
                  <span className="system-admin-checkbox-row">
                    <input type="checkbox" checked={Boolean(form[toggleKey])} onChange={(event) => updateField(toggleKey, event.target.checked)} />
                    Tampilkan bagian {form[key] || label.replace("Label menu ", "")}
                  </span>
                )}
              </label>
            ))}
            <label className="system-admin-field system-admin-color-field">
              <span>Warna aksen utama</span>
              <span className="system-admin-color-control">
                <input type="color" value={/^#[0-9a-f]{6}$/i.test(form.accent_color || "") ? form.accent_color : "#2458EC"} onChange={(event) => updateField("accent_color", event.target.value.toUpperCase())} />
                <code>{form.accent_color || "#2458EC"}</code>
              </span>
            </label>
          </div>
          <div className="system-admin-form-footer">
            <span>Konten diperlakukan sebagai teks biasa; kode HTML/script tidak dijalankan.</span>
            <button type="submit" className="primary-btn" disabled={saving}>
              {saving ? <LoaderCircle className="spinning" size={16} /> : <Save size={16} />}
              {saving ? "Menyimpan…" : "Simpan perubahan"}
            </button>
          </div>
        </form>
      ) : (
        <div className="system-admin-credentials">
          <div className="system-admin-panel-head">
            <span className="system-admin-panel-icon credential"><KeyRound size={18} /></span>
            <div><h2>PDF NIP/NIK &amp; PIN sementara</h2><p>PDF hanya dibuat saat PIN baru diterbitkan; PIN lama tidak dapat dibaca dari hash.</p></div>
            <button type="button" className="secondary-btn system-admin-refresh" onClick={refreshCredentialStatus} disabled={statusBusy}>
              {statusBusy ? <LoaderCircle className="spinning" size={15} /> : "Muat ulang"}
            </button>
          </div>

          <div className="credential-stat-grid">
            <div><span>Pegawai aktif</span><b>{status?.total_staff ?? "—"}</b></div>
            <div><span>NIP/NIK valid</span><b>{status?.with_official_identity ?? "—"}</b></div>
            <div><span>PIN aktif</span><b>{status?.activated_accounts ?? "—"}</b></div>
            <div><span>Belum aktivasi</span><b>{status?.pending_accounts ?? "—"}</b></div>
          </div>

          <div className="credential-security-note">
            <ShieldAlert size={18} />
            <div>
              <b>Unduhan ini mereset PIN semua pegawai aktif.</b>
              <p>Setiap PIN lama diganti dengan PIN sementara acak; seluruh sesi pegawai dicabut. PIN sementara wajib diganti saat login pertama, dan nilainya tidak disimpan sebagai teks biasa atau dapat diunduh ulang.</p>
            </div>
          </div>

          {status?.missing_or_placeholder_identity > 0 && (
            <div className="credential-missing-note" role="status">
              <b>{status.missing_or_placeholder_identity} pegawai belum memiliki NIP/NIK resmi yang valid.</b>
              <span>Impor/benahi roster resmi dari menu Daftar staf terlebih dahulu. Nomor contoh atau nomor placeholder tidak dapat digunakan untuk membuat PDF.</span>
              {status.missing_staff?.length > 0 && (
                <small>Contoh: {status.missing_staff.slice(0, 6).map((person) => person.name).join(", ")}{status.missing_staff.length > 6 ? ", …" : ""}</small>
              )}
            </div>
          )}

          <div className="system-admin-download-row">
            <div><b>Daftar perubahan kredensial</b><span>Memuat NIP/NIK, PIN sementara, dan status PIN awal/dirotasi.</span></div>
            <button type="button" className="primary-btn credential-download-button" data-testid="download-staff-credentials-pdf" disabled={!status?.ready_for_pin_pdf || downloadBusy || statusBusy} onClick={downloadCredentials}>
              {downloadBusy ? <LoaderCircle className="spinning" size={17} /> : <Download size={17} />}
              {downloadBusy ? "Menerbitkan PIN…" : "Rotasi & unduh PDF"}
            </button>
          </div>
          <p className="credential-distribution-warning">RAHASIA: simpan PDF di tempat aman, jangan unggah ke repositori/grup umum, dan bagikan hanya kepada pegawai yang bersangkutan.</p>
        </div>
      )}
    </section>
  );
}
