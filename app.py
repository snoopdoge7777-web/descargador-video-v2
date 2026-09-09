import os
import tempfile
from flask import Flask, request, jsonify
import yt_dlp
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# Configuración de Google Drive (Lee las credenciales desde una variable de entorno en Render)
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def upload_to_drive(file_path, file_name):
    """Sube el archivo descargado a Google Drive y retorna el enlace web."""
    # Puedes guardar tus credenciales de Service Account en una variable de entorno llamada GOOGLE_CREDENTIALS_JSON
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json:
        raise Exception("Falta la variable de entorno GOOGLE_CREDENTIALS_JSON")

    # Guardar temporalmente el JSON de credenciales
    creds_path = '/tmp/credentials.json'
    with open(creds_path, 'w') as f:
        f.write(creds_json)

    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': file_name}
    media = MediaFileUpload(file_path, resumable=True)

    file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    
    # Limpiar archivo temporal de credenciales
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
    output_template = os.path.join(temp_dir, 'source_video.mp4')

    proxy_url = os.environ.get('PROXY_URL')

    # Opciones de yt-dlp seguras y limitadas a 720p para cuidar la RAM de Render
    ydl_opts = {
        'format': 'b[height<=720]/best[height<=720]/b/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },
        'quiet': True
    }

    if proxy_url:
        ydl_opts['proxy'] = proxy_url

    try:
        # 1. Descargar el video de YouTube en Render
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(output_template):
            # Buscar si se guardó con otra extensión por el merge
            files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith('.mp4')]
            if files:
                output_template = files[0]
            else:
                return jsonify({'status': 'error', 'message': 'No se pudo descargar el video'}), 500

        # 2. Subir directamente a Google Drive
        file_name = f"youtube_video_{os.path.basename(output_template)}"
        web_link, file_id = upload_to_drive(output_template, file_name)

        # 3. Borrar el video localmente en Render para liberar espacio/RAM de inmediato
        if os.path.exists(output_template):
            os.remove(output_template)

        # 4. Devolver la URL de Drive a n8n
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
