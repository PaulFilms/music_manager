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
from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import Any
from tinytag import TinyTag
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

    value = SEPARATOR_RE.sub("_", value)

    value = value.strip("_")

    if not value:
        return "untranslatable"

    if value in WINDOWS_RESERVED:
        value = "_" + value

    return value[:MAX_LENGTH]

def get_tags(path: str) -> dict[str, any]:
    PATH = Path(path)
    if not PATH.suffix.lower() in TinyTag.SUPPORTED_FILE_EXTENSIONS:
        return None
    return TinyTag.get(path).as_dict()

def get_df_tags_from_path(path: str) -> _pd.DataFrame:
    from ._optional import pandas; pd = pandas()

    path_songs = [file for file in Path(path).rglob('*') if file.is_file() and file.suffix.lower() in TinyTag.SUPPORTED_FILE_EXTENSIONS]
    tag_songs = [TinyTag.get(file).as_dict() for file in path_songs]
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

