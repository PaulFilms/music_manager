import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

fake_mutagen = types.ModuleType("mutagen")
fake_mutagen.File = lambda *args, **kwargs: None

fake_mutagen_flac = types.ModuleType("mutagen.flac")


class FakePicture:
    def __init__(self):
        self.type = None
        self.desc = None
        self.mime = None
        self.data = None

    def write(self):
        return b""


fake_mutagen_flac.Picture = FakePicture

fake_mutagen_id3 = types.ModuleType("mutagen.id3")
fake_mutagen_id3.ID3Tags = type("ID3Tags", (), {})
fake_mutagen_id3.COMM = type("COMM", (), {})

fake_mutagen_mp4 = types.ModuleType("mutagen.mp4")
fake_mutagen_mp4.MP4Tags = type("MP4Tags", (), {})

fake_yt_dlp = types.ModuleType("yt_dlp")
fake_yt_dlp.YoutubeDL = object

sys.modules.setdefault("mutagen", fake_mutagen)
sys.modules.setdefault("mutagen.flac", fake_mutagen_flac)
sys.modules.setdefault("mutagen.id3", fake_mutagen_id3)
sys.modules.setdefault("mutagen.mp4", fake_mutagen_mp4)
sys.modules.setdefault("yt_dlp", fake_yt_dlp)

from music_manager import ytuf


class FakeAudioTags(dict):
    def __init__(self):
        super().__init__()
        self.tags = {}
        self.saved = False

    def add_tags(self):
        self.tags = {}

    def save(self):
        self.saved = True


class DownloadAudioTests(unittest.TestCase):
    def test_audio_download_keeps_original_files_when_replace_is_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            webm_path = output_dir / "track.webm"
            cover_path = output_dir / "track.jpg"
            ogg_path = output_dir / "track.ogg"
            audio_tags = FakeAudioTags()

            class FakeYoutubeDL:
                def __init__(self, opts):
                    self.opts = opts

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def extract_info(self, url, download=False):
                    return {
                        "title": "Track",
                        "webpage_url": url,
                    }

                def download(self, urls):
                    self.opts["writethumbnail"]
                    webm_path.write_bytes(b"webm")
                    if self.opts.get("writethumbnail"):
                        cover_path.write_bytes(b"cover")
                    return 0

                def prepare_filename(self, info):
                    return str(webm_path)

            def fake_convert(input_file: str, cover: str | None = None) -> str:
                self.assertEqual(str(webm_path.resolve()), input_file)
                self.assertEqual(str(cover_path.resolve()), cover)
                ogg_path.write_bytes(b"ogg")
                return str(ogg_path)

            with (
                patch("music_manager.ytuf.yt_dlp.YoutubeDL", FakeYoutubeDL),
                patch("music_manager.ytuf.from_webm_to_ogg", side_effect=fake_convert),
                patch("music_manager.ytuf.MutagenFile", return_value=audio_tags),
            ):
                result = ytuf.download(tmpdir, "https://example.com/audio", audio=True, replace=False)

            self.assertEqual(str(ogg_path), result)
            self.assertTrue(webm_path.exists())
            self.assertTrue(cover_path.exists())
            self.assertTrue(ogg_path.exists())
            self.assertEqual(["Track"], audio_tags["TITLE"])
            self.assertIn("#url: https://example.com/audio", audio_tags["COMMENT"])
            self.assertTrue(audio_tags.saved)

    def test_audio_download_removes_original_files_when_replace_is_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            webm_path = output_dir / "track.webm"
            cover_path = output_dir / "track.jpg"
            ogg_path = output_dir / "track.ogg"
            audio_tags = FakeAudioTags()

            class FakeYoutubeDL:
                def __init__(self, opts):
                    self.opts = opts

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def extract_info(self, url, download=False):
                    return {
                        "title": "Track",
                        "webpage_url": url,
                    }

                def download(self, urls):
                    self.opts["writethumbnail"]
                    webm_path.write_bytes(b"webm")
                    if self.opts.get("writethumbnail"):
                        cover_path.write_bytes(b"cover")
                    return 0

                def prepare_filename(self, info):
                    return str(webm_path)

            def fake_convert(input_file: str, cover: str | None = None) -> str:
                self.assertEqual(str(webm_path.resolve()), input_file)
                self.assertEqual(str(cover_path.resolve()), cover)
                ogg_path.write_bytes(b"ogg")
                return str(ogg_path)

            with (
                patch("music_manager.ytuf.yt_dlp.YoutubeDL", FakeYoutubeDL),
                patch("music_manager.ytuf.from_webm_to_ogg", side_effect=fake_convert),
                patch("music_manager.ytuf.MutagenFile", return_value=audio_tags),
            ):
                result = ytuf.download(tmpdir, "https://example.com/audio", audio=True, replace=True)

            self.assertEqual(str(ogg_path), result)
            self.assertFalse(webm_path.exists())
            self.assertFalse(cover_path.exists())
            self.assertTrue(ogg_path.exists())

    def test_youtube_playlist_url_returns_none_without_downloading(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            class FakeYoutubeDL:
                def __init__(self, opts):
                    self.opts = opts
                    self.download_called = False

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def extract_info(self, url, download=False):
                    return {
                        "_type": "playlist",
                        "extractor_key": "YoutubeTab",
                        "webpage_url": url,
                        "entries": [{"url": "https://www.youtube.com/watch?v=abc"}],
                    }

                def download(self, urls):
                    self.download_called = True
                    raise AssertionError("download() should not be called for YouTube playlists")

            with patch("music_manager.ytuf.yt_dlp.YoutubeDL", FakeYoutubeDL):
                result = ytuf.download(
                    tmpdir,
                    "https://www.youtube.com/playlist?list=PL123",
                    audio=True,
                    replace=False,
                )

            self.assertIsNone(result)
            self.assertEqual([], list(output_dir.iterdir()))


if __name__ == "__main__":
    unittest.main()
