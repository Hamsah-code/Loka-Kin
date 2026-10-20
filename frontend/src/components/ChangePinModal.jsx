import { useState } from "react";
import axios from "axios";
import { KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : "/api";

export default function ChangePinModal({ onChanged }) {
  const [form, setForm] = useState({ current_pin: "", new_pin: "", pin_confirmation: "" });
  const [busy, setBusy] = useState(false);
  const change = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value.replace(/\D/g, "").slice(0, 6) }));

  const submit = async (event) => {
    event.preventDefault();
    if (!/^\d{6}$/.test(form.new_pin)) return toast.error("PIN baru harus terdiri dari enam angka.");
    if (form.new_pin !== form.pin_confirmation) return toast.error("Konfirmasi PIN tidak sama.");
    setBusy(true);
    try {
      await axios.post(`${API}/auth/change-pin`, form, { withCredentials: true });
      toast.success("PIN berhasil diganti.");
      onChanged?.();
    } catch (error) {
      toast.error(error.response?.data?.detail || "PIN belum berhasil diganti.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop change-pin-backdrop" data-testid="change-pin-modal">
      <section className="modal change-pin-card" role="dialog" aria-modal="true" aria-labelledby="change-pin-title">
        <div className="change-pin-icon"><LockKeyhole size={22} /></div>
        <span className="eyebrow">KEAMANAN AKUN</span>
        <h2 id="change-pin-title">Ganti PIN sementara</h2>
        <p className="modal-subtitle">PIN sementara hanya untuk masuk pertama kali. Buat PIN pribadi enam digit sebelum menggunakan aplikasi.</p>
        <form onSubmit={submit} className="change-pin-form">
          <label><span><KeyRound size={14} /> PIN sementara</span><input autoFocus name="current_pin" type="password" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="current-password" value={form.current_pin} onChange={change} required /></label>
          <label><span><KeyRound size={14} /> PIN baru</span><input name="new_pin" type="password" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="new-password" value={form.new_pin} onChange={change} required /></label>
          <label><span><KeyRound size={14} /> Ulangi PIN baru</span><input name="pin_confirmation" type="password" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="new-password" value={form.pin_confirmation} onChange={change} required /></label>
          <div className="auth-security-note"><ShieldCheck size={14} /> PIN baru disimpan sebagai hash dan tidak dapat dibaca Admin.</div>
          <button className="primary-btn" type="submit" disabled={busy}>{busy ? "Menyimpan…" : "Simpan PIN baru"}</button>
        </form>
      </section>
    </div>
  );
}
