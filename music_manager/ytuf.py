'''
wrapper from yt_dlp to download music from youtube and other sites

Methods:
--------
    download(path: str, url: str, audio: bool = False) -> bool
    get_items(url: str) -> list[str]
'''

import yt_dlp
from datetime import datetime
from pathlib import Path
from mutagen import File as MutagenFile

from .audio import from_webm_to_ogg


def download(path: str, url: str, audio: bool = False):
    '''
    Download a video or audio from a given URL using yt_dlp.

    Args:
        path (str): The directory where the downloaded file will be saved.
        url (str): The URL of the video or audio to download.
        audio (bool): If True, download only the audio. If False, download both video and audio.

    Returns:
        bool: True if the download was successful, False otherwise.
    '''
    output_dir = Path(path)
    output_dir.mkdir(parents=True, exist_ok=True)

    opts = {
        "quiet": True,
        'no_warnings': True,
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
        "restrictfilenames": True,
        'merge_output_format': 'mp4',
    }
    if audio:
        # opts = {
        #     'no_warnings': True,
        #     'format': 'bestaudio[ext=webm]/bestaudio',
        #     'merge_output_format': 'webm',
        #     'writethumbnail': True,
        #     'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
        #     "restrictfilenames": True,
        # }
        opts.update({
            'format': 'bestaudio[ext=webm]/bestaudio',
            'merge_output_format': 'webm',
        })

    with yt_dlp.YoutubeDL(opts) as ydl:
        if not audio:
            return ydl.download([url]) == 0

        before_files = {file.resolve() for file in output_dir.iterdir() if file.is_file()}
        info = ydl.extract_info(url, download=True)
        if info is None:
            return False

        after_files = {file.resolve() for file in output_dir.iterdir() if file.is_file()}
        new_files = sorted(after_files - before_files)

        webm_file = next((file for file in new_files if file.suffix.lower() == ".webm"), None)
        if webm_file is None:
            expected_file = Path(ydl.prepare_filename(info))
            if expected_file.exists() and expected_file.suffix.lower() == ".webm":
                webm_file = expected_file.resolve()
            else:
                return False

        cover_extensions = {".webp", ".jpg", ".jpeg", ".png", ".avif", ".bmp"}
        cover_file = next(
            (
                file for file in new_files
                if file.suffix.lower() in cover_extensions
            ),
            None,
        )
        if cover_file is None:
            cover_file = next(
                (
                    file for file in output_dir.iterdir()
                    if file.is_file()
                    and file.stem == webm_file.stem
                    and file.suffix.lower() in cover_extensions
                ),
                None,
            )

        ogg_file = from_webm_to_ogg(
            input_file=str(webm_file),
            cover=str(cover_file) if cover_file is not None else None,
        )

        audio_tags = MutagenFile(ogg_file, easy=False)
        if audio_tags is None:
            raise RuntimeError(f"No se pudieron abrir tags en '{ogg_file}'")

        if audio_tags.tags is None:
            audio_tags.add_tags()

        title = info.get("title")
        if title:
            audio_tags["TITLE"] = [str(title)]

        original_url = info.get("original_url") or info.get("webpage_url") or url
        comments = [
            f"#url: {original_url}",
            f"#mngr: {datetime.now():%Y%m%d}",
        ]
        audio_tags["COMMENT"] = comments
        audio_tags.save()

        webm_file.unlink(missing_ok=True)
        if cover_file is not None:
            cover_file.unlink(missing_ok=True)

        return ogg_file


def get_items(url: str) -> list[str]:
    '''
    Returns a list of item URLs from a playlist, album or any collection.
    If the URL points to a single video, returns a list with just that URL.
    '''
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info is None:
        return []

    if info.get('_type') == 'playlist':
        return [
            entry['url']
            for entry in info.get('entries', [])
            if entry is not None and entry.get('url')
        ]

    item_url = info.get('webpage_url') or url
    return [item_url]