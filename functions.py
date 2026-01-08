import os, re, unicodedata, subprocess, io
from pathlib import Path
from time import sleep
from enum import Enum
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs, urlunparse, unquote
from typing import List, Dict, Any

import streamlit as st
import pandas as pd
import numpy as np
from tinytag import TinyTag
import yt_dlp
# from gamdl.apple_music_api import AppleMusicApi
from gamdl.api import AppleMusicApi
from rapidfuzz import fuzz
from PIL import Image
import librosa
import plotly.graph_objects as go

__version__ = '2025.08.09'


## FUNCTIONS

def normalizar(valor):
    if isinstance(valor, list):
        valor = valor[0] if valor else ""
    return str(valor).lower().strip()

def clean_filename(name: str) -> str:
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r'[\\/:*?"<>|⧸]', '-', name)  # elimina caracteres peligrosos
    name = name.replace('？', '?')               # normaliza símbolos específicos
    return name.strip().lower()

common_formats = ['.aac', '.flac', '.m4a', '.mp3', '.ogg', '.opus', '.wav']

def get_audio_properties(file_path) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration:stream=sample_rate,channels,bit_rate",
        "-of", "default=noprint_wrappers=1",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    props = {}
    for line in result.stdout.splitlines():
        if '=' in line:
            k, v = line.strip().split('=', 1)
            props[k] = v
    
    if 'sample_rate' in props:
        props['sample_rate'] = f"{props['sample_rate']} Hz"
    # Convertir duración a mm:ss si es posible
    
    if 'duration' in props:
        try:
            dur = float(props['duration'])
            mins = int(dur // 60)
            secs = int(dur % 60)
            props['duration'] = f"{mins:02d}:{secs:02d}"
        except Exception:
            pass
    
    try:
        size = os.path.getsize(file_path)
        if size > 1e9: size = f'{size/1e9:.2f} GB'
        elif size > 1e6: size = f'{size/1e6:.2f} MB'
        elif size > 1e3: size = f'{size/1e3:.2f} kB'
        else:
            size = f'{size:.2f} B'
        props['size'] = size
    except Exception:
        pass

    return props

def get_waveform(audio_path: str):
    # Cargar audio
    y, sr = librosa.load(audio_path, sr=None, mono=True)

    # Número de "barras"
    num_windows = 1000
    hop_length = len(y) // num_windows

    # Calcular solo máximos (parte positiva de la señal)
    envelope = []
    for i in range(num_windows):
        start = i * hop_length
        end = start + hop_length
        segment = y[start:end]
        if len(segment) > 0:
            envelope.append(segment.max())

    envelope = np.array(envelope)
    times = np.linspace(0, len(y)/sr, num_windows)

    # Crear figura Plotly
    fig = go.Figure()

    # Forma de onda positiva en amarillo
    fig.add_trace(go.Scatter(
        x=np.concatenate([times, times[::-1]]),
        y=np.concatenate([np.zeros_like(envelope), envelope[::-1]]),  # desde 0 hasta max
        fill="toself",
        line=dict(color="yellow"),
        fillcolor="yellow",
        hoverinfo="skip",
        showlegend=False
    ))

    # Configuración limpia y altura fija (100px)
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        dragmode=False,
        height=100  # altura de 100px
    )

    # Render en Streamlit
    return st.plotly_chart(
        fig, 
        width='stretch', 
        config= {
            "staticPlot": True,
            "displayModeBar": False
        }
    )

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

@dataclass
class track_check:
    artist: str
    name: str

def check_duplicates(
        track: track_check,
        df_local: pd.DataFrame,
        threshold: float = 80,
        ) -> bool:
    
    artista_a = normalizar(track.artist)
    titulo_a = normalizar(track.name)
    objetivo = f"{artista_a} {titulo_a}"

    for _, fila in df_local.iterrows():
        artista_b = normalizar(fila["artist"])
        titulo_b = normalizar(fila["title"])
        candidato = f"{artista_b} {titulo_b}"

        similitud = fuzz.token_set_ratio(objetivo, candidato)

        if similitud >= threshold:
            return True

    return False

## FFMPEG

class MMFILE:
    pass



## GAMDL

