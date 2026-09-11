import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  BarChart3, Calendar, Camera, CheckCircle2, ClipboardList, FileSpreadsheet, FileText,
  LayoutDashboard, Menu, Moon, Plus, Search, Settings2, Sun, Trash2, Users, X,
} from "lucide-react";
import { Toaster, toast } from "sonner";
import "@/App.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const columns = [
  { key: "plan", label: "Plan", color: "blue", hint: "Rencana yang akan dikerjakan" },
  { key: "doing", label: "Doing", color: "amber", hint: "Sedang berjalan" },
  { key: "finish", label: "Finish", color: "green", hint: "Sudah diselesaikan" },
];
const departments = [
  "Admin", "Bendahara", "Perencanaan", "Informasi dan Humas",
  "Layanan Rehabilitasi Medis", "Layanan Rehabilitasi Sosial", "Umum",
];
const currentDate = () =>
  new Intl.DateTimeFormat("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date());

const pad = (n) => String(n).padStart(2, "0");
const toDateInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

function computeRange(period, refDateStr) {
  const ref = refDateStr ? new Date(`${refDateStr}T00:00:00`) : new Date();
  let start, end, label;
  if (period === "harian") {
    start = new Date(ref); start.setHours(0, 0, 0, 0);
    end = new Date(ref); end.setHours(23, 59, 59, 999);
    label = new Intl.DateTimeFormat("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(start);
  } else if (period === "mingguan") {
    const day = ref.getDay(); // 0=Minggu
    const monday = new Date(ref);
    monday.setDate(ref.getDate() - ((day + 6) % 7));
    start = new Date(monday); start.setHours(0, 0, 0, 0);
    end = new Date(start); end.setDate(start.getDate() + 6); end.setHours(23, 59, 59, 999);
    const fmt = (d) => new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", year: "numeric" }).format(d);
    label = `Minggu ${fmt(start)} – ${fmt(end)}`;
  } else {
    start = new Date(ref.getFullYear(), ref.getMonth(), 1, 0, 0, 0, 0);
    end = new Date(ref.getFullYear(), ref.getMonth() + 1, 0, 23, 59, 59, 999);
    label = new Intl.DateTimeFormat("id-ID", { month: "long", year: "numeric" }).format(start);
  }
  return { start, end, label };
}

function filterTasksByRange(tasks, start, end) {
  return tasks.filter((t) => {
    if (!t.created_at) return true;
    const c = new Date(t.created_at);
    return c >= start && c <= end;
  });
}

function Avatar({ name }) {
  return (
    <span className="avatar" data-testid="staff-avatar">
      {name?.split(" ").map((x) => x[0]).slice(0, 2).join("")}
    </span>
  );
}

function TaskCard({ task, staff, onEdit }) {
  const person = staff.find((s) => s.id === task.staff_id);
  return (
    <button className="task-card" data-testid={`task-card-${task.id}`} onClick={() => onEdit(task)}>
      <div className="task-top">
        <span className={`priority ${task.priority.toLowerCase()}`}>{task.priority}</span>
        <span className="task-menu">{task.photo_data ? <Camera size={14} /> : "•••"}</span>
      </div>
      <strong data-testid="task-title">{task.title}</strong>
      <p className="task-target" data-testid="task-target">Target · {task.target || "Belum ditentukan"}</p>
      <div className="task-bottom">
        <span className="person"><Avatar name={person?.name} />{person?.name?.split(" ").slice(0, 2).join(" ")}</span>
        <span className="due">{task.due_date || "Tanpa tenggat"}</span>
      </div>
    </button>
  );
}

function TaskModal({ task, staff, onClose, onSave }) {
  const [form, setForm] = useState(task || {
    title: "", staff_id: staff[0]?.id || "", status: "plan", target: "", priority: "Sedang",
    due_date: "", notes: "", proof_link: "", photo_data: "", photo_name: "",
  });
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const uploadPhoto = (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    if (!file.type.startsWith("image/")) return toast.error("Pilih file foto kegiatan");
    if (file.size > 5 * 1024 * 1024) return toast.error("Ukuran foto maksimal 5 MB");
    const reader = new FileReader();
    reader.onload = () => setForm((p) => ({ ...p, photo_data: reader.result, photo_name: file.name }));
    reader.readAsDataURL(file);
  };
  return (
    <div className="modal-backdrop" data-testid="task-modal">
      <div className="modal">
        <div className="modal-head">
          <div><span className="eyebrow">LAPORAN HARIAN</span><h2>{task ? "Edit tugas" : "Tambah tugas baru"}</h2></div>
          <button className="icon-button" data-testid="task-modal-close" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="form-grid">
          <label>Nama tugas<input autoFocus data-testid="task-title-input" name="title" value={form.title} onChange={change} placeholder="Contoh: Rekap laporan layanan" /></label>
          <label>Penanggung jawab<select data-testid="task-staff-select" name="staff_id" value={form.staff_id} onChange={change}>{staff.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.department}</option>)}</select></label>
          <label>Status<select data-testid="task-status-select" name="status" value={form.status} onChange={change}>{columns.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}</select></label>
          <label>Prioritas<select data-testid="task-priority-select" name="priority" value={form.priority} onChange={change}><option>Rendah</option><option>Sedang</option><option>Tinggi</option></select></label>
          <label>Target<input data-testid="task-target-input" name="target" value={form.target} onChange={change} placeholder="Contoh: 10 laporan" /></label>
          <label>Tenggat<input data-testid="task-due-input" name="due_date" value={form.due_date} onChange={change} placeholder="Contoh: Hari ini" /></label>
          <label className="full">Catatan<textarea data-testid="task-notes-input" name="notes" value={form.notes} onChange={change} placeholder="Tambahkan konteks pekerjaan..." /></label>
          <label className="full">Link bukti / dokumen<input data-testid="task-proof-input" name="proof_link" value={form.proof_link} onChange={change} placeholder="https://..." /></label>
          <label className="full photo-upload-label">Foto kegiatan
            <input className="photo-input" type="file" accept="image/*" data-testid="task-photo-input" onChange={uploadPhoto} />
            <span className="photo-dropzone"><Camera size={18} /><span>{form.photo_name || "Pilih foto kegiatan (maks. 5 MB)"}</span></span>
          </label>
          {form.photo_data && (
            <div className="photo-preview-wrap full">
              <img src={form.photo_data} alt="Pratinjau kegiatan" data-testid="task-photo-preview" />
              <button type="button" className="remove-photo" data-testid="remove-photo-button" onClick={() => setForm({ ...form, photo_data: "", photo_name: "" })}><X size={14} /> Hapus foto</button>
            </div>
          )}
        </div>
        <div className="modal-actions">
          <button className="secondary-btn" data-testid="task-cancel-button" onClick={onClose}>Batal</button>
          <button className="primary-btn" data-testid="task-save-button" onClick={() => { if (!form.title.trim()) return toast.error("Nama tugas wajib diisi"); onSave(form); }}>Simpan tugas</button>
        </div>
      </div>
    </div>
  );
}

