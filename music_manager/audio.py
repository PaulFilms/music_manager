"""
Modulo para la gestion de audio
"""

import subprocess
from pathlib import Path


def from_webm_to_ogg(input_file: str, cover: str = None) -> None:
    """
    Remuxea un archivo webm a ogg sin recodificar el audio.

    Solo copia el stream de audio (Opus o Vorbis) al contenedor ogg,
    por lo que es instantáneo y sin pérdida de calidad.
    El archivo resultante es editable con mutagen (VorbisComment).
    """
    p = Path(input_file)

    if cover:
        command = [
            "ffmpeg",
            "-y",                  # sobreescribir sin preguntar
            "-i", input_file,
            "-i", cover,           # cover image
            
            # no se para que valen
            "-map", "0:a",
            "-map", "1:v",
            "-c:a", "copy",
            "-c:v", "mjpeg",

            "-vn",                 # descartar streams de video/imagen
            "-c:a", "copy",
            "-metadata:s:v", f"comment=Cover (front)",
            "-metadata:s:v", f"title=Album cover",
            "-disposition:v:0", "attached_pic",
            "-loglevel", "error",  # silenciar output salvo errores
            str(p.with_suffix(".ogg")),
        ]
    else:
        command = [
            "ffmpeg",
            "-y",                  # sobreescribir sin preguntar
            "-i", input_file,
            "-vn",                 # descartar streams de video/imagen
            "-c:a", "copy",
            "-loglevel", "error",  # silenciar output salvo errores
            str(p.with_suffix(".ogg")),
        ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falló al convertir '{input_file}':\n{result.stderr}"
        )