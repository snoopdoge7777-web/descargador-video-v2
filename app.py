import os
import tempfile
from flask import Flask, request, send_file, jsonify
import yt_dlp

app = Flask(__name__)

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'status': 'error', 'message': 'Falta el parámetro url'}), 400

    url = data['url']
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, 'clipped_video.mp4')

    proxy_url = os.environ.get('PROXY_URL')

    # Definir un rango de corte (Ejemplo: desde el segundo 30 hasta el 45)
    start_time = 30
    end_time = 45

    ydl_opts = {
        'format': 'b[height<=720]/best[height<=720]/b/best',
        'outtmpl': output_template,
        'noplaylist': True,
        # Esto le dice a yt-dlp que descargue únicamente el fragmento indicado ahorrando RAM y ancho de banda
        'download_ranges': yt_dlp.utils.download_range_func(None, [(start_time, end_time)]),
        'force_keyframes_at_cuts': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['tv_embedded', 'web', 'mweb']
            },
            'youtubetab': {
                'skip': ['authcheck']
            }
        },
        'quiet': False,
        'no_warnings': False,
    }

    if proxy_url:
        ydl_opts['proxy'] = proxy_url

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(output_template):
            return jsonify({'status': 'error', 'message': 'No se pudo generar el recorte'}), 500

        return send_file(output_template, as_attachment=True, download_name='clip.mp4')

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error de proceso: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
