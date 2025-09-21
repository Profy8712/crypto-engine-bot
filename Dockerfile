# ===== Base image =====
FROM python:3.11-slim

# ===== Workdir =====
WORKDIR /app

# ===== System deps =====
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ===== Copy project =====
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ===== Env =====
ENV PYTHONUNBUFFERED=1

# ===== Entrypoint =====
CMD ["python", "-m", "app.main"]
