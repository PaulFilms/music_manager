'''
Toolkit with simplified functions and methods for audio file tags and names

Include:
    - normalize
    - get_tags
    - get_df_tags_from_path
    - get_filename_from_tags
    - TrackCheck

    
BUG:

- Usar rapidfuzz.process.extractOne()

Con extractOne() la librería hace ese trabajo por ti en C++

por ejemplo:

    from rapidfuzz import process, fuzz

    choices = [track._track_ref for track in source]

    best = process.extractOne(
        self._track_ref,
        choices,
        scorer=fuzz.token_set_ratio,
        score_cutoff=80
    )

    if best is not None:
        return True

    return False

y devuelve algo como:

    (
        "queen bohemian rhapsody",
        96.3,
        153
    )

- Crear clase TrackLibrary
'''

## OPTIONAL IMPORTS
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import pandas as _pd

import re
import unicodedata
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import Any
from mutagen import File as MutagenFile
from mutagen.id3 import ID3Tags
from mutagen.mp4 import MP4Tags
from rapidfuzz import fuzz


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

    value = value.strip("_")

    if not value:
        return "untranslatable"

    if value in WINDOWS_RESERVED:
        value = "_" + value

    return value[:MAX_LENGTH]

## ── Tag key mappings ──────────────────────────────────────────────────────────

# ID3 (MP3, AIFF): frame_id → normalized key
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

# MP4/M4A (iTunes atoms): atom → normalized key
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

# VorbisComment (FLAC, OGG, Opus): uppercase key → normalized key
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

SUPPORTED_EXTENSIONS = {
    ".mp3", ".mp4", ".m4a", ".m4b", ".m4p",
    ".flac", ".ogg", ".oga", ".opus",
    ".wav", ".aiff", ".aif", ".wv", ".ape",
}


def _first(value: Any) -> Any:
    """Unwrap single-element lists returned by mutagen."""
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value


def _extract_id3(tags: ID3Tags) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for frame_id, key in _ID3_MAP.items():
        # COMM and USLT frames can have lang suffixes → iterate all
        frames = tags.getall(frame_id)
        if not frames:
            continue
        frame = frames[0]
        if key == "cover":
            result[key] = getattr(frame, "data", None)
        elif key == "comment":
            result[key] = getattr(frame, "text", str(frame))
        elif hasattr(frame, "text"):
            raw = frame.text
            result[key] = str(_first(raw)) if raw else None
        else:
            result[key] = str(frame)
    return result


def _extract_mp4(tags: MP4Tags) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for atom, key in _MP4_MAP.items():
        if atom not in tags:
            continue
        value = _first(tags[atom])
        if key == "cover":
            result[key] = bytes(value) if value is not None else None
        elif key in ("track", "disc") and isinstance(value, tuple):
            # MP4 stores (number, total) as a tuple
            result[key] = str(value[0]) if value[0] else None
            total_key = "track_total" if key == "track" else "disc_total"
            result[total_key] = str(value[1]) if len(value) > 1 and value[1] else None
        else:
            result[key] = str(value) if value is not None else None
    return result


def _extract_vorbis(tags: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for vorbis_key, key in _VORBIS_MAP.items():
        raw = tags.get(vorbis_key) or tags.get(vorbis_key.lower())
        if not raw:
            continue
        if key == "cover":
            result[key] = _first(raw)
        else:
            result[key] = str(_first(raw))
    return result


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


def get_tags(path: str) -> dict[str, Any] | None:
    """
    Extract tags from an audio file using mutagen.

    Supports MP3, MP4/M4A, FLAC, OGG, Opus, WAV, AIFF and more.
    Returns a normalized dict with consistent keys regardless of format,
    plus audio stream info (length, bitrate, sample_rate, channels).
    Returns None if the file format is unsupported.

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
            tag_data = _extract_id3(tags)
        elif isinstance(tags, MP4Tags):
            tag_data = _extract_mp4(tags)
        else:
            # VorbisComment (FLAC, OGG, Opus) and others share a dict-like interface
            tag_data = _extract_vorbis(tags)

    result = {**_extract_info(audio), **tag_data}
    return result


def get_df_tags_from_path(path: str) -> _pd.DataFrame:
    from ._optional import pandas; pd = pandas()

    path_songs = [
        file for file in Path(path).rglob("*")
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    tag_songs = [get_tags(str(file)) for file in path_songs]
    tag_songs = [t for t in tag_songs if t is not None]
    return pd.DataFrame(tag_songs)

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
        - 0. Single -> artist - title 
        - 1. Album -> album - track - title 
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

    return f"{album} - {track:02d} - {title}"

@dataclass
class TrackCheck:
    '''
    Object for detecting duplicates from the tags of a track

    Attributes:
        artist
        title
    
    Class methods:
        from_tags()
        from_file()
        list_from_path()
    
    Static methods:
        is_duplicate
    '''
    artist: str
    title: str

    _track_key: str = field(init=False, repr=False)

    def __post_init__(self):
        self._track_key = f"{normalize(self.artist)} {normalize(self.title)}"

    @classmethod
    def from_tags(cls, tags_dict: dict[str, Any]):
        return cls(
            artist = tags_dict['artist'],
            title = tags_dict['title'],
        )

    @classmethod
    def from_file(cls, path_file: str):
        return cls.from_tags(
            get_tags(path_file)
        )

    @classmethod
    def list_from_path(cls, path: str) -> list[TrackCheck]:
        df = get_df_tags_from_path(path)
        return [
            cls(
                artist = normalize(row["artist"]),
                title = normalize(row["title"])
            )
            for _, row in df.iterrows()
        ]

    def is_duplicate(self, source: list[TrackCheck], threshold: float = 80) -> bool:
        for s in source:
            match = fuzz.token_set_ratio(
                self._track_key, 
                s._track_key
            )
            if match >= threshold:
                return True
        return False


CONSOLIDATED_PREFIX = "#mngr-"

def consolidated_signature() -> str:
    return f"{CONSOLIDATED_PREFIX}{datetime.now():%Y%m%d}"

def update_comment(comment: str | list[str] | None) -> list[str]:
    """
    Mantiene comentarios existentes y añade/reemplaza la firma mngr.
    """

    signature = consolidated_signature()

    if comment is None:
        comments = []

    elif isinstance(comment, str):
        comments = [comment]

    else:
        comments = list(comment)

    # eliminar firmas antiguas
    comments = [
        c
        for c in comments
        if not c.startswith(CONSOLIDATED_PREFIX)
    ]

    comments.append(signature)

    return comments

def consolided_file(path: str) -> None:
    tags: dict[str, Any] = get_tags(path) # validado / tinytag
    filename = get_filename_from_tags(tags, mode=0) # modes: 0. Single / 1. Album
    # Despues implementare añadir un count para duplicados
    oldfile = Path(path)
    oldfile.rename(filename)
    consolided_tag(filename)

# import mutagen
# from mutagen.id3 import COMM, ID3, ID3NoHeaderError

# def get_comments(audio) -> list[str]:

#     # MP3 (ID3)
#     if isinstance(audio.tags, ID3):

#         result = []

#         for c in audio.tags.getall("COMM"):
#             result.extend(c.text)

#         return result


#     # MP4/M4A
#     if "\xa9cmt" in audio.tags:

#         return list(audio["\xa9cmt"])


#     # Vorbis (FLAC, OGG)
#     if "comment" in audio.tags:

#         value = audio["comment"]

#         if isinstance(value, list):
#             return value

#         return [value]


#     # otros formatos
#     return []