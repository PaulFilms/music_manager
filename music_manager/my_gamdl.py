'''
Wrapper of gamdl module

`source:` https://github.com/glomatico/gamdl.git

include:
- AppleMusicService
'''

from dataclasses import dataclass, asdict
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Optional, Any
import sqlite3

from gamdl.api import AppleMusicApi
from gamdl.downloader import (
    AppleMusicBaseDownloader,
    AppleMusicDownloader,
    AppleMusicMusicVideoDownloader,
    AppleMusicSongDownloader,
    AppleMusicUploadedVideoDownloader,
)
from gamdl.interface import (
    AppleMusicBaseInterface,
    AppleMusicInterface,
    AppleMusicMusicVideoInterface,
    AppleMusicSongInterface,
    AppleMusicUploadedVideoInterface,
)
from gamdl.interface.enums import SongCodec
# from rapidfuzz import fuzz

# BUG: Importar
# Esta funcion esta en music_manager/tags.py
# import sys
# sys.path.append("/home/pgp/Documents/Develop/music_manager")
## Quitar warning de import fantasma
from music_manager.tags import Extractor # normalize 


@dataclass
class AM_Metadata:
    artist: str
    title: str
    album: str
    genre: str
    year: int
    duration: int
    thumbnail: bytes | None
    url: str

    def to_dict(self) -> dict:
        return {
            "artist": self.artist,
            "title": self.title,
            "album": self.album,
            "genre": self.genre,
            "year": self.year,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "url": self.url,
        }

