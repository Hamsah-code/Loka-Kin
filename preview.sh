#!/usr/bin/env bash
# Jalankan preview LOKA-Kin: API FastAPI (port 8000) + dashboard React (port 3000).
#
#   ./preview.sh
#
# Dashboard memakai proxy bawaan react-scripts (frontend/package.json -> "proxy")
# sehingga semua permintaan "/api" dari browser diteruskan ke backend di port 8000.
# Backend berjalan tanpa MongoDB asli: server.py otomatis memakai mongomock saat
# variabel MONGO_URL tidak diisi, lalu menyemai 78 staf resmi + contoh tugas.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PREVIEW_PORT="${PREVIEW_PORT:-3000}"
cd "$ROOT"

# --- Backend: virtualenv + dependensi ---------------------------------------
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --quiet --disable-pip-version-check \
  "fastapi==0.110.1" "uvicorn==0.25.0" "motor==3.3.1" "mongomock-motor==0.0.20" \
  "pydantic>=2.6.4" "python-dotenv>=1.0.1" "pymongo==4.6.3" \
  "pdfplumber>=0.11.0" "python-multipart>=0.0.9"

# --- Frontend: dependensi npm ----------------------------------------------
if [ ! -d frontend/node_modules ]; then
  ( cd frontend && yarn install --registry https://registry.npmjs.org --network-timeout 900000 )
fi

# --- Backend (http://0.0.0.0:8000) -----------------------------------------
.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000 --app-dir backend \
  >/tmp/loka-kin-backend.log 2>&1 &
BACKEND_PID=$!

cleanup() { kill "$BACKEND_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# --- Dashboard (/api diproksi ke backend) -----------------------------------
# HMR harus memakai origin HTTPS preview, bukan port 0. Port PREVIEW_PORT
# dapat dinaikkan untuk menghindari cache/runtime lama pada tab preview yang usang.
cd frontend
unset WDS_SOCKET_PORT
HOST=0.0.0.0 PORT="$PREVIEW_PORT" BROWSER=none DANGEROUSLY_DISABLE_HOST_CHECK=true yarn start
