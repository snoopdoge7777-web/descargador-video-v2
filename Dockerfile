FROM python:3.11-slim

# Instalar FFmpeg y dependencias básicas
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar Deno para resolver retos JS
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Habilitar y pre-descargar el componente EJS de yt-dlp globalmente
RUN yt-dlp --remote-components ejs:github --version || true

COPY . .

CMD gunicorn --bind 0.0.0.0:10000 --workers 1 app:app
