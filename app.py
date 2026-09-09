import os
import tempfile
import zipfile
import numpy as np
from flask import Flask, request, send_file, jsonify
import yt_dlp
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

app = Flask(__name__)

def detect_audio_highlights(video_path, clip_duration=15, top_n=3):
    """Analiza los picos de volumen del audio para extraer las mejores partes."""
    temp_audio = video_path + ".wav"
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(temp_audio, logger=None)

    # Cargar audio para análisis
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
        
        # Redimensionar a 720p si el video original es mayor/distinto
        subclip_720p = subclip.resize(height=720) 
        
        clip_name = os.path.join(output_dir, f"highlight_{idx+1}.mp4")
        subclip_720p.write_videofile(
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

    ydl_opts = {
        # Forzar descarga en 720p o la mejor calidad MP4 disponible hasta 720p
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
        'outtmpl': video_path,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['tv_embedded', 'web', 'mweb']
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
        # 1. Descarga el video en 720p con proxy
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 2. Corta las mejores partes basadas en el audio
        clips = detect_audio_highlights(video_path, clip_duration=15, top_n=3)

        # 3. Comprime los clips en un .zip para n8n
        zip_path = os.path.join(temp_dir, 'highlights.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for clip_file in clips:
                zipf.write(clip_file, os.path.basename(clip_file))

        # 4. Devuelve el archivo ZIP
        return send_file(zip_path, mimetype='application/zip', as_attachment=True, download_name='highlights.zip')

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error de proceso: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
