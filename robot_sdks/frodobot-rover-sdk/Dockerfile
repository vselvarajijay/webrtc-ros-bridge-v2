# Use a base image with Python
FROM --platform=linux/arm64/v8 python:3.9

# Define environment variables
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Install necessary packages and Chromium
RUN apt-get update \
  && apt-get install -y wget gnupg \
  && apt-get install -y chromium fonts-ipafont-gothic fonts-wqy-zenhei fonts-thai-tlwg fonts-khmeros fonts-kacst fonts-freefont-ttf libxss1 \
  --no-install-recommends \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv and project dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-install-project

# Copy full project and install the package
COPY . .
RUN uv sync

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["python", "-m", "hypercorn", "frodobot_rover_sdk.main:app", "--bind", "0.0.0.0:8000"]
