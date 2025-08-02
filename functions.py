import os, re, unicodedata
from pathlib import Path
from time import sleep

import streamlit as st
import pandas as pd
from tinytag import TinyTag
import yt_dlp
from gamdl.apple_music_api import AppleMusicApi
from rapidfuzz import fuzz
from PIL import Image


## TAGS

def get_song_tags(path: str) -> dict[str, any]:
    PATH = Path(path)
    if not PATH.suffix.lower() in TinyTag.SUPPORTED_FILE_EXTENSIONS:
        return None
    return TinyTag.get(path).as_dict()

def get_df_tags_from_path(path: str) -> pd.DataFrame:
    path_songs = [file for file in Path(path).rglob('*') if file.is_file() and file.suffix.lower() in TinyTag.SUPPORTED_FILE_EXTENSIONS]
    tag_songs = [TinyTag.get(file).as_dict() for file in path_songs]
    return pd.DataFrame(tag_songs)


## GAMDL

def get_playlist_id(url: str) -> str:
    match = re.search(r'/playlist/.+/([a-zA-Z0-9\.-]+)', url)
    return match.group(1) if match else None

def get_playlist_tracks(playlist_url) -> list:
    playlist_id = get_playlist_id(playlist_url)
    api = AppleMusicApi(storefront='es')
    playlist = api.get_playlist(playlist_id)
    pl_data = playlist['relationships']['tracks']['data']
    return [track['attributes'] for track in pl_data]


## DUPLICATES

def normalizar(valor):
    if isinstance(valor, list):
        valor = valor[0] if valor else ""
    return str(valor).lower().strip()

def clean_filename(name: str) -> str:
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r'[\\/:*?"<>|⧸]', '-', name)  # elimina caracteres peligrosos
    name = name.replace('？', '?')               # normaliza símbolos específicos
    return name.strip().lower()


def check_duplicates(track_apple: dict, df_local: pd.DataFrame, threshold: float = 90):
    artista_a = track_apple["artistName"].lower()
    titulo_a = track_apple["name"].lower()
    objetivo = f"{artista_a} {titulo_a}"

    for _, fila in df_local.iterrows():
        artista_b = normalizar(fila["artist"])
        titulo_b = normalizar(fila["title"])
        candidato = f"{artista_b} {titulo_b}"
        similitud = fuzz.token_set_ratio(objetivo, candidato)
        if similitud >= threshold:
            return True  # ya existe localmente
    
    return False

def get_not_duplicates(apple_playlist_url: str, path: str):
    apple_tracks = get_playlist_tracks(apple_playlist_url)
    df_local = get_df_tags_from_path(path)
    return [track for track in apple_tracks if not check_duplicates(track, df_local)]

## YUTUF

class YUTUF:
    __yutuf_formats = ['.mp4', '.webm', '.mkv', '.avi', '.mov']

    @staticmethod
    @st.cache_data
    def get_files(path: str, count: int) -> pd.DataFrame:
        files = [file for file in Path(path).rglob('*') if file.suffix.lower() in YUTUF.__yutuf_formats]
        files_with_dates = [(str(file), file.suffix.lower(), file.stat().st_ctime) for file in files]
        files_df = pd.DataFrame(files_with_dates, columns=['file', 'type', 'date'])
        files_df['date'] = pd.to_datetime(files_df['date'], unit='s').dt.strftime('%Y-%m-%d %H:%M')
        return files_df

    @staticmethod
    def download(yutuf_path: str, url: str, audio: bool = False) -> None:
        opts = {
            'format': 'bestvideo+bestaudio/best',  # Máxima calidad disponible
            'outtmpl': yutuf_path + '/%(title)s.%(ext)s',  # Ruta de guardado y nombre de archivo
            'merge_output_format': 'mp4',  # Fusionar video y audio en MP4
        }
        if audio:
            opts = {
                'format': 'bestaudio',
                'merge_output_format': 'webm',  # sin reencodeo
                # 'postprocessors': [{
                #     'key': 'FFmpegCopyAudio',  # copia sin reconvertir
                # }],
                'outtmpl': yutuf_path + '/%(title)s.%(ext)s',
            }

        with yt_dlp.YoutubeDL(opts) as ydl:
            if ydl.download([url]):
                st.rerun()

    
    @staticmethod
    def get_file_name(url: str):
        with yt_dlp.YoutubeDL() as ydl:
            info = ydl.extract_info(url, download=False)
            # print(info)
            # print(info.get('title', 'unknown'))
            # print(ydl.prepare_filename(info))
            return info.get('title', 'unknown')
    
    @staticmethod
    def get_thumbnail(yutuf_path: str, url: str):
        def create_jpg(webp_path: str):
            img = Image.open(webp_path).convert("RGB")
            jpg_path = webp_path.replace(".webp", ".jpg")
            img.save(jpg_path, "JPEG")
            os.remove(webp_path)
            return jpg_path
        
        thumb_opts = {
            'skip_download': True,
            'writethumbnail': True,
            'outtmpl': os.path.join(yutuf_path, '%(title)s.%(ext)s'),
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(thumb_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title")
            ext = "webp"  # yt-dlp suele descargar thumbnails en webp

            # Descargar la miniatura
            ydl.download([url])

            # Convertir a JPG si es webp
            for _ in range(10):
                webp_files = list(Path(yutuf_path).rglob("*.webp"))
                for f in webp_files:
                    file_name = normalizar(f.stem.replace(yutuf_path, ''))
                    ratio = fuzz.token_set_ratio(file_name, title)
                    if ratio > 50:
                        create_jpg(str(f))
                        st.rerun()
                        return 
                sleep(0.5)  # Esperar un poco antes de volver a comprobar
            st.rerun()
        
        return None
