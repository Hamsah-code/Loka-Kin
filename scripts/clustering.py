#!/usr/bin/env python3
"""Clustering akun LOKA-Kin: penyeragaman PIN, format peran, dan laporan cluster.

Perintah
--------
  template   Buat berkas Excel untuk mengisi peran setiap akun (satu kolom per
             peran: Super Admin, Kepala Loka, Clinical Supervisor, Ketua Tim,
             Staf) sekaligus blok akun Super Admin terpisah.
  pin        Seragamkan PIN semua akun roster (default 123456) dan aktifkan
             sehingga setiap akun dapat dipakai untuk clustering.
  apply      Terapkan peran dari berkas Excel ke database (PIN tetap diseragamkan).
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

Format Excel/CSV/cetak yang sama juga dapat diunduh dari aplikasi melalui
menu Super Admin → Clustering akun (endpoint ``/api/admin/clustering/*``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
DATA_FILE = BACKEND / "data" / "loka_kin_db.json"
DEFAULT_TEMPLATE = REPO / "Clustering-Akun-LokaKin.xlsx"

sys.path.insert(0, str(BACKEND))

from clustering_export import (  # noqa: E402  (butuh sys.path di atas)
    DEFAULT_PIN,
    ROLES,
    ROLE_ACCESS,
    ROLE_CODE_BY_LABEL,
    ROLE_LABEL_BY_CODE,
    SEPARATE_SUPER_ADMIN_DEFAULT,
    SEPARATE_SUPER_ADMIN_ID,
    SUPERVISOR_ROLES,
    build_workbook,
    normalize_digits,
    roster_rows,
    separate_super_admin,
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


def account_label(row: Dict[str, Any]) -> str:
    return ROLE_LABEL_BY_CODE.get(str(row.get("role") or "staff"), "Staf")


def id_type_for(nip: str) -> str:
    return {16: "NIK", 18: "NIP"}.get(len(nip), "")


def uniform_pin_fields(pin: str, source: str = "uniform-clustering") -> Dict[str, Any]:
    from auth_utils import hash_credential

    return {
        "pin_hash": hash_credential(pin),
        "is_activated": True,
        "pin_change_required": False,
        "activation_code_hash": "",
        "activation_code_expires_at": "",
        "activation_code_attempts": 0,
        "activation_code_locked_until": "",
        "login_failed_attempts": 0,
        "login_locked_until": "",
        "pin_source": source,
        "pin_updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


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
    changed = 0
    for row in targets:
        row.update(fields)
        if row.get("identity_is_placeholder") and not row.get("credential_source"):
            row["credential_source"] = "uniform-clustering"
        changed += 1

    if revoke_sessions:
        store.data["auth_sessions"] = []

    return {"pin": pin, "accounts": changed, "sessions_revoked": bool(revoke_sessions)}


# --------------------------------------------------------------------------- #
# apply (peran dari Excel)
# --------------------------------------------------------------------------- #
TRUE_MARKS = {"1", "01", "x", "X", "✓", "v", "V", "ya", "YA", "yes", "TRUE", "True", "true"}


def _is_marked(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    return str(value).strip() in TRUE_MARKS


def read_template(path: Path) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    if "Isi Peran" not in wb.sheetnames:
        raise SystemExit("Sheet 'Isi Peran' tidak ditemukan pada berkas ini.")

    ws = wb["Isi Peran"]
    header_row = None
    for row in range(1, 15):
        if str(ws.cell(row=row, column=2).value or "").strip() == "ID Akun":
            header_row = row
            break
    if header_row is None:
        raise SystemExit("Baris header ('ID Akun') tidak ditemukan pada sheet 'Isi Peran'.")

    role_cols: Dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        label = str(ws.cell(row=header_row, column=col).value or "").strip()
        if label in ROLE_CODE_BY_LABEL:
            role_cols[ROLE_CODE_BY_LABEL[label]] = col
    missing = [label for code, label in ROLES if code not in role_cols]
    if missing:
        raise SystemExit(f"Kolom peran tidak lengkap: {', '.join(missing)}")

    entries: List[Dict[str, Any]] = []
    blank_streak = 0
    for row in range(header_row + 1, ws.max_row + 1):
        marker = str(ws.cell(row=row, column=1).value or "")
        if marker.startswith("AKUN SUPER ADMIN TERPISAH"):
            break
        ident = str(ws.cell(row=row, column=2).value or "").strip()
        if not ident:
            blank_streak += 1
            if blank_streak >= 5:
                break
            continue
        blank_streak = 0
        marks = [code for code, col in role_cols.items() if _is_marked(ws.cell(row=row, column=col).value)]
        entries.append({
            "row": row,
            "id": ident,
            "nama": str(ws.cell(row=row, column=3).value or "").strip(),
            "nip": normalize_digits(ws.cell(row=row, column=4).value),
            "department": str(ws.cell(row=row, column=5).value or "").strip(),
            "marks": marks,
            "supervised": str(ws.cell(row=row, column=role_cols["staff"] + 1).value or "").strip(),
        })

    separate: Optional[Dict[str, Any]] = None
    for row in range(1, ws.max_row + 1):
        marker = str(ws.cell(row=row, column=1).value or "")
        if marker.startswith("AKUN SUPER ADMIN TERPISAH"):
            values = [ws.cell(row=row + 2, column=col).value for col in range(1, 5)]
            separate = {
                "name": str(values[0] or "").strip(),
                "nip": normalize_digits(values[1]),
                "pin": normalize_digits(values[2]) or DEFAULT_PIN,
                "note": str(values[3] or "").strip(),
                "row": row + 2,
            }
            break
    return entries, separate


def apply_roles(store: Snapshot, entries: Iterable[Dict[str, Any]], pin: str,
                strict: bool = False) -> Dict[str, Any]:
    staff_by_id = {str(row.get("id")): row for row in store.staff}
    seen_nip: Dict[str, str] = {}
    for row in store.staff:
        nip = normalize_digits(row.get("nip"))
        if nip:
            seen_nip[nip] = str(row.get("id"))

    problems: List[str] = []
    warnings: List[str] = []
    missing_identity: List[Tuple[str, str]] = []
    changed: List[Tuple[str, str, str]] = []
    fields = uniform_pin_fields(pin)

    for entry in entries:
        ident = entry["id"]
        row = staff_by_id.get(ident)
        if row is None:
            problems.append(f"Baris {entry['row']}: ID '{ident}' tidak ada di database.")
            continue
        if row.get("system_super_admin"):
            warnings.append(f"Baris {entry['row']}: '{ident}' adalah akun Super Admin terpisah; dilewati.")
            continue
        if len(entry["marks"]) > 1:
            labels = ", ".join(ROLE_LABEL_BY_CODE[code] for code in entry["marks"])
            problems.append(
                f"Baris {entry['row']} ({ident}): lebih dari satu peran ditandai ({labels}). "
                f"Hapus angka 1 pada kolom peran lain (pilih sel lalu tekan Delete), sisakan satu."
            )
            continue
        if not entry["marks"]:
            if strict:
                problems.append(f"Baris {entry['row']} ({ident}): belum ada peran yang ditandai.")
                continue
            warnings.append(f"Baris {entry['row']} ({ident}): peran kosong, peran lama dipertahankan.")
            role_code = str(row.get("role") or "staff")
        else:
            role_code = entry["marks"][0]

        nip = entry["nip"]
        if nip:
            if len(nip) not in (16, 18):
                problems.append(f"Baris {entry['row']} ({ident}): NIP/NIK '{nip}' bukan 16/18 digit.")
                continue
            owner = seen_nip.get(nip)
            if owner and owner != ident:
                problems.append(f"Baris {entry['row']} ({ident}): NIP/NIK '{nip}' sudah dipakai {owner}.")
                continue
        else:
            nip = normalize_digits(row.get("nip"))
            if not nip:
                missing_identity.append((ident, str(row.get("name") or "")))

        supervised = [
            item.strip() for item in entry["supervised"].replace(",", ";").split(";") if item.strip()
        ]
        if role_code not in SUPERVISOR_ROLES:
            supervised = []
        elif not supervised:
            supervised = [row.get("department")] if row.get("department") else []

        before = str(row.get("role") or "staff")
        row["role"] = role_code
        if nip:
            row["nip"] = nip
            row["id_type"] = id_type_for(nip)
            seen_nip[nip] = ident
        row["supervised_departments"] = supervised
        row.update(fields)
        if before != role_code:
            changed.append((ident, before, role_code))

    return {
        "pin": pin,
        "problems": problems,
        "warnings": warnings,
        "missing_identity": missing_identity,
        "role_changes": changed,
        "processed": len(list(entries)),
    }


def upsert_separate_super_admin(store: Snapshot, info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not info or not info.get("nip"):
        return {"created": False, "reason": "NIP/NIK Super Admin terpisah kosong — dilewati."}
    nip = normalize_digits(info["nip"])
    if len(nip) not in (16, 18):
        return {"created": False, "reason": f"NIP/NIK Super Admin '{nip}' bukan 16/18 digit — dilewati."}
    for row in store.staff:
        if str(row.get("id")) != SEPARATE_SUPER_ADMIN_ID and normalize_digits(row.get("nip")) == nip:
            return {"created": False, "reason": f"NIP/NIK {nip} sudah dipakai akun {row.get('id')}."}

    name = info.get("name") or SEPARATE_SUPER_ADMIN_DEFAULT["name"]
    pin = info.get("pin") or DEFAULT_PIN
    existing = separate_super_admin(store.staff)
    payload = {
        "id": SEPARATE_SUPER_ADMIN_ID,
        "name": name,
        "initials": "".join(part[0] for part in name.split()[:2]).upper() or "SA",
        "department": "Admin",
        "position": "Super Admin",
        "keterangan": "Akun sistem terpisah (di luar roster staf)",
        "active": True,
        "archived": False,
        "nip": nip,
        "id_type": id_type_for(nip),
        "role": "super_admin",
        "system_super_admin": True,
        "supervised_departments": [],
        "identity_is_placeholder": True,
        "credential_source": "clustering-setup",
    }
    payload.update(uniform_pin_fields(pin, source="clustering-setup"))
    if existing is None:
        store.staff.append(payload)
        return {"created": True, "id": SEPARATE_SUPER_ADMIN_ID, "pin": pin, "nip": nip}
    existing.update(payload)
    return {"created": False, "updated": True, "id": SEPARATE_SUPER_ADMIN_ID, "pin": pin, "nip": nip}


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

    app = sub.add_parser("apply", help="terapkan peran dari berkas Excel")
    app.add_argument("path", nargs="?", type=Path, default=DEFAULT_TEMPLATE, help="berkas Excel terisi")
    app.add_argument("--pin", default=DEFAULT_PIN, help=f"PIN seragam (default {DEFAULT_PIN})")
    app.add_argument("--strict", action="store_true", help="gagalkan bila ada baris tanpa peran")
    app.add_argument("--keep-sessions", action="store_true", help="jangan cabut sesi login yang ada")
    app.add_argument("--no-backup", action="store_true", help="lewati pencadangan snapshot")

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
    entries, separate = read_template(path)
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