class AppleMusicService:
    '''
    Service for interacting with A_Music.

    `[async] methods`:
    - get_song_tags(url: str) -> dict: Get the tags of a song.
    - get_items(url: str) -> list[AM_Metadata]: Preview songs before downloading.
    - download_song(url: str) -> list[dict]: Download a song and return information about the result.

    Use as an async context manager within one event loop to reuse the clients
    across a batch and close them before that loop exits.
    '''
    def __init__(self, cookies_path: str, output_path: str = "downloads"):
        self.cookies_path = cookies_path
        self.output_path = Path(output_path)

        self.apple_music_api = None
        self.base_interface = None
        self.interface = None
        self.downloader = None

        self._api_ready = False
        self._initialized = False

    async def __aenter__(self) -> "AppleMusicService":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the owned HTTP clients, including after failed initialization."""
        async with AsyncExitStack() as stack:
            if self.apple_music_api is not None:
                stack.push_async_callback(self.apple_music_api.client.aclose)
            if self.base_interface is not None:
                stack.push_async_callback(self.base_interface.itunes_api.client.aclose)
            self.apple_music_api = None
            self.base_interface = None
            self.interface = None
            self.downloader = None
            self._api_ready = False
            self._initialized = False

    async def _init_api(self):
        """Nivel ligero: solo lo necesario para consultar tags."""

        if self._api_ready:
            return

        self.apple_music_api = await AppleMusicApi.create_from_netscape_cookies(
            cookies_path=self.cookies_path,
        )

        if not self.apple_music_api.active_subscription:
            raise RuntimeError("No active Apple Music subscription")

        self.base_interface = await AppleMusicBaseInterface.create(
            apple_music_api=self.apple_music_api,
        )

        self._api_ready = True

    async def initialize(self):
        """Nivel completo: interfaces y downloaders (necesario para descargar)."""

        if self._initialized:
            return

        await self._init_api()

        song_interface = AppleMusicSongInterface(
            base=self.base_interface,
            codec_priority=[SongCodec.AAC_WEB],
        )
        music_video_interface = AppleMusicMusicVideoInterface(base=self.base_interface)
        uploaded_video_interface = AppleMusicUploadedVideoInterface(base=self.base_interface)

        self.interface = AppleMusicInterface(
            song=song_interface,
            music_video=music_video_interface,
            uploaded_video=uploaded_video_interface,
        )

        base_downloader = AppleMusicBaseDownloader(
            interface=self.interface,
            output_path=self.output_path,
        )

        self.downloader = AppleMusicDownloader(
            song=AppleMusicSongDownloader(base=base_downloader),
            music_video=AppleMusicMusicVideoDownloader(base=base_downloader),
            uploaded_video=AppleMusicUploadedVideoDownloader(base=base_downloader),
        )

        self._initialized = True

    # ---------- MODO RÁPIDO: solo tags ----------

    async def get_song_tags(self, url: str) -> dict:
        """
        Tags de UNA canción por la vía rápida:
        regex local + webplayback + lookup iTunes. Sin portada, lyrics,
        stream info ni decryption key.
        """

        await self._init_api()

        url_info = AppleMusicInterface.get_url_info(url)
        if not url_info:
            raise ValueError(f"URL no válida: {url}")

        song_id = url_info.sub_id or url_info.id or url_info.library_id
        is_library = bool(url_info.library_type)

        webplayback = await self.apple_music_api.get_webplayback(song_id, is_library)
        asset_metadata = webplayback["songList"][0]["assets"][0]["metadata"]

        tags = await self.base_interface.get_tags_from_asset_info(asset_metadata)
        return asdict(tags)

    # ---------- EXPANSIÓN DE COLECCIONES ----------

    async def get_urls(self, url: str) -> list[str]:
        """
        Devuelve las URLs de las canciones de una URL.

        - Canción (o álbum con ?i=) -> [url]
        - Álbum o playlist          -> [url_track_1, url_track_2, ...]

        Los music-videos dentro de colecciones se omiten.
        """

        await self._init_api()

        url_info = AppleMusicInterface.get_url_info(url)
        if not url_info:
            raise ValueError(f"URL no válida: {url}")

        is_library = bool(url_info.library_type)

        # Canción individual (incluye URL de álbum con ?i=)
        if url_info.type == "song" or url_info.sub_id or url_info.library_type == "songs":
            return [url]

        media_id = url_info.id or url_info.library_id

        if url_info.type == "album" or url_info.library_type == "albums":
            metadata = (
                await (
                    self.apple_music_api.get_library_album(media_id)
                    if is_library
                    else self.apple_music_api.get_album(media_id)
                )
            )["data"][0]
            tracks = metadata["relationships"]["tracks"]["data"]

        elif url_info.type == "playlist" or url_info.library_type == "playlist":
            metadata = (
                await (
                    self.apple_music_api.get_library_playlist(media_id)
                    if is_library
                    else self.apple_music_api.get_playlist(media_id)
                )
            )["data"][0]

            tracks_rel = metadata["relationships"]["tracks"]
            tracks = tracks_rel["data"]

            # Las playlists paginan: drenar las páginas restantes
            next_uri = tracks_rel.get("next")
            href_uri = tracks_rel.get("href")
            while next_uri:
                extended = await self.apple_music_api.get_extended_api_data(
                    next_uri, href_uri
                )
                tracks.extend(extended["data"])
                next_uri = extended.get("next")

        else:
            raise ValueError(
                f"Tipo de URL no soportado por get_urls: {url_info.type}"
            )

        base_url = url.split("?")[0]

        return [
            track.get("attributes", {}).get("url") or f"{base_url}?i={track['id']}"
            for track in tracks
            if track["type"] in {"songs", "library-songs"}
        ]

    async def get_items(self, url: str) -> list[AM_Metadata]:
        """Preview a song, album or playlist without downloading audio.

        Uses get_urls to expand collections, preserving their order. Channel
        contains the artist, duration is in seconds, and thumbnail contains
        cover bytes when available. Description uses editorial notes or the
        album name. Missing optional attributes are returned as None.
        """
        urls = await self.get_urls(url)
        items: list[AM_Metadata] = []

        for song_url in urls:
            url_info = AppleMusicInterface.get_url_info(song_url)
            if not url_info:
                raise ValueError(f"Invalid song URL: {song_url}")

            song_id = url_info.sub_id or url_info.id or url_info.library_id
            response = await (
                self.apple_music_api.get_library_song(song_id)
                if url_info.library_type
                else self.apple_music_api.get_song(song_id)
            )
            metadata = response["data"][0]
            attributes = metadata.get("attributes") or {}
            notes = attributes.get("editorialNotes") or {}
            duration_ms = attributes.get("durationInMillis")
            thumbnail = None
            artwork = attributes.get("artwork") or {}
            if artwork.get("url"):
                try:
                    cover_url = self.base_interface.format_cover(
                        artwork["url"],
                        self.base_interface.cover_size,
                        self.base_interface.cover_format,
                    )
                    thumbnail = await self.base_interface.get_cover_bytes(cover_url)
                except Exception:
                    thumbnail = None

            items.append(AM_Metadata(
                artist=attributes.get("artistName"),
                title=attributes.get("name"),
                album=attributes.get("albumName"),
                genre=attributes.get("genreNames")[0] if attributes.get("genreNames") else None,
                year=attributes.get("releaseDate")[:4] if attributes.get("releaseDate") else None,
                duration=int(duration_ms / 1000) if duration_ms is not None else None,
                url=song_url,
                thumbnail=thumbnail,

            ))

        return items

    # ---------- DESCARGA ----------

    async def download_song(self, 
        url: str, filename_mode: int = 0, 
        # db: Optional[str | Path] = None, threshold: float = 80
        ) -> list[dict]:
        """
        Descarga y devuelve resultados útiles (path, tags, errores).  

        Args:
            url (str): URL de la canción a descargar.
            filename_mode (int): 
                - 0. Single `artist - title` 
                - 1. Album `album - track - title`
            db (Optional[str | Path], optional): Ruta a la base de datos SQLite. Por defecto es None.
            threshold (float, optional): Umbral de similitud para evitar duplicados en la DB. Por defecto es 80.

        Returns:
            list[dict]: Resultados con "success" y "final_path"/"tags" o "error".
                Si no hay medios descargables, devuelve un error explicito.
                Los errores al expandir la URL pueden propagarse al llamador.

        """

        if not self._initialized:
            await self.initialize()

        ## BUG: Quietar de aqui y pasar a tags
        ## DB
        # if db is not None:
        #     if not isinstance(db, (str, Path)):
        #         raise ValueError(f"DB must be a string or Path, got {type(db)}")
        #     if not Path(db).exists():
        #         raise ValueError(f"DB file does not exist: {db}")
        #     try:
        #         conn = sqlite3.connect(db)
        #     except Exception as e:
        #         raise ValueError(f"Failed to connect to DB: {e}")

        #     # Compruebo que exista la tabla 'files'
        #     try:
        #         cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files';")
        #         table_exists = cursor.fetchone()
        #         if not table_exists:
        #             raise ValueError("La tabla 'files' no existe en la DB")
        #     except Exception as e:
        #         raise ValueError(f"Failed to check 'files' table in DB: {e}")

        #     tags = await self.get_song_tags(url)

        #     filename = Extractor.get_filename_from_tags(tags, mode=filename_mode)
        #     cursor = conn.execute("SELECT filename FROM files")
        #     candidatos = [e[0] for e in cursor.fetchall()]

        #     for candidato in candidatos:
        #         if fuzz.ratio(filename, candidato) >= threshold:
        #             return [{"success": False, "error": "File already exists in DB"}]

        #         # similitud = fuzz.token_set_ratio(objetivo, candidato)

        #         # if similitud >= threshold:
        #         #     return True


        ## Download
        results = []

        async for item in self.downloader.get_download_item_from_url(url):
            media = item.media

            if media.error:
                results.append({"success": False, "error": str(media.error)})
                continue

            if media.partial:
                continue

            try:
                # Nombre de salida con el saneador propio (sin extensión rara)
                custom_name = Extractor.get_filename_from_tags(
                    asdict(media.tags) if media.tags else {},
                    mode=filename_mode,
                )

                ext = Path(item.final_path).suffix or ".m4a"
                item.final_path = str(self.output_path / f"{custom_name}{ext}")

                # Archivos auxiliares coherentes con el nuevo nombre
                # if item.synced_lyrics_path:
                #     item.synced_lyrics_path = str(
                #         self.output_path / f"{custom_name}.lrc"
                #     )
                item.synced_lyrics_path = None
                
                if item.cover_path:
                    item.cover_path = str(
                        self.output_path / f"Cover{Path(item.cover_path).suffix}"
                    )

                await self.downloader.download(item)
                if not Path(item.final_path).is_file():
                    raise RuntimeError(f"Downloaded file not found: {item.final_path}")
                results.append({
                    "success": True,
                    "final_path": item.final_path,
                    "tags": asdict(media.tags) if media.tags else None,
                })
            except Exception as e:
                results.append({"success": False, "error": str(e)})

        return results or [{"success": False, "error": "No downloadable media found"}]


# import asyncio
# import mimetypes
# from pathlib import Path
# from typing import Any
# from dataclasses import asdict

# from gamdl.api import AppleMusicApi
# from gamdl.downloader import (
#     AppleMusicBaseDownloader,
#     AppleMusicDownloader,
#     AppleMusicMusicVideoDownloader,
#     AppleMusicSongDownloader,
#     AppleMusicUploadedVideoDownloader,
# )
# from gamdl.interface import (
#     AppleMusicBaseInterface,
#     AppleMusicInterface,
#     AppleMusicMusicVideoInterface,
#     AppleMusicSongInterface,
#     AppleMusicUploadedVideoInterface,
# )
# from gamdl.interface.enums import SongCodec


# class AppleMusicService:
#     def __init__(
#         self,
#         cookies_path: str,
#         output_path: str = "downloads",
#     ):
#         self.cookies_path = cookies_path
#         self.output_path = Path(output_path)

#         self.apple_music_api = None
#         self.base_interface = None
#         self.interface = None
#         self.base_downloader = None
#         self.downloader = None

#         self._initialized = False

#     async def initialize(self):
#         """Inicializa Apple Music y todos los downloaders."""

#         if self._initialized:
#             return

#         # Apple Music API
#         self.apple_music_api = await AppleMusicApi.create_from_netscape_cookies(
#             cookies_path=self.cookies_path,
#         )

#         if not self.apple_music_api.active_subscription:
#             raise RuntimeError(
#                 "No active Apple Music subscription"
#             )

#         # Base interface
#         self.base_interface = await AppleMusicBaseInterface.create(
#             apple_music_api=self.apple_music_api,
#         )

#         # Song
#         song_interface = AppleMusicSongInterface(
#             base=self.base_interface,
#             codec_priority=[SongCodec.AAC_WEB],
#         )

#         # Music videos
#         music_video_interface = AppleMusicMusicVideoInterface(
#             base=self.base_interface,
#         )

#         # Uploaded videos
#         uploaded_video_interface = AppleMusicUploadedVideoInterface(
#             base=self.base_interface,
#         )

#         # Main interface
#         self.interface = AppleMusicInterface(
#             song=song_interface,
#             music_video=music_video_interface,
#             uploaded_video=uploaded_video_interface,
#         )

#         # Base downloader
#         self.base_downloader = AppleMusicBaseDownloader(
#             interface=self.interface,
#             output_path=self.output_path,
#         )

#         # Specialized downloaders
#         song_downloader = AppleMusicSongDownloader(
#             base=self.base_downloader,
#         )

#         music_video_downloader = AppleMusicMusicVideoDownloader(
#             base=self.base_downloader,
#         )

#         uploaded_video_downloader = AppleMusicUploadedVideoDownloader(
#             base=self.base_downloader,
#         )

#         # Main downloader
#         self.downloader = AppleMusicDownloader(
#             song=song_downloader,
#             music_video=music_video_downloader,
#             uploaded_video=uploaded_video_downloader,
#         )

#         self._initialized = True

#     async def download_song(self, url: str):
#         """
#         Descarga una canción desde una URL de Apple Music.

