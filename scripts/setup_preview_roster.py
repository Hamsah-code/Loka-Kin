#!/usr/bin/env python3
"""Bangun ulang roster pratinjau dari berkas sumber clustering (idempotent).

Dipanggil oleh ``preview.sh`` SEBELUM server dinyalakan, sehingga snapshot
``backend/data/loka_kin_db.json`` (yang tidak masuk Git) selalu sama dengan
berkas sumber ``Clustering-Akun-LokaKin_Isi-Peran.csv``.

Yang dilakukan:
  * membaca berkas 'Isi Peran' (CSV ber-pemisah ';' atau format clustering);
  * menerapkan NIP/NIK, peran, departemen pengawasan, dan ID akun sesuai berkas;
  * mengatur PIN seragam (default 123456) dan mengaktifkan akun roster;
  * memastikan akun Super Admin terpisah ada (NIP 0000000000000001);
  * akun lama yang tidak ada di berkas diarsipkan (nonaktif, ID ``arsip-*``);
  * PIN yang diganti sendiri oleh pegawai (pin_source = self-service) dipertahankan;
  * tugas (tasks) dan data lain dibiarkan apa adanya; sesi login dicabut.

Jalankan manual:  python scripts/setup_preview_roster.py [--data-file PATH] [--pin 123456]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from auth_utils import hash_credential  # noqa: E402
from roster_template import load_template_bytes  # noqa: E402

DEFAULT_DATA_FILE = BACKEND / "data" / "loka_kin_db.json"
DEFAULT_SOURCE = REPO / "Clustering-Akun-LokaKin_Isi-Peran.csv"
DEFAULT_PIN = "123456"
SUPER_ADMIN_ID = "super-admin"


def id_type_for(nip: str) -> str:
    return {16: "NIK", 18: "NIP"}.get(len(nip), "")


def pin_fields(pin: str) -> dict:
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
        "pin_source": "preview-roster",
        "pin_updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def load_entries(source: Path):
    entries, meta = load_template_bytes(source.name, source.read_bytes())
    for entry in entries:
        # NIP/NIK yang bukan 16/18 digit dikosongkan (dilaporkan sebagai peringatan).
        if entry.get("nip") and len(entry["nip"]) not in (16, 18):
            print(f"Peringatan: NIP/NIK {entry['name']} ('{entry['nip']}') bukan 16/18 digit - dikosongkan.")
            entry["nip"] = ""
    return entries, meta


def build_snapshot(data: dict, entries, meta, pin: str) -> dict:
    data = copy.deepcopy(data)
    staff = data.setdefault("staff", [])
    data.setdefault("tasks", [])

    by_nip = {row["nip"]: row for row in staff if row.get("nip")}
    by_name = {}
    for row in staff:
        by_name.setdefault(str(row.get("name", "")).strip().lower(), row)

    # Pasangkan setiap baris berkas dengan record yang ada (NIP dulu, lalu nama
    # untuk akun tanpa NIP). Record yang tidak dipasangkan diarsipkan.
    file_ids = {entry["file_id"] for entry in entries}
    matched_ids: set[int] = set()
    for entry in entries:
        record = by_nip.get(entry["nip"]) if entry["nip"] else by_name.get(entry["name"].strip().lower())
        if record is not None:
            matched_ids.add(id(record))

    keep: list[dict] = []
    for record in staff:
        if record.get("id") == SUPER_ADMIN_ID or record.get("system_super_admin") or id(record) in matched_ids:
            keep.append(record)
            continue
        # Akun lama yang tidak ada di berkas: arsipkan (nonaktif).
        if record.get("id") in file_ids:
            record["id"] = "arsip-" + str(record["id"])
        record["active"] = False
        record["is_activated"] = False
        keep.append(record)

    template = next((r for r in keep if r.get("id") != SUPER_ADMIN_ID), {})

    for entry in entries:
        record = None
        for r in keep:
            if entry["nip"] and r.get("nip") == entry["nip"]:
                record = r
                break
        if record is None and not entry["nip"]:
            for r in keep:
                if str(r.get("name", "")).strip().lower() == entry["name"].strip().lower() and not r.get("nip"):
                    record = r
                    break
        if record is None:
            record = copy.deepcopy({k: v for k, v in template.items() if k not in {"id", "nip", "name"}})
            record.update({"id": str(uuid.uuid4())})
            keep.append(record)

        role = entry.get("role") or "staff"
        supervised = list(entry.get("supervised") or []) if role in {"team_lead", "clinical_supervisor", "head"} else []
        record.update({
            "id": entry["file_id"],
            "name": entry["name"],
            "department": entry.get("department") or "Admin",
            "role": role,
            "supervised_departments": supervised,
            "active": True,
            "archived": False,
            "identity_is_placeholder": False,
        })
        if entry["nip"]:
            record["nip"] = entry["nip"]
            record["id_type"] = id_type_for(entry["nip"])
        else:
            record["nip"] = ""
            record["id_type"] = ""
        # PIN yang sudah diganti sendiri oleh pegawai tetap dipertahankan saat
        # roster dibangun ulang; akun lain memakai PIN seragam.
        if record.get("pin_source") != "self-service" or not record.get("pin_hash"):
            record.update(pin_fields(pin))

    # ID harus unik; akun roster sudah memakai ID dari berkas.
    ids = Counter(str(r.get("id")) for r in keep)
    dups = [k for k, v in ids.items() if v > 1]
    if dups:
        raise SystemExit(f"ID duplikat setelah sinkronisasi: {dups}")

    # Akun Super Admin terpisah (dibuat jika belum ada).
    sa = next((r for r in keep if r.get("id") == SUPER_ADMIN_ID or r.get("system_super_admin")), None)
    sa_nip = meta.get("super_admin", {}).get("nip") or "0000000000000001"
    sa_name = meta.get("super_admin", {}).get("name") or "Super Admin Loka-Kin"
    if sa is None:
        sa = {"id": SUPER_ADMIN_ID}
        keep.append(sa)
    sa.update({
        "id": SUPER_ADMIN_ID,
        "name": sa_name,
        "initials": "".join(part[0] for part in sa_name.split()[:2]).upper() or "SA",
        "department": "Admin",
        "position": "Super Admin",
        "keterangan": "Akun sistem terpisah (di luar roster staf)",
        "active": True,
        "archived": False,
        "nip": sa_nip,
        "id_type": id_type_for(sa_nip),
        "role": "super_admin",
        "system_super_admin": True,
        "supervised_departments": [],
        "identity_is_placeholder": True,
        "credential_source": "clustering-setup",
    })
    if sa.get("pin_source") != "self-service" or not sa.get("pin_hash"):
        sa.update(pin_fields(meta.get("super_admin", {}).get("pin") or pin))

    data["staff"] = keep
    data["auth_sessions"] = []
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA_FILE)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--pin", default=DEFAULT_PIN)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not (len(args.pin) == 6 and args.pin.isdigit()):
        raise SystemExit("PIN harus 6 digit angka.")
    if not args.source.is_file():
        raise SystemExit(f"Berkas sumber tidak ditemukan: {args.source}")

    entries, meta = load_entries(args.source)
    if args.data_file.is_file():
        data = json.loads(args.data_file.read_text(encoding="utf-8"))
    else:
        data = {"staff": [], "tasks": []}

    result = build_snapshot(data, entries, meta, args.pin)
    print(f"Akun di berkas : {len(entries)}")
    print(f"Akun di snapshot: {len([r for r in result['staff'] if not r.get('system_super_admin')])} roster + Super Admin")
    if args.dry_run:
        print("[dry-run] snapshot tidak ditulis.")
        return 0

    args.data_file.parent.mkdir(parents=True, exist_ok=True)
    if args.data_file.is_file():
        backup = args.data_file.with_name(f"{args.data_file.stem}.backup-{datetime.now():%Y%m%d-%H%M%S}.json")
        backup.write_text(args.data_file.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Cadangan       : {backup.name}")
    args.data_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Snapshot ditulis: {args.data_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
