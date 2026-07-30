import yt_dlp


class YTUFF:

    @staticmethod
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