function StaffModal({ onClose, onSave }) {
  const [form, setForm] = useState({ name: "", department: departments[0] });
  return (
    <div className="modal-backdrop" data-testid="staff-modal">
      <div className="modal">
        <div className="modal-head">
          <div><span className="eyebrow">ADMINISTRASI TIM</span><h2>Tambah staf</h2></div>
          <button className="icon-button" data-testid="staff-modal-close" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="form-grid">
          <label className="full">Nama lengkap<input autoFocus data-testid="staff-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Contoh: Sari Wulandari" /></label>
          <label className="full">Departemen<select data-testid="staff-department-select" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>{departments.map((d) => <option key={d}>{d}</option>)}</select></label>
        </div>
        <div className="modal-actions">
          <button className="secondary-btn" data-testid="staff-cancel-button" onClick={onClose}>Batal</button>
          <button className="primary-btn" data-testid="staff-save-button" onClick={() => form.name.trim() ? onSave(form) : toast.error("Nama staf wajib diisi")}>Simpan staf</button>
        </div>
      </div>
    </div>
  );
}

function ExportDialog({ mode, onClose, onConfirm }) {
  const [period, setPeriod] = useState("harian");
  const [refDate, setRefDate] = useState(toDateInput(new Date()));
  const { label } = useMemo(() => computeRange(period, refDate), [period, refDate]);
  const periods = [
    { key: "harian", label: "Harian", hint: "Laporan tanggal terpilih" },
    { key: "mingguan", label: "Mingguan", hint: "Senin – Minggu di pekan tanggal terpilih" },
    { key: "bulanan", label: "Bulanan", hint: "Seluruh laporan pada bulan tanggal terpilih" },
  ];
  return (
    <div className="modal-backdrop" data-testid="export-dialog">
      <div className="modal export-modal">
        <div className="modal-head">
          <div>
            <span className="eyebrow">EKSPOR {mode.toUpperCase()}</span>
            <h2>Pilih periode laporan</h2>
          </div>
          <button className="icon-button" data-testid="export-dialog-close" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="period-picker">
          {periods.map((p) => (
            <button
              key={p.key}
              type="button"
              className={period === p.key ? "period-choice active" : "period-choice"}
              data-testid={`export-period-${p.key}`}
              onClick={() => setPeriod(p.key)}
            >
              <strong>{p.label}</strong>
              <small>{p.hint}</small>
            </button>
          ))}
        </div>
        <label className="date-field">
          <span><Calendar size={14} /> Tanggal acuan</span>
          <input
            type="date"
            data-testid="export-date-input"
            value={refDate}
            onChange={(e) => setRefDate(e.target.value)}
          />
        </label>
        <div className="export-summary" data-testid="export-range-label">Rentang: <b>{label}</b></div>
        <div className="modal-actions">
          <button className="secondary-btn" data-testid="export-cancel" onClick={onClose}>Batal</button>
          <button
            className="primary-btn"
            data-testid="export-confirm"
            onClick={() => onConfirm({ period, refDate })}
          >
            Unduh {mode === "excel" ? "Excel" : "PDF"}
          </button>
        </div>
      </div>
    </div>
  );
}

