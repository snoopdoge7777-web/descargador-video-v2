import os
import re
import shutil
import subprocess
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

def descargar_con_cobalt(youtube_url, output_path):
    url_api = "https://api.cobalt.tools/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": youtube_url,
        "vQuality": "1080"
    }
    res = requests.post(url_api, json=payload, headers=headers, timeout=30)
    data = res.json()
    
    stream_url = data.get("url")
    if not stream_url:
        raise Exception(f"Error con Cobalt: {data}")

    with requests.get(stream_url, stream=True) as r:
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

def process_and_send(url, webhook_url):
    work_dir = '/tmp/clips'
    try:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        raw_path = os.path.join(work_dir, 'input.mp4')

        # 1. Descarga directa con Cobalt
        descargar_con_cobalt(url, raw_path)

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

        # Helper para recortar y enviar individualmente
        def recortar_y_enviar(inicio, fin):
            nonlocal clip_index
            clip_name = f'clip_{clip_index:03d}.mp4'
            out_clip = os.path.join(clips_dir, clip_name)
            
            cmd = ['ffmpeg', '-y', '-ss', str(inicio)]
            if fin is not None:
                cmd.extend(['-to', str(fin)])
            cmd.extend(['-i', raw_path, '-c', 'copy', out_clip])

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Enviar el archivo individual al Webhook de n8n
            if webhook_url and os.path.exists(out_clip):
                with open(out_clip, 'rb') as f:
                    files = {'file': (clip_name, f, 'video/mp4')}
                    requests.post(webhook_url, files=files)
                os.remove(out_clip) # Liberar memoria inmediatamente

            clip_index += 1

        # 3. Procesar y transmitir clip por clip
        for s_start, s_end in zip(starts, ends):
            duration = s_start - current_start
            if duration > 1.5:
                recortar_y_enviar(current_start, s_start)
            current_start = s_end

        # Último fragmento
        recortar_y_enviar(current_start, None)

        if os.path.exists(raw_path):
            os.remove(raw_path)

    except Exception as e:
        print(f"Error en el procesamiento: {str(e)}")

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url')
    webhook_url = data.get('webhook_url')
    
    if not url:
        return {"status": "error", "message": "Falta la URL"}, 400

    thread = threading.Thread(target=process_and_send, args=(url, webhook_url))
    thread.start()

    return jsonify({"status": "processing", "message": "El proceso ha comenzado. Los clips se enviarán secuencialmente."}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
