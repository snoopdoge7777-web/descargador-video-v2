import os
import re
import shutil
import subprocess
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

def descargar_video(youtube_url, output_path):
    # Limpiar URL por si viene con signo '=' al principio desde n8n
    youtube_url = youtube_url.lstrip("=")
    print(f"--> Descargando video con yt-dlp usando cliente movil: {youtube_url}")

    # Forzar el cliente 'ios' y 'mweb' para saltear la verificacion de bot/login de YouTube en servidores cloud
    cmd = [
        'yt-dlp',
        '--extractor-args', 'youtube:player_client=ios,mweb',
        '-f', 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '--no-playlist',
        '--merge-output-format', 'mp4',
        '-o', output_path,
        youtube_url
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode != 0:
        print(f"--> Intento 1 fallido: {result.stderr}")
        print("--> Reintentando con cliente 'android'...")
        
        # Segundo intento con cliente android de respaldo
        cmd_alt = [
            'yt-dlp',
            '--extractor-args', 'youtube:player_client=android',
            '-f', 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--no-playlist',
            '--merge-output-format', 'mp4',
            '-o', output_path,
            youtube_url
        ]
        res_alt = subprocess.run(cmd_alt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if res_alt.returncode != 0:
            raise Exception(f"No se pudo descargar de YouTube: {res_alt.stderr}")

    print("--> Descarga completada con éxito.")

def process_and_send(url, webhook_url):
    work_dir = '/tmp/clips'
    try:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        raw_path = os.path.join(work_dir, 'input.mp4')

        # 1. Descarga del video
        descargar_video(url, raw_path)

        # 2. Análisis de silencios con FFmpeg
        print("--> Analizando silencios en el video con FFmpeg...")
        silence_cmd = [
            'ffmpeg', '-i', raw_path,
            '-af', 'silencedetect=noise=-30dB:d=0.8',
            '-f', 'null', '-'
        ]
        result = subprocess.run(silence_cmd, stderr=subprocess.PIPE, text=True)

        starts = [float(x) for x in re.findall(r'silence_start: (\d+\.?\d*)', result.stderr)]
        ends = [float(x) for x in re.findall(r'silence_end: (\d+\.?\d*)', result.stderr)]

        clips_dir = os.path.join(work_dir, 'output')
        os.makedirs(clips_dir, exist_ok=True)

        current_start = 0.0
        clip_index = 1

        def recortar_y_enviar(inicio, fin):
            nonlocal clip_index
            clip_name = f'clip_{clip_index:03d}.mp4'
            out_clip = os.path.join(clips_dir, clip_name)
            
            cmd = ['ffmpeg', '-y', '-ss', str(inicio)]
            if fin is not None:
                cmd.extend(['-to', str(fin)])
            cmd.extend(['-i', raw_path, '-c', 'copy', out_clip])

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Enviar archivo individual a n8n
            if webhook_url and os.path.exists(out_clip):
                webhook_clean = webhook_url.lstrip("=")
                print(f"--> Enviando {clip_name} a n8n ({webhook_clean})...")
                with open(out_clip, 'rb') as f:
                    files = {'data': (clip_name, f, 'video/mp4')}
                    response = requests.post(webhook_clean, files=files)
                    print(f"--> Respuesta de n8n para {clip_name}: Código {response.status_code}")
                os.remove(out_clip)
            elif not webhook_url:
                print(f"--> ADVERTENCIA: No se recibió webhook_url. {clip_name} no fue enviado.")

            clip_index += 1

        # 3. Procesar y enviar clip por clip
        print("--> Recortando y enviando clips secuencialmente...")
        for s_start, s_end in zip(starts, ends):
            duration = s_start - current_start
            if duration > 1.5:
                recortar_y_enviar(current_start, s_start)
            current_start = s_end

        # Último fragmento
        recortar_y_enviar(current_start, None)

        if os.path.exists(raw_path):
            os.remove(raw_path)
            
        print("--> ¡Proceso finalizado correctamente!")

    except Exception as e:
        print(f"--> ERROR CRÍTICO en el procesamiento: {str(e)}")

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json() or {}
    
    url = data.get('url') or data.get('targetUrl') or ""
    webhook_url = data.get('webhook_url') or data.get('webhookUrl') or ""
    
    url = url.lstrip("=")
    webhook_url = webhook_url.lstrip("=")
    
    print(f"--> Petición recibida en /download. URL: {url} | Webhook: {webhook_url}")

    if not url:
        return jsonify({"status": "error", "message": "Falta la URL del video"}), 400

    thread = threading.Thread(target=process_and_send, args=(url, webhook_url))
    thread.start()

    return jsonify({"status": "processing", "message": "El proceso ha comenzado. Los clips se enviarán secuencialmente."}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
