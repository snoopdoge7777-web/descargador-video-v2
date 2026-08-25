FROM python:3.11-slim

# Instalar dependencias del sistema (ffmpeg)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

# Comando con timeout ampliado para evitar cortes
CMD ["gunicorn", "app:app", "--timeout", "900", "--bind", "0.0.0.0:10000"]
