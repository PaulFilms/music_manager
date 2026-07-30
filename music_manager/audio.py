"""
Modulo para la gestion de audio
"""

def from_webm_to_ogg(input_file: str, output_file: str) -> None:
    """
    Convierte un archivo de audio de formato webm a ogg sin recodificar el audio.
    """
    import subprocess

    command = [
        "ffmpeg",
        "-i", input_file,
        "-c:a", "copy",
        output_file
    ]

    subprocess.run(command, check=True)

p = "/home/pgp/Documents/Share/[MUSIC CONSOLIDED]/[#SAMPLER 20260102]/Darwin's Theory - I Hope You'll Be [US] Soul, Funk (1978).webm"

from_webm_to_ogg(p, p.replace(".webm", ".ogg"))