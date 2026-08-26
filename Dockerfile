FROM python:3.11-slim

# Instalar dependencias del sistema (ffmpeg, curl, unzip, nodejs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    nodejs \
    ca-certificates \
    ffmpeg \
    && curl -fsSL https://deno.land/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# Configurar el PATH para Deno
ENV PATH="/root/.deno/bin:$PATH"

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

EXPOSE 10000

# Comando con timeout de 300 segundos (5 min) y 1 solo worker para optimizar la RAM en Render
CMD ["gunicorn", "-w", "1", "--bind", "0.0.0.0:10000", "--timeout", "300", "app:app"]
