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

    proxy_url = os.environ.get('PROXY_URL')

    ydl_opts = {
        # Fuerza la mejor combinación de video y audio hasta 1080p
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        'merge_output_format': 'mp4',
        'outtmpl': output_template,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                # Forzar el cliente mweb y web junto con el bypass de nsig
                'player_client': ['mweb', 'web']
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
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            base, _ = os.path.splitext(filename)
            mp4_filename = base + '.mp4'
            if os.path.exists(mp4_filename):
                filename = mp4_filename

        return send_file(filename, as_attachment=True)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error de proceso: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
