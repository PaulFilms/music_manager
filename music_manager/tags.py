'''
Toolkit with simplified functions and methods for audio file tags and names

Include:
    - normalize
    - get_tags
    - get_df_tags_from_path
    - get_filename_from_tags
    - TrackCheck

    
BUG's:

- Crear clase TrackLibrary
- set_tags: a un mp3, error al insertar List[str]
'''

## OPTIONAL IMPORTS
# from __future__ import annotations
# from typing import TYPE_CHECKING

import sqlite3
import re
import base64
import unicodedata
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import Any
from mutagen import File as MutagenFile
from mutagen.id3 import (
    ID3Tags, COMM,
    TIT2, TIT3, TPE1, TPE2, TALB, TRCK, TPOS, TCON, TDRC, TCOM, TBPM, USLT, APIC,
)
from mutagen.mp4 import MP4Tags, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen.apev2 import APEv2, APEBinaryValue
from mutagen._vorbis import VCommentDict
from rapidfuzz import fuzz

from music_manager import __version__



MAX_LENGTH = 100

INVALID_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]+')
SPACE_RE = re.compile(r'\s+')
EXTRA_RE = re.compile(r"[^\w\s\-.()&+,]")
SEPARATOR_RE = re.compile(r"[_\-. ]+")
WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

def normalize(value: Any) -> str:
    """
    Returns a normalized str to avoid problems with incompatible characters
    """

    if value is None:
        return "unknown"

    ## Iterables

    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):

        values = [
            normalize(v)
            for v in value
        ]

        values = [
            v if v else "untranslatable"
            for v in values
        ]

        return ", ".join(values)

    ## Texto

    value = str(value).strip()

    if not value:
        return "unknown"

    value = unicodedata.normalize("NFKD", value)

    value = "".join(
        c
        for c in value
        if not unicodedata.combining(c)
    )

    value = value.casefold()

    value = INVALID_RE.sub("_", value)

    value = EXTRA_RE.sub("", value)

    value = SPACE_RE.sub(" ", value).strip()

    value = SEPARATOR_RE.sub(" ", value)

    value = value.encode("latin-1", errors="ignore").decode("latin-1")
    ## Mas estricto, pero elimina ñ, ü, é, etc
    # value = value.encode("ascii", errors="ignore").decode("ascii")

    value = value.strip("_")

    if not value:
        return "untranslatable"

    if value.split(".", 1)[0].casefold() in WINDOWS_RESERVED:
        value = "_" + value

    return value[:MAX_LENGTH]

SUPPORTED_EXTENSIONS: set[str] = {
    ".mp3", ".mp4", ".m4a", ".m4b", ".m4p",
    ".flac", ".ogg", ".oga", ".opus",
    ".wav", ".aiff", ".aif", ".wv", ".ape",
}

## TAG KEY MAPPINGS key mappings 

_ID3_MAP: dict[str, str] = {
    "TIT2": "title",
    "TIT3": "subtitle",
    "TPE1": "artist",
    "TPE2": "albumartist",
    "TALB": "album",
    "TRCK": "track",
    "TPOS": "disc",
    "TCON": "genre",
    "TDRC": "year",
    "TCOM": "composer",
    "TLEN": "duration_ms",
    "TBPM": "bpm",
    "COMM": "comment",
    "USLT": "lyrics",
    "APIC": "cover",
}
_MP4_MAP: dict[str, str] = {
    "©nam": "title",
    "©ART": "artist",
    "aART": "albumartist",
    "©alb": "album",
    "trkn": "track",
    "disk": "disc",
    "©gen": "genre",
    "gnre": "genre",
    "©day": "year",
    "©wrt": "composer",
    "tmpo": "bpm",
    "©cmt": "comment",
    "©lyr": "lyrics",
    "covr": "cover",
    "soal": "album_sort",
    "soar": "artist_sort",
    "sonm": "title_sort",
}
_VORBIS_MAP: dict[str, str] = {
    "TITLE":        "title",
    "ARTIST":       "artist",
    "ALBUMARTIST":  "albumartist",
    "ALBUM":        "album",
    "TRACKNUMBER":  "track",
    "DISCNUMBER":   "disc",
    "GENRE":        "genre",
    "DATE":         "year",
    "COMPOSER":     "composer",
    "BPM":          "bpm",
    "COMMENT":      "comment",
    "LYRICS":       "lyrics",
    "METADATA_BLOCK_PICTURE": "cover",
}
_ID3_WRITE_MAP: dict[str, str] = {v: k for k, v in _ID3_MAP.items()}
_MP4_WRITE_MAP: dict[str, str] = {
    v: k for k, v in _MP4_MAP.items() if k != "gnre"
}
_VORBIS_WRITE_MAP: dict[str, str] = {v: k for k, v in _VORBIS_MAP.items()}


