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



    # Lee el proxy desde las variables de Render

    proxy_url = os.environ.get('PROXY_URL')



    ydl_opts = {

        'format': 'b/best[ext=mp4]/best',

        'outtmpl': output_template,

        'noplaylist': True,

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



    # Asigna el proxy para salir por la IP limpia de Webshare

    if proxy_url:

        ydl_opts['proxy'] = proxy_url



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
