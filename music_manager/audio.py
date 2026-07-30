"""
Modulo para la gestion de audio
"""

import subprocess


def from_webm_to_ogg(input_file: str, output_file: str) -> None:
    """
    Remuxea un archivo webm a ogg sin recodificar el audio.

    Solo copia el stream de audio (Opus o Vorbis) al contenedor ogg,
    por lo que es instantáneo y sin pérdida de calidad.
    El archivo resultante es editable con mutagen (VorbisComment).
    """
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