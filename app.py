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
    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

    ydl_opts = {
        # 1. Solicita un solo formato combinado para no hacer peticiones dobles de audio/video
        'format': 'b/best[ext=mp4]/best',
        'outtmpl': output_template,
        
        # 2. Tu archivo de cookies recargado
        'cookiefile': 'www.youtube.com_cookies.txt',
        
        # 3. Evita procesar listas de reproducción enteras
        'noplaylist': True,
        
        # 4. Reduce peticiones secundarias
        'writethumbnail': False,
        'writeinfojson': False,
        'ignoreerrors': False,
        
        # 5. Restringe las consultas a un solo cliente móvil liviano para minimizar llamadas a la API
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb'],
                'skip': ['dash', 'hls']  # Salta fragmentación innecesaria
            },
            'youtubetab': {
                'skip': ['authcheck']
            }
        },
        'quiet': False,
        'no_warnings': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        return send_file(filename, as_attachment=True)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error de proceso: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
