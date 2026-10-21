"""Pembaca berkas format clustering (Excel/CSV) dan penyusun roster resmi.

Dipakai oleh:
* ``scripts/clustering.py`` (perintah ``template``/``apply``/``sync``/``pin``).
* Endpoint ``/api/admin/clustering/*`` pada ``server.py``.

Format yang dikenali
--------------------
1. **Templat aplikasi (CSV/Excel)** — sheet/berkas "Isi Peran": baris judul,
   deskripsi, lalu header ``No;ID Akun;Nama Lengkap;NIP/NIK;Departemen;...``
   dengan satu kolom per peran berisi angka ``1``. Blok "AKUN SUPER ADMIN
   TERPISAH" di bagian bawah ikut dikenali.
2. **CSV datar** — hanya header ``ID Akun`` + kolom peran (format unduhan CSV).

Catatan: berkas ekspor Excel di Indonesia biasanya memakai pemisah ``;`` dan
pengodean Windows-1252, sehingga pembaca di sini mendeteksi keduanya.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from clustering_export import DEPARTMENTS, ROLES, ROLE_CODE_BY_LABEL, normalize_digits

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

# Label peran pada berkas (Indonesia) -> kode database.
ROLE_ALIASES = {
    "super admin": "super_admin",
    "superadmin": "super_admin",
    "kepala loka": "head",
    "kepala": "head",
    "head": "head",
    "clinical supervisor": "clinical_supervisor",
    "supervisor klinis": "clinical_supervisor",
    "ketua tim": "team_lead",
    "team lead": "team_lead",
    "staf": "staff",
    "staff": "staff",
}

# Alias departemen/bagian pada berkas -> departemen resmi aplikasi.
DEPARTMENT_ALIASES = {
    "layanan umum": "Umum",
    "umum": "Umum",
    "tata usaha": "Umum",
    "admin": "Admin",
    "administrasi": "Admin",
    "administrasi & sdm": "Admin",
    "administrasi dan sdm": "Admin",
    "pengadaan barang & jasa": "Admin",
    "bendahara": "Bendahara",
    "perencanaan": "Perencanaan",
    "informasi dan humas": "Informasi dan Humas",
    "humas": "Informasi dan Humas",
    "layanan rehabilitasi medis": "Layanan Rehabilitasi Medis",
    "layanan medis": "Layanan Rehabilitasi Medis",
    "medis": "Layanan Rehabilitasi Medis",
    "layanan rehabilitasi sosial": "Layanan Rehabilitasi Sosial",
    "layanan sosial": "Layanan Rehabilitasi Sosial",
    "sosial": "Layanan Rehabilitasi Sosial",
    "sarana & prasarana": "Sarana & Prasarana",
    "sarana prasarana": "Sarana & Prasarana",
    "sarana dan prasarana": "Sarana & Prasarana",
    "clinical supervisor": "Clinical Supervisor",
    "supervisor klinis": "Clinical Supervisor",
}

SUPERVISOR_ROLE_CODES = {"head", "clinical_supervisor", "team_lead"}

# Departemen bawaan untuk akun Kepala Loka (bukan bagian layanan).
DEFAULT_HEAD_DEPARTMENT = "Admin"


class TemplateError(ValueError):
    """Berkas unggahan tidak sesuai format clustering."""


# --------------------------------------------------------------------------- #
# Utilitas teks
# --------------------------------------------------------------------------- #
def decode_bytes(payload: bytes) -> str:
    for encoding in ENCODINGS:
        try:
            text = payload.decode(encoding)
        except UnicodeDecodeError:
            continue
        if text.strip():
            return text
    raise TemplateError("Isi berkas tidak dapat dibaca sebagai teks.")


def normalize_department(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    key = re.sub(r"\s+", " ", raw.lower())
    if key in DEPARTMENT_ALIASES:
        return DEPARTMENT_ALIASES[key]
    for department in DEPARTMENTS:
        if key == department.lower():
            return department
    return raw if raw in DEPARTMENTS else ""


def parse_supervised(value: Any) -> List[str]:
    """Pisahkan 'Layanan Umum, Medis, Sosial' menjadi departemen resmi."""
    raw = str(value or "").strip()
    if not raw:
        return []
    parts = [part.strip() for part in re.split(r"[;,/]|\bdan\b", raw) if part.strip()]
    result: List[str] = []
    for part in parts:
        department = normalize_department(part)
        if department and department not in result:
            result.append(department)
    return result


def role_from_marks(row: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Tentukan satu peran dari kolom berisi angka 1 (label Excel atau kode)."""
    marks: List[str] = []
    for code, label in ROLES:
        value = str(row.get(label) or "").strip()
        if value in {"1", "1.0", "x", "X", "ya", "YA", "TRUE", "True", "true"}:
            marks.append(code)
    if not marks:
        for alias, code in ROLE_ALIASES.items():
            if str(row.get("Peran") or row.get("Role") or "").strip().lower() == alias:
                marks.append(code)
                break
    return (marks[0] if len(marks) == 1 else ""), marks


