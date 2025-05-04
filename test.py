from tinytag import TinyTag
tag: TinyTag = TinyTag.get(r'/Users/mbair/Desktop/AppleMusic/[D&B 20250504]/02 Boom Blast.m4a')

fields = [
    'filename',
    'filesize',
    'duration',
    'channels',
    'bitrate',
    'bitdepth',
    'samplerate',
    'artist',
    'albumartist',
    'composer',
    'album',
    'disc',
    'disc_total',
    'title',
    'track',
    'track_total',
    'genre',
    'year',
    'comment',
]

print(f'This track is by {tag.artist}.')
for f in fields:
    print(getattr(tag, f))
print(f'It is {tag.duration:.2f} seconds long.')

