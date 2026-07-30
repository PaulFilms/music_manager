'''
wrapper from yt_dlp to download music from youtube and other sites
'''

import yt_dlp

# def get_files(url: str, count: int) -> pd.DataFrame:
#     files = [file for file in Path(path).rglob('*') if file.suffix.lower() in YUTUF.__yutuf_formats]
#     files_with_dates = [(str(file), file.suffix.lower(), file.stat().st_ctime) for file in files]
#     files_df = pd.DataFrame(files_with_dates, columns=['file', 'type', 'date'])
#     files_df['date'] = pd.to_datetime(files_df['date'], unit='s').dt.strftime('%Y-%m-%d %H:%M')
#     return files_df


def download(path: str, url: str, audio: bool = False) -> bool:
    '''
    Download a video or audio from a given URL using yt_dlp.

    Args:
        path (str): The directory where the downloaded file will be saved.
        url (str): The URL of the video or audio to download.
        audio (bool): If True, download only the audio. If False, download both video and audio.

    Returns:
        bool: True if the download was successful, False otherwise.
    '''
    opts = {
        'format': 'bestvideo+bestaudio/best',  # Máxima calidad disponible
        'outtmpl': path + '/%(title)s.%(ext)s',  # Ruta de guardado y nombre de archivo
        'merge_output_format': 'mp4',  # Fusionar video y audio en MP4
    }
    if audio:
        opts = {
            'format': 'bestaudio',
            'merge_output_format': 'webm',  # sin reencodeo
            # 'postprocessors': [{
            #     'key': 'FFmpegCopyAudio',  # copia sin reconvertir
            # }],
            'outtmpl': path + '/%(title)s.%(ext)s',
        }

    with yt_dlp.YoutubeDL(opts) as ydl:
        if ydl.download([url]):
            # st.rerun()
            return True
    
    return False


def get_items(url: str) -> list[str]:
    '''
    Returns a list of item URLs from a playlist, album or any collection.
    If the URL points to a single video, returns a list with just that URL.
    '''
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info is None:
        return []

    if info.get('_type') == 'playlist':
        return [
            entry['url']
            for entry in info.get('entries', [])
            if entry is not None and entry.get('url')
        ]

    item_url = info.get('webpage_url') or url
    return [item_url]
