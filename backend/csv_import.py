"""Pembaca daftar staf dari berkas CSV (mis. "DAFTAR STAF.csv").

Dirancang toleran terhadap ekspor spreadsheet sehari-hari:
- pemisah (koma / titik-koma ala Excel Indonesia / tab / pipa) dipilih otomatis
  dengan cara mencoba semuanya lalu menilai hasilnya;
- baris judul kolom dideteksi (termasuk bila didahului baris judul tabel);
- nama + gelar yang terpotong karena tanda koma tanpa tanda kutip disatukan kembali;
- nomor NIP/NIK dibersihkan dari titik/spasi, jenis nomor ditentukan dari panjangnya;
- pengkodean berkas dideteksi (UTF-8/BOM, lalu Windows-1252 sebagai cadangan).
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pdf_import import (
    clean_text,
    digits_only,
    find_id_token,
    looks_like_header,
    strip_leading_numbering,
)

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
DELIMITERS = [",", ";", "\t", "|"]
DELIMITER_LABELS = {",": "koma", ";": "titik-koma", "\t": "tab", "|": "pipa"}

NAME_FIELD_HINTS = ("nama", "name", "pegawai", "staf", "petugas", "personil")
ID_FIELD_HINTS = ("nip", "nik", "nrp", "nomor induk", "no induk", "nomor pegawai", "id")
KETERANGAN_FIELD_HINTS = (
    "jabatan", "keterangan", "bagian", "instalasi", "unit kerja", "unit", "posisi",
    "peran", "tugas", "profesi", "status", "ruang", "bidang", "seksi", "departemen",
)
IGNORED_FIELD_HINTS = ("no", "nomor", "urut", "no.", "no ")


def read_csv_text(path: Path) -> str:
    raw = Path(path).read_bytes()
    for encoding in ENCODINGS:
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if text.strip():
            return text
    raise ValueError("Isi berkas CSV tidak dapat dibaca.")


def looks_like_degree(part: str) -> bool:
    """Gelar seperti S.Sos / A.Md.Kep / M.IKom / SE ditulis setelah tanda koma."""
    part = part.strip()
    if not part or any(ch.isdigit() for ch in part):
        return False
    if "." in part:
        return True
    compact = re.sub(r"[^A-Za-z]", "", part)
    return bool(compact) and 2 <= len(compact) <= 4 and compact.isupper()


HEADER_WORD_ONLY = re.compile(
    r"^(?:no|nomor|urut|nama|name|nip|nik|nrp|jabatan|keterangan|bagian|instalasi|"
    r"departemen|unit|status|pegawai|staf|petugas)[\s.:/()\-]*$",
    re.IGNORECASE,
)


def join_name_parts(parts: Sequence[str]) -> str:
    result = ""
    for part in [clean_text(p) for p in parts if clean_text(p)]:
        if not result:
            result = part
        elif looks_like_degree(part):
            result += ", " + part
        else:
            result += " " + part
    return clean_text(result)


def strip_id_from_text(text: str, nip: str) -> str:
    """Buang nomor identitas yang menempel pada sel nama."""
    if not text:
        return text
    if re.search(r"\d[\d.,\s]{14,22}\d", text):
        text = re.sub(r"\d[\d.,\s]{14,22}\d", " ", text, count=1)
    if nip and nip in text:
        text = text.replace(nip, " ")
    return clean_text(text)


def column_stats(rows: Sequence[Sequence[str]], idx: int) -> Optional[Dict[str, float]]:
    cells = [row[idx] for row in rows if idx < len(row) and row[idx]]
    if not cells:
        return None
    return {
        "n": len(cells),
        "letters": sum(1 for c in cells if re.search(r"[a-zA-Z]", c)) / len(cells),
        "id_hits": sum(1 for c in cells if find_id_token(c)),
        "avg_len": sum(len(c) for c in cells) / len(cells),
    }


def find_header_row(grid: Sequence[Sequence[str]]) -> Optional[int]:
    for idx, row in enumerate(grid[:3]):
        hits = 0
        name_hit = False
        for cell in row:
            low = cell.lower()
            if any(h in low for h in NAME_FIELD_HINTS):
                hits += 1
                name_hit = True
            elif any(h in low for h in ID_FIELD_HINTS):
                hits += 1
            elif any(h in low for h in KETERANGAN_FIELD_HINTS):
                hits += 1
            elif any(h in low for h in IGNORED_FIELD_HINTS):
                hits += 1
        if hits >= 2 and name_hit:
            return idx
    return None


def parse_rows(raw_rows: Sequence[Sequence[str]]) -> List[Dict[str, str]]:
    """Ubah grid CSV (hasil satu pemisah) menjadi baris staf."""
    grid = [[clean_text(cell) for cell in row] for row in raw_rows]
    grid = [row for row in grid if any(row)]
    if not grid:
        return []

    header_idx = find_header_row(grid)
    header = grid[header_idx] if header_idx is not None else []
    data_rows = grid[header_idx + 1:] if header_idx is not None else grid
    if not data_rows:
        return []
    width = max(len(row) for row in data_rows)

    name_col = ket_col = id_col = None
    for idx, cell in enumerate(header):
        low = cell.lower()
        if id_col is None and any(h in low for h in ID_FIELD_HINTS):
            id_col = idx
        elif name_col is None and any(h in low for h in NAME_FIELD_HINTS):
            name_col = idx
        elif ket_col is None and any(h in low for h in KETERANGAN_FIELD_HINTS):
            ket_col = idx

    stats = {idx: column_stats(data_rows, idx) for idx in range(width)}

    # Kolom NIP/NIK: dari judul, atau dari kolom yang isinya paling banyak 16/18 digit.
    if id_col is None:
        candidates = [
            (idx, s) for idx, s in stats.items()
            if s and s["id_hits"] >= max(1, len(data_rows) * 0.25)
        ]
        if candidates:
            # Kolom NIP/NIK sebenarnya: paling banyak berisi nomor, muncul di banyak
            # baris, dan selnya cenderung panjang (bukan potongan nama/gelar).
            candidates.sort(key=lambda item: (-item[1]["id_hits"], -item[1]["n"], -item[1]["avg_len"]))
            id_col = candidates[0][0]

    # Kolom nama: kolom teks pertama sebelum kolom NIP/NIK (agar gelar ikut),
    # atau kolom teks terpanjang bila berkas tanpa kolom NIP/NIK.
    if name_col is None:
        text_columns = [
            (idx, s["avg_len"]) for idx, s in stats.items()
            if idx != id_col and s and s["letters"] >= 0.6 and s["avg_len"] >= 3
        ]
        if id_col is not None:
            before_id = [item for item in text_columns if item[0] < id_col]
            if before_id:
                name_col = min(before_id, key=lambda item: item[0])[0]
        if name_col is None and text_columns:
            name_col = max(text_columns, key=lambda item: item[1])[0]

    if name_col is None and id_col is None:
        return []

    rows: List[Dict[str, str]] = []
    for cells in data_rows:
        joined = " ".join(c for c in cells if c)
        if not joined or looks_like_header(joined):
            continue

        def cell(idx: Optional[int]) -> str:
            if idx is None or idx >= len(cells):
                return ""
            return cells[idx]

        id_cell = cell(id_col)
        nip = find_id_token(id_cell) if id_col is not None else ""
        if not nip and id_col is not None:
            candidate = digits_only(id_cell)
            if 16 <= len(candidate) <= 18:
                nip = candidate
        if not nip:
            nip = find_id_token(joined)

        # Nama = seluruh kolom teks sebelum kolom NIP/NIK (agar gelar tidak hilang).
        first = name_col if name_col is not None else 0
        stop = id_col if id_col is not None else width
        name_parts = []
        for idx in range(min(first, len(cells)), min(stop, len(cells))):
            value = cells[idx]
            if not value or find_id_token(value) or not re.search(r"[a-zA-Z]", value):
                continue
            name_parts.append(value)
        name = strip_leading_numbering(join_name_parts(name_parts)) if name_parts else ""

        # Bila sel kolom NIP/NIK ternyata berisi gelar (baris bergeser karena tanda
        # koma tanpa tanda kutip), potongan itu dikembalikan ke bagian nama.
        leftover = clean_text(id_cell if id_col is not None else "")
        if leftover and not find_id_token(leftover) and looks_like_degree(leftover) and leftover not in name:
            name = join_name_parts([name, leftover]) if name else leftover

        # Keterangan: kolom yang ditandai pada judul, kolom teks setelah kolom
        # NIP/NIK, atau sisa sel teks yang belum terpakai sebagai nama.
        # Potongan berbentuk gelar (S.Sos, A.Md.Kep) dikembalikan ke bagian nama.
        bagian_parts: List[str] = []

        def usable_as_keterangan(value: str) -> bool:
            return bool(value) and bool(re.search(r"[a-zA-Z]", value)) and not find_id_token(value)

        if ket_col is not None and usable_as_keterangan(cell(ket_col)):
            bagian_parts.append(cell(ket_col))

        start = (id_col + 1) if id_col is not None else (first + 1)
        for idx in range(start, len(cells)):
            value = cells[idx]
            if not usable_as_keterangan(value):
                continue
            if idx == ket_col or value in bagian_parts or value in name_parts or value in name:
                continue
            if not bagian_parts and looks_like_degree(value) and name and value not in name:
                name = join_name_parts([name, value])
                name_parts.append(value)
                continue
            bagian_parts.append(value)

        if not bagian_parts:
            for idx, value in enumerate(cells):
                if not usable_as_keterangan(value):
                    continue
                if idx in (id_col, name_col) or value in name_parts or value in name or value in bagian_parts:
                    continue
                bagian_parts.append(value)

        bagian = join_name_parts(bagian_parts)

        if not name:
            name = strip_leading_numbering(strip_id_from_text(joined, nip))
        name = strip_id_from_text(name, nip)
        if not name or len(name) < 3 or not re.search(r"[a-zA-Z]", name):
            continue
        if HEADER_WORD_ONLY.match(name):
            continue
        rows.append({"name": clean_text(name), "nip": nip, "bagian": clean_text(bagian)})
    return rows


def is_suspicious(row: Dict[str, str]) -> bool:
    """Baris hasil pemisah yang salah biasanya menyisakan tanda pemisah/nomor di nama."""
    name = row.get("name", "")
    if re.search(r"[;|\t]", name) or name.count(",") > 3:
        return True
    if len(name) > 70 or len(digits_only(name)) >= 5:
        return True
    if re.search(r"[,;|\t-]$", name):
        return True
    return False


def score_parse(rows: Sequence[Dict[str, str]]) -> Tuple[int, int, int]:
    """Nilai hasil pembacaan: makin tinggi makin baik."""
    with_nip = sum(1 for row in rows if row["nip"])
    filled_keterangan = sum(1 for row in rows if row["bagian"])
    suspicious = sum(1 for row in rows if is_suspicious(row))
    score = 3 * with_nip + len(rows) + filled_keterangan - 3 * suspicious
    return score, len(rows), with_nip


def extract_rows(csv_path: Path) -> Dict[str, Any]:
    """Ekstrak daftar staf dari berkas CSV, memilih pemisah terbaik otomatis."""
    text = read_csv_text(csv_path)
    if not text.strip():
        raise ValueError("Berkas CSV kosong.")

    best: Optional[Tuple[Tuple[int, int, int], str, List[Dict[str, str]]]] = None
    for delimiter in DELIMITERS:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        candidate = parse_rows([row for row in reader])
        score = score_parse(candidate)
        if best is None or score > best[0]:
            best = (score, delimiter, candidate)

    assert best is not None
    _score, delimiter, rows = best

    # buang duplikat (nama + nomor sama)
    unique: List[Dict[str, str]] = []
    seen = set()
    duplicates = 0
    for row in rows:
        key = (row["name"].lower(), row["nip"])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(row)

    if not unique:
        raise ValueError(
            "Daftar staf tidak dapat dikenali dari berkas CSV ini. Pastikan ada kolom nama "
            "dan (bila tersedia) kolom NIP/NIK serta keterangan/jabatan."
        )

    warnings: List[str] = []
    with_nip = sum(1 for row in unique if row["nip"])
    if not with_nip:
        warnings.append("Tidak ada NIP/NIK pada berkas. Kolom NIP/NIK akan tetap kosong dan bisa diisi manual.")
    elif with_nip < len(unique):
        warnings.append(f"{len(unique) - with_nip} staf belum memiliki NIP/NIK pada berkas CSV.")
    if duplicates:
        warnings.append(f"{duplicates} baris ganda dilewati.")

    return {
        "rows": unique,
        "count": len(unique),
        "with_nip": with_nip,
        "delimiter": DELIMITER_LABELS.get(delimiter, delimiter),
        "pages": None,
        "warnings": warnings,
        "raw_text": text[:20000],
    }