def _first(value: Any) -> Any:
    """Unwrap single-element lists returned by mutagen."""
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value

def _first_non_empty(value: Any) -> Any:
    """Return the first non-empty element when mutagen returns a sequence."""
    if isinstance(value, (list, tuple)):
        for item in value:
            if not _is_empty(item):
                return item
        return None
    return value

def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (str, bytes)):
        return len(value) == 0
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    return False

def _add_if_present(result: dict[str, Any], key: str, value: Any) -> None:
    if key == "bpm" and not _is_empty(value):
        try:
            value = int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        except (InvalidOperation, ValueError, OverflowError):
            return
    if not _is_empty(value):
        result[key] = value


class Extractor:
    """
    Class for extracting tags from audio files using mutagen. 

    Attributes:
        get_tags: method - Extracts tags from an audio file and returns a normalized dictionary.
        get_cover: method - Returns the embedded cover art for an audio file, if present.
        get_filename_from_tags: method - Returns a normalized string for filename from a tag dictionary.
    """ 

    @staticmethod
    def _extract_id3(tags: ID3Tags) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for frame_id, key in _ID3_MAP.items():
            frames = tags.getall(frame_id)
            if not frames:
                continue
            frame = frames[0]
            if key == "cover":
                value = getattr(frame, "data", None)
            elif key == "comment":
                raw = getattr(frame, "text", None)
                value = str(_first(raw)) if raw else None
            elif hasattr(frame, "text"):
                raw = frame.text
                value = str(_first(raw)) if raw else None
            else:
                value = str(frame)
            _add_if_present(result, key, value)
        return result

    @staticmethod
    def _extract_mp4(tags: MP4Tags) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for atom, key in _MP4_MAP.items():
            if atom not in tags:
                continue
            value = _first_non_empty(tags[atom])
            if key == "cover":
                value = bytes(value) if value is not None else None
            elif key in ("track", "disc") and isinstance(value, tuple):
                # MP4 stores (number, total) as a tuple
                _add_if_present(result, key, str(value[0]) if value[0] else None)
                total_key = "track_total" if key == "track" else "disc_total"
                _add_if_present(result, total_key, str(value[1]) if len(value) > 1 and value[1] else None)
                continue
            else:
                value = str(value) if value is not None else None
            _add_if_present(result, key, value)
        return result

    @staticmethod
    def _decode_vorbis_cover(value: Any) -> bytes | None:
        """
        Decode cover art from a VorbisComment value.

        Handles the standard METADATA_BLOCK_PICTURE (base64-encoded FLAC
        Picture block), raw image bytes and the legacy COVERART tag.
        Returns raw image bytes (JPEG/PNG) or None.
        """
        if value is None:
            return None

        if isinstance(value, bytes):
            data = value
        else:
            try:
                data = base64.b64decode(str(value))
            except Exception:
                return None

        # Already raw image bytes
        if data[:4] == b"\x89PNG" or data[:3] == b"\xff\xd8\xff":
            return data

        # FLAC Picture block -> raw image bytes
        try:
            return Picture(data).data
        except Exception:
            return None

    @staticmethod
    def _extract_vorbis(audio: Any) -> dict[str, Any]:
        tags = audio.tags
        result: dict[str, Any] = {}
        for vorbis_key, key in _VORBIS_MAP.items():
            if key == "cover":
                continue  # se gestiona al final
            raw = tags.get(vorbis_key) or tags.get(vorbis_key.lower())
            if not raw:
                continue
            if key == "comment":
                joined = "\n".join(str(v) for v in raw if v)
                _add_if_present(result, key, joined)
            else:
                _add_if_present(result, key, str(_first(raw)))

        # Cover: FLAC la guarda en audio.pictures (nativo);
        # OGG/Opus en el tag METADATA_BLOCK_PICTURE
        value = None
        pictures = getattr(audio, "pictures", None)
        if pictures:
            value = bytes(pictures[0].data)
        else:
            raw = (
                tags.get("metadata_block_picture")
                or tags.get("coverart")
                or tags.get("cover")
            )
            if raw:
                value = Extractor._decode_vorbis_cover(_first(raw))
        _add_if_present(result, "cover", value)

        return result

    @staticmethod
    def _extract_info(audio: Any) -> dict[str, Any]:
        """Extract audio stream properties from mutagen's info object."""
        info = getattr(audio, "info", None)
        if info is None:
            return {}
        props: dict[str, Any] = {}
        for attr in ("length", "bitrate", "sample_rate", "channels", "bits_per_sample"):
            val = getattr(info, attr, None)
            if val is not None:
                props[attr] = val
        return props

    @staticmethod
    def get_tags(path: str) -> dict[str, Any] | None:
        """
        Extract tags from an audio file using mutagen.

        Supports MP3, MP4/M4A, FLAC, OGG, Opus, WAV, AIFF and more.
        Returns a normalized dict with consistent keys regardless of format,
        plus audio stream info (length, bitrate, sample_rate, channels).
        Returns None if the file format is unsupported.
        BPM is an int when valid, otherwise omitted. Existing decimal BPM
        values are rounded to the nearest integer, with ties rounded up.

        Normalized tag keys
        -------------------
        title, artist, albumartist, album, track, track_total,
        disc, disc_total, genre, year, composer, bpm, comment,
        lyrics, cover (bytes), album_sort, artist_sort, title_sort

        Audio info keys
        ---------------
        length (seconds), bitrate (bps), sample_rate (Hz),
        channels, bits_per_sample
        """
        suffix = Path(path).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            return None

        audio = MutagenFile(path, easy=False)
        if audio is None:
            return None

        tags = audio.tags
        tag_data: dict[str, Any] = {}

        if tags is not None:
            if isinstance(tags, ID3Tags):
                # MP3, WAV, AIFF
                tag_data = Extractor._extract_id3(tags)
            elif isinstance(tags, MP4Tags):
                # M4A, MP4
                tag_data = Extractor._extract_mp4(tags)
            elif isinstance(tags, VCommentDict):
                # VorbisComment: FLAC, OGG, Opus, Speex
                tag_data = Extractor._extract_vorbis(audio)
            # Nuevos formatos (APEv2, ASF...): añadir aquí su rama isinstance.
            # Sin rama -> tag_data vacío y se recurre al fallback easy.

        if not tag_data:
            audio_easy = MutagenFile(path, easy=True)
            easy_tags = getattr(audio_easy, "tags", None) if audio_easy is not None else None
            if easy_tags is not None:
                for key in ("title", "artist", "album", "albumartist", "genre", "date", "bpm"):
                    if key not in easy_tags:
                        continue
                    value = _first_non_empty(easy_tags.get(key))
                    normalized_key = "year" if key == "date" else key
                    _add_if_present(tag_data, normalized_key, str(value) if value is not None else None)

        result = {**Extractor._extract_info(audio), **tag_data}
        return result

    @staticmethod
    def get_cover(path: str) -> bytes | None:
        """
        Return the embedded cover art for an audio file, if present.
        """
        suffix = Path(path).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            return None

        audio = MutagenFile(path, easy=False)
        if audio is None:
            return None

        tags = audio.tags
        if tags is None:
            return None

        if isinstance(tags, ID3Tags):
            for frame in tags.getall("APIC"):
                data = getattr(frame, "data", None)
                if data:
                    return bytes(data)
            return None

        if isinstance(tags, MP4Tags):
            cover = tags.get("covr")
            if cover is None:
                return None
            value = _first(cover)
            if value is None:
                return None
            return bytes(value)

        if isinstance(tags, VCommentDict):
            # VorbisComment: FLAC, OGG, Opus, Speex
            # FLAC guarda la carátula en audio.pictures (nativo)
            pictures = getattr(audio, "pictures", None)
            if pictures:
                return bytes(pictures[0].data)

            raw = (
                tags.get("metadata_block_picture")
                or tags.get("coverart")
                or tags.get("cover")
            )
            if raw is None:
                return None
            return Extractor._decode_vorbis_cover(_first(raw))

        # Nuevos formatos (APEv2, ASF...): añadir aquí su rama isinstance
        return None

    @staticmethod
    def get_filename_from_tags(tags: dict[str, Any], mode: int = 0) -> str:
        """
        Returns a normalized str for filename from a tag dictionary
        
        Parameters
        ---------- 
        tags : dict[str, Any] 
        mode : int

        Returns
        --------
        mode:
            - 0. Single `artist - title` 
            - 1. Album `album - track - title`
        """
        artist = normalize(tags.get("artist"))
        title = normalize(tags.get("title"))
        album = normalize(tags.get("album"))

        track = (
            tags.get("track")
            or tags.get("track_number")
            or tags.get("trkn")
            or 0
        )

        try:
            track = int(track)
        except (TypeError, ValueError):
            track = 0

        if mode == 0:
            return f"{artist} - {title}"
        elif mode == 1:
            return f"{album} - {track:02d} - {title}"
        else:
            raise ValueError(f"Unsupported mode: {mode}")


