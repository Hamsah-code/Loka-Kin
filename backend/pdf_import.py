"""Pembaca daftar staf dari berkas PDF (mis. "DATA STAF" / "DAFTAR STAF").

Alur:
1. Teks diekstrak dengan pdfplumber (lapisan teks PDF).
2. Bila dokumen memiliki garis tabel, kolom dipetakan lewat judul kolom
   (nama, NIP/NIK, jabatan/keterangan/bagian).
3. Bila tidak ada tabel, dipakai pemetaan per baris: token 16/18 digit dianggap
   NIP/NIK, teks berhuruf sebelumnya menjadi nama, sisanya keterangan.

Fungsi ini sengaja toleran: PDF daftar staf biasanya hasil cetak/scan tabel
sehingga susunannya bisa berbeda-beda antar dokumen.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber

# 16 digit = NIK, 18 digit = NIP. Titik/spasi pemisah di dalam nomor tetap diterima.
ID_PATTERN = re.compile(r"\d[\d.,\s]{14,22}\d")
ID_EXACT = re.compile(r"\d{16,18}")

HEADER_WORDS = (
    "nama", "nip", "nik", "no.", "no ", "nomor", "jabatan", "keterangan", "bagian",
    "instalasi", "unit", "status", "pegawai", "daftar", "staf", "hadir", "tanda",
    "puskesmas", "kecamatan", "kabupaten", "lampung", "rehabilitasi", "loka",
    "narkotika", "kalianda", "tabel", "urut", "pendidikan", "golongan", "pangkat",
)

NAME_FIELD_HINTS = ("nama", "name", "pegawai", "staf", "petugas")
ID_FIELD_HINTS = ("nip", "nik", "nrp", "nomor induk", "no induk", "id")
KETERANGAN_FIELD_HINTS = (
    "jabatan", "keterangan", "bagian", "instalasi", "unit kerja", "posisi",
    "peran", "tugas", "profesi", "status", "ruang",
)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ")
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s{2,}", " ", text).strip()


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def find_id_token(text: str) -> str:
    """Cari NIP/NIK (16 atau 18 digit) di dalam satu baris teks."""
    if not text:
        return ""
    # rapikan pemisah di dalam nomor: 1985.0101.2010.0110.01 atau 1 985 0101 ...
    normalized = re.sub(r"(?<=\d)[.\-\s](?=\d)", "", text)
    match = ID_EXACT.search(normalized)
    if match:
        return match.group(0)
    spaced = ID_PATTERN.search(text)
    if spaced:
        candidate = digits_only(spaced.group(0))
        if 16 <= len(candidate) <= 18:
            return candidate
    return ""


def looks_like_header(text: str) -> bool:
    low = text.lower()
    if not low.strip():
        return True
    if not re.search(r"[a-zA-Z]", low):
        return True  # baris nomor/angka saja
    words = re.findall(r"[a-zA-Z]+", low)
    if not words:
        return True
    header_hits = sum(1 for w in words if any(w.startswith(h.strip(".")) for h in HEADER_WORDS))
    # baris dianggap judul kolom bila mayoritas katanya kata kunci tabel
    return header_hits >= max(2, len(words) - 1)


def strip_leading_numbering(text: str) -> str:
    return re.sub(r"^\s*(?:no\.?|nomor)?\s*\d{1,3}\s*[.)\-–]?\s*", "", text, flags=re.IGNORECASE).strip()


def split_name_and_rest(segment: str) -> Tuple[str, str]:
    """Pisahkan nama dari keterangan pada satu potongan teks tanpa NIP."""
    text = clean_text(segment)
    if not text:
        return "", ""
    # nama biasanya dipisahkan tanda " - ", " / ", " – ", atau titik dua
    for sep in (" - ", " – ", " / ", " | ", ": "):
        if sep in text:
            head, tail = text.split(sep, 1)
            return clean_text(head), clean_text(tail)
    return text, ""


def row_from_line(line: str) -> Optional[Dict[str, str]]:
    """Ubah satu baris teks PDF menjadi {name, nip, bagian}."""
    text = clean_text(line)
    if not text or looks_like_header(text):
        return None

    nip = find_id_token(text)
    remaining = text
    if nip:
        # Buang nomor beserta varian pemisahnya (titik/spasi) dari teks.
        remaining = re.sub(r"\d[\d.,\s]{14,22}\d", " ", remaining, count=1)
        if nip in remaining:
            remaining = remaining.replace(nip, " ", 1)
    remaining = clean_text(remaining)

    if not re.search(r"[a-zA-Z]", remaining):
        return None

    parts = [clean_text(p) for p in re.split(r"\s{2,}|\t|\||;", remaining) if clean_text(p)]
    if not parts:
        return None

    name = strip_leading_numbering(parts[0])
    bagian = " ".join(parts[1:]).strip()
    if not bagian:
        name2, rest = split_name_and_rest(name)
        if rest:
            name, bagian = name2, rest

    if not name or len(name) < 3:
        return None
    return {"name": name, "nip": nip, "bagian": bagian}


def classify_segments(segments: List[str]) -> Optional[Dict[str, str]]:
    """Tentukan nama, NIP/NIK, dan keterangan dari potongan kolom satu baris."""
    segs = [clean_text(s) for s in segments if clean_text(s)]
    if not segs:
        return None

    nip = ""
    nip_index = -1
    for idx, seg in enumerate(segs):
        found = find_id_token(seg)
        if found:
            nip, nip_index = found, idx
            break

    leftover_in_nip_cell = ""
    if nip_index >= 0:
        leftover = segs[nip_index]
        leftover = re.sub(r"\d[\d.,\s]{14,22}\d", " ", leftover, count=1)
        if nip in leftover:
            leftover = leftover.replace(nip, " ", 1)
        leftover_in_nip_cell = clean_text(leftover)

    candidates: List[str] = []
    for idx, seg in enumerate(segs):
        if idx == nip_index:
            if leftover_in_nip_cell:
                candidates.append(leftover_in_nip_cell)
            continue
        if re.fullmatch(r"[\d.,\-–/()\s]+", seg):  # nomor urut, tanda hubung, dsb.
            continue
        candidates.append(seg)

    candidates = [c for c in candidates if re.search(r"[a-zA-Z]", c) and len(c.strip()) >= 2]
    if not candidates:
        return None

    name = strip_leading_numbering(candidates[0])
    if not name or len(name) < 3 or looks_like_header(name):
        return None
    bagian = " ".join(candidates[1:]).strip()
    return {"name": name, "nip": nip, "bagian": bagian}


def word_rows_from_page(page) -> List[Dict[str, str]]:
    """Susun baris dari posisi kata: celah lebar antar kata = batas kolom."""
    try:
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    except Exception:
        return []
    if not words:
        return []

    # lebar rata-rata karakter untuk menakar besar celah antar kolom
    widths = [(w["x1"] - w["x0"]) / max(1, len(w["text"])) for w in words if w["text"].strip()]
    char_w = sorted(widths)[len(widths) // 2] if widths else 5.0
    gap_threshold = max(5.0, 1.5 * char_w)

    lines: Dict[int, List[Dict[str, Any]]] = {}
    for word in words:
        key = round(word["top"] / 3.0)  # toleransi perbedaan kecil posisi vertikal
        lines.setdefault(key, []).append(word)

    rows: List[Dict[str, str]] = []
    for key in sorted(lines):
        line_words = sorted(lines[key], key=lambda w: w["x0"])
        groups: List[List[Dict[str, Any]]] = [[line_words[0]]]
        for prev, word in zip(line_words, line_words[1:]):
            if word["x0"] - prev["x1"] > gap_threshold:
                groups.append([word])
            else:
                groups[-1].append(word)
        segments = [" ".join(w["text"] for w in group) for group in groups]
        parsed = classify_segments(segments)
        if parsed:
            rows.append(parsed)
    return rows


def detect_columns(grid: List[List[str]]) -> Dict[str, Optional[int]]:
    """Tebak kolom nama / NIP-NIK / keterangan dari isi tabel (tanpa judul kolom)."""
    height = len(grid)
    width = max((len(row) for row in grid), default=0)
    if height == 0 or width == 0:
        return {"name": None, "id": None, "keterangan": None}

    def column(idx: int) -> List[str]:
        return [row[idx] if idx < len(row) else "" for row in grid]

    # kolom nomor identitas = kolom yang isinya paling sering 16/18 digit
    id_idx, id_score = None, 0.0
    for idx in range(width):
        cells = column(idx)
        hits = sum(1 for cell in cells if find_id_token(cell))
        score = hits / height
        if hits >= 1 and score > id_score:
            id_idx, id_score = idx, score
    if id_score < 0.25:
        id_idx = None

    # kolom teks (mengandung huruf & bukan kolom nomor) → nama = paling kiri, sisanya keterangan
    text_cols: List[int] = []
    for idx in range(width):
        if idx == id_idx:
            continue
        cells = [c for c in column(idx) if c]
        if not cells:
            continue
        letter_ratio = sum(1 for c in cells if re.search(r"[a-zA-Z]", c)) / len(cells)
        avg_len = sum(len(c) for c in cells) / len(cells)
        if letter_ratio >= 0.6 and avg_len >= 3:
            text_cols.append(idx)

    return {
        "name": text_cols[0] if text_cols else None,
        "id": id_idx,
        "keterangan": text_cols[1] if len(text_cols) > 1 else None,
        "extra_text_cols": text_cols[2:],
    }


def table_rows_from_page(page) -> List[Dict[str, str]]:
    """Petakan tabel PDF memakai judul kolom, atau deteksi kolom dari isinya."""
    rows: List[Dict[str, str]] = []
    try:
        tables = page.extract_tables()
    except Exception:
        return rows

    for table in tables or []:
        if not table:
            continue
        grid = [[clean_text(c) for c in (row or [])] for row in table]
        rows_in_grid = [row for row in grid if any(row)]
        if not rows_in_grid:
            continue

        first_row_text = " ".join(c for c in rows_in_grid[0] if c)
        mapping: Dict[str, Optional[int]] = {"name": None, "id": None, "keterangan": None}
        data_rows = rows_in_grid

        if looks_like_header(first_row_text):
            header = [c.lower() for c in rows_in_grid[0]]
            for idx, cell in enumerate(header):
                if mapping["id"] is None and any(h in cell for h in ID_FIELD_HINTS):
                    mapping["id"] = idx
            for idx, cell in enumerate(header):
                if idx == mapping["id"]:
                    continue
                if mapping["name"] is None and any(h in cell for h in NAME_FIELD_HINTS):
                    mapping["name"] = idx
                elif mapping["keterangan"] is None and any(h in cell for h in KETERANGAN_FIELD_HINTS):
                    mapping["keterangan"] = idx
            data_rows = rows_in_grid[1:]

        if mapping["name"] is None and mapping["id"] is None:
            mapping = detect_columns(data_rows)

        if mapping["name"] is None and mapping["id"] is None:
            # benar-benar tidak terpetakan → susun dari potongan sel tiap baris
            for raw in data_rows:
                candidate = classify_segments(raw)
                if candidate:
                    rows.append(candidate)
            continue

        for cells in data_rows:
            if not any(cells):
                continue
            joined = " ".join(c for c in cells if c)
            if looks_like_header(joined):
                continue

            def cell(idx: Optional[int]) -> str:
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx]

            name = cell(mapping["name"])
            nip = find_id_token(cell(mapping["id"])) if mapping["id"] is not None else ""
            bagian = cell(mapping["keterangan"])
            extra = mapping.get("extra_text_cols") or []
            extras = [cell(idx) for idx in extra]
            if extras:
                bagian = " ".join([b for b in [bagian] + extras if b]).strip()

            if not nip:
                nip = find_id_token(joined)
            if not name:
                parsed = classify_segments(cells)
                if not parsed:
                    continue
                name, bagian = parsed["name"], bagian or parsed["bagian"]
                nip = nip or parsed["nip"]

            name = strip_leading_numbering(name)
            if name and re.search(r"[a-zA-Z]", name) and not looks_like_header(name):
                rows.append({"name": name, "nip": nip, "bagian": bagian})
    return rows


def extract_rows(pdf_path: Path) -> Dict[str, Any]:
    """Ekstrak daftar staf dari berkas PDF.

    Mengembalikan dict: rows, count, with_nip, pages, warnings, raw_text.
    """
    rows: List[Dict[str, str]] = []
    warnings: List[str] = []
    raw_lines: List[str] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            raw_lines.extend(line for line in text.splitlines())

            # 1) tabel bergaris dengan judul kolom yang dikenali
            page_rows = table_rows_from_page(page)
            # 2) susunan kolom dari posisi kata (paling umum untuk daftar staf)
            if not page_rows:
                page_rows = word_rows_from_page(page)
            # 3) cadangan terakhir: pemetaan per baris teks
            if not page_rows:
                for line in text.splitlines():
                    candidate = row_from_line(line)
                    if candidate:
                        page_rows.append(candidate)
            rows.extend(page_rows)

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

    raw_text = "\n".join(raw_lines)
    with_nip = sum(1 for r in unique if r["nip"])
    if page_count == 0:
        raise ValueError("Berkas PDF tidak memiliki halaman yang bisa dibaca.")
    if not unique:
        if not raw_text.strip():
            raise ValueError(
                "PDF ini tidak memiliki lapisan teks (kemungkinan hasil scan/foto). "
                "Silakan unggah PDF hasil ekspor digital, atau tempel daftarnya pada kolom teks."
            )
        raise ValueError(
            "Teks PDF terbaca tetapi daftar staf tidak dapat dikenali otomatis. "
            "Silakan gunakan mode tempel teks dan rapikan formatnya."
        )
    if not with_nip:
        warnings.append(
            "Tidak ada nomor 16/18 digit yang terdeteksi. Pastikan kolom NIP/NIK tercantum pada PDF, "
            "atau lengkapi lewat kolom teks."
        )
    elif with_nip < len(unique):
        warnings.append(f"{len(unique) - with_nip} baris belum memiliki NIP/NIK dan perlu dilengkapi manual.")
    if duplicates:
        warnings.append(f"{duplicates} baris ganda dilewati.")

    return {
        "rows": unique,
        "count": len(unique),
        "with_nip": with_nip,
        "pages": page_count,
        "warnings": warnings,
        "raw_text": raw_text[:20000],
    }