#         Devuelve una lista con los resultados de descarga.
#         """

#         if not self._initialized:
#             await self.initialize()

#         results = []

#         async for download_item in self.downloader.get_download_item_from_url(url):
#             try:
#                 result = await self.downloader.download(download_item)
#                 results.append(result)

#             except Exception as e:
#                 results.append({
#                     "url": url,
#                     "success": False,
#                     "error": str(e),
#                 })

#         return results


#     ## UNDER TEST

#     async def get_song_info(self, url: str) -> list[dict]:
#         """
#         Obtiene info y tags de una URL SIN descargar el audio.

#         Funciona con URLs de canción, álbum o playlist.
#         """

#         if not self._initialized:
#             await self.initialize()

#         infos = []

#         async for item in self.downloader.get_download_item_from_url(url):
#             media = item.media

#             if media.error:
#                 infos.append({
#                     "url": url,
#                     "success": False,
#                     "error": str(media.error),
#                 })
#                 continue

#             if media.partial:
#                 continue  # item preliminar sin tags, lo ignoramos

#             infos.append({
#                 "success": True,
#                 "media_id": media.media_id,
#                 "tags": asdict(media.tags) if media.tags else None,
#                 "cover_url": media.cover.url if media.cover else None,
#                 "lyrics_synced": media.lyrics.synced if media.lyrics else None,
#                 "lyrics_unsynced": media.lyrics.unsynced if media.lyrics else None,
#                 "final_path": item.final_path,
#             })

#         return infos