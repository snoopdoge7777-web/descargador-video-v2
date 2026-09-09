import os
import tempfile
import zipfile
import numpy as np
from flask import Flask, request, send_file, jsonify
import yt_dlp

# Soporte de compatibilidad para MoviePy v1 y v2
try:
    from moviepy.editor import VideoFileClip, CompositeVideoClip, vfx
except ModuleNotFoundError:
    from moviepy import VideoFileClip, CompositeVideoClip, vfx

from pydub import AudioSegment

app = Flask(__name__)

def make_vertical_clip(clip, target_w=1080, target_h=1920):
    """Transforma un clip horizontal a vertical 9:16 con fondo desenfocado."""
    # 1. Crear el fondo ampliado y desenfocado
    bg = clip.resize(height=target_h)
    if bg.w < target_w:
        bg = clip.resize(width=target_w)
    bg = bg.crop(x_center=bg.w / 2, y_center=bg.h / 2, width=target_w, height=target_h)
    bg = bg.filter(vfx.gaussian_blur, sigma=15) # Desenfoque de fondo

    # 2. Redimensionar el video principal para que encaje al ancho
    fg = clip.resize(width=target_w)

    # 3. Superponer el video principal sobre el fondo
    final = CompositeVideoClip([bg, fg.set_position("center")], size=(target_w, target_h))
    
    # 4. Transiciones suaves (fade in/out de 0.5s)
    final = final.fadein(0.5).fadeout(0.5)
    return final

def detect_audio_highlights(video_path, clip_duration=15, top_n=3):
    """Analiza picos de audio, corta los clips y los convierte a formato vertical."""
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
        
        # Convertir a formato vertical 9:16
        vertical_clip = make_vertical_clip(subclip)
        
        clip_name = os.path.join(output_dir, f"highlight_{idx+1}.mp4")
        vertical_clip.write_videofile(
            clip_name, 
            codec="libx264", 
            audio_codec="aac", 
            preset="fast",
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

    # Regla ultra permisiva de formatos
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'outtmpl': video_path,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web', 'mweb', 'tv_embedded']
            },
            'youtubetab': {
                'skip': ['authcheck']
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

        # Recortar mejores partes y convertir a vertical 9:16
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
