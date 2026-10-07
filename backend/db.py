"""Lapisan database LOKA-Kin.

Dua mode penyimpanan:
1. MongoDB asli — dipakai bila variabel lingkungan ``MONGO_URL`` diisi (produksi).
2. Database lokal persisten — dipakai bila ``MONGO_URL`` kosong/"mock". Data
   disimpan sebagai snapshot JSON di ``backend/data/loka_kin_db.json`` sehingga
   tetap ada setelah server di-restart (sebelumnya memakai mongomock in-memory
   yang selalu hilang setiap restart).

Kedua mode mengekspos API yang sama dengan motor (``find``, ``insert_one``,
``update_one``, ...), jadi kode endpoint di ``server.py`` tidak perlu diubah.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Method yang mengubah isi koleksi — setelah dipanggil, snapshot ditulis ke disk.
MUTATING_METHODS = {
    "insert_one",
    "insert_many",
    "update_one",
    "update_many",
    "replace_one",
    "delete_one",
    "delete_many",
    "find_one_and_update",
    "find_one_and_replace",
    "find_one_and_delete",
    "bulk_write",
    "drop",
    "create_index",
    "drop_index",
}

DEFAULT_DATA_FILE = Path(__file__).resolve().parent / "data" / "loka_kin_db.json"


class JsonSnapshotStore:
    """Menyimpan isi semua koleksi ke satu berkas JSON (aman untuk restart)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._serialized: Dict[str, str] = {}

    # ---- internal ---------------------------------------------------------
    def _read(self) -> Dict[str, List[Dict[str, Any]]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return {
            name: docs for name, docs in raw.items() if isinstance(docs, list)
        }

    @staticmethod
    def _dump(name: str, docs: Iterable[Dict[str, Any]]) -> str:
        return json.dumps(list(docs), ensure_ascii=False, sort_keys=True, default=str)

    # ---- public -----------------------------------------------------------
    async def restore(self, database) -> int:
        """Isi ulang koleksi mongomock dari berkas snapshot saat startup."""
        self._data = self._read()
        total = 0
        for name, docs in self._data.items():
            if not docs:
                continue
            payload = [dict(doc) for doc in docs]
            await database.raw_collection(name).insert_many(payload)
            self._serialized[name] = self._dump(name, payload)
            total += len(payload)
        return total

    async def save(self, name: str, docs: List[Dict[str, Any]]) -> bool:
        """Tulis snapshot koleksi bila isinya benar-benar berubah."""
        payload = self._dump(name, docs)
        async with self._lock:
            if self._serialized.get(name) == payload:
                return False
            self._serialized[name] = payload
            self._data[name] = docs
            # Tulis atomik: tulis ke berkas sementara lalu ganti.
            content = json.dumps(self._data, ensure_ascii=False, indent=2, default=str)
            fd, tmp_path = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(content)
                os.replace(tmp_path, self.path)
            except BaseException:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
            return True

    @property
    def collections(self) -> Dict[str, List[Dict[str, Any]]]:
        return self._data


class CollectionProxy:
    """Membungkus koleksi motor/mongomock dan menyimpan snapshot setelah write."""

    def __init__(self, collection, database: "DatabaseProxy", name: str):
        self._collection = collection
        self._database = database
        self._name = name

    def __getattr__(self, item: str):
        attr = getattr(self._collection, item)
        if item in MUTATING_METHODS and callable(attr):
            async def mutation(*args, **kwargs):
                result = await attr(*args, **kwargs)
                await self._database.persist(self._name)
                return result

            return mutation
        return attr

    def __repr__(self) -> str:  # pragma: no cover - bantuan debug
        return f"<CollectionProxy {self._name}>"


class DatabaseProxy:
    """Meniru ``client[DB_NAME]`` motor sekaligus menangani persistensi."""

    def __init__(self, raw_database, store: Optional[JsonSnapshotStore] = None, backend: str = "mongodb"):
        self._raw = raw_database
        self._store = store
        self.backend = backend
        self._collections: Dict[str, CollectionProxy] = {}
        # PENTING: mongomock_motor membungkus ulang `_iter_documents` pada SETIAP
        # akses koleksi (Database.get_collection). Rantai pembungkusan itu makin
        # panjang dan berujung RecursionError. Karena itu setiap koleksi diambil
        # dari database tepat satu kali lalu di-cache untuk seluruh proses.
        self._raw_collections: Dict[str, Any] = {}

    def raw_collection(self, name: str):
        if name not in self._raw_collections:
            self._raw_collections[name] = self._raw[name]
        return self._raw_collections[name]

    # akses koleksi: db.staff atau db["staff"]
    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    def __getitem__(self, name: str) -> CollectionProxy:
        if name not in self._collections:
            self._collections[name] = CollectionProxy(self.raw_collection(name), self, name)
        return self._collections[name]

    def __contains__(self, name: str) -> bool:
        return name in self._raw.list_collection_names()

    @property
    def persistent(self) -> bool:
        return self._store is not None

    async def restore(self) -> int:
        if self._store is None:
            return 0
        return await self._store.restore(self)

    async def persist(self, collection_name: str) -> None:
        """Ambil isi koleksi terbaru lalu simpan ke disk (bila memakai mode lokal)."""
        if self._store is None:
            return
        docs = await self.raw_collection(collection_name).find({}, {"_id": 0}).to_list(length=None)
        await self._store.save(collection_name, docs)

    def stats(self) -> Dict[str, int]:
        return {name: len(docs) for name, docs in (self._store.collections.items() if self._store else [])}


def create_database(
    mongo_url: Optional[str] = None,
    db_name: str = "loka_kin",
    data_file: Optional[Path] = None,
) -> Tuple[DatabaseProxy, Any, str]:
    """Bangun koneksi database.

    Mengembalikan ``(db, client, mode)`` dengan ``mode`` bernilai ``"mongodb"``
    atau ``"local-json"``.
    """
    mongo_url = (mongo_url or "").strip()
    if mongo_url and mongo_url.lower() != "mock":
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except ImportError as exc:  # pragma: no cover - dependensi wajib
            raise RuntimeError(
                "MONGO_URL diisi tetapi driver motor tidak tersedia. "
                "Jalankan: pip install motor"
            ) from exc
        client = AsyncIOMotorClient(mongo_url)
        return DatabaseProxy(client[db_name], store=None, backend="mongodb"), client, "mongodb"

    try:
        from mongomock_motor import AsyncMongoMockClient
    except ImportError:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient("mongodb://localhost:27017")
        return DatabaseProxy(client[db_name], store=None, backend="mongodb-local"), client, "mongodb-local"

    client = AsyncMongoMockClient()
    store = JsonSnapshotStore(data_file or DEFAULT_DATA_FILE)
    return DatabaseProxy(client[db_name], store=store, backend="local-json"), client, "local-json"
