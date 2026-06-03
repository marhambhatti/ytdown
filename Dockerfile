# ─── Base image ──────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ─── System dependencies: ffmpeg (audio/video merge ke liye zaroori) ─────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ─── Working directory ────────────────────────────────────────────────────────
WORKDIR /app

# ─── Python dependencies ─────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── yt-dlp ko latest version pe update karo (bot detection bypass ke liye) ──
RUN pip install --no-cache-dir --upgrade yt-dlp

# ─── App files copy karo ─────────────────────────────────────────────────────
COPY . .

# ─── Downloads folder ────────────────────────────────────────────────────────
RUN mkdir -p /app/downloads

# ─── cookies.txt — agar hai to copy ho jayegi, nahi hai to blank create karo ─
RUN touch /app/cookies.txt

# ─── Port expose ─────────────────────────────────────────────────────────────
EXPOSE 8080

# ─── Gunicorn se run karo (production-grade, threads ke saath) ───────────────
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 300 --keep-alive 5 --log-level info app:app"]
