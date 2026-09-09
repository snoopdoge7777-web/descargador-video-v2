import os
import tempfile
import zipfile
import subprocess
import numpy as np
from flask import Flask, request, send_file, jsonify

# Asegurar yt-dlp actualizado al vuelo
subprocess.run(["pip", "install", "--upgrade", "yt-dlp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

import yt_dlp

try:
    from moviepy.editor import VideoFileClip, CompositeVideoClip
except ModuleNotFoundError:
    from moviepy import VideoFileClip, CompositeVideoClip

from pydub import AudioSegment

app = Flask(__name__)

def make_vertical_clip(clip, target_w=720, target_h=1280):
    """Transforma a vertical 720p optimizado para bajo consumo de RAM."""
    fg = clip.resize(width=target_w)
    final = CompositeVideoClip([fg.set_position("center")], size=(target_w, target_h))
    return final

def detect_audio_highlights(video_path, clip_duration=15, top_n=3):
    """Analiza picos de audio con baja tasa de muestreo para ahorrar RAM."""
    temp_audio = video_path + ".wav"
    clip = VideoFileClip(video_path)
    
    # Extraer audio a 16kHz reduce drásticamente el consumo de memoria en Render
    clip.audio.write_audiofile(temp_audio, logger=None, fps=16000)

    audio = AudioSegment.from_wav(temp_audio)
    samples = np.array(audio.get_array_of_samples())
    
    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).mean(axis=1)

    sample_rate = audio.frame_rate
    window_size = int(clip_duration * sample_rate)
    scores = []

    # Ventanas de análisis más eficientes
    step_size = int(sample_rate * 3)
    for start in range(0, len(samples) - window_size, step_size):
        window = samples[start:start + window_size]
        rms = np.sqrt(np.mean(window**2))
        scores.append((rms, start / sample_rate))

    scores.sort(key=lambda x: x[0], reverse=True)
    
    # Evitar clips encimados
    best_starts = []
    for _, start_t in scores:
        if all(abs(start_t - existing) > clip_duration for existing in best_starts):
            best_starts.append(start_t)
        if len(best_starts) >= top_n:
            break
    best_starts.sort()

    if not best_starts:
        best_starts = [0]

    output_clips = []
    output_dir = os.path.dirname(video_path)
    
    for idx, start_t in enumerate(best_starts):
        end_t = min(start_t + clip_duration, clip.duration)
        subclip = clip.subclip(start_t, end_t)
        
        vertical_clip = make_vertical_clip(subclip)
        
        clip_name = os.path.join(output_dir, f"highlight_{idx+1}.mp4")
        vertical_clip.write_videofile(
            clip_name, 
            codec="libx264", 
            audio_codec="aac", 
            preset="ultrafast",
            threads=2,
            logger=None
        )
        vertical_clip.close()
        subclip.close()
        output_clips.append(clip_name)

    clip.close()
    if os.path.exists(temp_audio):
        os.remove(temp_audio)

    return output_clips

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'status': 'error', 'message': 'Falta el parámetro url'}), 400

    url = data['url']
    temp_dir = tempfile.mkdtemp()
    video_path = os.path.join(temp_dir, 'source_video.mp4')

    # Configuración anti-bloqueo con cliente mweb y android para servidores cloud
    ydl_opts = {
        'format': 'b[height<=720]/best[height<=720]/b/best',
        'outtmpl': video_path,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'android', 'web']
            }
        },
        'geo_bypass': True,
        'quiet': True
    }

    try:
        # Descarga el video en 720p
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(video_path):
            return jsonify({'status': 'error', 'message': 'No se pudo descargar el video'}), 500

        # Procesar recortes y verticalizar
        clips = detect_audio_highlights(video_path, clip_duration=15, top_n=3)

        if not clips:
            return jsonify({'status': 'error', 'message': 'No se pudieron generar los clips'}), 500

        # Comprimir en ZIP
        zip_path = os.path.join(temp_dir, 'highlights.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for clip_file in clips:
                zipf.write(clip_file, os.path.basename(clip_file))

        # Liberar espacio del video fuente pesado inmediatamente
        if os.path.exists(video_path):
            os.remove(video_path)

        return send_file(zip_path, mimetype='application/zip', as_attachment=True, download_name='highlights.zip')

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error de proceso: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
