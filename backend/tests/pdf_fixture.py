"""Pembuat berkas PDF minimal untuk pengujian pembaca daftar staf (tanpa dependensi luar)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _write_pdf(objects: Sequence[bytes], path: Path) -> Path:
    out = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    path.write_bytes(out)
    return path


def _page_objects(content: str) -> List[bytes]:
    stream = content.encode("latin-1", "replace")
    return [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]


def build_text_pdf(path: Path, lines: Sequence[Sequence[Tuple[float, str]]], font_size: int = 10) -> Path:
    """PDF tanpa garis: setiap baris berisi daftar (posisi_x, teks) per kolom."""
    content = ["BT"]
    y = 800
    for line in lines:
        content.append(f"/F1 {font_size} Tf")
        for x, text in line:
            content.append(f"1 0 0 1 {x} {y} Tm ({_escape(text)}) Tj")
        y -= 15
    content.append("ET")
    return _write_pdf(_page_objects("\n".join(content)), path)


def build_table_pdf(path: Path, columns: Sequence[Tuple[float, float, str]], rows: Sequence[Sequence[str]], font_size: int = 9) -> Path:
    """PDF dengan grid garis tabel (judul kolom berada di luar area tabel)."""
    content = ["BT"]
    y = 800
    separators: List[float] = []
    content.append(f"/F1 {font_size} Tf")
    for x, _w, text in columns:
        content.append(f"1 0 0 1 {x + 3} {y} Tm ({_escape(text)}) Tj")
    separators.extend([y + 12, y - 4])
    y -= 18
    for row in rows:
        content.append(f"/F1 {font_size} Tf")
        for (x, _w, _h), text in zip(columns, row):
            content.append(f"1 0 0 1 {x + 3} {y} Tm ({_escape(text)}) Tj")
        separators.append(y - 4)
        y -= 16
    content.append("ET")
    bottom = y + 8
    for x, _w, _h in columns:
        content.append(f"{x} {bottom + 6} m {x} {bottom} l S")
    right = columns[-1][0] + columns[-1][1]
    content.append(f"{right} {bottom + 6} m {right} {bottom} l S")
    for separator in separators:
        content.append(f"{columns[0][0]} {separator} m {right} {separator} l S")
    return _write_pdf(_page_objects("\n".join(content)), path)


def build_empty_pdf(path: Path) -> Path:
    """PDF tanpa lapisan teks — mensimulasikan hasil scan."""
    content = "BT /F1 10 Tf 1 0 0 1 40 800 Tm () Tj ET"
    return _write_pdf(_page_objects(content), path)
