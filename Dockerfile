FROM python:3.11-slim

# Instalar dependencias del sistema (ffmpeg, curl, unzip)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar Deno (necesario para que yt-dlp resuelva los retos de JavaScript de YouTube)
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:$PATH"

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

CMD gunicorn -w 1 -b 0.0.0.0:10000 app:app
