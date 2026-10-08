import { useState } from "react";
import axios from "axios";
import { ArrowLeft, KeyRound, ShieldCheck, UserRound, X } from "lucide-react";
import { toast } from "sonner";
import "./AuthModal.css";

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : "/api";

export default function AuthModal({ mode = "login", onModeChange, onClose, onAuthenticated }) {
  const [busy, setBusy] = useState(false);
  const [generatedCode, setGeneratedCode] = useState(null);
  const [rosterRows, setRosterRows] = useState([]);
  const [rosterBusy, setRosterBusy] = useState(false);
  const [form, setForm] = useState({ nip: "", pin: "", pin_confirmation: "", activation_code: "", setup_secret: "" });

  const change = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  const setMode = (next) => {
    setGeneratedCode(null);
    if (next !== "bootstrap") setRosterRows([]);
    onModeChange(next);
  };

  const previewRoster = async (file) => {
    if (!file) return;
    if (!form.setup_secret) {
      toast.error("Masukkan kode penyiapan pemilik sistem sebelum membaca roster.");
      return;
    }
    setRosterBusy(true);
    try {
      const upload = new FormData();
      upload.append("file", file);
      upload.append("setup_secret", form.setup_secret);
      const response = await axios.post(`${API}/auth/initial-roster/preview`, upload, { withCredentials: true });
      setRosterRows(response.data.rows || []);
      toast.success(`${response.data.count} baris roster berhasil dibaca.`);
    } catch (error) {
      setRosterRows([]);
      toast.error(error.response?.data?.detail || "Roster CSV tidak dapat dibaca.");
    } finally {
      setRosterBusy(false);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      if (mode === "login") {
        const response = await axios.post(`${API}/auth/login`, { nip: form.nip, pin: form.pin }, { withCredentials: true });
        onAuthenticated(response.data.user);
        return;
      }
      if (mode === "activate") {
        await axios.post(`${API}/auth/activate`, {
          nip: form.nip,
          activation_code: form.activation_code,
          pin: form.pin,
          pin_confirmation: form.pin_confirmation,
        }, { withCredentials: true });
        setForm((current) => ({ ...current, pin: "", pin_confirmation: "", activation_code: "" }));
        onModeChange("login");
        return;
      }
      const response = await axios.post(`${API}/auth/bootstrap-admin`, {
        setup_secret: form.setup_secret,
        nip: form.nip,
        ...(rosterRows.length ? { roster: rosterRows } : {}),
      }, { withCredentials: true });
      setGeneratedCode(response.data);
      setForm((current) => ({ ...current, setup_secret: "" }));
    } catch (error) {
      const detail = error.response?.data?.detail;
      const message = Array.isArray(detail) ? detail[0]?.msg : detail;
      toast.error(message || "Permintaan tidak dapat diproses. Coba kembali.");
    } finally {
      setBusy(false);
    }
  };

  const title = mode === "login" ? "Selamat datang kembali" : mode === "activate" ? "Aktifkan akun" : "Penyiapan Admin pertama";
  const subtitle = mode === "login"
    ? "Masuk dengan NIP/NIK dan PIN pribadi Anda."
    : mode === "activate"
      ? "Masukkan kode sekali pakai dari Admin, lalu buat PIN enam digit."
      : "Gunakan kode penyiapan dari pemilik sistem untuk menerbitkan aktivasi kepada Admin di roster.";

  return (
    <div className="auth-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="auth-card" role="dialog" aria-modal="true" aria-labelledby="auth-title">
        <button className="auth-close" type="button" aria-label="Tutup" onClick={onClose}><X size={19} /></button>
        <div className="auth-brand-mark"><ShieldCheck size={23} /></div>
        <span className="auth-eyebrow">LOKA-KIN · RUANG KINERJA</span>
        <h2 id="auth-title">{title}</h2>
        <p className="auth-subtitle">{subtitle}</p>

        {generatedCode ? (
          <div className="auth-code-result" role="status">
            <b>Kode aktivasi Admin</b>
            <code>{generatedCode.activation_code}</code>
            <span>Berlaku hingga {new Date(generatedCode.expires_at).toLocaleString("id-ID")}. Kode ini hanya ditampilkan sekarang; serahkan langsung kepada Admin dan jangan kirim melalui kanal publik.</span>
            <button type="button" className="auth-primary" onClick={() => navigator.clipboard?.writeText(generatedCode.activation_code)}>Salin kode</button>
            <button type="button" className="auth-link" onClick={() => { setGeneratedCode(null); onModeChange("login"); }}>Kembali ke Masuk</button>
          </div>
        ) : (
          <form onSubmit={submit} className="auth-form">
            <label>
              <span><UserRound size={14} /> NIP / NIK</span>
              <input
                autoFocus
                name="nip"
                value={form.nip}
                onChange={change}
                inputMode="numeric"
                autoComplete="username"
                placeholder="Masukkan 16 atau 18 digit"
                required
              />
            </label>

            {mode === "login" && (
              <label>
                <span><KeyRound size={14} /> PIN 6 digit</span>
                <input name="pin" value={form.pin} onChange={change} type="password" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="current-password" placeholder="••••••" required />
              </label>
            )}

            {mode === "activate" && (
              <>
                <label>
                  <span><KeyRound size={14} /> Kode aktivasi</span>
                  <input name="activation_code" value={form.activation_code} onChange={change} inputMode="numeric" autoComplete="one-time-code" placeholder="Contoh: 1234-5678-9012" required />
                </label>
                <div className="auth-pin-grid">
                  <label><span>PIN baru</span><input name="pin" value={form.pin} onChange={change} type="password" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="new-password" placeholder="6 angka" required /></label>
                  <label><span>Ulangi PIN</span><input name="pin_confirmation" value={form.pin_confirmation} onChange={change} type="password" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="new-password" placeholder="6 angka" required /></label>
                </div>
                <p className="auth-hint">Pilih PIN yang mudah Anda ingat, tetapi jangan gunakan tanggal lahir atau nomor identitas.</p>
              </>
            )}

            {mode === "bootstrap" && (
              <>
                <label>
                  <span><KeyRound size={14} /> Kode penyiapan sistem</span>
                  <input name="setup_secret" value={form.setup_secret} onChange={change} type="password" autoComplete="off" placeholder="Diberikan pemilik sistem" required />
                </label>
                <label>
                  <span>Roster awal (CSV, opsional jika sudah dimuat)</span>
                  <input type="file" accept=".csv,.txt,text/csv" disabled={rosterBusy} onChange={(event) => previewRoster(event.target.files?.[0])} />
                </label>
                {rosterRows.length > 0 && (
                  <div className="auth-roster-preview">
                    <b>{rosterRows.length} orang pada roster · {rosterRows.filter((row) => String(row.role || "").toLowerCase() === "admin").length} baris ber-role Admin</b>
                    {rosterRows.slice(0, 4).map((row, index) => <span key={`${row.nip}-${index}`}>{row.name} · {row.role || "Staf"} · {row.nip || "tanpa NIP/NIK"}</span>)}
                    {rosterRows.length > 4 && <small>dan {rosterRows.length - 4} baris lainnya</small>}
                  </div>
                )}
                <p className="auth-hint">Jika roster belum dimuat, unggah CSV dengan kolom Nama, NIP/NIK, Departemen, Role, dan (untuk pimpinan) Departemen diawasi. Baris Admin harus sesuai dengan NIP/NIK di atas. PIN tidak boleh ada di spreadsheet.</p>
              </>
            )}

            <button className="auth-primary" type="submit" disabled={busy || (mode === "bootstrap" && rosterBusy)}>
              {busy ? "Memproses…" : mode === "login" ? "Masuk" : mode === "activate" ? "Buat PIN dan aktifkan" : "Terbitkan kode aktivasi"}
            </button>
          </form>
        )}

        {!generatedCode && (
          <div className="auth-mode-links">
            {mode !== "login" && <button type="button" className="auth-link" onClick={() => setMode("login")}><ArrowLeft size={14} /> Kembali ke Masuk</button>}
            {mode === "login" && <>
              <button type="button" className="auth-link" onClick={() => setMode("activate")}>Aktivasi akun / lupa PIN</button>
              <button type="button" className="auth-link" onClick={() => setMode("bootstrap")}>Penyiapan Admin pertama</button>
            </>}
          </div>
        )}
        <div className="auth-security-note"><ShieldCheck size={14} /> PIN Anda disimpan sebagai hash dan tidak dapat dibaca Admin.</div>
      </section>
    </div>
  );
}
