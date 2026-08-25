import os
import re
import shutil
import subprocess
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

def descargar_con_cobalt(youtube_url, output_path):
    print(f"--> Iniciando descarga desde Cobalt para: {youtube_url}")
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

    print("--> Cobalt generó el enlace. Descargando archivo MP4...")
    with requests.get(stream_url, stream=True) as r:
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print("--> Descarga completada con éxito.")

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
                print(f"--> Enviando {clip_name} al Webhook de n8n ({webhook_url})...")
                with open(out_clip, 'rb') as f:
                    files = {'data': (clip_name, f, 'video/mp4')}
                    response = requests.post(webhook_url, files=files)
                    print(f"--> Estado de envío para {clip_name}: {response.status_code}")
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
    
    # Busca 'url' o 'targetUrl' (según cómo lo mande n8n)
    url = data.get('url') or data.get('targetUrl')
    
    # Busca 'webhook_url' o 'webhookUrl'
    webhook_url = data.get('webhook_url') or data.get('webhookUrl')
    
    print(f"--> Petición recibida en /download. URL: {url} | Webhook: {webhook_url}")

    if not url:
        return jsonify({"status": "error", "message": "Falta la URL del video"}), 400

    thread = threading.Thread(target=process_and_send, args=(url, webhook_url))
    thread.start()

    return jsonify({"status": "processing", "message": "El proceso ha comenzado. Los clips se enviarán secuencialmente."}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
