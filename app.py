def descargar_video(youtube_url, output_path):
    # Limpiar URL por si viene con signo '=' al principio desde n8n
    youtube_url = youtube_url.lstrip("=")
    print(f"--> Descargando video con yt-dlp usando cliente movil y cookies: {youtube_url}")

    # Forzar el cliente 'ios' y 'mweb' con el archivo de cookies
    cmd = [
        'yt-dlp',
        '--cookies', 'cookies.txt',  # <-- LÍNEA AGREGADA
        '--extractor-args', 'youtube:player_client=ios,mweb',
        '-f', 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '--no-playlist',
        '--merge-output-format', 'mp4',
        '-o', output_path,
        youtube_url
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode != 0:
        print(f"--> Intento 1 fallido: {result.stderr}")
        print("--> Reintentando con cliente 'android'...")
        
        # Segundo intento con cliente android de respaldo y cookies
        cmd_alt = [
            'yt-dlp',
            '--cookies', 'cookies.txt',  # <-- LÍNEA AGREGADA
            '--extractor-args', 'youtube:player_client=android',
            '-f', 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--no-playlist',
            '--merge-output-format', 'mp4',
            '-o', output_path,
            youtube_url
        ]
        res_alt = subprocess.run(cmd_alt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if res_alt.returncode != 0:
            raise Exception(f"No se pudo descargar de YouTube: {res_alt.stderr}")

    print("--> Descarga completada con éxito.")
