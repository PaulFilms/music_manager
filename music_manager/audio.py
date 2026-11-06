"""
Module for audio management
"""

import base64
import mimetypes
import subprocess
import tempfile
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import Picture

# VorbisComment estándar (https://xiph.org/vorbis/doc/v-comment.html).
from music_manager.tags import _VORBIS_MAP

def _embed_cover_in_ogg(ogg_file: str, cover_file: str) -> None:
    audio = MutagenFile(ogg_file, easy=False)
    if audio is None:
        raise RuntimeError(f"No se pudo abrir el archivo OGG '{ogg_file}' para incrustar cover")

    if audio.tags is None:
        audio.add_tags()

    picture = Picture()
    picture.type = 3  # front cover
    picture.desc = "Cover"

    mime, _ = mimetypes.guess_type(cover_file)
    picture.mime = mime or "image/jpeg"
    picture.data = Path(cover_file).read_bytes()

    encoded_picture = base64.b64encode(picture.write()).decode("ascii")
    audio.tags["METADATA_BLOCK_PICTURE"] = [encoded_picture]
    audio.save()


def from_webm_to_ogg(input_file: str, cover: str = None, tags: dict = None) -> str:
    """
    Remuxea un archivo webm a ogg sin recodificar el audio.

    Solo copia el stream de audio (Opus o Vorbis) al contenedor ogg,
    por lo que es instantáneo y sin pérdida de calidad.
    El archivo resultante es editable con mutagen (VorbisComment).
    """
    p = Path(input_file)

    output_file = str(p.with_suffix(".ogg"))
    command = [
        "ffmpeg",
        "-y",
        "-i", input_file,
        "-vn",
        "-c:a", "copy",
        "-loglevel", "error",
        output_file,
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falló al convertir '{input_file}':\n{result.stderr}"
        )

    if cover:
        _embed_cover_in_ogg(output_file, cover)

    return output_file


# VorbisComment estándar (https://xiph.org/vorbis/doc/v-comment.html).
# Claves normalizadas -> clave VorbisComment que espera el software de terceros.
# _VORBIS_TAG_MAP = {
#     "title":       "TITLE",
#     "subtitle":    "SUBTITLE",
#     "artist":      "ARTIST",
#     "albumartist": "ALBUMARTIST",
#     "album":       "ALBUM",
#     "track":       "TRACKNUMBER",
#     "disc":        "DISCNUMBER",
#     "genre":       "GENRE",
#     "year":        "DATE",
#     "composer":    "COMPOSER",
#     "bpm":         "BPM",
#     "comment":     "COMMENT",
#     "lyrics":      "LYRICS",
# }

_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG",      "image/png"),
)


def _get_audio_codec(path: Path) -> str:
    """Devuelve el codec del primer stream de audio usando ffprobe."""
    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe no pudo analizar '{path}':\n{result.stderr}"
        )

    codec = result.stdout.strip().lower()
    if not codec:
        raise ValueError(f"'{path}' no contiene ningún stream de audio")
    return codec


def _detect_image_mime(cover_file: Path) -> str:
    """Valida que el cover es JPEG, PNG o WebP leyendo sus magic bytes."""
    with open(cover_file, "rb") as f:
        head = f.read(12)

    for signature, mime in _IMAGE_SIGNATURES:
        if head.startswith(signature):
            return mime

    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"

    raise ValueError(
        f"El cover '{cover_file}' no es JPEG, PNG ni WebP; "
        "METADATA_BLOCK_PICTURE solo admite JPEG/PNG de forma estándar "
        "(los WebP se convierten a PNG automáticamente)"
    )


def _webp_to_png(cover_file: Path) -> Path:
    """Convierte un WebP a PNG temporal (primer frame si es animado)."""
    tmp = Path(tempfile.mktemp(suffix=".png"))
    command = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-i", str(cover_file),
        "-frames:v", "1",
        str(tmp),
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"ffmpeg no pudo convertir el WebP '{cover_file}':\n{result.stderr}"
        )
    return tmp


def _embed_cover_vorbis(audio, cover_file: Path, mime: str) -> None:
    """Incrusta la carátula como METADATA_BLOCK_PICTURE (bloque Picture FLAC en base64)."""
    picture = Picture()
    picture.type = 3  # front cover
    picture.desc = "Cover"
    picture.mime = mime
    picture.data = cover_file.read_bytes()

    encoded_picture = base64.b64encode(picture.write()).decode("ascii")
    audio.tags["METADATA_BLOCK_PICTURE"] = [encoded_picture]


def _apply_vorbis_tags(audio, tags: dict) -> None:
    """Aplica tags con claves VorbisComment estándar sobre un audio abierto."""
    for key, value in tags.items():
        if key == "cover":
            continue  # el cover se gestiona aparte

        vorbis_key = _VORBIS_MAP.get(key, key.upper())

        if value is None or value == "":
            audio.tags.pop(vorbis_key, None)
            audio.tags.pop(vorbis_key.lower(), None)
            continue

        if isinstance(value, (list, tuple)):
            values = [str(v) for v in value if v not in (None, "")]
        else:
            values = [str(value)]

        if values:
            audio.tags[vorbis_key] = values
        else:
            audio.tags.pop(vorbis_key, None)
            audio.tags.pop(vorbis_key.lower(), None)


