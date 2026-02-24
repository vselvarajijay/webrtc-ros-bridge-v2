# App: FastAPI serves UI (static) + /data, /api, /ws on port 8000. Single process for reliability.
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY app/server/pyproject.toml .
RUN pip install --no-cache-dir fastapi>=0.129.0 "uvicorn[standard]>=0.41.0"

# Cache-bust so rebuilds get a fresh COPY of app/ (set from cli.sh rebuild)
ARG CACHEBUST=0
RUN echo "App build at: ${CACHEBUST}"

# Copy app code (server + built www/dist from host pnpm build)
COPY app/ /app/app/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
