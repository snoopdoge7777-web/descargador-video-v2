import os
import re
import shutil
import subprocess
import threading
import requests
from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)

def process_and_send(url, webhook_url):
    work_dir = '/tmp/clips'
    try:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        raw_path = os.path.join(work_dir, 'input.mp4')
        
        # Ruta robusta para encontrar el archivo de cookies en el directorio del script
        cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'www.youtube.com_cookies.txt')

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': raw_path,
            'quiet': True,
            'extractor_args': {'youtube': ['player_client=ios,android,web']}
        }

        if os.path.exists(cookie_path):
            ydl_opts['cookiefile'] = cookie_path

        # 1. Descarga completa del video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 2. Análisis de silencios con FFmpeg
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

        # 3. Recorte de clips
        for s_start, s_end in zip(starts, ends):
            duration = s_start - current_start
            if duration > 1.5:
                out_clip = os.path.join(clips_dir, f'clip_{clip_index:03d}.mp4')
                subprocess.run([
                    'ffmpeg', '-y',
                    '-ss', str(current_start), '-to', str(s_start),
                    '-i', raw_path,
                    '-c', 'copy',
                    out_clip
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                clip_index += 1
            current_start = s_end

        # Último fragmento hasta el final
        subprocess.run([
            'ffmpeg', '-y',
            '-ss', str(current_start),
            '-i', raw_path,
            '-c', 'copy',
            os.path.join(clips_dir, f'clip_{clip_index:03d}.mp4')
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 4. Compresión a ZIP
        zip_path = '/tmp/clips_recortados'
        archive_path = shutil.make_archive(zip_path, 'zip', clips_dir)

        if os.path.exists(raw_path):
            os.remove(raw_path)

        # 5. Enviar el ZIP resultante al Webhook de n8n
        if webhook_url:
            with open(archive_path, 'rb') as f:
                files = {'file': ('clips_recortados.zip', f, 'application/zip')}
                requests.post(webhook_url, files=files)

    except Exception as e:
        print(f"Error en segundo plano: {str(e)}")

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url')
    webhook_url = data.get('webhook_url')
    
    if not url:
        return {"status": "error", "message": "Falta la URL"}, 400

    # Iniciar el proceso en segundo plano para liberar a Render y evitar timeouts
    thread = threading.Thread(target=process_and_send, args=(url, webhook_url))
    thread.start()

    return jsonify({"status": "processing", "message": "El proceso ha comenzado en segundo plano."}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
