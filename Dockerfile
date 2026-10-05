# Multi-stage Dockerfile untuk Loka-Kin fullstack
# Build: docker build -t loka-kin .
# Run:   docker run -p 8000:8000 loka-kin
#
# Image ini serve frontend static via FastAPI + serve backend API.
# Cocok untuk Railway, Render, Fly.io, VPS (docker), dll.

# ============= Stage 1: build frontend =============
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend

# Install deps
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --legacy-peer-deps --no-audit --no-fund

# Build static assets
COPY frontend/ ./
RUN npm run build

# ============= Stage 2: build backend & serve FE =============
FROM python:3.11-slim
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir mongomock-motor

# Copy backend
COPY backend/ ./

# Copy built frontend ke static dir
COPY --from=frontend-build /app/frontend/build /app/static

# Patch server.py untuk serve static files (idempotent)
RUN python -c "
import re, pathlib
p = pathlib.Path('server.py')
src = p.read_text()
marker = '# === STATIC FILE SERVING ==='
if marker in src:
    print('Already patched')
else:
    inject = '''

''' + marker + '''
import pathlib as _pl
_STATIC_DIR = _pl.Path(__file__).parent / 'static'
if _STATIC_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    # Serve assets (JS/CSS/images) with proper caching
    app.mount('/static', StaticFiles(directory=str(_STATIC_DIR / 'static')), name='static')
    @app.get('/{full_path:path}', include_in_schema=False)
    async def spa_fallback(full_path: str):
        # API routes handled above; everything else → index.html (SPA)
        if full_path.startswith('api/') or full_path.startswith('docs') or full_path.startswith('openapi'):
            from fastapi import HTTPException
            raise HTTPException(404)
        index = _STATIC_DIR / 'index.html'
        if index.exists():
            return FileResponse(str(index))
        from fastapi import HTTPException
        raise HTTPException(404)
'''
    # inject before the last 'if __name__' line, or at end
    if 'if __name__' in src:
        src = src.replace('if __name__', inject + '\nif __name__', 1)
    else:
        src = src + inject
    p.write_text(src)
    print('Patched server.py to serve static frontend')
"

ENV MONGO_URL=mock \
    DB_NAME=loka_kin \
    PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
