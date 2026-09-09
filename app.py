import os
import tempfile
from flask import Flask, request, jsonify
import yt_dlp
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def upload_to_drive(file_path, file_name):
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json:
        raise Exception("Falta la variable de entorno GOOGLE_CREDENTIALS_JSON")

    creds_path = '/tmp/credentials.json'
    with open(creds_path, 'w') as f:
        f.write(creds_json)

    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': file_name}
    media = MediaFileUpload(file_path, resumable=True)

    file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    
    if os.path.exists(creds_path):
        os.remove(creds_path)

    return file.get('webViewLink'), file.get('id')

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

    if proxy_url:
        ydl_opts['proxy'] = proxy_url

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            return jsonify({'status': 'error', 'message': 'No se pudo descargar el archivo'}), 500

        # Subir a Google Drive
        file_name = os.path.basename(filename)
        web_link, file_id = upload_to_drive(filename, file_name)

        # Limpiar archivo local para liberar espacio en Render
        if os.path.exists(filename):
            os.remove(filename)

        return jsonify({
            'status': 'success',
            'drive_url': web_link,
            'file_id': file_id
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error de proceso: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
