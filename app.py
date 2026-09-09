import os
import tempfile
import zipfile
import numpy as np
from flask import Flask, request, send_file, jsonify
import yt_dlp

# Soporte de compatibilidad para MoviePy v1 y v2
try:
    from moviepy.editor import VideoFileClip, CompositeVideoClip
except ModuleNotFoundError:
    from moviepy import VideoFileClip, CompositeVideoClip

from pydub import AudioSegment

app = Flask(__name__)

def make_vertical_clip(clip, target_w=720, target_h=1280):
    """Transforma un clip a vertical 720p sin filtros pesados de fondo."""
    # Redimensionar el video principal para que encaje al ancho (720px)
    fg = clip.resize(width=target_w)
    
    # Superponer sobre lienzo centrado
    final = CompositeVideoClip([fg.set_position("center")], size=(target_w, target_h))
    return final

def detect_audio_highlights(video_path, clip_duration=15, top_n=3):
    """Analiza picos de audio, corta los clips y los convierte a formato vertical 720p."""
    temp_audio = video_path + ".wav"
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(temp_audio, logger=None)

    audio = AudioSegment.from_wav(temp_audio)
    samples = np.array(audio.get_array_of_samples())
    
    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).mean(axis=1)

    sample_rate = audio.frame_rate
    window_size = int(clip_duration * sample_rate)
    scores = []

    for start in range(0, len(samples) - window_size, int(sample_rate * 5)):
        window = samples[start:start + window_size]
        rms = np.sqrt(np.mean(window**2))
        scores.append((rms, start / sample_rate))

    scores.sort(key=lambda x: x[0], reverse=True)
    best_starts = [start_time for _, start_time in scores[:top_n]]
    best_starts.sort()

    output_clips = []
    output_dir = os.path.dirname(video_path)
    
    for idx, start_t in enumerate(best_starts):
        end_t = min(start_t + clip_duration, clip.duration)
        subclip = clip.subclip(start_t, end_t)
        
        # Convertir a formato vertical 720p
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

    proxy_url = os.environ.get('PROXY_URL')

    # Descarga priorizando la calidad de 720p
    ydl_opts = {
        'format': 'b[height<=720]/best[height<=720]/b/best',
        'outtmpl': video_path,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios']
            }
        },
        'quiet': False
    }

    if proxy_url:
        ydl_opts['proxy'] = proxy_url

    try:
        # Descargar video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Recortar mejores partes en 720p
        clips = detect_audio_highlights(video_path, clip_duration=15, top_n=3)

        # Comprimir en un .zip para n8n
        zip_path = os.path.join(temp_dir, 'highlights.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for clip_file in clips:
                zipf.write(clip_file, os.path.basename(clip_file))

        return send_file(zip_path, mimetype='application/zip', as_attachment=True, download_name='highlights.zip')

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error de proceso: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
