import base64
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from mutagen import File
from mutagen.apev2 import APEv2
from mutagen._vorbis import VCommentDict
from mutagen.id3 import ID3, TBPM
from mutagen.mp4 import MP4Tags

from music_manager.tags import Editor, Extractor


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
    "x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


class TestBPM(unittest.TestCase):
    def test_rejects_non_integer_values_before_opening_audio(self):
        with patch("music_manager.tags.MutagenFile") as open_audio:
            for value in ("110", "110.0", "", 110.0, 110.5, True, False):
                with self.subTest(value=value):
                    with self.assertRaisesRegex(TypeError, "bpm must be an int or None"):
                        Editor.set_tags("track.m4a", {"bpm": value})
            open_audio.assert_not_called()

    def test_mp4_writes_integer_and_preserves_other_tags(self):
        tags = MP4Tags()
        audio = SimpleNamespace(tags=tags, save=Mock())
        with patch("music_manager.tags.MutagenFile", return_value=audio):
            Editor.set_tags("track.m4a", {"artist": "Becky G", "bpm": 110})
            self.assertEqual(tags["tmpo"], [110])
            self.assertIs(type(tags["tmpo"][0]), int)
            Editor.set_tags("track.m4a", {"title": "Zooted"})
            self.assertEqual(tags["tmpo"], [110])
            for unused in range(2):
                Editor.set_tags("track.m4a", {"bpm": None})
                self.assertNotIn("tmpo", tags)
            self.assertEqual(Extractor._extract_mp4(tags)["artist"], "Becky G")

    def test_extracts_integer_bpm_from_text_formats(self):
        for value, expected in (("110", 110), ("110.0", 110), ("110.49", 110),
                                ("110.5", 111), ("invalid", None), ("NaN", None),
                                ("Infinity", None)):
            with self.subTest(value=value):
                id3 = ID3()
                id3.add(TBPM(encoding=3, text=[value]))
                vorbis = VCommentDict()
                vorbis["BPM"] = [value]
                results = (
                    Extractor._extract_id3(id3),
                    Extractor._extract_vorbis(SimpleNamespace(tags=vorbis)),
                )
                for result in results:
                    self.assertEqual(result.get("bpm"), expected)
                    if expected is not None:
                        self.assertIs(type(result["bpm"]), int)


class TestSetVorbisTags(unittest.TestCase):
    def test_remove_present_and_missing_tags(self):
        for present in (False, True):
            for value in (None, ""):
                with self.subTest(present=present, value=value):
                    tags = VCommentDict()
                    tags["artist"] = ["keep"]
                    if present:
                        tags["bpm"] = ["120"]
                        tags["metadata_block_picture"] = ["old cover"]
                    Editor._set_vorbis_tags(tags, {"bpm": value, "cover": value})
                    self.assertNotIn("bpm", tags)
                    self.assertNotIn("metadata_block_picture", tags)
                    self.assertEqual(tags["artist"], ["keep"])

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_opus_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "track.opus")
            subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=48000:cl=mono", "-t", "0.1",
                    "-c:a", "libopus", path,
                ],
                check=True, capture_output=True,
            )
            Editor.set_tags(path, {"artist": "Masaaki Hirao", "bpm": 120})
            title = "\u5fc5\u6bba\u4ed5\u4e8b\u4eba Vol \u2162"
            for value in (None, None):
                with self.subTest(value=value):
                    Editor.set_tags(path, {"title": title, "bpm": value})
                    tags = Extractor.get_tags(path)
                    self.assertEqual(tags["title"], title)
                    self.assertEqual(tags["artist"], "Masaaki Hirao")
                    self.assertNotIn("bpm", File(path).tags)


class TestSetCover(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_audio_round_trips(self):
        formats = (
            ("mp3", "libmp3lame"),
            ("m4a", "aac"),
            ("flac", "flac"),
            ("ogg", "libvorbis"),
            ("opus", "libopus"),
            ("wav", "pcm_s16le"),
            ("aiff", "pcm_s16be"),
            ("wv", "wavpack"),
        )
        with tempfile.TemporaryDirectory() as directory:
            for suffix, codec in formats:
                with self.subTest(format=suffix):
                    path = str(Path(directory) / f"track.{suffix}")
                    subprocess.run(
                        [
                            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "anullsrc=r=44100:cl=mono", "-t", "0.1",
                            "-c:a", codec, path,
                        ],
                        check=True, capture_output=True,
                    )
                    Editor.set_tags(path, {"title": "keep"})
                    Editor.set_tags(path, {"bpm": 110})
                    self.assertEqual(Extractor.get_tags(path)["bpm"], 110)
                    self.assertIs(type(Extractor.get_tags(path)["bpm"]), int)
                    Editor.set_tags(path, {"bpm": None})
                    self.assertIsNone(Extractor.get_tags(path).get("bpm"))
                    for cover in (PNG, b"\xff\xd8\xffreplacement", b""):
                        Editor.set_cover(path, cover)
                        audio = File(path)
                        if isinstance(audio.tags, APEv2):
                            embedded = audio.tags.get("Cover Art (Front)")
                            actual = (
                                embedded.value.split(b"\x00", 1)[1]
                                if embedded is not None else None
                            )
                        else:
                            actual = Extractor.get_cover(path)
                        self.assertEqual(actual, cover or None)
                        self.assertEqual(Extractor.get_tags(path)["title"], "keep")

    def test_ape_cover_serialization(self):
        tags = APEv2()
        tags["Title"] = "keep"
        audio = SimpleNamespace(tags=tags, save=Mock())
        with patch("music_manager.tags.MutagenFile", return_value=audio):
            Editor.set_cover("track.ape", PNG)
            self.assertEqual(tags["Cover Art (Front)"].value, b"cover.png\x00" + PNG)
            Editor.set_cover("track.ape", b"")
        self.assertNotIn("Cover Art (Front)", tags)
        self.assertEqual(str(tags["Title"]), "keep")

    def test_rejects_invalid_inputs_before_opening_audio(self):
        with patch("music_manager.tags.MutagenFile") as open_audio:
            with self.assertRaises(TypeError):
                Editor.set_cover("track.mp3", "not bytes")
            with self.assertRaises(ValueError):
                Editor.set_cover("track.mp3", b"GIF89a")
            with self.assertRaises(ValueError):
                Editor.set_cover("track.txt", PNG)
            open_audio.assert_not_called()