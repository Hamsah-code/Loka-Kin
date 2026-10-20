#!/usr/bin/env bash
# Uji build Netlify secara lokal (tanpa harus push)
# Meniru environment yang dipakai netlify.toml / GitHub Actions
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

echo "== LOKA-Kin — Netlify local build check =="
echo "Node: $(node --version) | Yarn: $(yarn --version)"
echo "NPM: $(npm --version 2>&1 | head -n1)"

# Default untuk Netlify root deploy — sama persis dengan netlify.toml
export CI="${CI:-true}"
export GENERATE_SOURCEMAP="${GENERATE_SOURCEMAP:-false}"
export PUBLIC_URL="${PUBLIC_URL:-/}"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=4096}"
export REACT_APP_PREVIEW_TOKEN_FALLBACK=""
export REACT_APP_BACKEND_URL="${REACT_APP_BACKEND_URL:-}"

echo "Env: CI=$CI | PUBLIC_URL=$PUBLIC_URL | GENERATE_SOURCEMAP=$GENERATE_SOURCEMAP"
echo "Env: NODE_OPTIONS=$NODE_OPTIONS"
echo "Env: REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL:-<kosong → /api relatif>}"
echo "Env: REACT_APP_PREVIEW_TOKEN_FALLBACK=<kosong>"

if [ ! -d node_modules ]; then
  echo "→ yarn install (seperti Netlify)..."
  yarn install --frozen-lockfile --network-timeout 900000
else
  echo "→ node_modules sudah ada, skip install (hapus folder untuk test bersih)"
fi

echo "→ yarn build (seperti Netlify)..."
yarn build

echo ""
echo "✓ Build selesai: $ROOT/frontend/build"
ls -lh build/index.html build/_redirects 2>&1 || true
du -sh build
echo ""
echo "Verifikasi bundle:"
if grep -q "loka-kin-api" build/static/js/main.*.js 2>/dev/null; then
  echo "  ✓ REACT_APP_BACKEND_URL ter-embed di bundle"
else
  echo "  ℹ REACT_APP_BACKEND_URL kosong → build pakai /api relatif (butuh proxy atau CORS)"
fi
echo ""
echo "Preview lokal build statis:"
echo "  npx serve -s build -l 5000"
echo "  # lalu buka http://localhost:5000"
echo ""
echo "Untuk deploy ke Netlify:"
echo "  netlify deploy --build --prod   # butuh netlify-cli & link site"
echo "  atau push ke GitHub → Netlify auto deploy via netlify.toml"
