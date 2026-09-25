FROM nvidia/cuda:13.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    libopenslide0 \
    openslide-tools \
    libvips42 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt ./
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app 02_CODE ./02_CODE
COPY --chown=app:app 03_MODELS ./03_MODELS
COPY --chown=app:app 05_DEPLOYMENT ./05_DEPLOYMENT
COPY --chown=app:app LICENSE README.md ./

RUN mkdir -p /app/01_DATA /app/06_LOGS && chown -R app:app /app/01_DATA /app/06_LOGS

USER app
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/healthz', timeout=3)" || exit 1

CMD ["python3", "-m", "uvicorn", "05_DEPLOYMENT.api.server:app", "--host", "0.0.0.0", "--port", "8001", "--no-server-header"]
