#!/usr/bin/env python3
"""Clustering akun LOKA-Kin: penyeragaman PIN, format peran, dan laporan cluster.

Perintah
--------
  template   Buat berkas Excel untuk mengisi peran setiap akun (satu kolom per
             peran: Super Admin, Kepala Loka, Clinical Supervisor, Ketua Tim,
             Staf) sekaligus blok akun Super Admin terpisah.
  pin        Seragamkan PIN semua akun roster (default 123456) dan aktifkan
             sehingga setiap akun dapat dipakai untuk clustering.
  apply      Terapkan peran dari berkas Excel/CSV ke database (PIN diseragamkan).
  report     Tampilkan matriks cluster (peran x departemen) dari database.

Contoh
------
  python scripts/clustering.py template
  python scripts/clustering.py pin --pin 123456
  python scripts/clustering.py apply Clustering-Akun-LokaKin.xlsx
  python scripts/clustering.py report

Skrip ini menulis langsung ke snapshot JSON mode ``local-json``
(``backend/data/loka_kin_db.json``) yang dipakai bila ``MONGO_URL`` kosong.
Hentikan server pratinjau sebelum menjalankan ``pin``/``apply`` agar isi memori
server tidak menimpa perubahan: hentikan proses, jalankan perintah, nyalakan lagi.

Alternatif tanpa terminal: unggah berkas yang sudah diisi lewat aplikasi
(Super Admin → Pengaturan website → Clustering akun → Terapkan berkas).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
DATA_FILE = BACKEND / "data" / "loka_kin_db.json"
DEFAULT_TEMPLATE = REPO / "Clustering-Akun-LokaKin.xlsx"

sys.path.insert(0, str(BACKEND))

from clustering_export import (  # noqa: E402  (butuh sys.path di atas)
    DEFAULT_PIN,
    ROLES,
    ROLE_LABEL_BY_CODE,
    build_workbook,
    normalize_digits,
    roster_rows,
)
from clustering_apply import (  # noqa: E402
    TemplateError,
    apply_roles as _apply_roles,
    parse_workbook,
    uniform_pin_fields,
    upsert_separate_super_admin as _upsert_separate_super_admin,
)


# --------------------------------------------------------------------------- #
# Penyimpanan
# --------------------------------------------------------------------------- #
class Snapshot:
    """Snapshot JSON yang sama dengan yang dipakai ``backend/db.py``."""

    def __init__(self, path: Path = DATA_FILE):
        self.path = Path(path)
        if not self.path.is_file():
            raise SystemExit(f"Snapshot database tidak ditemukan: {self.path}")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.data: Dict[str, Any] = raw if isinstance(raw, dict) else {}
        self.data.setdefault("staff", [])

    @property
    def staff(self) -> List[Dict[str, Any]]:
        return self.data["staff"]

    def backup(self) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        target = self.path.with_name(f"{self.path.stem}.backup-{stamp}.json")
        target.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return target

    def save(self) -> None:
        content = json.dumps(self.data, ensure_ascii=False, indent=2, default=str)
        fd, tmp_path = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise


def roster_staff(store: Snapshot) -> List[Dict[str, Any]]:
    return roster_rows(store.staff)


# --------------------------------------------------------------------------- #
# template
# --------------------------------------------------------------------------- #
def build_template(store: Snapshot, out_path: Path, pin: str) -> Path:
    wb = build_workbook(store.staff, pin=pin)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


# --------------------------------------------------------------------------- #
# pin
# --------------------------------------------------------------------------- #
def apply_pin(store: Snapshot, pin: str, only_ids: Optional[Sequence[str]] = None,
              revoke_sessions: bool = True) -> Dict[str, Any]:
    if not (len(pin) == 6 and pin.isdigit()):
        raise SystemExit("PIN harus 6 digit angka.")

    targets = roster_staff(store)
    if only_ids:
        wanted = set(only_ids)
        targets = [row for row in targets if row.get("id") in wanted]

    fields = uniform_pin_fields(pin)
    for row in targets:
        row.update(fields)
        if row.get("identity_is_placeholder") and not row.get("credential_source"):
            row["credential_source"] = "uniform-clustering"

    if revoke_sessions:
        store.data["auth_sessions"] = []

    return {"pin": pin, "accounts": len(targets), "sessions_revoked": bool(revoke_sessions)}


# --------------------------------------------------------------------------- #
# apply (peran dari Excel/CSV)
# --------------------------------------------------------------------------- #
def read_template(path: Path):
    """Baca berkas isian (xlsx/csv) — lihat ``clustering_apply.parse_workbook``."""
    from clustering_apply import read_upload

    payload = Path(path).read_bytes()
    return read_upload(Path(path).name, payload)


def apply_roles(store: Snapshot, entries, pin: str, strict: bool = False) -> Dict[str, Any]:
    return _apply_roles(store.staff, entries, pin, strict=strict)


def upsert_separate_super_admin(store: Snapshot, info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return _upsert_separate_super_admin(store.staff, info)


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def print_report(store: Snapshot) -> None:
    from clustering_export import summarize

    summary = summarize(store.staff)
    staff = roster_staff(store)
    print(f"Total akun roster : {summary['roster_total']}")
    print("\nSebaran peran (roster):")
    for code, label in ROLES:
        count = summary["role_counts"].get(code, 0)
        if code == "super_admin" and not count:
            continue
        print(f"  {label:<20} {count:>3}")
    separate = summary.get("separate_super_admin")
    if separate:
        print(f"  {'Super Admin terpisah':<20} {1:>3}")

    print("\nMatriks departemen x peran:")
    width = max(14, max(len(label) for _code, label in ROLES) + 3)
    print(f"  {'Departemen':<32}" + "".join(f"{label:>{width}}" for _code, label in ROLES))
    for department in summary["departments"]:
        cells = "".join(
            f"{(summary['matrix'][department].get(code) or '-'):>{width}}" for code, _label in ROLES
        )
        print(f"  {department:<32}" + cells)

    print(f"\nAkun tanpa NIP/NIK valid (tidak bisa login): {summary['missing_identity']}")
    for person in summary["missing_staff"][:10]:
        print(f"  - {person['id']}  {person['name']}")
    if summary["missing_identity"] > 10:
        print(f"  ... dan {summary['missing_identity'] - 10} akun lain")
    belum_aktif = [row for row in staff if not row.get("is_activated")]
    print(f"Akun belum aktivasi: {len(belum_aktif)}")
    if separate:
        print(f"Super Admin terpisah: {separate['name']} | NIP/NIK {separate['nip']} | id {separate['id']}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def run_sync(args) -> int:
    """Kirim berkas clustering ke API untuk memperbarui roster resmi + PIN seragam."""
    import urllib.error
    import urllib.request
    import uuid

    from roster_template import build_roster_rows, load_template_bytes

    path = Path(args.path)
    if not path.is_file():
        raise SystemExit(f"Berkas tidak ditemukan: {path}")
    entries, meta = load_template_bytes(path.name, path.read_bytes())
    rows, warnings, invalid_nip = build_roster_rows(entries)

    print(f"Berkas          : {path.name}")
    print(f"Akun terbaca    : {len(entries)}")
    print(f"Roster siap     : {len(rows)} baris")
    from collections import Counter
    print(f"Peran           : {dict(Counter(row['role'] for row in rows))}")
    print(f"Departemen      : {dict(Counter(row['department'] for row in rows))}")
    if invalid_nip:
        print(f"NIP tidak valid : {len(invalid_nip)}")
        for item in invalid_nip:
            print(f"  - {item['name']}: {item['nip']}")
    if warnings:
        print("Peringatan      :")
        for warning in warnings[:10]:
            print(f"  - {warning}")
    if args.dry_run:
        print("\n[dry-run] berkas tidak dikirim.")
        return 0

    # 1) Login sebagai Super Admin.
    api = args.api.rstrip("/")
    login_body = json.dumps({"nip": normalize_digits(args.nip), "pin": args.admin_pin}).encode()
    login_req = urllib.request.Request(f"{api}/api/auth/login", data=login_body, method="POST",
                                       headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(login_req, timeout=20) as response:
            login = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Gagal masuk sebagai Super Admin ({exc.code}): {exc.read().decode()[:200]}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"API tidak dapat dihubungi di {api}: {exc.reason}")

    token = login.get("session_token") or ""
    if not token:
        raise SystemExit("Login berhasil tetapi server tidak mengembalikan token sesi. "
                         "Jalankan server pratinjau dengan AUTH_PREVIEW_TOKEN_FALLBACK=true.")

    # 2) Kirim berkas ke endpoint sinkronisasi roster.
    boundary = f"----lokakin{uuid.uuid4().hex}"
    parts: List[bytes] = []
    for key, value in (("mode", args.mode), ("pin", args.pin)):
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'.encode() + path.read_bytes() + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    request = urllib.request.Request(
        f"{api}/api/admin/clustering/sync-roster",
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        try:
            detail = json.loads(detail).get("detail") or detail
        except json.JSONDecodeError:
            pass
        raise SystemExit(f"Sinkronisasi gagal ({exc.code}): {detail}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"API tidak dapat dihubungi: {exc.reason}")

    print("\n== Hasil sinkronisasi ==")
    print(f"  Roster diimpor : {result.get('imported')} akun (dilewati {result.get('skipped')})")
    print(f"  Total roster   : {result.get('total_roster')}")
    print(f"  Akun aktif+PIN : {result.get('activated')} akun dengan PIN {result.get('pin')}")
    print(f"  Sebaran peran  : {result.get('role_counts')}")
    print(f"  Super Admin    : {'dipertahankan' if result.get('super_admin_kept') else 'TIDAK DITEMUKAN'}")
    if result.get("warning_count"):
        print(f"  Peringatan     : {result['warning_count']}")
        for warning in result.get("warnings", [])[:10]:
            print(f"    - {warning}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Clustering akun LOKA-Kin")
    parser.add_argument("--data-file", type=Path, default=DATA_FILE,
                        help=f"snapshot database (default {DATA_FILE})")
    sub = parser.add_subparsers(dest="command", required=True)

    tpl = sub.add_parser("template", help="buat berkas Excel untuk mengisi peran")
    tpl.add_argument("--out", type=Path, default=DEFAULT_TEMPLATE,
                     help=f"lokasi berkas (default {DEFAULT_TEMPLATE.name})")
    tpl.add_argument("--pin", default=DEFAULT_PIN, help=f"PIN yang ditulis pada panduan (default {DEFAULT_PIN})")

    pin_cmd = sub.add_parser("pin", help="seragamkan PIN semua akun roster")
    pin_cmd.add_argument("--pin", default=DEFAULT_PIN, help=f"PIN 6 digit (default {DEFAULT_PIN})")
    pin_cmd.add_argument("--keep-sessions", action="store_true", help="jangan cabut sesi login yang ada")
    pin_cmd.add_argument("--dry-run", action="store_true", help="tampilkan rencana tanpa menulis")

    app = sub.add_parser("apply", help="terapkan peran dari berkas Excel/CSV")
    app.add_argument("path", nargs="?", type=Path, default=DEFAULT_TEMPLATE, help="berkas isian (xlsx/csv)")
    app.add_argument("--pin", default=DEFAULT_PIN, help=f"PIN seragam (default {DEFAULT_PIN})")
    app.add_argument("--strict", action="store_true", help="gagalkan bila ada baris tanpa peran")
    app.add_argument("--keep-sessions", action="store_true", help="jangan cabut sesi login yang ada")
    app.add_argument("--no-backup", action="store_true", help="lewati pencadangan snapshot")

    sync = sub.add_parser("sync", help="perbarui roster staf dari berkas clustering (via API)")
    sync.add_argument("path", type=Path, help="berkas Excel/CSV format clustering ('Isi Peran')")
    sync.add_argument("--api", default="http://127.0.0.1:8000", help="alamat API (default http://127.0.0.1:8000)")
    sync.add_argument("--nip", default=os.environ.get("LOKA_ADMIN_NIP", "0000000000000001"),
                      help="NIP/NIK Super Admin untuk masuk (default Super Admin terpisah)")
    sync.add_argument("--admin-pin", default=os.environ.get("LOKA_ADMIN_PIN", DEFAULT_PIN),
                      help=f"PIN Super Admin (default {DEFAULT_PIN})")
    sync.add_argument("--mode", choices=["replace", "merge"], default="replace",
                      help="replace = ganti seluruh roster resmi (default), merge = tambah")
    sync.add_argument("--pin", default=DEFAULT_PIN, help=f"PIN seragam untuk semua akun (default {DEFAULT_PIN})")
    sync.add_argument("--dry-run", action="store_true", help="baca berkas & tampilkan ringkasan tanpa mengirim")

    sub.add_parser("report", help="tampilkan matriks cluster dari database")

    args = parser.parse_args(argv)
    store = Snapshot(args.data_file)

    if args.command == "template":
        path = build_template(store, args.out, args.pin)
        print(f"Template dibuat: {path}")
        print(f"  staf roster: {len(roster_staff(store))} akun")
        return 0

    if args.command == "report":
        print_report(store)
        return 0

    if args.command == "sync":
        return run_sync(args)

    if args.command == "pin":
        plan = apply_pin(store, args.pin, revoke_sessions=not args.keep_sessions)
        if args.dry_run:
            print(f"[dry-run] {plan['accounts']} akun akan memakai PIN {plan['pin']}")
            return 0
        backup = store.backup()
        store.save()
        print(f"PIN {plan['pin']} diterapkan pada {plan['accounts']} akun roster.")
        print(f"Sesi login dicabut: {'ya' if plan['sessions_revoked'] else 'tidak'}")
        print(f"Cadangan: {backup}")
        return 0

    path = Path(args.path)
    if not path.is_file():
        raise SystemExit(f"Berkas tidak ditemukan: {path}")
    try:
        entries, separate = read_template(path)
    except TemplateError as exc:
        raise SystemExit(f"Berkas tidak sesuai format: {exc}")

    result = apply_roles(store, entries, args.pin, strict=args.strict)
    if result["problems"]:
        print("Peran TIDAK diterapkan karena ada masalah pada berkas:")
        for problem in result["problems"]:
            print(f"  - {problem}")
        print("Perbaiki lalu jalankan ulang perintah apply.")
        return 1

    super_admin = upsert_separate_super_admin(store, separate)
    if not args.keep_sessions:
        store.data["auth_sessions"] = []
    backup = store.backup() if not args.no_backup else None
    store.save()

    print(f"Berhasil menerapkan {result['processed']} baris. PIN seragam: {result['pin']}")
    if result["role_changes"]:
        print("Perubahan peran:")
        for ident, before, after in result["role_changes"]:
            print(f"  - {ident}: {ROLE_LABEL_BY_CODE.get(before, before)} -> {ROLE_LABEL_BY_CODE.get(after, after)}")
    if result["warnings"]:
        print("Peringatan:")
        for warning in result["warnings"][:20]:
            print(f"  - {warning}")
        if len(result["warnings"]) > 20:
            print(f"  ... dan {len(result['warnings']) - 20} peringatan lain")
    missing = result.get("missing_identity") or []
    if missing:
        print(f"Akun tanpa NIP/NIK (peran disimpan, login belum bisa): {len(missing)}")
        for ident, name in missing[:5]:
            print(f"  - {ident}  {name}")
        if len(missing) > 5:
            print(f"  ... dan {len(missing) - 5} akun lain; lengkapi kolom NIP/NIK di sheet 'Isi Peran'.")
    if super_admin.get("created") or super_admin.get("updated"):
        action = "dibuat" if super_admin.get("created") else "diperbarui"
        print(f"Super Admin terpisah {action}: {super_admin['id']} | NIP/NIK {super_admin['nip']} | PIN {super_admin['pin']}")
    elif super_admin.get("reason"):
        print(f"Super Admin terpisah: {super_admin['reason']}")
    if backup:
        print(f"Cadangan: {backup}")
    print()
    print_report(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