def from_webm_to_opus(
    webm_path: str | Path,
    cover_path: str | Path | None = None,
    tags: dict = None,
) -> str:
    """
    Remuxea un .webm a .opus copiando el audio sin recodificar.

    Pasos:
        1. Verifica rutas y archivos de entrada.
        2. Comprueba que el audio es Opus (un .opus estándar lo exige).
        3. Remux con ffmpeg (-c:a copy): instantáneo y sin pérdida.
        4. Incrusta la carátula como METADATA_BLOCK_PICTURE estándar.
        5. Escribe los tags como VorbisComment estándar.

    Todo ello legible por software de terceros (reproductores, taggers, etc.).

    Parameters
    ----------
    webm_path : str | Path
        Ruta al archivo .webm de origen (audio Opus).
    cover_path : str | Path | None
        Ruta a una imagen JPEG, PNG o WebP para la carátula (opcional).
        Los WebP se convierten a PNG automáticamente, pues no son
        estándar para carátulas embebidas.
    tags : dict | None
        Tags normalizados (title, artist, album, genre, year, track...).
        Un valor None o "" elimina el tag. También admite 'cover' con
        bytes de imagen (JPEG/PNG).

    Returns
    -------
    str
        Ruta del archivo .opus generado.
    """
    ## 1. Verificar rutas y archivos

    webm = Path(webm_path)

    if not webm.exists():
        raise FileNotFoundError(f"No existe el archivo: {webm}")
    if not webm.is_file():
        raise ValueError(f"La ruta no es un archivo: {webm}")
    if webm.suffix.lower() != ".webm":
        raise ValueError(f"Se esperaba un .webm: {webm}")

    cover = None
    cover_mime = None
    cover_tmp = None
    if cover_path is not None:
        cover = Path(cover_path)
        if not cover.exists():
            raise FileNotFoundError(f"No existe el cover: {cover}")
        if not cover.is_file():
            raise ValueError(f"La ruta del cover no es un archivo: {cover}")
        cover_mime = _detect_image_mime(cover)
        if cover_mime == "image/webp":
            # WebP no es estándar para covers embebidas: convertir a PNG
            cover_tmp = _webp_to_png(cover)
            cover = cover_tmp
            cover_mime = "image/png"

    ## 2. Verificar que el audio es Opus

    codec = _get_audio_codec(webm)
    if codec != "opus":
        raise ValueError(
            f"El audio de '{webm.name}' es '{codec}', no Opus. "
            f"Un .opus estándar requiere audio Opus; "
            f"usa from_webm_to_ogg() para audio Vorbis."
        )

    ## 3. Remux sin conversión del audio

    output = webm.with_suffix(".opus")
    command = [
        "ffmpeg",
        "-y",
        "-i", str(webm),
        "-map", "0:a:0",
        "-c:a", "copy",
        "-loglevel", "error",
        str(output),
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falló al remuxear '{webm}':\n{result.stderr}"
        )
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg no generó un .opus válido: '{output}'")

    ## 4-5. Cover y tags (formato estándar VorbisComment)

    cover_bytes = tags.pop("cover", None) if tags else None

    try:
        if cover is not None or tags or cover_bytes:
            audio = MutagenFile(str(output), easy=False)
            if audio is None:
                raise RuntimeError(f"mutagen no reconoce el archivo generado: '{output}'")
            if audio.tags is None:
                audio.add_tags()

            if tags:
                _apply_vorbis_tags(audio, tags)

            if cover is not None:
                _embed_cover_vorbis(audio, cover, cover_mime)
            elif isinstance(cover_bytes, bytes) and cover_bytes:
                mime = "image/png" if cover_bytes[:4] == b"\x89PNG" else "image/jpeg"
                picture = Picture()
                picture.type = 3
                picture.desc = "Cover"
                picture.mime = mime
                picture.data = cover_bytes
                audio.tags["METADATA_BLOCK_PICTURE"] = [
                    base64.b64encode(picture.write()).decode("ascii")
                ]

            audio.save()
    finally:
        if cover_tmp is not None:
            cover_tmp.unlink(missing_ok=True)

    return str(output)

def get_wav(path: str, sample_rate: int = 44100, bit_depth: int = 16) -> str:
    """
    Convert an audio file to WAV format using ffmpeg.

    Returns the path to the generated WAV file.

    Args:
        path: Ruta al archivo de audio de entrada.
        sample_rate: Frecuencia de muestreo deseada para el WAV generado (por defecto 44100 Hz).
        bit_depth: Profundidad de bits deseada para el WAV generado (por defecto 16 bits).
    """
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"La ruta no es un archivo: {input_path}")

    output = input_path.with_suffix(".wav")
    command = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-ar", str(sample_rate),
        "-c:a", f"pcm_s{bit_depth}le",
        "-loglevel", "error",
        str(output),
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falló al convertir a WAV '{input_path}':\n{result.stderr}"
        )
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg no generó un WAV válido: '{output}'")

    return str(output)