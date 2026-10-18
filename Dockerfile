# 1) сборка фронта
FROM node:22-alpine AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx tsc --noEmit && npx vite build --outDir /front/dist

# 2) бэкенд + ML-модуль + собранный фронт
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/data STATIC_DIR=/app/static
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY schema/ schema/
COPY tools/ tools/
COPY b02/ b02/
COPY ml/ ml/
COPY backend/*.py backend/schema.sql backend/
COPY --from=front /front/dist static/
RUN useradd -m app && mkdir -p /data && chown app /data
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
