FROM python:3.11-slim

# Instalar ffmpeg, curl y unzip
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar Deno
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-descargar el solucionador de retos JS para yt-dlp
RUN yt-dlp --remote-components ejs:github --version || true

COPY . .

CMD gunicorn --bind 0.0.0.0:10000 --workers 1 app:app
