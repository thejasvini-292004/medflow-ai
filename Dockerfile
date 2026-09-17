# MedFlow AI — Streamlit app container
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (build tools for chromadb wheels on some platforms)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Build the DB + vector index at image-build time so the container is self-contained.
RUN python -m scripts.bootstrap

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# .env is provided at runtime via --env-file for secrets (OPENAI_API_KEY).
CMD ["streamlit", "run", "src/medflow/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true"]
