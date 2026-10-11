# ── Stage 1: Builder ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies in isolation
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Ultron Memory Agent"
LABEL org.opencontainers.image.description="Enterprise-grade autonomous AI cognitive system with persistent long-term memory"
LABEL org.opencontainers.image.author="Ultron Maintainers <maintainer@example.com>"
LABEL org.opencontainers.image.source="https://github.com/apparcora-app/ultron-memory-agent"
LABEL org.opencontainers.image.licenses="MIT"

# Security: run as non-root user
RUN groupadd -r ultron && useradd -r -g ultron -d /app -s /sbin/nologin ultron

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=ultron:ultron . .

# Create runtime directories
RUN mkdir -p data/chroma data/sessions output && \
    chown -R ultron:ultron data output

USER ultron

# Default: FastAPI Web HUD
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Override CMD to use CLI or Discord bot as needed
CMD ["python", "app.py"]
