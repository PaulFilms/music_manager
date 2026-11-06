import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from gamdl.interface import AppleMusicBaseInterface
from gamdl.interface.enums import CoverFormat

from music_manager.my_gamdl import AM_Metadata, AppleMusicService


class GetItemsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = AppleMusicService("unused-cookies")
        self.service._init_api = AsyncMock()
        self.service.apple_music_api = SimpleNamespace(
            get_song=AsyncMock(return_value={"data": [{"attributes": {}}]}),
            get_library_song=AsyncMock(return_value={"data": [{"attributes": {}}]}),
            get_album=AsyncMock(),
            get_playlist=AsyncMock(),
            get_extended_api_data=AsyncMock(),
        )
        self.service.base_interface = SimpleNamespace(
            format_cover=AppleMusicBaseInterface.format_cover,
            cover_size=300,
            cover_format=CoverFormat.JPG,
            get_cover_bytes=AsyncMock(return_value=b"cover"),
        )
        self.song_url = "https://music.apple.com/us/song/test/123"

    async def test_single_song_metadata_without_downloader(self):
        self.service.apple_music_api.get_song.return_value = {"data": [{
            "attributes": {
                "name": "Track",
                "artistName": "Artist",
                "albumName": "Album",
                "editorialNotes": {"short": "Notes"},
                "durationInMillis": 123456,
                "artwork": {"url": "https://example.com/{w}x{h}bb.jpg"},
            },
        }]}

        items = await self.service.get_items(self.song_url)

        self.assertEqual(items, [AM_Metadata(
            title="Track", url=self.song_url, description="Notes",
            channel="Artist", thumbnail=b"cover", duration=123,
        )])
        self.service.base_interface.get_cover_bytes.assert_awaited_once_with(
            "https://example.com/300x300bb.jpg"
        )
        self.assertIsNone(self.service.downloader)
        self.assertFalse(self.service._initialized)

    async def test_album_expands_tracks_and_omits_videos(self):
        track_url = "https://music.apple.com/us/album/test/456?i=789"
        self.service.apple_music_api.get_album.return_value = {"data": [{
            "relationships": {"tracks": {"data": [
                {"id": "123", "type": "songs", "attributes": {"url": self.song_url}},
                {"id": "456", "type": "music-videos"},
                {"id": "789", "type": "songs"},
            ]}},
        }]}

        items = await self.service.get_items("https://music.apple.com/us/album/test/456")

        self.assertEqual([item.url for item in items], [self.song_url, track_url])
        self.assertEqual(
            [call.args[0] for call in self.service.apple_music_api.get_song.await_args_list],
            ["123", "789"],
        )
        self.assertIsNone(items[0].duration)
        self.assertIsNone(items[0].thumbnail)

    async def test_playlist_reads_remaining_pages(self):
        self.service.apple_music_api.get_playlist.return_value = {"data": [{
            "relationships": {"tracks": {
                "data": [{"id": "123", "type": "songs", "attributes": {"url": self.song_url}}],
                "next": "/next", "href": "/tracks",
            }},
        }]}
        self.service.apple_music_api.get_extended_api_data.return_value = {
            "data": [{"id": "123", "type": "songs", "attributes": {"url": self.song_url}}],
        }

        items = await self.service.get_items(
            "https://music.apple.com/us/playlist/test/pl.abe8ba42278f4ef490e3a9fc5ec8e8c5"
        )

        self.assertEqual(len(items), 2)
        self.service.apple_music_api.get_extended_api_data.assert_awaited_once_with(
            "/next", "/tracks"
        )

    async def test_library_song_uses_library_api(self):
        info = SimpleNamespace(
            type=None, sub_id=None, id=None, library_id="i.123", library_type="songs"
        )
        with patch("music_manager.my_gamdl.AppleMusicInterface.get_url_info", return_value=info):
            items = await self.service.get_items("https://music.apple.com/library/song/i.123")

        self.assertEqual(len(items), 1)
        self.service.apple_music_api.get_library_song.assert_awaited_once_with("i.123")
        self.service.apple_music_api.get_song.assert_not_awaited()

    async def test_cover_failure_keeps_song_and_album_description(self):
        self.service.apple_music_api.get_song.return_value = {"data": [{"attributes": {
            "name": "Track", "albumName": "Album", "durationInMillis": 0,
            "artwork": {"url": "https://example.com/{w}x{h}bb.jpg"},
        }}]}
        self.service.base_interface.get_cover_bytes.side_effect = OSError("unavailable")

        items = await self.service.get_items(self.song_url)

        self.assertEqual(items[0].title, "Track")
        self.assertEqual(items[0].description, "Album")
        self.assertEqual(items[0].duration, 0)
        self.assertIsNone(items[0].thumbnail)

    async def test_empty_collection_returns_empty_list(self):
        self.service.get_urls = AsyncMock(return_value=[])
        self.assertEqual(await self.service.get_items("empty-collection"), [])
        self.service.get_urls.assert_awaited_once_with("empty-collection")
        self.service.apple_music_api.get_song.assert_not_awaited()

    async def test_invalid_url_raises(self):
        with self.assertRaises(ValueError):
            await self.service.get_items("invalid-url")
        self.service.apple_music_api.get_song.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()