class Editor:
    """
    Class for editing tags of audio files using mutagen.

    Attributes:
        edit_comment: method - Edits the comment tags of an audio file with key:value formatted stickers.
        set_tags: method - Sets tags for an audio file from a dictionary.
    """ 

    @staticmethod
    def edit_comment(comment: str, stickers: dict[str, str] = None) -> str:
        '''
        Edita un comentario con formato de etiquetas clave:valor.
        
        Args:
            comment (str): El comentario original.
            stickers (dict[str, str]): Diccionario con los valores a actualizar.
    
        Returns:
            str: Comentario reconstruido con los valores actualizados.
        '''
        if comment is None or comment.strip() == "":
            comment = ""
        # if ":" not in comment and not stickers:
        #     return comment
        comment_text = ""
        comment_stickers = {}
        for item in comment.split(","):
            if ":" in item and "#" in item:
                key, value = item.split(":", 1)
                if key.strip()[0] != "#":
                    pos = key.find("#")
                    comment_text += key[:pos].strip()
                    key = key[pos:]
                key = key.upper().strip().strip("#")
                value = value.strip()
                comment_stickers[key] = value
            else:
                if item.strip() != "":
                    comment_text += item.strip() + ", "
        if stickers:
            for key, value in stickers.items():
                comment_stickers[key.upper().strip()] = value.strip()
        reconstructed = ", ".join([f"#{k.upper()}:{v}" for k, v in comment_stickers.items()])
        if comment_text != "":
            reconstructed = comment_text.strip() + " " + reconstructed
        return reconstructed

    # @staticmethod
    # def set_comments(path: str, comments: list[str]) -> None:
    #     """
    #     Set the comment tags of an audio file to a list of strings.
    #     Overwrites any existing comments.
    #     """
        
    #     audio = MutagenFile(path, easy=False)
    #     if audio is None:
    #         raise ValueError(f"Unsupported file format: {path}")

    #     tags = audio.tags
    #     if tags is None:
    #         raise ValueError(f"No tags found in file: {path}")

    #     # Normalize comments
    #     comments = [
    #         c.strip() 
    #         for c in comments 
    #         if c and c.strip()
    #     ]

    #     if isinstance(tags, ID3Tags):
    #         # Remove existing COMM frames
    #         tags.delall("COMM")

    #         if comments:
    #             # Single COMM frame containing multiple texts
    #             tags.add(
    #                 COMM(
    #                     encoding=3,  # UTF-8
    #                     lang="und",
    #                     desc="",
    #                     text=comments
    #                 )
    #             )
        
    #     elif isinstance(tags, MP4Tags):
    #         if comments:
    #             tags["©cmt"] = comments
    #         else:
    #             tags.pop("©cmt", None)

    #     # VorbisComment (FLAC, OGG, Opus) and others
    #     else:
    #         tags["COMMENT"] = comments
    #         if comments:
    #             tags["COMMENT"] = comments
    #         else:
    #             tags.pop("COMMENT", None)

    #     audio.save()

    @staticmethod
    def _set_id3_tags(tags: ID3Tags, tags_dict: dict[str, Any]) -> None:
        _ID3_TEXT_FRAMES = {
            "title":       TIT2,
            "subtitle":    TIT3,
            "artist":      TPE1,
            "albumartist": TPE2,
            "album":       TALB,
            "track":       TRCK,
            "disc":        TPOS,
            "genre":       TCON,
            "year":        TDRC,
            "composer":    TCOM,
            "bpm":         TBPM,
        }
        for key, FrameClass in _ID3_TEXT_FRAMES.items():
            if key not in tags_dict:
                continue
            value = tags_dict[key]
            frame_id = _ID3_WRITE_MAP[key]
            if value is None or value == "":
                tags.delall(frame_id)
            else:
                tags[frame_id] = FrameClass(encoding=3, text=[str(value)])

        if "comment" in tags_dict:
            value = tags_dict["comment"]
            tags.delall("COMM")
            if value is not None and value != "":
                text = list(value) if isinstance(value, (list, tuple)) else [str(value)]
                tags.add(COMM(encoding=3, lang="und", desc="", text=text))

        if "lyrics" in tags_dict:
            value = tags_dict["lyrics"]
            tags.delall("USLT")
            if value is not None and value != "":
                tags.add(USLT(encoding=3, lang="und", desc="", text=str(value)))

        if "cover" in tags_dict:
            value = tags_dict["cover"]
            tags.delall("APIC")
            if isinstance(value, bytes) and value:
                mime = "image/png" if value[:4] == b"\x89PNG" else "image/jpeg"
                tags.add(APIC(encoding=3, mime=mime, type=3, desc="", data=value))

    @staticmethod
    def _set_mp4_tags(tags: MP4Tags, tags_dict: dict[str, Any]) -> None:
        if "genre" in tags_dict:
            tags.pop("gnre", None)
        
        for key, atom in _MP4_WRITE_MAP.items():
            if key == "bpm" or key not in tags_dict:
                continue
            value = tags_dict[key]
            if value is None or value == "":
                tags.pop(atom, None)
            else:
                tags[atom] = [str(value)]

        if "bpm" in tags_dict:
            value = tags_dict["bpm"]
            if value is None:
                tags.pop("tmpo", None)
            else:
                tags["tmpo"] = [value]

        for num_key, total_key, atom in (("track", "track_total", "trkn"), ("disc", "disc_total", "disk")):
            if num_key not in tags_dict and total_key not in tags_dict:
                continue
            current = tags.get(atom)
            current_tuple = _first(current) if current else None
            curr_num   = current_tuple[0] if isinstance(current_tuple, tuple) else 0
            curr_total = current_tuple[1] if isinstance(current_tuple, tuple) and len(current_tuple) > 1 else 0

            new_num   = curr_num
            new_total = curr_total
            if num_key in tags_dict:
                v = tags_dict[num_key]
                new_num = int(v) if v not in (None, "") else 0
            if total_key in tags_dict:
                v = tags_dict[total_key]
                new_total = int(v) if v not in (None, "") else 0

            if new_num == 0 and new_total == 0:
                tags.pop(atom, None)
            else:
                tags[atom] = [(new_num, new_total)]

        if "cover" in tags_dict:
            value = tags_dict["cover"]
            if not isinstance(value, bytes) or not value:
                tags.pop("covr", None)
            else:
                fmt = MP4Cover.FORMAT_PNG if value[:4] == b"\x89PNG" else MP4Cover.FORMAT_JPEG
                tags["covr"] = [MP4Cover(value, imageformat=fmt)]

    @staticmethod
    def _set_vorbis_tags(tags: Any, tags_dict: dict[str, Any]) -> None:
        for key, vorbis_key in _VORBIS_WRITE_MAP.items():
            if key not in tags_dict:
                continue
            value = tags_dict[key]
            if value is None or value == "":
                for tag_key in (vorbis_key, vorbis_key.lower()):
                    if tag_key in tags:
                        del tags[tag_key]
            else:
                tags[vorbis_key] = [str(value)]

        if "cover" in tags_dict:
            value = tags_dict["cover"]
            if not isinstance(value, bytes) or not value:
                for tag_key in ("METADATA_BLOCK_PICTURE", "metadata_block_picture"):
                    if tag_key in tags:
                        del tags[tag_key]
            else:
                tags["METADATA_BLOCK_PICTURE"] = [value]

    @staticmethod
    def set_tags(path: str, tags_dict: dict[str, Any]) -> None:
        """
        Update tags of an audio file from a dictionary.

        Only the keys present in ``tags_dict`` are modified.  A value of
        ``None`` or ``""`` (empty string) removes that tag from the file;
        any other value overwrites it.  Keys absent from ``tags_dict`` are
        left exactly as they are.

        Supports all formats covered by mutagen: MP3, MP4/M4A, FLAC, OGG,
        Opus, WAV, AIFF, WavPack, APE, and others.

        Parameters
        ----------
        path : str
            Path to the audio file.
        tags_dict : dict[str, Any]
            Mapping of normalized tag keys to new values.
            BPM must be an int or None (removes the tag). Strings, floats,
            and booleans are rejected before opening the audio file.

        Normalized tag keys
        -------------------
        title, subtitle, artist, albumartist, album,
        track, track_total, disc, disc_total,
        genre, year, composer, bpm, comment, lyrics,
        cover (bytes), album_sort, artist_sort, title_sort
        """
        suffix = Path(path).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {path}")

        if "bpm" in tags_dict:
            bpm = tags_dict["bpm"]
            if bpm is not None and type(bpm) is not int:
                raise TypeError("bpm must be an int or None")

        audio = MutagenFile(path, easy=False)
        if audio is None:
            raise ValueError(f"Unsupported file format: {path}")

        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags

        if isinstance(tags, ID3Tags):
            Editor._set_id3_tags(tags, tags_dict)
        elif isinstance(tags, MP4Tags):
            Editor._set_mp4_tags(tags, tags_dict)
        else:
            Editor._set_vorbis_tags(tags, tags_dict)

        audio.save()

    @staticmethod
    def set_cover(path: str, cover: bytes) -> None:
        """Replace embedded artwork with JPEG/PNG bytes; b"" removes it.

        Supports ID3, MP4, native FLAC pictures, Vorbis comments and APEv2.
        Other metadata is preserved. Unsupported image/tag formats raise
        ValueError before the file is saved.
        """
        if not isinstance(cover, bytes):
            raise TypeError("cover must be bytes")
        if cover.startswith(b"\x89PNG\r\n\x1a\n"):
            mime, image_format, filename = "image/png", MP4Cover.FORMAT_PNG, "cover.png"
        elif cover.startswith(b"\xff\xd8\xff"):
            mime, image_format, filename = "image/jpeg", MP4Cover.FORMAT_JPEG, "cover.jpg"
        elif cover:
            raise ValueError("Cover must be a JPEG or PNG image")

        if Path(path).suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {path}")
        audio = MutagenFile(path, easy=False)
        if audio is None:
            raise ValueError(f"Unsupported file format: {path}")
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags

        if isinstance(tags, ID3Tags):
            Editor._set_id3_tags(tags, {"cover": cover})
        elif isinstance(tags, MP4Tags):
            if cover:
                tags["covr"] = [MP4Cover(cover, imageformat=image_format)]
            else:
                tags.pop("covr", None)
        elif isinstance(audio, FLAC) or isinstance(tags, VCommentDict):
            for key in ("metadata_block_picture", "coverart", "coverartmime", "cover"):
                if key in tags:
                    del tags[key]
            picture = Picture()
            if cover:
                picture.type = 3
                picture.mime = mime
                picture.data = cover
            if isinstance(audio, FLAC):
                audio.clear_pictures()
                if cover:
                    audio.add_picture(picture)
            elif cover:
                tags["metadata_block_picture"] = [
                    base64.b64encode(picture.write()).decode("ascii")
                ]
        elif isinstance(tags, APEv2):
            for key in list(tags):
                if key.lower().startswith("cover art ("):
                    del tags[key]
            if cover:
                tags["Cover Art (Front)"] = APEBinaryValue(
                    filename.encode("ascii") + b"\x00" + cover
                )
        else:
            raise ValueError(f"Unsupported tag format for cover art: {path}")

        audio.save()


