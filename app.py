import os
import re
import shutil
import subprocess
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

def descargar_video(youtube_url, output_path):
    youtube_url = youtube_url.lstrip("=")
    print(f"--> Descargando video en máxima calidad: {youtube_url}")

    # Descarga la máxima calidad disponible (video + audio) sin restringir contenedor a mp4 inicial
    cmd = [
        'yt-dlp',
        '--cookies', 'cookies.txt',
        '--extractor-args', 'youtube:player_client=web,mweb',
        '-f', 'bv*+ba/b',
        '--no-playlist',
        '--merge-output-format', 'mp4',
        '-o', output_path,
        youtube_url
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode != 0:
        print(f"--> Falló intento 1. Reintentando sin extractor-args...")
        cmd_alt = [
            'yt-dlp',
            '--cookies', 'cookies.txt',
            '-f', 'bv*+ba/b',
            '--no-playlist',
            '--merge-output-format', 'mp4',
            '-o', output_path,
            youtube_url
        ]
        res_alt = subprocess.run(cmd_alt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_alt.returncode != 0:
            raise Exception(f"Error descargando YouTube: {res_alt.stderr}")

@app.route('/download', methods=['POST'])
def process_video():
    work_dir = '/tmp/clips_work'
    try:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        data = request.get_json() or {}
        url = data.get('url') or data.get('targetUrl') or ""
        url = url.lstrip("=")

        if not url:
            return jsonify({"error": "No se proporcionó URL"}), 400

        raw_path = os.path.join(work_dir, 'input.mp4')
        clips_dir = os.path.join(work_dir, 'clips')
        os.makedirs(clips_dir, exist_ok=True)

        # 1. Descargar video
        descargar_video(url, raw_path)

        # 2. Analizar silencios
        print("--> Analizando silencios...")
        silence_cmd = [
            'ffmpeg', '-i', raw_path,
            '-af', 'silencedetect=noise=-30dB:d=0.8',
            '-f', 'null', '-'
        ]
        res_silence = subprocess.run(silence_cmd, stderr=subprocess.PIPE, text=True)

        starts = [float(x) for x in re.findall(r'silence_start: (\d+\.?\d*)', res_silence.stderr)]
        ends = [float(x) for x in re.findall(r'silence_end: (\d+\.?\d*)', res_silence.stderr)]

        # 3. Generar clips independientes
        print("--> Recortando clips individuales...")
        current_start = 0.0
        clip_index = 1

        def recortar_clip(inicio, fin):
            nonlocal clip_index
            clip_name = f'clip_{clip_index:03d}.mp4'
            out_clip = os.path.join(clips_dir, clip_name)
            
            cmd = ['ffmpeg', '-y', '-ss', str(inicio)]
            if fin is not None:
                cmd.extend(['-to', str(fin)])
            cmd.extend([
                '-i', raw_path,
                '-c:v', 'libx264', '-crf', '18', '-preset', 'ultrafast',
                '-c:a', 'aac', '-b:a', '192k',
                out_clip
            ])
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            clip_index += 1

        for s_start, s_end in zip(starts, ends):
            duration = s_start - current_start
            if duration > 1.5:
                recortar_clip(current_start, s_start)
            current_start = s_end

        recortar_clip(current_start, None)

        # 4. Crear archivo ZIP con los clips
        zip_path_base = os.path.join(work_dir, 'clips_procesados')
        shutil.make_archive(zip_path_base, 'zip', clips_dir)
        final_zip = zip_path_base + '.zip'

        print("--> Enviando archivo ZIP de vuelta a n8n...")
        return send_file(
            final_zip,
            mimetype='application/zip',
            as_attachment=True,
            download_name='clips_procesados.zip'
        )

    except Exception as e:
        print(f"--> ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
