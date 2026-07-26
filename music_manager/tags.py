'''
Toolkit with simplified functions and methods for audio file tags and names

Include:
    - get_song_tags
    - get_df_tags_from_path
    - track_check

    
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
from dataclasses import dataclass, field
from typing import Any
from tinytag import TinyTag
from rapidfuzz import fuzz


def normalize(value: Any) -> str:
    """
    Normaliza texto para comparación de duplicados.

    - Convierte cualquier valor a texto.
    - Elimina diferencias de mayúsculas/minúsculas.
    - Elimina acentos y diacríticos.
    - Normaliza espacios.
    """

    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(
            str(v).strip()
            for v in value
            if v is not None and str(v).strip()
        )
    else:
        value = str(value).strip()

    if not value:
        return ""

    # Normalización Unicode
    value = unicodedata.normalize("NFKD", value)

    # Eliminar diacríticos
    value = "".join(
        c for c in value
        if not unicodedata.combining(c)
    )

    # Minúsculas inteligentes
    value = value.casefold()

    # Espacios
    value = SPACE_RE.sub(" ", value)

    return value.strip()

def get_song_tags(path: str) -> dict[str, any]:
    PATH = Path(path)
    if not PATH.suffix.lower() in TinyTag.SUPPORTED_FILE_EXTENSIONS:
        return None
    return TinyTag.get(path).as_dict()

def get_df_tags_from_path(path: str) -> _pd.DataFrame:
    from ._optional import pandas; pd = pandas()

    path_songs = [file for file in Path(path).rglob('*') if file.is_file() and file.suffix.lower() in TinyTag.SUPPORTED_FILE_EXTENSIONS]
    tag_songs = [TinyTag.get(file).as_dict() for file in path_songs]
    return pd.DataFrame(tag_songs)

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
            get_song_tags(path_file)
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


""" BUG BORRAR

# SPACE_RE = re.compile(r"\s+")
# INVALID_PATH_CHARS = r'<>:"/\\|?*\x00\x1F'
# INVALID_RE = re.compile(f"[{re.escape(INVALID_PATH_CHARS)}]")

def normalize_filename(value: str) -> str:
    if not value: return ""
    value = value.strip()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        c for c in value
        if not unicodedata.combining(c)
    )
    # value = value.casefold() # Minúsculas robustas
    value = INVALID_RE.sub("_", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()

# def clean_filename(name: str) -> str:
#     name = unicodedata.normalize("NFKC", name)
#     name = re.sub(r'[\\/:*?"<>|⧸]', '-', name)  # elimina caracteres peligrosos
#     name = name.replace('？', '?')               # normaliza símbolos específicos
#     return name.strip().lower()

def get_filename_from_tags(tags: dict[str, Any], mode: int = 0) -> str:
    '''
    Returns a normalized str from a tag dictionary

    Parameters
    __________
    tags : dict[str, Any]
    mode : int

    Returns
    _______
    Mode :
        - 0. Single "<artist> - <title>" -> str 
        - 1. Album "<album> - <trkn> - <title>" -> str 
    '''
    artist = normalize_filename(tags['artist'] if tags['artist'] else 'unknown')
    title = normalize_filename(tags['title'] if tags['title'] else 'unknown')
    album = normalize_filename(tags['album'] if tags['album'] else 'unknown')
    trkn = f"{tags['trkn']:02d}" if tags['trkn'] else '00'

    if mode == 0:
        return f'{artist} - {title}'
    if mode == 1:
        return f'{album} - {trkn} - {title}'
"""




MAX_FILENAME = 100

# Caracteres prohibidos en Windows
INVALID_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]+')

# Espacios consecutivos
SPACE_RE = re.compile(r"\s+")

# Todo lo que no queremos conservar
EXTRA_RE = re.compile(r"[^\w\s\-.()&+,]")

# Separadores consecutivos
SEPARATOR_RE = re.compile(r"[_\-. ]+")

WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

def normalize_filename(value: Any) -> str:
    """
    Normaliza un texto para utilizarlo como nombre de archivo.

    Reglas:
        - strip()
        - Unicode NFKD
        - elimina diacríticos
        - casefold()
        - caracteres ilegales -> "_"
        - elimina símbolos y emoji
        - separadores redundantes -> "_"
        - espacios alrededor del "_" eliminados
        - longitud máxima
    """

    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    # Unicode
    value = unicodedata.normalize("NFKD", value)

    # Eliminar acentos
    value = "".join(
        c
        for c in value
        if not unicodedata.combining(c)
    )

    # Minúsculas robustas
    value = value.casefold()

    # Caracteres ilegales Windows
    value = INVALID_RE.sub("_", value)

    # Eliminar símbolos (emoji, etc.)
    value = EXTRA_RE.sub("", value)

    # Compactar espacios
    value = SPACE_RE.sub(" ", value).strip()

    # Cualquier secuencia de separadores -> "_"
    # value = SEPARATOR_RE.sub("_", value)

    # Quitar "_" inicial/final
    value = value.strip("_")

    if not value:
        return ""

    if value in WINDOWS_RESERVED:
        value = "_" + value

    return value[:MAX_FILENAME]

def get_filename_from_tags(tags: dict[str, Any], mode: int = 0) -> str:
    """
    Returns a normalized str from a tag dictionary 
    
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

    def clean(value: Any) -> str:
        if value is None:
            return "unknown"

        value = str(value).strip()

        if not value:
            return "unknown"

        normalized = normalize_filename(value)

        return normalized if normalized else "untranslatable"

    artist = clean(tags.get("artist"))
    title = clean(tags.get("title"))
    album = clean(tags.get("album"))

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