class TrackCheck:
    '''
    Class for checking if a track is a duplicate based on its tags.
    
    `methods:`
        isDuplicate(audio_path: str | Path, threshold: float = 80) -> bool

    '''
    def __init__(self, db_path: str | Path) -> None:
        if not Path(db_path).exists():
            raise ValueError(f"DB file does not exist: {db_path}")
        try:
            conn = sqlite3.connect(db_path)
        except Exception as e:
            raise ValueError(f"Failed to connect to DB: {e}")

        # Compruebo que exista la tabla 'files'
        try:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files';")
            table_exists = cursor.fetchone()
            if not table_exists:
                raise ValueError("'files' table does not exist in the DB")
        except Exception as e:
            raise ValueError(f"Failed to check 'files' table in DB: {e}")

        cursor = conn.execute("SELECT filename, artist, title FROM files")
        rows = cursor.fetchall()

        self.filenames: list[str] = [e[0] for e in rows]
        self.filenames_set: set[str] = set(self.filenames)
        self.artist_title = []
        for e in rows:
            db_artist = self._normalize(e[1]) if e[1] else ''
            db_title = self._normalize(e[2]) if e[2] else ''
            artist_title = f"{db_artist} {db_title}"
            if len(artist_title.strip()) ==0:
                artist_title = self._normalize(e[0])
            self.artist_title.append(artist_title)
        # self.artist_title: list[str] = [f"{self._normalize(e[1]) if e[1] else 'unknown'} {self._normalize(e[2])}" for e in rows]
        self.artist_title_set: set[str] = set(self.artist_title)

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.casefold()
        # Eliminar acentos
        text = unicodedata.normalize("NFKD", text)
        text = "".join(
            c for c in text
            if not unicodedata.combining(c)
        )
        # Sustituir puntuación por espacios
        text = re.sub(r"[^\w\s]", " ", text)
        # Normalizar espacios
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def isDuplicate_file(self, filename: str | Path) -> bool:
        if str(filename) in self.filenames_set:
            return True
        return False

    def isDuplicate_tags(self, artist: str , title: str, filename: str = None, threshold: float = 80) -> bool:
        if filename:
            if filename in self.filenames_set:
                return True
        key = f"{self._normalize(artist)} {self._normalize(title)}"
        if key in self.artist_title_set:
            return True
        for existing in self.artist_title:
            ratio = fuzz.ratio(key, existing)
            token_sort = fuzz.token_sort_ratio(key, existing)
            score = (token_sort * 0.85) + (ratio * 0.15)
            if score >= threshold:
                return True
        return False

