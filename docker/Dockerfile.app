# App server: FastAPI signaling + www
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY app/server/pyproject.toml .
RUN pip install --no-cache-dir fastapi>=0.129.0 "uvicorn[standard]>=0.41.0"

# Copy app code
COPY app/ /app/app/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
