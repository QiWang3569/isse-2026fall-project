FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend
WORKDIR /app
COPY backend/requirements.lock.txt /app/backend/requirements.lock.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.lock.txt
COPY backend/app /app/backend/app
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist
RUN mkdir -p /app/data/uploads && useradd --system --uid 10001 --home-dir /app yandu \
    && chown -R yandu:yandu /app/data
USER yandu
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
