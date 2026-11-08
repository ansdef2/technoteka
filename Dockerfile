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
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/data STATIC_DIR=/app/static LLM_PROVIDER=demo
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# языковые данные для OCR сканов (сам Tesseract встроен в pymupdf); папка зависит от версии пакета —
# находим её и даём постоянный путь, а без данных сборка падает, чтобы OCR не выключился молча
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr-rus tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s "$(dirname "$(find /usr/share/tesseract-ocr -name rus.traineddata | head -1)")" /usr/share/tessdata \
    && test -f /usr/share/tessdata/rus.traineddata -a -f /usr/share/tessdata/eng.traineddata
ENV TESSDATA_PREFIX=/usr/share/tessdata
COPY schema/ schema/
COPY tools/ tools/
COPY b02/ b02/
COPY ml/ ml/
COPY backend/*.py backend/schema.sql backend/
COPY --from=front /front/dist static/
RUN useradd -m app && mkdir -p /data && chown app /data
# Облака (Amvera, Render) и docker с папкой хоста подключают диск данных от root: стартуем от root,
# отдаём DATA_DIR пользователю app и запускаем приложение уже от него (если платформа сама задала
# пользователя — запускаем как есть).
ENTRYPOINT ["sh", "-c", "if [ \"$(id -u)\" = 0 ]; then mkdir -p \"$DATA_DIR\" && chown -R app \"$DATA_DIR\" || true; exec setpriv --reuid=app --regid=app --init-groups \"$@\"; fi; exec \"$@\"", "--"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
