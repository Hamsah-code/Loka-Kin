# Image API LOKA-Kin (FastAPI). Frontend disajikan terpisah, mis. GitHub Pages.
# Uji lokal:  docker build -t loka-kin-api . && docker run -p 8000:8000 loka-kin-api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Lapisan dependensi lebih dulu supaya cache build terpakai ulang.
COPY backend/requirements-prod.txt /app/backend/requirements-prod.txt
RUN pip install -r /app/backend/requirements-prod.txt

COPY backend/ /app/backend/

# Snapshot JSON ditulis ke backend/data saat MONGO_URL kosong; siapkan direktori
# dan turunkan hak aksesnya ke pengguna non-root.
RUN useradd --create-home --uid 10001 loka \
 && mkdir -p /app/backend/data \
 && chown -R loka:loka /app
USER loka

# Render mengisi PORT sendiri; 8000 dipakai untuk uji lokal dan oleh proxy dev CRA.
ENV PORT=8000
EXPOSE 8000

# --proxy-headers + --forwarded-allow-ips: wajib di belakang proxy agar skema
# request terdeteksi https (menentukan atribut Secure pada cookie sesi).
CMD ["sh", "-c", "uvicorn server:app --app-dir /app/backend --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c 'import os,urllib.request;urllib.request.urlopen("http://127.0.0.1:%s/api/" % os.environ.get("PORT","8000"), timeout=4)'
