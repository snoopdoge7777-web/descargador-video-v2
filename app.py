import os
import tempfile
import zipfile
import subprocess
import numpy as np
from flask import Flask, request, send_file, jsonify

# Forzar actualización de yt-dlp al vuelo para evitar bloqueos de YouTube
subprocess.run(["pip", "install", "--upgrade", "yt-dlp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

import yt_dlp

try:
    from moviepy.editor import VideoFileClip, CompositeVideoClip
except ModuleNotFoundError:
    from moviepy import VideoFileClip, CompositeVideoClip

from pydub import AudioSegment

app = Flask(__name__)

def make_vertical_clip(clip, target_w=720, target_h=1280):
    """Transforma el clip a vertical 720p sin sobrecargar memoria."""
    fg = clip.resize(width=target_w)
    final = CompositeVideoClip([fg.set_position("center")], size=(target_w, target_h))
    return final

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'status': 'error', 'message': 'Falta el parámetro url'}), 400

    url = data['url']
    temp_dir = tempfile.mkdtemp()
    
    # Opciones robustas con clientes múltiples para evitar bloqueos de player response
    ydl_base_opts = {
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'mweb', 'android']
            }
        },
        'quiet': True
    }

    # 1. Obtener la duración total del video
    probe_opts = {**ydl_base_opts, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration', 60)
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'No se pudo leer el video: {str(e)}'}), 500

    # Definir 3 puntos de corte
    clip_duration = 15
    start_times = [
        max(0, int(duration * 0.2)),
        max(0, int(duration * 0.5)),
        max(0, int(duration * 0.8))
    ]

    output_clips = []

    # 2. Descargar y procesar los rangos de tiempo
    for idx, start_t in enumerate(start_times):
        end_t = min(start_t + clip_duration, duration)
        section_path = os.path.join(temp_dir, f'part_{idx}.mp4')
        
        ydl_opts = {
            **ydl_base_opts,
            'format': 'b[height<=720]/best[height<=720]/b/best',
            'outtmpl': section_path,
            'download_ranges': yt_dlp.utils.download_range_func(None, [(start_t, end_t)]),
            'force_keyframes_at_cuts': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if os.path.exists(section_path):
                clip = VideoFileClip(section_path)
                vertical_clip = make_vertical_clip(clip)
                
                final_clip_name = os.path.join(temp_dir, f"highlight_{idx+1}.mp4")
                vertical_clip.write_videofile(
                    final_clip_name,
                    codec="libx264",
                    audio_codec="aac",
                    preset="ultrafast",
                    threads=2,
                    logger=None
                )
                clip.close()
                output_clips.append(final_clip_name)
        except Exception:
            continue

    if not output_clips:
        return jsonify({'status': 'error', 'message': 'No se pudieron generar los clips del video'}), 500

    # 3. Comprimir en ZIP
    zip_path = os.path.join(temp_dir, 'highlights.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for clip_file in output_clips:
            zipf.write(clip_file, os.path.basename(clip_file))

    return send_file(zip_path, mimetype='application/zip', as_attachment=True, download_name='highlights.zip')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