function PageIntro({ title, desc, action }) {
  return (
    <div className="page-intro">
      <div>
        <span className="eyebrow" data-testid="realtime-date">{currentDate()}</span>
        <h1 data-testid="page-title">{title}</h1>
        <p data-testid="page-description">{desc}</p>
      </div>
      {action}
    </div>
  );
}

function Metric({ label, value, detail, icon: Icon, tone }) {
  return (
    <div className="metric" data-testid={`metric-${label.toLowerCase().replaceAll(" ", "-")}`}>
      <div className={`metric-icon ${tone}`}><Icon size={19} /></div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function Overview({ analytics, tasks, staffCount, onGo }) {
  return (
    <>
      <PageIntro
        title="Tabik Pun Staf Loka Rehabilitasi Narkotika Kalianda"
        desc="Berikut ringkasan kinerja tim untuk hari ini."
        action={<button className="primary-btn" data-testid="overview-add-button" onClick={onGo}><Plus size={17} /> Buat laporan</button>}
      />
      <div className="metric-grid">
        <Metric label="Total laporan" value={analytics.total_tasks} detail="Laporan aktif hari ini" icon={ClipboardList} tone="blue" />
        <Metric label="Selesai" value={`${analytics.completion_rate}%`} detail={`${analytics.counts.finish} laporan finish`} icon={CheckCircle2} tone="green" />
        <Metric label="Sedang berjalan" value={analytics.counts.doing} detail="Perlu perhatian tim" icon={BarChart3} tone="amber" />
        <Metric label="Total staf aktif" value={staffCount} detail="Di seluruh departemen" icon={Users} tone="violet" />
      </div>
      <div className="overview-grid">
        <section className="surface chart-panel">
          <div className="section-head">
            <div><span className="eyebrow">PROGRES WORKFLOW</span><h2>Distribusi laporan</h2></div>
            <button className="text-btn" data-testid="view-board-button" onClick={onGo}>Lihat board →</button>
          </div>
          <div className="progress-chart">
            {columns.map((c) => (
              <div className="progress-row" key={c.key}>
                <span>{c.label}</span>
                <div className="progress-track"><i className={c.color} style={{ width: `${analytics.percentages[c.key]}%` }} /></div>
                <b>{analytics.percentages[c.key]}%</b>
              </div>
            ))}
          </div>
        </section>
        <section className="surface recent-panel">
          <div className="section-head">
            <div><span className="eyebrow">AKTIVITAS TERBARU</span><h2>Laporan masuk</h2></div>
            <span className="live-label"><span className="live-dot" />Live</span>
          </div>
          {tasks.slice(0, 3).map((t) => (
            <div className="recent-item" key={t.id}>
              <span className={`status-icon ${t.status}`}>{t.status === "finish" ? "✓" : "•"}</span>
              <div><strong>{t.title}</strong><small>{t.status === "finish" ? "Diselesaikan" : "Diperbarui"} · hari ini</small></div>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}

function StaffPage({ staff, tasks, onAdd, onDelete }) {
  return (
    <>
      <PageIntro
        title="Daftar staf"
        desc="Kelola anggota tim dan lihat ringkasan laporan mereka."
        action={<button className="primary-btn" data-testid="add-staff-button" onClick={onAdd}><Plus size={17} /> Tambah staf</button>}
      />
      <div className="surface staff-table">
        <div className="table-head">
          <strong>Nama staf</strong><strong>Departemen</strong><strong>Laporan</strong><strong>Status</strong><strong>Aksi</strong>
        </div>
        {staff.map((s) => (
          <div className="staff-row" data-testid={`staff-row-${s.id}`} key={s.id}>
            <div className="staff-name">
              <Avatar name={s.name} />
              <span><strong>{s.name}</strong><small>ID · {s.id.replace("staff-", "LK-")}</small></span>
            </div>
            <span>{s.department}</span>
            <b>{tasks.filter((t) => t.staff_id === s.id).length} laporan</b>
            <span className="active-pill"><i /> Aktif</span>
            <button className="delete-staff" data-testid={`delete-staff-${s.id}`} onClick={() => onDelete(s)}>
              <Trash2 size={15} /> Hapus
            </button>
          </div>
        ))}
      </div>
    </>
  );
}

function Analytics({ analytics }) {
  const [period, setPeriod] = useState("daily");
  const trends = analytics.trends?.[period] || [];
  const max = Math.max(...trends.map((x) => x.total), 1);
  const rate = analytics.completion_rate || 0;
  return (
    <>
      <PageIntro title="Analitik kinerja" desc="Data Analitik Kinerja Tim harian, mingguan dan bulanan." />
      <div className="analytics-cards">
        <div className="surface big-score">
          <div className="score-header">
            <span className="eyebrow">COMPLETION RATE</span>
            <span className="score-badge">{analytics.counts.finish} selesai</span>
          </div>
          <div className="score-body">
            <div className="score-ring" style={{ "--score": `${rate}%` }} data-testid="completion-ring">
              <div className="score-ring-inner">
                <strong data-testid="completion-rate">{rate}%</strong>
                <small>tercapai</small>
              </div>
            </div>
            <div className="score-legend">
              <p>Persentase laporan yang telah diselesaikan tim dari total laporan aktif.</p>
              <ul>
                <li><span className="legend-dot green" /> Selesai · {analytics.percentages.finish}%</li>
                <li><span className="legend-dot amber" /> Sedang berjalan · {analytics.percentages.doing}%</li>
                <li><span className="legend-dot blue" /> Rencana · {analytics.percentages.plan}%</li>
              </ul>
            </div>
          </div>
        </div>
        <div className="surface breakdown">
          <span className="eyebrow">WORKFLOW BREAKDOWN</span>
          <h2>Posisi seluruh laporan</h2>
          {columns.map((c) => (
            <div className="break-row" key={c.key}>
              <span className={`column-dot ${c.color}`} /><span>{c.label}</span>
              <b>{analytics.counts[c.key]}</b><small>{analytics.percentages[c.key]}%</small>
            </div>
          ))}
        </div>
      </div>
      <div className="surface trend-panel">
        <div className="section-head">
          <div>
            <span className="eyebrow">TREN PRODUKTIVITAS</span>
            <h2 data-testid="trend-title">Laporan {period === "daily" ? "harian" : period === "weekly" ? "mingguan" : "bulanan"}</h2>
          </div>
          <div className="period-tabs">
            {[["daily", "Harian"], ["weekly", "Mingguan"], ["monthly", "Bulanan"]].map(([key, label]) => (
              <button className={period === key ? "period-tab active" : "period-tab"} data-testid={`analytics-${key}-tab`} key={key} onClick={() => setPeriod(key)}>{label}</button>
            ))}
          </div>
        </div>
        <div className="bar-chart" data-testid="trend-chart">
          {trends.map((item) => (
            <div className="bar-group" key={item.label}>
              <div className="bar-value">{item.total}</div>
              <div className="bar" style={{ height: `${Math.max(12, item.total / max * 130)}px` }} />
              <small>{item.label}</small>
            </div>
          ))}
        </div>
      </div>
      <div className="surface department-panel">
        <span className="eyebrow">PER DEPARTEMEN</span>
        <h2>Aktivitas laporan setiap unit</h2>
        <div className="department-grid">
          {(analytics.departments || departments.map((name) => ({ name, total: 0, finish: 0 }))).map((department) => (
            <div className="department-stat" data-testid={`department-${department.name.toLowerCase().replaceAll(" ", "-")}`} key={department.name}>
              <span className="dept-icon"><Users size={16} /></span>
              <div><strong>{department.name}</strong><small>{department.total} laporan tercatat</small></div>
              <b>{department.finish || 0}</b>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [staff, setStaff] = useState([]);
  const [analytics, setAnalytics] = useState({
    counts: { plan: 0, doing: 0, finish: 0 },
    percentages: { plan: 0, doing: 0, finish: 0 },
    total_tasks: 0, completion_rate: 0, total_staff: 0,
  });
  const [modal, setModal] = useState(null);
  const [exportMode, setExportMode] = useState(null); // 'excel' | 'pdf' | null
  const [active, setActive] = useState("overview");
  const [query, setQuery] = useState("");
  const [selectedStaff, setSelectedStaff] = useState("all");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("loka-kin-theme") === "dark");

  const load = async () => {
    try {
      const [t, s, a] = await Promise.all([
        axios.get(`${API}/tasks`), axios.get(`${API}/staff`), axios.get(`${API}/analytics`),
      ]);
      setTasks(t.data); setStaff(s.data); setAnalytics(a.data);
    } catch { toast.error("Data belum dapat dimuat"); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    document.body.classList.toggle("dark-mode", dark);
    localStorage.setItem("loka-kin-theme", dark ? "dark" : "light");
  }, [dark]);

  const filtered = useMemo(
    () => tasks.filter((t) =>
      (!selectedStaff || selectedStaff === "all" || t.staff_id === selectedStaff) &&
      t.title.toLowerCase().includes(query.toLowerCase())
    ),
    [tasks, query, selectedStaff]
  );

  const save = async (form) => {
    try {
      const res = await (modal?.id ? axios.patch(`${API}/tasks/${modal.id}`, form) : axios.post(`${API}/tasks`, form));
      setTasks((prev) => modal?.id ? prev.map((t) => t.id === modal.id ? res.data : t) : [res.data, ...prev]);
      setModal(null); await load(); toast.success("Laporan tersimpan");
    } catch { toast.error("Gagal menyimpan laporan"); }
  };
  const addStaff = async (form) => {
    try {
      const res = await axios.post(`${API}/staff`, form);
      setStaff((prev) => [...prev, res.data]); setModal(null); toast.success("Staf berhasil ditambahkan");
    } catch { toast.error("Gagal menambahkan staf"); }
  };
  const deleteStaff = async (person) => {
    if (!window.confirm(`Hapus staf ${person.name}?`)) return;
    try {
      await axios.delete(`${API}/staff/${person.id}`);
      setStaff((prev) => prev.filter((s) => s.id !== person.id));
      toast.success("Staf berhasil dihapus");
    } catch { toast.error("Gagal menghapus staf"); }
  };

  const buildRows = (data) => data.map((t) => {
    const person = staff.find((s) => s.id === t.staff_id);
    return [
      t.title, person?.name || "", person?.department || "", t.status, t.priority,
      t.target, t.due_date, t.notes, t.proof_link, t.photo_name ? `Foto: ${t.photo_name}` : "",
    ];
  });

  const signatureHtml = `<table class="signature-table"><tr><td><b>Mengetahui</b></td><td><b>Kalianda, ${currentDate()}</b></td></tr><tr><td><b>Kepala Loka Rehabilitasi Narkotika Kalianda</b></td><td><b>Penanggung Jawab Admin &amp; SDM</b></td></tr><tr class="signature-space"><td></td><td></td></tr><tr><td><b>Heru Herlambang, S. AP</b></td><td><b>Daniel, Amd.Kep</b></td></tr></table>`;

  const periodTitle = { harian: "Harian", mingguan: "Mingguan", bulanan: "Bulanan" };

  const runExportExcel = (period, refDate) => {
    const { start, end, label } = computeRange(period, refDate);
    const scoped = filterTasksByRange(tasks, start, end);
    const rows = [["Judul", "Staf", "Departemen", "Status", "Prioritas", "Target", "Tenggat", "Catatan", "Bukti", "Foto"], ...buildRows(scoped)];
    const html = `<html><head><meta charset="UTF-8"><style>body{font-family:Arial;color:#111827}h1{font-size:18px;margin:0 0 4px}p{font-size:11px;margin:0 0 12px;color:#374151}.report-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:10px}.report-table th,.report-table td{border:1px solid #cbd5e1;padding:7px;vertical-align:top;word-break:break-word}.report-table th{background:#e8f0ff;font-weight:700}.signature-table{border-collapse:collapse;width:100%;table-layout:fixed;margin-top:55px;font-size:12px}.signature-table td{border:0;width:50%;text-align:center;vertical-align:top;padding:4px 16px;line-height:1.25}.signature-table .signature-space td{height:88px;padding:0}</style></head><body><h1>LOKA-Kin · Laporan ${periodTitle[period]}</h1><p>${label} · Total ${scoped.length} laporan</p><table class="report-table">${rows.map((row, index) => `<tr>${row.map((cell) => index === 0 ? `<th>${String(cell || "").replaceAll("<", "&lt;")}</th>` : `<td>${String(cell || "").replaceAll("<", "&lt;")}</td>`).join("")}</tr>`).join("")}</table>${signatureHtml}</body></html>`;
    const blob = new Blob([html], { type: "application/vnd.ms-excel" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `loka-kin-${period}-${toDateInput(start)}.xls`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success(`Excel ${periodTitle[period].toLowerCase()} berhasil diunduh`);
  };

  const runExportPdf = (period, refDate) => {
    const { start, end, label } = computeRange(period, refDate);
    const scoped = filterTasksByRange(tasks, start, end);
    const rows = scoped.map((t) => {
      const person = staff.find((s) => s.id === t.staff_id);
      const cells = [t.title, person?.name || "", person?.department || "", t.status, t.priority, t.target, t.due_date];
      const photoCell = t.photo_data
        ? `<img src="${t.photo_data}" alt="foto" class="task-photo"/>`
        : `<span class="no-photo">–</span>`;
      return `<tr>${cells.map((c) => `<td>${String(c || "").replaceAll("<", "&lt;")}</td>`).join("")}<td class="photo-cell">${photoCell}</td></tr>`;
    }).join("");
    const win = window.open("", "_blank");
    if (!win) return toast.error("Izinkan pop-up untuk membuat PDF");
    win.document.write(`<html><head><meta charset="UTF-8"><title>LOKA-Kin - Laporan ${periodTitle[period]}</title><style>@page{size:A4 landscape;margin:14mm}body{font-family:Arial;color:#111827;margin:0}h1{font-size:20px;margin:0 0 6px}p{font-size:11px;margin:0 0 16px}.report-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:10px}.report-table td,.report-table th{border:1px solid #cbd5e1;padding:7px;text-align:left;vertical-align:top;word-break:break-word}.report-table th{background:#e8f0ff}.report-table col.c-title{width:16%}.report-table col.c-staff{width:12%}.report-table col.c-dept{width:12%}.report-table col.c-status{width:7%}.report-table col.c-prio{width:8%}.report-table col.c-target{width:11%}.report-table col.c-due{width:9%}.report-table col.c-photo{width:15%}.photo-cell{text-align:center;padding:4px}.task-photo{max-width:110px;max-height:80px;object-fit:cover;border-radius:4px;border:1px solid #dbe3ee}.no-photo{color:#94a3b8;font-size:10px}.signature-table{border-collapse:collapse;width:100%;table-layout:fixed;margin-top:55px;font-size:12px}.signature-table td{border:0;width:50%;text-align:center;vertical-align:top;padding:4px 16px;line-height:1.25}.signature-table .signature-space td{height:88px;padding:0}</style></head><body><h1>LOKA-Kin · Laporan ${periodTitle[period]}</h1><p>${label} · Total ${scoped.length} laporan</p><table class="report-table"><colgroup><col class="c-title"/><col class="c-staff"/><col class="c-dept"/><col class="c-status"/><col class="c-prio"/><col class="c-target"/><col class="c-due"/><col class="c-photo"/></colgroup><thead><tr><th>Judul</th><th>Staf</th><th>Departemen</th><th>Status</th><th>Prioritas</th><th>Target</th><th>Tenggat</th><th>Foto</th></tr></thead><tbody>${rows}</tbody></table>${signatureHtml}<script>window.addEventListener('load',function(){setTimeout(function(){window.focus();window.print();},300);});<\/script></body></html>`);
    win.document.close();
    toast.success(`Dialog cetak PDF ${periodTitle[period].toLowerCase()} dibuka`);
  };

  const handleExportConfirm = ({ period, refDate }) => {
    if (exportMode === "excel") runExportExcel(period, refDate);
    else if (exportMode === "pdf") runExportPdf(period, refDate);
    setExportMode(null);
  };

  const nav = [
    { id: "overview", label: "Ringkasan", icon: LayoutDashboard },
    { id: "board", label: "Laporan harian", icon: ClipboardList },
    { id: "staff", label: "Daftar staf", icon: Users },
    { id: "analytics", label: "Analitik", icon: BarChart3 },
  ];
  const today = currentDate();
  const go = (id) => { setActive(id); setMobileOpen(false); };

  return (
    <div className="app-shell">
      <Toaster position="top-right" />
      <aside className={mobileOpen ? "sidebar mobile-visible" : "sidebar"}>
        <div className="brand">
          <div className="brand-mark">LK</div>
          <div><b>LOKA-Kin</b><small>Kinerja harian</small></div>
        </div>
        <div className="side-label">RUANG KERJA</div>
        <nav>
          {nav.map((n) => {
            const Icon = n.icon;
            return (
              <button className={active === n.id ? "nav-item active" : "nav-item"} data-testid={`nav-${n.id}`} key={n.id} onClick={() => go(n.id)}>
                <Icon size={17} />{n.label}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="sync-mini">
            <span className="live-dot" />Database aktif<strong>MongoDB lokal</strong>
          </div>
          <button className="nav-item" data-testid="nav-settings" onClick={() => toast.info("Pengaturan segera tersedia")}>
            <Settings2 size={17} />Pengaturan
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <button className="mobile-menu" data-testid="mobile-menu-button" onClick={() => setMobileOpen(!mobileOpen)}><Menu size={20} /></button>
          <div className="breadcrumb">LOKA-Kin <span>/</span> {nav.find((n) => n.id === active)?.label}</div>
          <div className="top-actions">
            <span className="today" data-testid="today-label">{today}</span>
            <button className="export-btn" data-testid="export-excel-button" onClick={() => setExportMode("excel")}><FileSpreadsheet size={16} /> Excel</button>
            <button className="export-btn" data-testid="export-pdf-button" onClick={() => setExportMode("pdf")}><FileText size={16} /> PDF</button>
            <button className="theme-toggle" data-testid="theme-toggle-button" onClick={() => setDark(!dark)}>
              {dark ? <Sun size={17} /> : <Moon size={17} />}
              <span>{dark ? "Light" : "Dark"}</span>
            </button>
          </div>
        </header>
        <div className="content">
          {active === "overview" && <Overview analytics={analytics} tasks={tasks} staffCount={analytics.total_staff || staff.length} onGo={() => go("board")} />}
          {active === "board" && (
            <>
              <PageIntro title="Laporan harian" desc="Pantau progres pekerjaan tim dalam satu ruang kerja."
                action={<button className="primary-btn" data-testid="add-task-button" onClick={() => setModal({})}><Plus size={17} /> Tambah laporan</button>} />
              <div className="toolbar">
                <div className="search"><Search size={17} /><input data-testid="task-search-input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Cari laporan..." /></div>
                <select className="filter" data-testid="staff-filter-select" value={selectedStaff} onChange={(e) => setSelectedStaff(e.target.value)}>
                  <option value="all">Semua staf</option>
                  {staff.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                <span className="result-count" data-testid="task-count">{filtered.length} laporan aktif</span>
              </div>
              <div className="kanban">
                {columns.map((col) => (
                  <section className="column" data-testid={`column-${col.key}`} key={col.key}>
                    <div className="column-head">
                      <div>
                        <h3><span className={`column-dot ${col.color}`} />{col.label}<em data-testid={`count-${col.key}`}>{filtered.filter((t) => t.status === col.key).length}</em></h3>
                        <p>{col.hint}</p>
                      </div>
                      <button className="add-column" data-testid={`add-${col.key}-button`} onClick={() => setModal({ status: col.key })}><Plus size={17} /></button>
                    </div>
                    <div className="task-list">
                      {filtered.filter((t) => t.status === col.key).map((t) => <TaskCard task={t} staff={staff} onEdit={setModal} key={t.id} />)}
                      {!filtered.some((t) => t.status === col.key) && <div className="empty-state">Belum ada laporan</div>}
                    </div>
                  </section>
                ))}
              </div>
            </>
          )}
          {active === "staff" && <StaffPage staff={staff} tasks={tasks} onAdd={() => setModal({ staffModal: true })} onDelete={deleteStaff} />}
          {active === "analytics" && <Analytics analytics={analytics} />}
        </div>
      </main>
      {modal?.staffModal
        ? <StaffModal onClose={() => setModal(null)} onSave={addStaff} />
        : modal && <TaskModal task={modal.id ? modal : null} staff={staff} onClose={() => setModal(null)} onSave={save} />}
      {exportMode && <ExportDialog mode={exportMode} onClose={() => setExportMode(null)} onConfirm={handleExportConfirm} />}
    </div>
  );
}