#     '''
#     Object for detecting duplicates from the tags of a track

#     Attributes:
#         artist
#         title
    
#     Class methods:
#         from_tags()
#         from_file()
#         list_from_path()
    
#     Static methods:
#         is_duplicate
#     '''
#     artist: str
#     title: str

#     _track_key: str = field(init=False, repr=False)

#     def __post_init__(self):
#         self._track_key = f"{normalize(self.artist)} {normalize(self.title)}"

#     @classmethod
#     def from_tags(cls, tags_dict: dict[str, Any]):
#         return cls(
#             artist = tags_dict['artist'],
#             title = tags_dict['title'],
#         )

#     @classmethod
#     def from_file(cls, path_file: str):
#         return cls.from_tags(
#             Extractor.get_tags(path_file)
#         )

#     @classmethod
#     def list_from_path(cls, path: str) -> list[TrackCheck]:
#         df = get_df_tags_from_path(path)
#         return [
#             cls(
#                 artist = normalize(row["artist"]),
#                 title = normalize(row["title"])
#             )
#             for _, row in df.iterrows()
#         ]

#     def is_duplicate(self, source: list[TrackCheck], threshold: float = 80) -> bool:
#         for s in source:
#             match = fuzz.token_set_ratio(
#                 self._track_key, 
#                 s._track_key
#             )
#             if match >= threshold:
#                 return True
#         return False



TAG_PATTERN = re.compile(r"^#(?P<key>[a-zA-Z0-9_-]+):\s*(?P<value>.*)$")

def consolidated_signature() -> str:
    CONSOLIDATED_PREFIX = "mngr"
    # return f"#{CONSOLIDATED_PREFIX}: {datetime.now():%Y%m%d}"
    return f"#{CONSOLIDATED_PREFIX}: {__version__}"


# def get_df_tags_from_path(path: str) -> _pd.DataFrame:
#     from ._optional import pandas; pd = pandas()

#     path_songs = [
#         file for file in Path(path).rglob("*")
#         if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
#     ]
#     tag_songs = [get_tags(str(file)) for file in path_songs]
#     tag_songs = [t for t in tag_songs if t is not None]
#     return pd.DataFrame(tag_songs)