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
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     import pandas as _pd

import re
import unicodedata
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import Any
from mutagen import File as MutagenFile
from mutagen.id3 import (
    ID3Tags, COMM,
    TIT2, TIT3, TPE1, TPE2, TALB, TRCK, TPOS, TCON, TDRC, TCOM, TBPM, USLT, APIC,
)
from mutagen.mp4 import MP4Tags, MP4Cover
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

SUPPORTED_EXTENSIONS: set[str] = {
    ".mp3", ".mp4", ".m4a", ".m4b", ".m4p",
    ".flac", ".ogg", ".oga", ".opus",
    ".wav", ".aiff", ".aif", ".wv", ".ape",
}

## ── Tag key mappings (read: native → normalized) ─────────────────────────────

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


## ── Tag key mappings (write: normalized → native) ────────────────────────────

# normalized key → ID3 frame id  (text-only frames; COMM/USLT/APIC handled separately)
_ID3_WRITE_MAP: dict[str, str] = {
    "title":       "TIT2",
    "subtitle":    "TIT3",
    "artist":      "TPE1",
    "albumartist": "TPE2",
    "album":       "TALB",
    "track":       "TRCK",
    "disc":        "TPOS",
    "genre":       "TCON",
    "year":        "TDRC",
    "composer":    "TCOM",
    "bpm":         "TBPM",
}

# normalized key → MP4 atom  (text atoms; trkn/disk/tmpo/covr handled separately)
_MP4_WRITE_MAP: dict[str, str] = {
    "title":       "©nam",
    "artist":      "©ART",
    "albumartist": "aART",
    "album":       "©alb",
    "genre":       "©gen",
    "year":        "©day",
    "composer":    "©wrt",
    "comment":     "©cmt",
    "lyrics":      "©lyr",
    "album_sort":  "soal",
    "artist_sort": "soar",
    "title_sort":  "sonm",
}

# normalized key → Vorbis tag key (cover/METADATA_BLOCK_PICTURE handled separately)
_VORBIS_WRITE_MAP: dict[str, str] = {
    "title":       "TITLE",
    "artist":      "ARTIST",
    "albumartist": "ALBUMARTIST",
    "album":       "ALBUM",
    "track":       "TRACKNUMBER",
    "disc":        "DISCNUMBER",
    "genre":       "GENRE",
    "year":        "DATE",
    "composer":    "COMPOSER",
    "bpm":         "BPM",
    "comment":     "COMMENT",
    "lyrics":      "LYRICS",
}


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
                value = getattr(frame, "text", str(frame))
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
    def _extract_vorbis(tags: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for vorbis_key, key in _VORBIS_MAP.items():
            raw = tags.get(vorbis_key) or tags.get(vorbis_key.lower())
            if not raw:
                continue
            value = _first(raw)
            if key == "cover":
                _add_if_present(result, key, value)
            else:
                _add_if_present(result, key, str(value))
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
                tag_data = Extractor._extract_id3(tags)
            elif isinstance(tags, MP4Tags):
                tag_data = Extractor._extract_mp4(tags)
            else:
                # VorbisComment (FLAC, OGG, Opus) and others share a dict-like interface
                tag_data = Extractor._extract_vorbis(tags)

        if not tag_data:
            audio_easy = MutagenFile(path, easy=True)
            easy_tags = getattr(audio_easy, "tags", None) if audio_easy is not None else None
            if easy_tags is not None:
                for key in ("title", "artist", "album", "albumartist", "genre", "date"):
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

        raw = tags.get("cover") or tags.get("metadata_block_picture")
        if raw is None:
            return None
        value = _first(raw)
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        return bytes(str(value), "utf-8")

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
        set_tags: method - Sets tags for an audio file from a dictionary.
    """ 

    @staticmethod
    def set_comments(path: str, comments: list[str]) -> None:
        """
        Set the comment tags of an audio file to a list of strings.
        Overwrites any existing comments.
        """
        
        audio = MutagenFile(path, easy=False)
        if audio is None:
            raise ValueError(f"Unsupported file format: {path}")

        tags = audio.tags
        if tags is None:
            raise ValueError(f"No tags found in file: {path}")

        # Normalize comments
        comments = [
            c.strip() 
            for c in comments 
            if c and c.strip()
        ]

        if isinstance(tags, ID3Tags):
            # Remove existing COMM frames
            tags.delall("COMM")

            if comments:
                # Single COMM frame containing multiple texts
                tags.add(
                    COMM(
                        encoding=3,  # UTF-8
                        lang="und",
                        desc="",
                        text=comments
                    )
                )
        
        elif isinstance(tags, MP4Tags):
            if comments:
                tags["©cmt"] = comments
            else:
                tags.pop("©cmt", None)

        # VorbisComment (FLAC, OGG, Opus) and others
        else:
            tags["COMMENT"] = comments
            if comments:
                tags["COMMENT"] = comments
            else:
                tags.pop("COMMENT", None)

        audio.save()





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
        for key, atom in _MP4_WRITE_MAP.items():
            if key not in tags_dict:
                continue
            value = tags_dict[key]
            if value is None or value == "":
                tags.pop(atom, None)
            else:
                tags[atom] = [str(value)]

        if "bpm" in tags_dict:
            value = tags_dict["bpm"]
            if value is None or value == "":
                tags.pop("tmpo", None)
            else:
                try:
                    tags["tmpo"] = [int(value)]
                except (ValueError, TypeError):
                    tags.pop("tmpo", None)

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
                tags.pop(vorbis_key, None)
                tags.pop(vorbis_key.lower(), None)
            else:
                tags[vorbis_key] = [str(value)]

        if "cover" in tags_dict:
            value = tags_dict["cover"]
            if not isinstance(value, bytes) or not value:
                tags.pop("METADATA_BLOCK_PICTURE", None)
                tags.pop("metadata_block_picture", None)
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
            Extractor.get_tags(path_file)
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



TAG_PATTERN = re.compile(r"^#(?P<key>[a-zA-Z0-9_-]+):\s*(?P<value>.*)$")

def consolidated_signature() -> str:
    CONSOLIDATED_PREFIX = "mngr"
    return f"#{CONSOLIDATED_PREFIX}: {datetime.now():%Y%m%d}"


# def get_df_tags_from_path(path: str) -> _pd.DataFrame:
#     from ._optional import pandas; pd = pandas()

#     path_songs = [
#         file for file in Path(path).rglob("*")
#         if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
#     ]
#     tag_songs = [get_tags(str(file)) for file in path_songs]
#     tag_songs = [t for t in tag_songs if t is not None]
#     return pd.DataFrame(tag_songs)