FROM python:3.11-slim

WORKDIR /app

# System dependencies for tree-sitter
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/traces

ENTRYPOINT ["python", "scripts/run.py"]
