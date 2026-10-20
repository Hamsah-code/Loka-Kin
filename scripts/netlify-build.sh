#!/usr/bin/env bash
# Uji build Netlify secara lokal (tanpa harus push)
# Meniru environment yang dipakai netlify.toml / GitHub Actions
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

echo "== LOKA-Kin — Netlify local build check =="
echo "Node: $(node --version) | Yarn: $(yarn --version)"

# Default untuk Netlify root deploy
export CI=true
export GENERATE_SOURCEMAP=false
export PUBLIC_URL="/"
# Isi jika mau test cross-origin, contoh:
# export REACT_APP_BACKEND_URL="https://loka-kin-api.onrender.com"
# Kosong = relative /api (butuh proxy redirects di netlify.toml)
export REACT_APP_BACKEND_URL="${REACT_APP_BACKEND_URL:-}"

echo "Env: PUBLIC_URL=$PUBLIC_URL"
echo "Env: REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL:-<kosong → /api relatif>}"

if [ ! -d node_modules ]; then
  echo "→ yarn install..."
  yarn install --frozen-lockfile --network-timeout 900000
fi

echo "→ yarn build..."
yarn build

echo ""
echo "✓ Build selesai: $ROOT/frontend/build"
ls -lh build/index.html
du -sh build
echo ""
echo "Preview lokal build statis:"
echo "  npx serve -s build -l 5000     # atau: python3 -m http.server --directory build 5000"
echo "  lalu buka http://localhost:5000"
echo ""
echo "Untuk deploy ke Netlify:"
echo "  netlify deploy --build --prod   # butuh netlify-cli & link site"
