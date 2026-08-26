import os
import re
import shutil
import subprocess
from flask import Flask, request, send_file
import yt_dlp

app = Flask(__name__)

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json() or {}
    url = data.get('url') or data.get('targetUrl') or ""
    url = url.lstrip("=")
    
    if not url:
        return {"status": "error", "message": "Falta la URL"}, 400

    work_dir = '/tmp/clips'
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(work_dir, exist_ok=True)

    raw_path = os.path.join(work_dir, 'input.mp4')
    
    cookie_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
    if not os.path.exists(cookie_path):
        cookie_path = os.path.join(os.path.dirname(__file__), 'www.youtube.com_cookies.txt')

    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/22/18',
        'outtmpl': raw_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'nocheckcertificate': True,
        # Cambiamos el cliente para evitar el bloqueo de página recargada
        'extractor_args': {
            'youtube': ['player_client=web,mweb']
        }
    }

    if os.path.exists(cookie_path):
        ydl_opts['cookiefile'] = cookie_path

    try:
        # 1. Actualizar yt-dlp automáticamente en cada ejecución para evitar bloqueos de YouTube
        subprocess.run(['pip', 'install', '--upgrade', 'yt-dlp'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Descargar video en 720p
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 3. Detectar marcas de silencio con ffmpeg
        silence_cmd = [
            'ffmpeg', '-i', raw_path,
            '-af', 'silencedetect=noise=-30dB:d=0.8',
            '-f', 'null', '-'
        ]
        result = subprocess.run(silence_cmd, stderr=subprocess.PIPE, text=True)

        starts = [float(x) for x in re.findall(r'silence_start: (\d+\.?\d*)', result.stderr)]
        ends = [float(x) for x in re.findall(r'silence_end: (\d+\.?\d*)', result.stderr)]

        # 4. Recortar en clips independientes descartando el silencio
        clips_dir = os.path.join(work_dir, 'output')
        os.makedirs(clips_dir, exist_ok=True)

        current_start = 0.0
        clip_index = 1

        for s_start, s_end in zip(starts, ends):
            duration = s_start - current_start
            if duration > 1.5:
                out_clip = os.path.join(clips_dir, f'clip_{clip_index:03d}.mp4')
                subprocess.run([
                    'ffmpeg', '-y', '-ss', str(current_start), '-to', str(s_start),
                    '-i', raw_path, '-c', 'copy', out_clip
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                clip_index += 1
            current_start = s_end

        # Último clip desde el último silencio hasta el final
        subprocess.run([
            'ffmpeg', '-y', '-ss', str(current_start),
            '-i', raw_path, '-c', 'copy', os.path.join(clips_dir, f'clip_{clip_index:03d}.mp4')
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 5. Empaquetar en un archivo ZIP
        zip_path = '/tmp/clips_recortados'
        archive_path = shutil.make_archive(zip_path, 'zip', clips_dir)

        return send_file(archive_path, as_attachment=True, download_name="clips_recortados.zip", mimetype="application/zip")

    except Exception as e:
        return {"status": "error", "message": f"Error de proceso: {str(e)}"}, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
