import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  AlertCircle, ArrowRight, Award, BarChart3, Building2, Calendar, Camera, CheckCircle2, ClipboardList, Clock, Download, FileSpreadsheet, FileText,
  HeartHandshake, History, Layers, LayoutDashboard, Menu, Moon, Plus, Printer, Search, Settings2, Stethoscope, Sun, Target, Trash2, TrendingUp, Users, X,
} from "lucide-react";
import { Toaster, toast } from "sonner";
import "@/App.css";

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : "/api";
const columns = [
  { key: "todo", label: "To Do List", color: "blue", hint: "Daftar rencana tugas yang akan dikerjakan" },
  { key: "doing", label: "Doing", color: "amber", hint: "Sedang dikerjakan" },
  { key: "finish", label: "Finish", color: "green", hint: "Sudah diselesaikan" },
];
const departments = [
  "Admin", "Bendahara", "Perencanaan", "Informasi dan Humas",
  "Layanan Rehabilitasi Medis", "Layanan Rehabilitasi Sosial", "Umum",
  "Sarana & Prasarana", "Clinical Supervisor",
];
const currentDate = () =>
  new Intl.DateTimeFormat("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date());

const pad = (n) => String(n).padStart(2, "0");
const toDateInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

const toDateTimeInput = (d = new Date()) => {
  if (!d) return "";
  if (typeof d === "string") {
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(d)) return d.slice(0, 16);
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(d)) return d.slice(0, 16).replace(" ", "T");
    const parsed = new Date(d);
    if (!isNaN(parsed.getTime())) d = parsed;
    else return "";
  }
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const formatDisplayDateTime = (val) => {
  if (!val) return "";
  try {
    const clean = val.includes("T") ? val : val.replace(" ", "T");
    const d = new Date(clean);
    if (isNaN(d.getTime())) return val;
    return new Intl.DateTimeFormat("id-ID", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return val;
  }
};

const statusLabelMap = { todo: "To Do List", plan: "To Do List", doing: "Doing", finish: "Finish" };

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

function TaskCard({ task, staff, onEdit, onTransition }) {
  const person = staff.find((s) => s.id === task.staff_id);
  const normalizedStatus = task.status === "plan" ? "todo" : (task.status || "todo");

  const statusTime = normalizedStatus === "todo"
    ? (task.todo_at || task.created_at)
    : normalizedStatus === "doing"
      ? (task.doing_at || task.status_updated_at || task.todo_at)
      : (task.finish_at || task.status_updated_at);

  const statusLabel = statusLabelMap[normalizedStatus] || normalizedStatus;
  const badgeColor = normalizedStatus === "todo" ? "blue" : normalizedStatus === "doing" ? "amber" : "green";

  return (
    <div
      className="task-card"
      data-testid={`task-card-${task.id}`}
      onClick={() => onEdit(task)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onEdit(task); }}
    >
      <div className="task-top">
        <span className={`priority ${task.priority.toLowerCase()}`}>{task.priority}</span>
        <span className="task-menu">{task.photo_data ? <Camera size={14} /> : "•••"}</span>
      </div>
      <strong data-testid="task-title">{task.title}</strong>

      <div className="task-target-highlight" data-testid="task-target">
        <Target size={13} style={{ flexShrink: 0, marginTop: 2, color: "#2563eb" }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>Target Riil:</span>
          <strong style={{ wordBreak: "break-word", fontSize: 12 }}>{task.target || "Wajib ditentukan"}</strong>
        </div>
        {task.target_history && task.target_history.length > 1 && (
          <span className="history-count" title={`Target riil telah disesuaikan ${task.target_history.length} kali`}>
            <History size={10} style={{ display: "inline", marginRight: 2 }} />
            {task.target_history.length}x
          </span>
        )}
      </div>

      {statusTime && (
        <div className={`status-time-badge ${badgeColor}`} data-testid={`status-time-${task.id}`}>
          <Clock size={11} />
          <span>{statusLabel}: {formatDisplayDateTime(statusTime)}</span>
        </div>
      )}

      <div className="task-bottom">
        <span className="person"><Avatar name={person?.name} />{person?.name?.split(" ").slice(0, 2).join(" ")}</span>
        <span className="due">{task.due_date || "Tanpa tenggat"}</span>
      </div>

      {onTransition && (
        <div className="card-actions">
          {normalizedStatus === "todo" && (
            <button
              type="button"
              className="card-action-btn doing"
              data-testid={`quick-doing-${task.id}`}
              title="Ubah status ke Doing & wajib perbarui target riil"
              onClick={(e) => {
                e.stopPropagation();
                onTransition(task, "doing");
              }}
            >
              <ArrowRight size={13} /> Mulai (Doing)
            </button>
          )}

          {normalizedStatus === "doing" && (
            <>
              <button
                type="button"
                className="card-action-btn finish"
                data-testid={`quick-finish-${task.id}`}
                title="Selesaikan tugas & wajib isi capaian riil akhir"
                onClick={(e) => {
                  e.stopPropagation();
                  onTransition(task, "finish");
                }}
              >
                <CheckCircle2 size={13} /> Selesaikan (Finish)
              </button>
              <button
                type="button"
                className="card-action-btn revert"
                data-testid={`quick-revert-${task.id}`}
                title="Kembalikan ke To Do List"
                onClick={(e) => {
                  e.stopPropagation();
                  onTransition(task, "todo");
                }}
              >
                &larr; To Do
              </button>
            </>
          )}

          {normalizedStatus === "finish" && (
            <button
              type="button"
              className="card-action-btn revert"
              data-testid={`quick-reopen-${task.id}`}
              title="Buka kembali ke status Doing"
              onClick={(e) => {
                e.stopPropagation();
                onTransition(task, "doing");
              }}
            >
              Buka kembali (Doing)
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function StatusTransitionModal({ transitionData, staff, onClose, onConfirm }) {
  const task = transitionData?.task || {};
  const nextStatus = transitionData?.nextStatus || "todo";
  const person = staff.find((s) => s.id === task.staff_id);
  const curStatus = task.status === "plan" ? "todo" : (task.status || "todo");

  const [realTarget, setRealTarget] = useState("");
  const [transitionTime, setTransitionTime] = useState(() => toDateTimeInput(new Date()));
  const [note, setNote] = useState("");

  if (!transitionData) return null;

  const nextLabel = statusLabelMap[nextStatus] || nextStatus;
  const curLabel = statusLabelMap[curStatus] || curStatus;

  const targetLabel = nextStatus === "doing"
    ? "Target Riil Progres (Doing) *"
    : nextStatus === "finish"
      ? "Target Riil Capaian Akhir (Finish) *"
      : "Target Riil Rencana (To Do List) *";

  const placeholder = nextStatus === "doing"
    ? "Contoh: 5 dari 10 berkas telah diverifikasi (kondisi riil progres pengerjaan)..."
    : nextStatus === "finish"
      ? "Contoh: 10 berkas 100% tuntas diverifikasi dan terarsip (kondisi riil hasil akhir)..."
      : "Contoh: 10 laporan layanan harian...";

  const handleSave = () => {
    if (!realTarget.trim()) {
      return toast.error("Kolom target wajib diisi sesuai kondisi riil terkini!");
    }
    if (!transitionTime) {
      return toast.error("Tanggal & jam perubahan status wajib diisi!");
    }

    onConfirm({
      task,
      nextStatus,
      realTarget: realTarget.trim(),
      transitionTime,
      note: note.trim(),
    });
  };

  return (
    <div className="modal-backdrop" data-testid="status-transition-modal">
      <div className="modal" style={{ maxWidth: 540 }}>
        <div className="modal-head">
          <div>
            <span className="eyebrow">PERUBAHAN STATUS &amp; TARGET RIIL</span>
            <h2>Ubah Status ke {nextLabel}</h2>
          </div>
          <button className="icon-button" data-testid="close-transition-modal" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Info Tugas & Perpindahan */}
          <div style={{ background: "var(--surface-2)", border: "1px solid var(--line)", borderRadius: 8, padding: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>{task.title}</div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 8 }}>
              Penanggung Jawab: <b>{person?.name || "Staf"}</b> ({person?.department || "-"})
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, fontWeight: 600 }}>
              <span className={`status-pill status-${curStatus}`}>{curLabel}</span>
              <ArrowRight size={14} />
              <span className={`status-pill status-${nextStatus}`}>{nextLabel}</span>
            </div>
          </div>

          {/* Target Sebelumnya */}
          <div className="previous-target-display">
            <span>Target pada status sebelumnya ({curLabel}):</span>
            <strong>{task.target || "Belum ditentukan"}</strong>
          </div>

          {/* Alert Peringatan Wajib Isi Target Riil */}
          <div className="target-change-alert warn">
            <AlertCircle size={17} style={{ flexShrink: 0, marginTop: 1 }} />
            <div>
              <strong>Kewajiban Pengisian Target Riil:</strong>
              <div>
                Setiap perubahan status wajib disertai penyesuaian target sesuai kondisi nyata pekerjaan staf di lapangan saat ini.
              </div>
            </div>
          </div>

          {/* Form Input Target Riil Wajib */}
          <label style={{ display: "flex", flexDirection: "column", gap: 5, fontSize: 12, fontWeight: 600 }}>
            <span>{targetLabel}</span>
            <input
              type="text"
              autoFocus
              data-testid="real-target-input"
              value={realTarget}
              onChange={(e) => setRealTarget(e.target.value)}
              placeholder={placeholder}
              style={{
                padding: "9px 12px",
                borderRadius: 6,
                border: "1px solid var(--line)",
                background: "var(--input-bg)",
                color: "var(--input-ink)",
                fontSize: 13,
              }}
              required
            />
            <small style={{ color: "var(--muted)", fontWeight: 400, fontSize: 11 }}>
              * Staf wajib mengisi target riil yang aktual sebelum status dapat disimpan.
            </small>
          </label>

          {/* Tanggal & Jam Perubahan Status */}
          <label style={{ display: "flex", flexDirection: "column", gap: 5, fontSize: 12, fontWeight: 600 }}>
            <span>Tanggal &amp; Jam Perubahan Status *</span>
            <input
              type="datetime-local"
              data-testid="transition-time-input"
              value={transitionTime}
              onChange={(e) => setTransitionTime(e.target.value)}
              style={{
                padding: "9px 12px",
                borderRadius: 6,
                border: "1px solid var(--line)",
                background: "var(--input-bg)",
                color: "var(--input-ink)",
                fontSize: 13,
              }}
              required
            />
          </label>

          {/* Catatan / Keterangan Tambahan */}
          <label style={{ display: "flex", flexDirection: "column", gap: 5, fontSize: 12, fontWeight: 600 }}>
            <span>Catatan Kondisi Riil / Keterangan Progres (Opsional)</span>
            <textarea
              data-testid="transition-note-input"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Tambahkan keterangan kondisi nyata pelaksanaan tugas di lapangan..."
              rows={2}
              style={{
                padding: "8px 12px",
                borderRadius: 6,
                border: "1px solid var(--line)",
                background: "var(--input-bg)",
                color: "var(--input-ink)",
                fontSize: 12,
                resize: "vertical",
              }}
            />
          </label>
        </div>

        <div className="modal-actions" style={{ marginTop: 20 }}>
          <button className="secondary-btn" data-testid="cancel-transition-button" onClick={onClose}>
            Batal
          </button>
          <button className="primary-btn" data-testid="confirm-transition-button" onClick={handleSave}>
            Simpan Status &amp; Target Riil
          </button>
        </div>
      </div>
    </div>
  );
}

function TaskModal({ task, staff, onClose, onSave }) {
  const isEditing = Boolean(task?.id);
  const nowInput = toDateTimeInput(new Date());

  const initialStatus = task ? (task.status === "plan" ? "todo" : (task.status || "todo")) : "todo";
  const initialTarget = task ? (task.target || "") : "";

  const [form, setForm] = useState(() => {
    if (task) {
      return {
        ...task,
        status: initialStatus,
        target: task.target || "",
        target_history: task.target_history || (task.target ? [{
          status: initialStatus,
          target: task.target,
          timestamp: task.status_updated_at || task.todo_at || task.created_at || nowInput,
          note: "Target awal",
        }] : []),
        todo_at: task.todo_at || task.created_at || nowInput,
        doing_at: task.doing_at || (initialStatus === "doing" || initialStatus === "finish" ? nowInput : ""),
        finish_at: task.finish_at || (initialStatus === "finish" ? nowInput : ""),
      };
    }
    return {
      title: "",
      staff_id: staff[0]?.id || "",
      status: "todo",
      target: "",
      target_history: [],
      priority: "Sedang",
      due_date: "",
      notes: "",
      proof_link: "",
      photo_data: "",
      photo_name: "",
      todo_at: nowInput,
      doing_at: "",
      finish_at: "",
    };
  });

  const statusChanged = isEditing && form.status !== initialStatus;
  const targetLabel = form.status === "doing"
    ? "Target Riil Progres (Doing) *"
    : form.status === "finish"
      ? "Target Riil Capaian Akhir (Finish) *"
      : "Target Riil Rencana (To Do List) *";

  const targetPlaceholder = form.status === "doing"
    ? "Contoh: 5 dari 10 berkas telah diverifikasi (kondisi riil progres)..."
    : form.status === "finish"
      ? "Contoh: 10 berkas 100% selesai dan diarsipkan (kondisi riil akhir)..."
      : "Contoh: 10 berkas layanan harian...";

  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleStatusChange = (e) => {
    const nextStatus = e.target.value;
    const currentNow = toDateTimeInput(new Date());
    setForm((prev) => {
      const updated = { ...prev, status: nextStatus };
      if (nextStatus === "doing" && !prev.doing_at) {
        updated.doing_at = currentNow;
      }
      if (nextStatus === "finish") {
        if (!prev.doing_at) updated.doing_at = prev.todo_at || currentNow;
        if (!prev.finish_at) updated.finish_at = currentNow;
      }
      return updated;
    });
  };

  const uploadPhoto = (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    if (!file.type.startsWith("image/")) return toast.error("Pilih file foto kegiatan");
    if (file.size > 5 * 1024 * 1024) return toast.error("Ukuran foto maksimal 5 MB");
    const reader = new FileReader();
    reader.onload = () => setForm((p) => ({ ...p, photo_data: reader.result, photo_name: file.name }));
    reader.readAsDataURL(file);
  };

  const handleSave = () => {
    if (!form.title.trim()) return toast.error("Nama tugas wajib diisi");
    if (!form.target.trim()) {
      return toast.error("Kolom target wajib diisi sesuai kondisi riil tugas.");
    }
    if (!form.todo_at) return toast.error("Tanggal & jam To Do List wajib diisi");

    if (form.status === "doing" && !form.doing_at) {
      return toast.error("Tanggal & jam status Doing wajib diisi sebelum menyimpan");
    }
    if (form.status === "finish" && !form.finish_at) {
      return toast.error("Tanggal & jam status Finish wajib diisi sebelum menyimpan");
    }

    const payload = { ...form };
    const currentNow = toDateTimeInput(new Date());

    // Rekam perubahan target riil ke riwayat
    if (statusChanged || (isEditing && form.target.trim() !== initialTarget.trim())) {
      const transitionTime = form.status === "finish"
        ? (form.finish_at || currentNow)
        : form.status === "doing"
          ? (form.doing_at || currentNow)
          : (form.todo_at || currentNow);

      payload.target_history = [
        ...(form.target_history || []),
        {
          status: form.status,
          target: form.target.trim(),
          timestamp: transitionTime,
          note: form.notes ? `Catatan: ${form.notes.slice(0, 50)}` : `Target riil saat status ${form.status.toUpperCase()}`,
        },
      ];
    } else if (!isEditing) {
      payload.target_history = [
        {
          status: "todo",
          target: form.target.trim(),
          timestamp: form.todo_at || currentNow,
          note: "Target awal To Do List",
        },
      ];
    }

    onSave(payload);
  };

  return (
    <div className="modal-backdrop" data-testid="task-modal">
      <div className="modal">
        <div className="modal-head">
          <div>
            <span className="eyebrow">LAPORAN HARIAN</span>
            <h2>{isEditing ? "Edit Laporan Tugas" : "Tambah To Do List Baru"}</h2>
          </div>
          <button className="icon-button" data-testid="task-modal-close" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="form-grid">
          <label>Nama tugas<input autoFocus data-testid="task-title-input" name="title" value={form.title} onChange={change} placeholder="Contoh: Rekap laporan layanan" /></label>
          <label>Penanggung jawab<select data-testid="task-staff-select" name="staff_id" value={form.staff_id} onChange={change}>{staff.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.department}</option>)}</select></label>
          <label>
            Status
            {isEditing ? (
              <select data-testid="task-status-select" name="status" value={form.status} onChange={handleStatusChange}>
                {columns.map((c) => (
                  <option key={c.key} value={c.key}>{c.label}</option>
                ))}
              </select>
            ) : (
              <select data-testid="task-status-select" name="status" value="todo" disabled title="Laporan baru wajib diawali dengan status To Do List">
                <option value="todo">To Do List (Wajib input awal)</option>
              </select>
            )}
          </label>
          <label>Prioritas<select data-testid="task-priority-select" name="priority" value={form.priority} onChange={change}><option>Rendah</option><option>Sedang</option><option>Tinggi</option></select></label>

          {/* Banner Peringatan jika status diubah */}
          {statusChanged && (
            <div className="target-change-alert warn full">
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <b>Perubahan Status ke {statusLabelMap[form.status] || form.status} Terdeteksi:</b>
                <div>
                  Kondisi riil pekerjaan telah berubah. Staf <b>wajib memperbarui kolom Target</b> di bawah sesuai capaian atau progres riil saat ini.
                </div>
              </div>
            </div>
          )}

          <label>
            <span>{targetLabel}</span>
            <input
              data-testid="task-target-input"
              name="target"
              value={form.target}
              onChange={change}
              placeholder={targetPlaceholder}
              required
            />
            <small style={{ color: "var(--muted)", fontSize: 10 }}>* Wajib diisi sesuai kondisi riil tugas</small>
          </label>
          <label>Tenggat<input data-testid="task-due-input" name="due_date" value={form.due_date} onChange={change} placeholder="Contoh: Hari ini" /></label>

          {/* Section Pencatatan Tanggal & Jam Status */}
          <div className="status-time-section full">
            <div className="status-time-title">
              <Clock size={14} />
              <span>Pencatatan Tanggal &amp; Jam Status (Periksa &amp; atur sebelum simpan)</span>
            </div>

            {!isEditing ? (
              <div className="status-notice">
                <AlertCircle size={15} />
                <span>
                  Laporan harian baru <b>wajib diinputkan ke To Do List</b> terlebih dahulu dan tidak dapat langsung berstatus Doing atau Finish.
                </span>
              </div>
            ) : (
              <div className="status-notice info-edit">
                <CheckCircle2 size={15} />
                <span>
                  Laporan telah tercatat di To Do List. Tanggal &amp; jam untuk setiap status pengerjaan dapat disesuaikan sebelum menyimpan.
                </span>
              </div>
            )}

            <div className="status-time-grid">
              <label>
                <span>Tanggal &amp; Jam To Do List *</span>
                <input
                  type="datetime-local"
                  data-testid="task-todo-time-input"
                  name="todo_at"
                  value={toDateTimeInput(form.todo_at)}
                  onChange={change}
                  required
                />
              </label>

              {(form.status === "doing" || form.status === "finish") && (
                <label>
                  <span>Tanggal &amp; Jam Mulai (Doing) *</span>
                  <input
                    type="datetime-local"
                    data-testid="task-doing-time-input"
                    name="doing_at"
                    value={toDateTimeInput(form.doing_at)}
                    onChange={change}
                    required
                  />
                </label>
              )}

              {form.status === "finish" && (
                <label>
                  <span>Tanggal &amp; Jam Selesai (Finish) *</span>
                  <input
                    type="datetime-local"
                    data-testid="task-finish-time-input"
                    name="finish_at"
                    value={toDateTimeInput(form.finish_at)}
                    onChange={change}
                    required
                  />
                </label>
              )}
            </div>
          </div>

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

          {/* Histori Target & Status */}
          {form.target_history && form.target_history.length > 0 && (
            <div className="target-history-box full" data-testid="task-target-history">
              <h4><History size={14} /> Riwayat Perubahan Target Riil &amp; Status ({form.target_history.length})</h4>
              <div className="target-history-list">
                {form.target_history.map((h, i) => (
                  <div className="target-history-entry" key={i}>
                    <div className="target-history-entry-left">
                      <span className={`status-pill status-${h.status}`}>{statusLabelMap[h.status] || h.status}</span>
                      <strong>{h.target}</strong>
                      {h.note && <span style={{ color: "var(--muted)", fontSize: 10 }}>— {h.note}</span>}
                    </div>
                    <div className="target-history-entry-right">
                      {formatDisplayDateTime(h.timestamp)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="modal-actions">
          <button className="secondary-btn" data-testid="task-cancel-button" onClick={onClose}>Batal</button>
          <button className="primary-btn" data-testid="task-save-button" onClick={handleSave}>Simpan tugas</button>
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

function ExportDialog({ mode, staff, onClose, onConfirm }) {
  const [period, setPeriod] = useState("harian");
  const [refDate, setRefDate] = useState(toDateInput(new Date()));
  const [staffId, setStaffId] = useState("all");
  const { label } = useMemo(() => computeRange(period, refDate), [period, refDate]);
  const periods = [
    { key: "harian", label: "Harian", hint: "Laporan tanggal terpilih" },
    { key: "mingguan", label: "Mingguan", hint: "Senin – Minggu di pekan tanggal terpilih" },
    { key: "bulanan", label: "Bulanan", hint: "Seluruh laporan pada bulan tanggal terpilih" },
  ];
  const selectedStaffObj = staff.find((s) => s.id === staffId);

  return (
    <div className="modal-backdrop" data-testid="export-dialog">
      <div className="modal export-modal">
        <div className="modal-head">
          <div>
            <span className="eyebrow">EKSPOR {mode.toUpperCase()}</span>
            <h2>Pilih periode &amp; staf laporan</h2>
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
        <div className="export-fields">
          <label className="export-field">
            <span><Calendar size={14} /> Tanggal acuan</span>
            <input
              type="date"
              data-testid="export-date-input"
              value={refDate}
              onChange={(e) => setRefDate(e.target.value)}
            />
          </label>
          <label className="export-field">
            <span><Users size={14} /> Staf penanggung jawab</span>
            <select
              data-testid="export-staff-select"
              value={staffId}
              onChange={(e) => setStaffId(e.target.value)}
            >
              <option value="all">Semua Staf (Laporan per Staf)</option>
              {staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.department}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="export-summary" data-testid="export-range-label">
          Rentang: <b>{label}</b>
          <br />
          Target: <b>{selectedStaffObj ? `${selectedStaffObj.name} (${selectedStaffObj.department})` : "Seluruh Staf (Dikelompokkan per Penanggung Jawab)"}</b>
        </div>
        <div className="modal-actions">
          <button className="secondary-btn" data-testid="export-cancel" onClick={onClose}>Batal</button>
          <button
            className="primary-btn"
            data-testid="export-confirm"
            onClick={() => onConfirm({ period, refDate, staffId })}
          >
            {mode === "excel" ? "Unduh Excel" : "Buka Pratinjau & Cetak PDF"}
          </button>
        </div>
      </div>
    </div>
  );
}

const printDocumentHtml = (htmlContent) => {
  let frame = document.getElementById("hidden-print-frame");
  if (!frame) {
    frame = document.createElement("iframe");
    frame.id = "hidden-print-frame";
    frame.style.position = "fixed";
    frame.style.right = "0";
    frame.style.bottom = "0";
    frame.style.width = "0";
    frame.style.height = "0";
    frame.style.border = "0";
    document.body.appendChild(frame);
  }
  const frameDoc = frame.contentWindow.document;
  frameDoc.open();
  frameDoc.write(htmlContent);
  frameDoc.close();
  setTimeout(() => {
    try {
      frame.contentWindow.focus();
      frame.contentWindow.print();
    } catch {
      window.print();
    }
  }, 350);
};

const downloadReportFile = (content, filename, type = "text/html;charset=utf-8") => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  setTimeout(() => {
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, 150);
};

function PdfPreviewModal({ preview, onClose }) {
  if (!preview) return null;
  const { title, fullHtml, bodyHtml, sigHtml, filename } = preview;

  const handlePrint = () => {
    printDocumentHtml(fullHtml);
  };

  const handleDownload = () => {
    downloadReportFile(fullHtml, filename);
    toast.success(`Dokumen ${filename} berhasil diunduh`);
  };

  return (
    <div className="pdf-modal-backdrop" data-testid="pdf-preview-modal">
      <div className="pdf-modal">
        <div className="pdf-modal-topbar">
          <div className="pdf-modal-title">
            <FileText size={18} />
            <span>Pratinjau Dokumen PDF · {title}</span>
          </div>
          <div className="pdf-modal-actions">
            <button
              className="primary-btn"
              data-testid="print-pdf-button"
              onClick={handlePrint}
              title="Cetak langsung atau Simpan sebagai PDF tanpa pop-up"
            >
              <Printer size={16} /> Cetak / Simpan PDF
            </button>
            <button
              className="secondary-btn"
              data-testid="download-pdf-doc-button"
              onClick={handleDownload}
              title="Unduh file dokumen laporan"
            >
              <Download size={16} /> Unduh Dokumen
            </button>
            <button className="icon-button" data-testid="close-pdf-modal" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="pdf-modal-body">
          <div className="pdf-paper">
            <h1>LOKA-Kin · {title}</h1>
            <div dangerouslySetInnerHTML={{ __html: bodyHtml }} />
            <div dangerouslySetInnerHTML={{ __html: sigHtml }} />
          </div>
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
  const counts = analytics.counts || {};
  const percentages = analytics.percentages || {};
  const todoCount = counts.todo ?? counts.plan ?? 0;
  const doingCount = counts.doing ?? 0;
  const finishCount = counts.finish ?? 0;

  return (
    <>
      <PageIntro
        title="Tabik Pun Staf Loka Rehabilitasi Narkotika Kalianda"
        desc="Berikut ringkasan kinerja tim untuk hari ini."
        action={<button className="primary-btn" data-testid="overview-add-button" onClick={onGo}><Plus size={17} /> Buat laporan</button>}
      />
      <div className="metric-grid">
        <Metric label="Total laporan" value={analytics.total_tasks || tasks.length} detail="Laporan aktif hari ini" icon={ClipboardList} tone="blue" />
        <Metric label="Selesai" value={`${analytics.completion_rate || 0}%`} detail={`${finishCount} laporan finish`} icon={CheckCircle2} tone="green" />
        <Metric label="Sedang berjalan" value={doingCount} detail="Dalam pengerjaan tim" icon={BarChart3} tone="amber" />
        <Metric label="To Do List" value={todoCount} detail="Daftar antrean tugas" icon={Clock} tone="violet" />
      </div>
      <div className="overview-grid">
        <section className="surface chart-panel">
          <div className="section-head">
            <div><span className="eyebrow">PROGRES WORKFLOW</span><h2>Distribusi laporan</h2></div>
            <button className="text-btn" data-testid="view-board-button" onClick={onGo}>Lihat board →</button>
          </div>
          <div className="progress-chart">
            {columns.map((c) => {
              const pct = percentages[c.key] ?? (c.key === "todo" ? percentages.plan : 0) ?? 0;
              return (
                <div className="progress-row" key={c.key}>
                  <span>{c.label}</span>
                  <div className="progress-track"><i className={c.color} style={{ width: `${pct}%` }} /></div>
                  <b>{pct}%</b>
                </div>
              );
            })}
          </div>
        </section>
        <section className="surface recent-panel">
          <div className="section-head">
            <div><span className="eyebrow">AKTIVITAS TERBARU</span><h2>Laporan masuk</h2></div>
            <span className="live-label"><span className="live-dot" />Live</span>
          </div>
          {tasks.slice(0, 3).map((t) => (
            <div className="recent-item" key={t.id}>
              <span className={`status-icon ${t.status === "plan" ? "todo" : t.status}`}>{t.status === "finish" ? "✓" : "•"}</span>
              <div>
                <strong>{t.title}</strong>
                <small>{t.status === "finish" ? "Diselesaikan" : t.status === "doing" ? "Sedang dikerjakan" : "To Do List"} · {formatDisplayDateTime(t.status_updated_at || t.todo_at || t.created_at)}</small>
              </div>
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

function KpiDashboard({ kpiList = [] }) {
  const [activeTab, setActiveTab] = useState("all");

  const iconMap = {
    Building2: Building2,
    Stethoscope: Stethoscope,
    HeartHandshake: HeartHandshake,
  };

  const displayedSections = activeTab === "all"
    ? kpiList
    : kpiList.filter((s) => s.id === activeTab);

  return (
    <div className="kpi-container" data-testid="kpi-dashboard">
      <div className="kpi-header">
        <div>
          <span className="eyebrow">KEY PERFORMANCE INDICATORS (KPI) LOKA KALIANDA</span>
          <h2 style={{ margin: "4px 0", fontSize: 20, fontWeight: 700, color: "var(--ink)" }}>
            Indikator Kinerja &amp; Standar Mutu Layanan
          </h2>
          <p style={{ margin: 0, fontSize: 12, color: "var(--muted)" }}>
            Evaluasi capaian mutu komprehensif bagian Umum, Layanan Medis, dan Layanan Sosial berbasis agregasi laporan harian staf.
          </p>
        </div>

        {/* Section Filter Tabs */}
        <div className="kpi-tabs" data-testid="kpi-tabs">
          <button
            className={`kpi-tab ${activeTab === "all" ? "active" : ""}`}
            data-testid="kpi-tab-all"
            onClick={() => setActiveTab("all")}
          >
            <Layers size={14} /> Semua Bagian ({kpiList.length})
          </button>
          {kpiList.map((sec) => {
            const Icon = iconMap[sec.icon] || Building2;
            return (
              <button
                key={sec.id}
                className={`kpi-tab ${activeTab === sec.id ? "active" : ""}`}
                data-testid={`kpi-tab-${sec.id}`}
                onClick={() => setActiveTab(sec.id)}
              >
                <Icon size={14} /> {sec.title.replace("Bagian ", "").replace("Layanan Rehabilitasi ", "")}
              </button>
            );
          })}
        </div>
      </div>

      {/* KPI Summary Cards Grid */}
      <div className="kpi-cards-grid">
        {kpiList.map((sec) => {
          const Icon = iconMap[sec.icon] || Building2;
          const isSelected = activeTab === "all" || activeTab === sec.id;
          return (
            <div
              className="kpi-card"
              data-testid={`kpi-card-${sec.id}`}
              key={sec.id}
              style={{
                opacity: isSelected ? 1 : 0.65,
                borderColor: activeTab === sec.id ? "#2563eb" : undefined,
                boxShadow: activeTab === sec.id ? "0 0 0 2px #2563eb33" : undefined,
                cursor: "pointer",
              }}
              onClick={() => setActiveTab(activeTab === sec.id ? "all" : sec.id)}
            >
              <div className="kpi-card-top">
                <div className={`kpi-card-icon ${sec.color}`}>
                  <Icon size={20} />
                </div>
                <span className={`kpi-badge ${sec.overall_tone}`}>
                  <Award size={11} />
                  {sec.overall_badge}
                </span>
              </div>

              <div className="kpi-card-titles">
                <h3>{sec.title}</h3>
                <p>{sec.tagline}</p>
              </div>

              <div className="kpi-score-display">
                <span className="kpi-score-big">{sec.overall_score}%</span>
                <span className="kpi-target-label">
                  Target Mutu: <b>{sec.target_avg}%</b> · Capaian: <b>{sec.achievement_rate}%</b>
                </span>
              </div>

              <div className="kpi-progress-wrap">
                <div className="kpi-progress-track">
                  <div
                    className={`kpi-progress-bar ${sec.color}`}
                    style={{ width: `${Math.min(100, sec.overall_score)}%` }}
                  />
                </div>
              </div>

              <div className="kpi-meta-pills">
                <span>Staf Aktif: <strong>{sec.staff_count} orang</strong></span>
                <span>Tugas Unit: <strong>{sec.task_stats?.finish || 0} Selesai / {sec.task_stats?.total || 0}</strong></span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Detailed Indicators Table per Section */}
      {displayedSections.map((sec) => {
        const Icon = iconMap[sec.icon] || Building2;
        return (
          <div className="kpi-detail-panel" data-testid={`kpi-detail-${sec.id}`} key={sec.id}>
            <div className="kpi-detail-head">
              <div className="kpi-detail-head-left">
                <h3>
                  <Icon size={18} />
                  <span>Rincian Indikator Kinerja &amp; Mutu · {sec.title}</span>
                </h3>
                <p>{sec.tagline} · Evaluasi berbasis {sec.staff_count} staf penanggung jawab</p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className={`kpi-badge ${sec.overall_tone}`}>
                  <TrendingUp size={12} />
                  Skor Mutu: {sec.overall_score}% ({sec.overall_badge})
                </span>
              </div>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table className="kpi-indicators-table">
                <thead>
                  <tr>
                    <th style={{ width: "35%" }}>Indikator Mutu &amp; Kinerja</th>
                    <th style={{ width: "12%", textAlign: "center" }}>Target Standar</th>
                    <th style={{ width: "14%", textAlign: "center" }}>Realisasi Laporan</th>
                    <th style={{ width: "23%" }}>Tingkat Ketercapaian</th>
                    <th style={{ width: "16%", textAlign: "center" }}>Status Mutu</th>
                  </tr>
                </thead>
                <tbody>
                  {sec.indicators?.map((ind) => (
                    <tr key={ind.code} data-testid={`kpi-row-${ind.code.toLowerCase()}`}>
                      <td>
                        <div className="kpi-indicator-name">
                          <span className="kpi-indicator-code">{ind.code} · Bobot {ind.weight}%</span>
                          <span className="kpi-indicator-title">{ind.name}</span>
                          <span className="kpi-indicator-desc">{ind.desc}</span>
                        </div>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <b style={{ fontSize: 13 }}>{ind.target}{ind.unit}</b>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <b style={{ fontSize: 13, color: ind.realization >= ind.target ? "#15803d" : "#b45309" }}>
                          {ind.realization}{ind.unit}
                        </b>
                      </td>
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                            <span>Realisasi vs Target</span>
                            <b>{ind.achievement_rate}%</b>
                          </div>
                          <div className="kpi-progress-track" style={{ height: 6 }}>
                            <div
                              className={`kpi-progress-bar ${ind.status_tone === "green" ? "emerald" : ind.status_tone === "amber" ? "amber" : "blue"}`}
                              style={{ width: `${Math.min(100, ind.achievement_rate)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <span className={`kpi-badge ${ind.status_tone}`}>
                          {ind.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
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
                <li><span className="legend-dot green" /> Selesai · {analytics.percentages?.finish || 0}%</li>
                <li><span className="legend-dot amber" /> Sedang berjalan · {analytics.percentages?.doing || 0}%</li>
                <li><span className="legend-dot blue" /> To Do List · {analytics.percentages?.todo ?? analytics.percentages?.plan ?? 0}%</li>
              </ul>
            </div>
          </div>
        </div>
        <div className="surface breakdown">
          <span className="eyebrow">WORKFLOW BREAKDOWN</span>
          <h2>Posisi seluruh laporan</h2>
          {columns.map((c) => {
            const count = analytics.counts?.[c.key] ?? (c.key === "todo" ? analytics.counts?.plan : 0) ?? 0;
            const pct = analytics.percentages?.[c.key] ?? (c.key === "todo" ? analytics.percentages?.plan : 0) ?? 0;
            return (
              <div className="break-row" key={c.key}>
                <span className={`column-dot ${c.color}`} /><span>{c.label}</span>
                <b>{count}</b><small>{pct}%</small>
              </div>
            );
          })}
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
      <KpiDashboard kpiList={analytics.kpi || []} />
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
  const [pdfPreview, setPdfPreview] = useState(null);
  const [transitionModal, setTransitionModal] = useState(null);
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
      const payload = {
        ...form,
        status: form.status === "plan" ? "todo" : (form.status || "todo"),
      };
      const res = await (modal?.id ? axios.patch(`${API}/tasks/${modal.id}`, payload) : axios.post(`${API}/tasks`, payload));
      setTasks((prev) => modal?.id ? prev.map((t) => t.id === modal.id ? res.data : t) : [res.data, ...prev]);
      setModal(null); await load(); toast.success("Laporan tersimpan");
    } catch (err) {
      const msg = err.response?.data?.detail || "Gagal menyimpan laporan";
      toast.error(msg);
    }
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

  const handleConfirmTransition = async ({ task, nextStatus, realTarget, transitionTime, note }) => {
    const curStatus = task.status === "plan" ? "todo" : (task.status || "todo");
    const existingHistory = [...(task.target_history || [])];
    if (existingHistory.length === 0 && task.target) {
      existingHistory.push({
        status: curStatus,
        target: task.target,
        timestamp: task.status_updated_at || task.todo_at || task.created_at || transitionTime,
        note: "Target awal",
      });
    }

    const updatedHistory = [
      ...existingHistory,
      {
        status: nextStatus,
        target: realTarget,
        timestamp: transitionTime,
        note: note || `Target riil saat status ${statusLabelMap[nextStatus] || nextStatus.toUpperCase()}`,
      },
    ];

    const updatedTask = {
      ...task,
      status: nextStatus,
      target: realTarget,
      target_history: updatedHistory,
      status_updated_at: transitionTime,
    };

    if (nextStatus === "doing") {
      updatedTask.doing_at = transitionTime;
    } else if (nextStatus === "finish") {
      if (!updatedTask.doing_at) updatedTask.doing_at = task.todo_at || transitionTime;
      updatedTask.finish_at = transitionTime;
    } else if (nextStatus === "todo") {
      updatedTask.todo_at = transitionTime;
    }

    try {
      const res = await axios.patch(`${API}/tasks/${task.id}`, updatedTask);
      setTasks((prev) => prev.map((t) => t.id === task.id ? res.data : t));
      setTransitionModal(null);
      await load();
      toast.success(`Status berhasil diubah ke ${statusLabelMap[nextStatus] || nextStatus} dengan target riil terbaru.`);
    } catch (err) {
      const msg = err.response?.data?.detail || "Gagal menyimpan perubahan status dan target riil";
      toast.error(msg);
    }
  };

  const formatExportTime = (val) => (!val ? "-" : formatDisplayDateTime(val));

  const buildRows = (data) => data.map((t) => {
    const person = staff.find((s) => s.id === t.staff_id);
    const norm = t.status === "plan" ? "todo" : (t.status || "todo");
    return [
      t.title,
      person?.name || "",
      person?.department || "",
      statusLabelMap[norm] || norm,
      t.priority,
      t.target,
      formatExportTime(t.todo_at || t.created_at),
      formatExportTime(t.doing_at),
      formatExportTime(t.finish_at),
      t.due_date,
      t.notes,
      t.proof_link,
      t.photo_name ? `Foto: ${t.photo_name}` : "",
    ];
  });

  const getStaffStats = (staffTasks) => {
    const total = staffTasks.length;
    const todo = staffTasks.filter((t) => t.status === "todo" || t.status === "plan").length;
    const doing = staffTasks.filter((t) => t.status === "doing").length;
    const finish = staffTasks.filter((t) => t.status === "finish").length;
    const rate = total > 0 ? Math.round((finish / total) * 100) : 0;
    return { total, todo, doing, finish, rate };
  };

  const periodTitle = { harian: "Harian", mingguan: "Mingguan", bulanan: "Bulanan" };

  const runExportExcel = (period, refDate, staffId = "all") => {
    const { start, end, label } = computeRange(period, refDate);
    const dateScoped = filterTasksByRange(tasks, start, end);
    const targetStaff = staff.find((s) => s.id === staffId);
    const isSingleStaff = Boolean(targetStaff && staffId !== "all");

    let title, filename, bodyHtml, sigHtml;

    if (isSingleStaff) {
      const staffTasks = dateScoped.filter((t) => t.staff_id === staffId);
      const stats = getStaffStats(staffTasks);
      title = `LOKA-Kin · Laporan Kinerja Staf (${periodTitle[period]})`;
      const slug = targetStaff.name.replace(/[^a-zA-Z0-9]/g, "_");
      filename = `loka-kin-${period}-${slug}-${toDateInput(start)}.xls`;

      const rows = staffTasks.map((t, idx) => {
        const norm = t.status === "plan" ? "todo" : (t.status || "todo");
        const historyText = t.target_history && t.target_history.length > 1
          ? t.target_history.map(h => `[${statusLabelMap[h.status] || h.status}] ${h.target}`).join(" → ")
          : "-";
        return [
          idx + 1,
          t.title,
          statusLabelMap[norm] || norm,
          t.priority,
          t.target,
          historyText,
          formatExportTime(t.todo_at || t.created_at),
          formatExportTime(t.doing_at),
          formatExportTime(t.finish_at),
          t.due_date,
          t.notes,
          t.proof_link,
          t.photo_name ? `Foto: ${t.photo_name}` : "",
        ];
      });

      bodyHtml = `
        <div style="margin-bottom:14px;background:#f8fafc;padding:12px;border:1px solid #cbd5e1;border-radius:6px;">
          <table style="width:100%;font-size:11px;border-collapse:collapse;">
            <tr><td style="width:160px;font-weight:bold;">Staf Penanggung Jawab</td><td>: ${targetStaff.name}</td><td style="width:130px;font-weight:bold;">Periode</td><td>: ${periodTitle[period]} (${label})</td></tr>
            <tr><td style="font-weight:bold;">Departemen</td><td>: ${targetStaff.department}</td><td style="font-weight:bold;">Capaian Kinerja</td><td>: Total ${stats.total} Tugas (Selesai: ${stats.finish} [${stats.rate}%], Doing: ${stats.doing}, To Do: ${stats.todo})</td></tr>
          </table>
        </div>
        <table class="report-table">
          <tr>
            <th style="width:30px;">No</th><th>Judul Tugas</th><th>Status</th><th>Prioritas</th><th>Target Riil</th><th>Riwayat Target</th><th>Waktu To Do</th><th>Waktu Doing</th><th>Waktu Selesai</th><th>Tenggat</th><th>Catatan</th><th>Bukti</th><th>Foto</th>
          </tr>
          ${rows.length > 0 ? rows.map((r) => `<tr>${r.map((c, ci) => ci === 0 ? `<td style="text-align:center;">${c}</td>` : `<td>${String(c || "").replaceAll("<", "&lt;")}</td>`).join("")}</tr>`).join("") : '<tr><td colspan="13" style="text-align:center;padding:12px;color:#64748b;">Belum ada laporan kerja pada periode ini</td></tr>'}
        </table>
      `;

      sigHtml = `
        <table class="signature-table">
          <tr><td><b>Mengetahui</b></td><td><b>Kalianda, ${currentDate()}</b></td></tr>
          <tr><td><b>Kepala Loka Rehabilitasi Narkotika Kalianda</b></td><td><b>Penanggung Jawab / Yang Melaporkan</b></td></tr>
          <tr class="signature-space"><td></td><td></td></tr>
          <tr><td><b>Heru Herlambang, S. AP</b></td><td><b>${targetStaff.name}</b></td></tr>
        </table>
      `;
    } else {
      title = `LOKA-Kin · Laporan Kinerja Tim per Staf Penanggung Jawab (${periodTitle[period]})`;
      filename = `loka-kin-${period}-per-staf-${toDateInput(start)}.xls`;

      const activeStaff = staff.filter((s) => dateScoped.some((t) => t.staff_id === s.id));
      const displayStaffList = activeStaff.length > 0 ? activeStaff : staff.slice(0, 5);

      const sectionsHtml = displayStaffList.map((s) => {
        const staffTasks = dateScoped.filter((t) => t.staff_id === s.id);
        const stats = getStaffStats(staffTasks);
        const taskRows = staffTasks.map((t, idx) => {
          const norm = t.status === "plan" ? "todo" : (t.status || "todo");
          const historyText = t.target_history && t.target_history.length > 1
            ? t.target_history.map(h => `[${statusLabelMap[h.status] || h.status}] ${h.target}`).join(" → ")
            : "-";
          return [
            idx + 1,
            t.title,
            statusLabelMap[norm] || norm,
            t.priority,
            t.target,
            historyText,
            formatExportTime(t.todo_at || t.created_at),
            formatExportTime(t.doing_at),
            formatExportTime(t.finish_at),
            t.due_date,
            t.notes,
            t.proof_link,
            t.photo_name ? `Foto: ${t.photo_name}` : "",
          ];
        });

        return `
          <div style="margin-top:20px;">
            <div style="background:#f1f5f9;padding:8px 10px;font-weight:bold;font-size:12px;border:1px solid #cbd5e1;border-bottom:0;">
              Staf: ${s.name} &nbsp;|&nbsp; Departemen: ${s.department} &nbsp;|&nbsp; ${stats.total} Tugas (Selesai: ${stats.finish} [${stats.rate}%], Doing: ${stats.doing}, To Do: ${stats.todo})
            </div>
            <table class="report-table">
              <tr>
                <th style="width:30px;">No</th><th>Judul Tugas</th><th>Status</th><th>Prioritas</th><th>Target Riil</th><th>Riwayat Target</th><th>Waktu To Do</th><th>Waktu Doing</th><th>Waktu Selesai</th><th>Tenggat</th><th>Catatan</th><th>Bukti</th><th>Foto</th>
              </tr>
              ${taskRows.length > 0 ? taskRows.map((r) => `<tr>${r.map((c, ci) => ci === 0 ? `<td style="text-align:center;">${c}</td>` : `<td>${String(c || "").replaceAll("<", "&lt;")}</td>`).join("")}</tr>`).join("") : '<tr><td colspan="13" style="text-align:center;color:#64748b;padding:12px;">Tidak ada laporan pada periode ini</td></tr>'}
            </table>
          </div>
        `;
      }).join("");

      bodyHtml = `
        <p style="font-size:11px;margin:0 0 12px;color:#374151;">Periode: ${label} · Total <b>${dateScoped.length}</b> laporan kinerja dikelompokkan per staf penanggung jawab.</p>
        ${sectionsHtml}
      `;

      sigHtml = `
        <table class="signature-table">
          <tr><td><b>Mengetahui</b></td><td><b>Kalianda, ${currentDate()}</b></td></tr>
          <tr><td><b>Kepala Loka Rehabilitasi Narkotika Kalianda</b></td><td><b>Penanggung Jawab Admin &amp; SDM</b></td></tr>
          <tr class="signature-space"><td></td><td></td></tr>
          <tr><td><b>Heru Herlambang, S. AP</b></td><td><b>Daniel, Amd.Kep</b></td></tr>
        </table>
      `;
    }

    const html = `<html><head><meta charset="UTF-8"><style>body{font-family:Arial;color:#111827}h1{font-size:18px;margin:0 0 4px}.report-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:10px;margin-bottom:12px}.report-table th,.report-table td{border:1px solid #cbd5e1;padding:7px;vertical-align:top;word-break:break-word}.report-table th{background:#e8f0ff;font-weight:700}.signature-table{border-collapse:collapse;width:100%;table-layout:fixed;margin-top:40px;font-size:12px}.signature-table td{border:0;width:50%;text-align:center;vertical-align:top;padding:4px 16px;line-height:1.25}.signature-table .signature-space td{height:88px;padding:0}</style></head><body><h1>${title}</h1>${bodyHtml}${sigHtml}</body></html>`;

    downloadReportFile(html, filename, "application/vnd.ms-excel;charset=utf-8");
    toast.success(`Excel ${isSingleStaff ? `staf ${targetStaff.name}` : "laporan per staf"} berhasil diunduh`);
  };

  const runExportPdf = (period, refDate, staffId = "all") => {
    const { start, end, label } = computeRange(period, refDate);
    const dateScoped = filterTasksByRange(tasks, start, end);
    const targetStaff = staff.find((s) => s.id === staffId);
    const isSingleStaff = Boolean(targetStaff && staffId !== "all");

    let title, contentHtml, sigHtml;

    if (isSingleStaff) {
      const staffTasks = dateScoped.filter((t) => t.staff_id === staffId);
      const stats = getStaffStats(staffTasks);
      title = `Laporan Kinerja Staf (${periodTitle[period]})`;

      const rows = staffTasks.map((t, idx) => {
        const norm = t.status === "plan" ? "todo" : (t.status || "todo");
        const curTime = norm === "todo"
          ? formatExportTime(t.todo_at || t.created_at)
          : norm === "doing"
            ? formatExportTime(t.doing_at || t.status_updated_at || t.todo_at)
            : formatExportTime(t.finish_at || t.status_updated_at);
        const photoCell = t.photo_data
          ? `<img src="${t.photo_data}" alt="foto" class="task-photo"/>`
          : `<span class="no-photo">–</span>`;

        const targetCell = `<b>${String(t.target || "-").replaceAll("<", "&lt;")}</b>` +
          (t.target_history && t.target_history.length > 1
            ? `<div style="font-size:8px;color:#64748b;margin-top:2px;line-height:1.2;">Riwayat: ${t.target_history.map(h => `${statusLabelMap[h.status] || h.status}: ${h.target}`).join(" → ")}</div>`
            : "");

        return `<tr>
          <td style="text-align:center;">${idx + 1}</td>
          <td><b>${String(t.title || "").replaceAll("<", "&lt;")}</b>${t.notes ? `<div style="color:#64748b;font-size:9px;margin-top:3px;">${String(t.notes).replaceAll("<", "&lt;")}</div>` : ""}</td>
          <td><span class="status-pill status-${norm}">${statusLabelMap[norm] || norm}</span></td>
          <td>${curTime}</td>
          <td>${t.priority}</td>
          <td>${targetCell}</td>
          <td>${t.due_date || "-"}</td>
          <td class="photo-cell">${photoCell}</td>
        </tr>`;
      }).join("");

      contentHtml = `
        <div class="staff-header-card">
          <table style="width:100%;font-size:11px;border-collapse:collapse;">
            <tr>
              <td style="width:160px;font-weight:bold;color:#475569;">Staf Penanggung Jawab</td>
              <td style="font-size:13px;font-weight:bold;color:#0f172a;">: ${targetStaff.name}</td>
              <td style="width:120px;font-weight:bold;color:#475569;">Periode Laporan</td>
              <td style="font-weight:bold;color:#0f172a;">: ${periodTitle[period]} (${label})</td>
            </tr>
            <tr>
              <td style="font-weight:bold;color:#475569;">Departemen</td>
              <td style="color:#1e293b;">: ${targetStaff.department}</td>
              <td style="font-weight:bold;color:#475569;">Pencapaian</td>
              <td style="color:#1e293b;">: ${stats.total} Tugas · Selesai: <b>${stats.finish}</b> (${stats.rate}%) · Doing: <b>${stats.doing}</b> · To Do: <b>${stats.todo}</b></td>
            </tr>
          </table>
        </div>
        <table class="report-table">
          <colgroup>
            <col style="width:4%;"/>
            <col style="width:23%;"/>
            <col style="width:11%;"/>
            <col style="width:14%;"/>
            <col style="width:9%;"/>
            <col style="width:14%;"/>
            <col style="width:10%;"/>
            <col style="width:15%;"/>
          </colgroup>
          <thead>
            <tr>
              <th>No</th><th>Judul Tugas</th><th>Status</th><th>Waktu Status</th><th>Prioritas</th><th>Target Riil</th><th>Tenggat</th><th>Foto</th>
            </tr>
          </thead>
          <tbody>
            ${rows || '<tr><td colspan="8" style="text-align:center;color:#64748b;padding:16px;">Belum ada laporan kerja pada periode ini</td></tr>'}
          </tbody>
        </table>
      `;

      sigHtml = `
        <table class="signature-table">
          <tr><td><b>Mengetahui</b></td><td><b>Kalianda, ${currentDate()}</b></td></tr>
          <tr><td><b>Kepala Loka Rehabilitasi Narkotika Kalianda</b></td><td><b>Penanggung Jawab / Yang Melaporkan</b></td></tr>
          <tr class="signature-space"><td></td><td></td></tr>
          <tr><td><b>Heru Herlambang, S. AP</b></td><td><b>${targetStaff.name}</b></td></tr>
        </table>
      `;
    } else {
      title = `Laporan Kinerja per Staf Penanggung Jawab (${periodTitle[period]})`;
      const activeStaff = staff.filter((s) => dateScoped.some((t) => t.staff_id === s.id));
      const displayStaffList = activeStaff.length > 0 ? activeStaff : staff.slice(0, 5);

      const staffSections = displayStaffList.map((s) => {
        const staffTasks = dateScoped.filter((t) => t.staff_id === s.id);
        const stats = getStaffStats(staffTasks);

        const rows = staffTasks.map((t, idx) => {
          const norm = t.status === "plan" ? "todo" : (t.status || "todo");
          const curTime = norm === "todo"
            ? formatExportTime(t.todo_at || t.created_at)
            : norm === "doing"
              ? formatExportTime(t.doing_at || t.status_updated_at || t.todo_at)
              : formatExportTime(t.finish_at || t.status_updated_at);
          const photoCell = t.photo_data
            ? `<img src="${t.photo_data}" alt="foto" class="task-photo"/>`
            : `<span class="no-photo">–</span>`;

          const targetCell = `<b>${String(t.target || "-").replaceAll("<", "&lt;")}</b>` +
            (t.target_history && t.target_history.length > 1
              ? `<div style="font-size:8px;color:#64748b;margin-top:2px;line-height:1.2;">Riwayat: ${t.target_history.map(h => `${statusLabelMap[h.status] || h.status}: ${h.target}`).join(" → ")}</div>`
              : "");

          return `<tr>
            <td style="text-align:center;">${idx + 1}</td>
            <td><b>${String(t.title || "").replaceAll("<", "&lt;")}</b></td>
            <td><span class="status-pill status-${norm}">${statusLabelMap[norm] || norm}</span></td>
            <td>${curTime}</td>
            <td>${t.priority}</td>
            <td>${targetCell}</td>
            <td>${t.due_date || "-"}</td>
            <td class="photo-cell">${photoCell}</td>
          </tr>`;
        }).join("");

        return `
          <div class="staff-section">
            <div class="staff-banner">
              <div>
                <strong>${s.name}</strong> · <span style="font-weight:normal;color:#475569;">${s.department}</span>
              </div>
              <div style="font-size:10px;font-weight:600;color:#1e3d75;">
                ${stats.total} Tugas · Selesai: ${stats.finish} (${stats.rate}%) · Doing: ${stats.doing} · To Do: ${stats.todo}
              </div>
            </div>
            <table class="report-table">
              <colgroup>
                <col style="width:4%;"/>
                <col style="width:23%;"/>
                <col style="width:11%;"/>
                <col style="width:14%;"/>
                <col style="width:9%;"/>
                <col style="width:14%;"/>
                <col style="width:10%;"/>
                <col style="width:15%;"/>
              </colgroup>
              <thead>
                <tr>
                  <th>No</th><th>Judul Tugas</th><th>Status</th><th>Waktu Status</th><th>Prioritas</th><th>Target Riil</th><th>Tenggat</th><th>Foto</th>
                </tr>
              </thead>
              <tbody>
                ${rows || '<tr><td colspan="8" style="text-align:center;color:#94a3b8;padding:10px;">Tidak ada laporan pada periode ini</td></tr>'}
              </tbody>
            </table>
          </div>
        `;
      }).join("");

      contentHtml = `
        <p style="font-size:11px;margin:0 0 16px;color:#334155;">Periode: ${label} · Total <b>${dateScoped.length}</b> laporan kinerja dikelompokkan berdasarkan staf penanggung jawab.</p>
        ${staffSections}
      `;

      sigHtml = `
        <table class="signature-table">
          <tr><td><b>Mengetahui</b></td><td><b>Kalianda, ${currentDate()}</b></td></tr>
          <tr><td><b>Kepala Loka Rehabilitasi Narkotika Kalianda</b></td><td><b>Penanggung Jawab Admin &amp; SDM</b></td></tr>
          <tr class="signature-space"><td></td><td></td></tr>
          <tr><td><b>Heru Herlambang, S. AP</b></td><td><b>Daniel, Amd.Kep</b></td></tr>
        </table>
      `;
    }

    const fullHtml = `<html><head><meta charset="UTF-8"><title>LOKA-Kin - ${title}</title><style>@page{size:A4 landscape;margin:12mm}body{font-family:Arial,sans-serif;color:#0f172a;margin:0;padding:12px}h1{font-size:19px;margin:0 0 6px;color:#0f172a}.staff-header-card{background:#f8fafc;border:1px solid #cbd5e1;border-radius:6px;padding:10px 14px;margin-bottom:14px}.staff-section{margin-bottom:20px;page-break-inside:avoid}.staff-banner{background:#e2e8f0;padding:7px 10px;font-size:11px;display:flex;justify-content:space-between;align-items:center;border:1px solid #cbd5e1;border-bottom:0;border-radius:4px 4px 0 0}.report-table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:10px}.report-table td,.report-table th{border:1px solid #cbd5e1;padding:6px 8px;text-align:left;vertical-align:top;word-break:break-word}.report-table th{background:#e8f0ff;font-weight:700}.status-pill{display:inline-block;padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700}.status-todo{background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe}.status-doing{background:#fffbeb;color:#b45309;border:1px solid #fde68a}.status-finish{background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0}.photo-cell{text-align:center;padding:4px}.task-photo{max-width:100px;max-height:75px;object-fit:cover;border-radius:4px;border:1px solid #cbd5e1}.no-photo{color:#94a3b8;font-size:10px}.signature-table{border-collapse:collapse;width:100%;table-layout:fixed;margin-top:40px;font-size:11px;page-break-inside:avoid}.signature-table td{border:0;width:50%;text-align:center;vertical-align:top;padding:4px 16px;line-height:1.25}.signature-table .signature-space td{height:80px;padding:0}</style></head><body><h1>LOKA-Kin · ${title}</h1>${contentHtml}${sigHtml}</body></html>`;

    const slug = isSingleStaff ? targetStaff.name.replace(/[^a-zA-Z0-9]/g, "_") : "per-staf";
    const filename = `loka-kin-${period}-${slug}-${toDateInput(start)}.html`;

    setPdfPreview({
      title,
      fullHtml,
      bodyHtml: contentHtml,
      sigHtml,
      filename,
    });
    toast.success(`Pratinjau PDF ${isSingleStaff ? `staf ${targetStaff.name}` : "laporan per staf"} siap dibuka.`);
  };

  const handleExportConfirm = ({ period, refDate, staffId }) => {
    if (exportMode === "excel") runExportExcel(period, refDate, staffId);
    else if (exportMode === "pdf") runExportPdf(period, refDate, staffId);
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
                {columns.map((col) => {
                  const columnTasks = filtered.filter((t) => t.status === col.key || (col.key === "todo" && t.status === "plan"));
                  return (
                    <section className="column" data-testid={`column-${col.key}`} key={col.key}>
                      <div className="column-head">
                        <div>
                          <h3>
                            <span className={`column-dot ${col.color}`} />
                            {col.label}
                            <em data-testid={`count-${col.key}`}>{columnTasks.length}</em>
                          </h3>
                          <p>{col.hint}</p>
                        </div>
                        {col.key === "todo" ? (
                          <button
                            className="add-column"
                            data-testid={`add-${col.key}-button`}
                            title="Tambah laporan ke To Do List"
                            onClick={() => setModal({ status: "todo" })}
                          >
                            <Plus size={17} />
                          </button>
                        ) : (
                          <button
                            className="add-column disabled-column-add"
                            data-testid={`add-${col.key}-button`}
                            title="Laporan harian baru wajib dimasukkan ke To Do List terlebih dahulu"
                            onClick={() => {
                              toast.info(`Laporan baru harus diinputkan ke To Do List terlebih dahulu sebelum dapat diubah ke ${col.label}.`);
                              setModal({ status: "todo" });
                            }}
                          >
                            <Plus size={17} />
                          </button>
                        )}
                      </div>
                      <div className="task-list">
                        {columnTasks.map((t) => (
                          <TaskCard
                            task={t}
                            staff={staff}
                            onEdit={setModal}
                            onTransition={(tsk, nextSt) => setTransitionModal({ task: tsk, nextStatus: nextSt })}
                            key={t.id}
                          />
                        ))}
                        {columnTasks.length === 0 && <div className="empty-state">Belum ada laporan {col.label}</div>}
                      </div>
                    </section>
                  );
                })}
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
      {transitionModal && (
        <StatusTransitionModal
          transitionData={transitionModal}
          staff={staff}
          onClose={() => setTransitionModal(null)}
          onConfirm={handleConfirmTransition}
        />
      )}
      {exportMode && <ExportDialog mode={exportMode} staff={staff} onClose={() => setExportMode(null)} onConfirm={handleExportConfirm} />}
      {pdfPreview && <PdfPreviewModal preview={pdfPreview} onClose={() => setPdfPreview(null)} />}
    </div>
  );
}
