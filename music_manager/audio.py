"""
Modulo para la gestion de audio
"""

import base64
import mimetypes
import subprocess
from pathlib import Path

from mutagen.flac import Picture
from mutagen.oggvorbis import OggVorbis


def _embed_cover_in_ogg(ogg_file: str, cover_file: str) -> None:
    audio = OggVorbis(ogg_file)

    picture = Picture()
    picture.type = 3  # front cover
    picture.desc = "Cover"

    mime, _ = mimetypes.guess_type(cover_file)
    picture.mime = mime or "image/jpeg"
    picture.data = Path(cover_file).read_bytes()

    encoded_picture = base64.b64encode(picture.write()).decode("ascii")
    audio["METADATA_BLOCK_PICTURE"] = [encoded_picture]
    audio.save()


def from_webm_to_ogg(input_file: str, cover: str = None) -> str:
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
        "-y",                  # sobreescribir sin preguntar
        "-i", input_file,
        "-vn",                 # descartar streams de video/imagen
        "-c:a", "copy",
        "-loglevel", "error",  # silenciar output salvo errores
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