class APPL:
    
    class URLType(str, Enum):
        TRACK = "track"
        MUSIC_VIDEO = 'music-video'
        ALBUM = "album"
        PLAYLIST = "playlist"
        ARTIST = "artist"

        @classmethod
        def get_type(cls, url: str) -> 'APPL.URLType':
            url = unquote(url).lower().rstrip("/")
            parsed = urlparse(url)
            path = parsed.path

            if parsed.query:
                return cls.TRACK
            
            if cls.ALBUM in path:
                return cls.ALBUM
            
            if cls.PLAYLIST in path:
                return cls.PLAYLIST
            
            if cls.ARTIST in path:
                return cls.ARTIST
            
            if cls.MUSIC_VIDEO in path:
                return cls.MUSIC_VIDEO

            return None

    @staticmethod
    def extract_single_track(data: dict) -> list[dict]:
        try:
            return [data["data"][0]["attributes"]]
        except (KeyError, IndexError):
            return []

    @staticmethod
    def extract_tracks(data: dict) -> list[dict]:
        # ["data"][0]["relationships"]["tracks"]["data"][0]["attributes"].keys()
        try:
            items = (
                data["data"][0]
                .get("relationships", {})
                .get("tracks", {})
                .get("data", [])
            )
        except (KeyError, IndexError):
            return []
        
        tracks = []

        for t in items:
            attr = t.get("attributes", {})
            tracks.append(attr)

        return tracks

    async def get_tracks(url: str, cookies_path: str):
        url_type = APPL.URLType.get_type(url)
        parsed = urlparse(url)
        path = parsed.path
        parts = path.strip("/").split("/")
        
        collection_id = parts[-1]

        api = await AppleMusicApi.create_from_netscape_cookies(
            cookies_path=cookies_path
        )

        if url_type == APPL.URLType.TRACK:
            query = parse_qs(parsed.query)
            song_id = query.get("i", [None])[0]
            data = await api.get_song(song_id)
            return APPL.extract_single_track(data)

        if url_type == APPL.URLType.PLAYLIST:
            data = await api.get_playlist(collection_id, limit_tracks=300)
            return APPL.extract_tracks(data)
        
        if url_type == APPL.URLType.ALBUM:
            data = await api.get_album(collection_id)
            return APPL.extract_tracks(data)
        
        if url_type == APPL.URLType.ARTIST:
            artist = await api.get_artist(collection_id)
            albums = (
                artist["data"][0]
                .get("relationships", {})
                .get("albums", {})
                .get("data", [])
            )

            tracks = []
            for a in albums:
                tracks.extend(await APPL.get_tracks(a["attributes"]["url"]))

            return tracks
        
        return []

    @staticmethod
    def get_track(url: str) -> None:
        cmd = [
            "gamdl",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

## YUTUF

class YUTUF:
    __yutuf_formats = ['.mp4', '.webm', '.mkv', '.avi', '.mov']

    @staticmethod # @st.cache_data
    def get_files(path: str, count: int) -> pd.DataFrame:
        files = [file for file in Path(path).rglob('*') if file.suffix.lower() in YUTUF.__yutuf_formats]
        files_with_dates = [(str(file), file.suffix.lower(), file.stat().st_ctime) for file in files]
        files_df = pd.DataFrame(files_with_dates, columns=['file', 'type', 'date'])
        files_df['date'] = pd.to_datetime(files_df['date'], unit='s').dt.strftime('%Y-%m-%d %H:%M')
        return files_df

    @staticmethod
    def download(yutuf_path: str, url: str, audio: bool = False) -> int:
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
                # st.rerun()
                return 1

    
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
                        # st.rerun()
                        return 
                sleep(0.5)  # Esperar un poco antes de volver a comprobar
            # st.rerun()
        
        return None


## TEST

# import soundfile as sf
# import numpy as np
# import plotly.graph_objects as go
# import streamlit as st

# def get_waveform(audio_path: str):
#     y, sr = sf.read(audio_path, dtype="float32")

#     # Si es estéreo → mono
#     if y.ndim > 1:
#         y = y.mean(axis=1)

#     num_windows = 1000
#     hop_length = len(y) // num_windows

#     # Envelope (max absoluto, más correcto visualmente)
#     envelope = np.maximum.reduceat(
#         np.abs(y),
#         np.arange(0, len(y), hop_length)
#     )[:num_windows]

#     times = np.linspace(0, len(y) / sr, len(envelope))

#     fig = go.Figure()
#     fig.add_trace(go.Scatter(
#         x=np.concatenate([times, times[::-1]]),
#         y=np.concatenate([np.zeros_like(envelope), envelope[::-1]]),
#         fill="toself",
#         line=dict(color="yellow"),
#         fillcolor="yellow",
#         hoverinfo="skip",
#         showlegend=False
#     ))

#     fig.update_layout(
#         xaxis=dict(visible=False),
#         yaxis=dict(visible=False),
#         margin=dict(l=0, r=0, t=0, b=0),
#         plot_bgcolor="rgba(0,0,0,0)",
#         paper_bgcolor="rgba(0,0,0,0)",
#         dragmode=False,
#         height=100
#     )

#     return st.plotly_chart(
#         fig,
#         width="stretch",
#         config={"staticPlot": True, "displayModeBar": False}
#     )
