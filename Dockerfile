FROM node:22-alpine AS frontend
WORKDIR /app/web-app
COPY web-app/package.json web-app/package-lock.json ./
RUN npm ci
COPY web-app/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUTH_COOKIE_SECURE=true
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /app/web-app/dist/ ./web-app/dist/
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn app:app --app-dir backend --host 0.0.0.0 --port ${PORT:-10000}"]
