# Usa una imagen oficial de Python
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias (incluyendo ffmpeg y nodejs para yt-dlp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Comando para ejecutar la aplicación con Gunicorn
CMD gunicorn --bind 0.0.0.0:10000 --workers 1 app:app