def role_from_label(value: Any) -> str:
    key = str(value or "").strip().lower()
    return ROLE_ALIASES.get(key, "")


# --------------------------------------------------------------------------- #
# Pembaca templat peran (CSV/Excel)
# --------------------------------------------------------------------------- #
def _looks_like_account_id(value: str) -> bool:
    return bool(re.match(r"^(staff|kepala|kepala-|head)[-_ ]?\w*$", value.strip(), re.IGNORECASE))


def parse_role_template_csv(payload: Union[bytes, str]) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Baca berkas 'Isi Peran' (CSV) termasuk baris pembuka dan blok Super Admin."""
    text = decode_bytes(payload) if isinstance(payload, (bytes, bytearray)) else str(payload)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    header_index = None
    delimiter = ";"
    for index, line in enumerate(lines):
        normalized = line.strip().lower()
        if "id akun" in normalized and "nama" in normalized:
            header_index = index
            delimiter = ";" if line.count(";") >= line.count(",") else ","
            break
    if header_index is None:
        raise TemplateError("Baris header ('ID Akun' + 'Nama Lengkap') tidak ditemukan pada berkas.")

    body: List[str] = []
    super_admin_block: List[str] = []
    in_super_block = False
    for line in lines[header_index:]:
        upper = line.upper()
        if upper.startswith("AKUN SUPER ADMIN TERPISAH"):
            in_super_block = True
        if in_super_block:
            super_admin_block.append(line)
        else:
            body.append(line)

    reader = csv.DictReader(io.StringIO("\n".join(body)), delimiter=delimiter)
    entries: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for offset, row in enumerate(reader, start=header_index + 2):
        if not row:
            continue
        ident = str(row.get("ID Akun") or "").strip()
        name = str(row.get("Nama Lengkap") or "").strip()
        if not ident or not name:
            continue
        if not _looks_like_account_id(ident):
            skipped.append(f"Baris {offset}: ID '{ident}' tidak dikenali — dilewati.")
            continue
        role_code, marks = role_from_marks(row)
        if not role_code:
            # Kolom "Peran Saat Ini" hanya label; pakai sebagai cadangan.
            fallback = role_from_label(row.get("Peran Saat Ini"))
            if fallback and not marks:
                role_code = fallback
        label = str(row.get("Departemen") or "").strip()
        entries.append({
            "row": offset,
            "file_id": ident,
            "name": name,
            "nip": normalize_digits(row.get("NIP/NIK")),
            "department_raw": label,
            "department": normalize_department(label),
            "role": role_code,
            "marks": marks,
            "supervised": parse_supervised(row.get("Departemen Diawasi")),
            "note": str(row.get("Catatan") or "").strip(),
        })

    super_admin = None
    for offset, line in enumerate(super_admin_block):
        cells = next(csv.reader([line], delimiter=delimiter), [])
        if cells and cells[0].strip().lower().startswith("nama"):
            values = next(csv.reader([super_admin_block[offset + 1]], delimiter=delimiter), []) if offset + 1 < len(super_admin_block) else []
            if values:
                super_admin = {
                    "name": values[0].strip(),
                    "nip": normalize_digits(values[1] if len(values) > 1 else ""),
                    "pin": normalize_digits(values[2] if len(values) > 2 else ""),
                }
            break

    if not entries:
        raise TemplateError("Tidak ada baris akun yang dapat dibaca (kolom 'ID Akun' kosong).")
    return entries, {"super_admin": super_admin, "skipped": skipped}


# --------------------------------------------------------------------------- #
# Penyusun roster untuk impor resmi
# --------------------------------------------------------------------------- #
def build_roster_rows(entries: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """Ubah entri 'Isi Peran' menjadi baris roster siap impor.

    Mengembalikan (rows, warnings, invalid_nip). NIP yang tidak 16/18 digit tidak
    dibuang (agar orangnya tetap ada di roster) tetapi dikosongkan dan dilaporkan
    supaya dapat dibetulkan.
    """
    rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    invalid_nip: List[Dict[str, Any]] = []
    seen_names: Dict[str, int] = {}

    for entry in entries:
        name = entry["name"]
        role = entry.get("role") or "staff"
        nip = entry.get("nip") or ""
        if nip and len(nip) not in (16, 18):
            invalid_nip.append({"name": name, "nip": nip})
            warnings.append(
                f"NIP/NIK {name} ('{nip}') bukan 16/18 digit — disimpan kosong, mohon dibetulkan."
            )
            nip = ""

        department = entry.get("department") or ""
        if not department:
            if role == "head":
                department = DEFAULT_HEAD_DEPARTMENT
                warnings.append(f"Departemen '{entry.get('department_raw')}' bukan departemen resmi; {name} ditempatkan di {department}.")
            else:
                department = "Admin"
                warnings.append(f"Departemen '{entry.get('department_raw')}' tidak dikenali; {name} ditempatkan di Admin.")

        supervised = list(entry.get("supervised") or [])
        if role not in SUPERVISOR_ROLE_CODES:
            supervised = []
        if role in SUPERVISOR_ROLE_CODES and not supervised:
            supervised = [department]

        key = name.lower()
        seen_names[key] = seen_names.get(key, 0) + 1
        if seen_names[key] > 1:
            warnings.append(f"Nama '{name}' muncul lebih dari sekali pada berkas; keduanya diimpor.")

        rows.append({
            "name": name,
            "bagian": entry.get("department_raw") or "",
            "nip": nip,
            "department": department,
            "role": role,
            "supervised_departments": supervised,
        })
    return rows, warnings, invalid_nip


def workbook_to_template_csv(payload: bytes) -> str:
    """Ubah sheet 'Isi Peran' pada berkas .xlsx menjadi teks CSV (;)."""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(payload), data_only=True)
    except Exception as exc:  # openpyxl melempar beragam tipe galat
        raise TemplateError("Berkas Excel tidak dapat dibaca.") from exc
    if "Isi Peran" not in wb.sheetnames:
        raise TemplateError(f"Sheet 'Isi Peran' tidak ditemukan. Sheet tersedia: {', '.join(wb.sheetnames)}.")
    ws = wb["Isi Peran"]
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    for row in ws.iter_rows(values_only=True):
        writer.writerow(["" if cell is None else str(cell) for cell in row])
    return buffer.getvalue()


def load_template_bytes(filename: str, payload: bytes):
    """Baca berkas templat peran dari nama berkas + isi binernya."""
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")) or payload[:2] == b"PK":
        return parse_role_template_csv(workbook_to_template_csv(payload))
    return parse_role_template_csv(payload)
