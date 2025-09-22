# ===== Base image =====
FROM python:3.11-slim

# ===== Workdir =====
WORKDIR /app

# ===== System deps =====
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ===== Copy requirements first (better caching) =====
COPY requirements.txt .

# upgrade pip and install deps
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ===== Copy project =====
COPY . .

# ===== Env =====
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ===== Entrypoint =====
CMD ["python", "-m", "app.main"]
