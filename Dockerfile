# ─── Base image ──────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ─── System dependencies ─────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    unzip \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ─── Deno install + PATH fix ─────────────────────────────────────────────────
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && deno --version

ENV DENO_INSTALL=/usr/local
ENV PATH="/usr/local/bin:${PATH}"

# ─── Working directory ────────────────────────────────────────────────────────
WORKDIR /app

# ─── Python dependencies ─────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── yt-dlp latest version ───────────────────────────────────────────────────
RUN pip install --no-cache-dir --upgrade "yt-dlp[default]"

# ─── Verify deno runtime yt-dlp ke saath kaam kar raha hai ───────────────────
RUN deno --version && yt-dlp --version

# ─── App files ───────────────────────────────────────────────────────────────
COPY . .

RUN mkdir -p /app/downloads
RUN touch /app/cookies.txt

EXPOSE 8080

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 300 --keep-alive 5 --log-level info app:app"]