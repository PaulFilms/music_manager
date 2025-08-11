## PYTHON
import os, subprocess
from pathlib import Path
import pandas as pd
# import yt_dlp
from functions import YUTUF, clean_filename
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# def extract_thumbnail(video_path, output_path):
#     # Extrae el primer frame como imagen
#     cmd = [
#         'ffmpeg',
#         '-i', str(video_path),
#         '-ss', '00:00:01.000',
#         '-vframes', '1',
#         str(output_path)
#     ]
#     subprocess.run(cmd, check=True)

## PAGE
import streamlit as st

@st.cache_data
def get_files(path: str, count: int) -> pd.DataFrame:
    return YUTUF.get_files(path, count)

if not 'yutuf_count' in st.session_state:
    st.session_state.yutuf_count = 0

logo = r'assets/yutuf.png'

# st.logo(
#     logo,
#     # link=logo
# )

# st.image(
#     # r'assets/download_folder_file_icon_219533.ico',
#     logo,
#     width=200
# )

with st.sidebar:
    st.image(
        logo,
        width=200
    )
    st.button('SET PATH', use_container_width=True)

yutuf_path = st.text_input(
    label='path',
    icon='📁',
    label_visibility='visible',
    value='yutuf'
)

# if not 'files_df' in st.session_state:
#     st.session_state.files_df = YUTUF.get_files(yutuf_path, st.session_state.yutuf_count)

## DOWNLOAD

st.subheader('⤵ DOWNLOAD', divider='blue')

url = st.text_input(
    'URL',
    label_visibility='visible',
    icon='🔗'
)

col1, col2 = st.columns(2)

# def download(ydl_opts, url):
#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         if ydl.download([url]):
#             st.rerun()

def download(url: str, audio: bool = False):
    ## THUMBNAIL
    yutuf_name = YUTUF.get_file_name(url)
    yutuf_name_clean = clean_filename(yutuf_name)
    st.write(f'**{yutuf_name}**')

    jpg_files = [
        clean_filename(Path(f).stem)
        for f in os.listdir(yutuf_path)
        if f.lower().endswith(".jpg")
    ] 
    if yutuf_name_clean not in jpg_files:
        st.write('✅ Thumbnail already exists.')

    # ## FILE
    extension = '.mp4' if not audio else '.webm'

    media_files = [
        clean_filename(Path(f).stem)
        for f in os.listdir(yutuf_path)
        if f.lower().endswith(extension)
    ]
    if yutuf_name_clean not in media_files:
        if YUTUF.download(yutuf_path, url, audio=audio):
            st.rerun()
    else:
        st.write('✅ File already exists.')
    # if YUTUF.get_file_name(url) + extension in os.listdir(yutuf_path):
    #     st.warning('⚠️ File already exists.')
    # else:
    #     YUTUF.download(yutuf_path, url, audio=audio)
    #     st.session_state.yutuf_count += 1

if url and col1.button('DOWNLOAD VIDEO', use_container_width=True):
    download(url, audio=False)

if url and col2.button('DOWNLOAD AUDIO', use_container_width=True):
    download(url, audio=True)

## PLAYER

st.subheader('📀 FILES', divider='orange')

if os.path.exists(yutuf_path):
    files_df = get_files(yutuf_path, st.session_state.yutuf_count)

    files_stdf = st.dataframe(
        files_df,
        # pd.DataFrame(files, columns=['file']),
        hide_index=True,
        use_container_width=True,
        selection_mode='single-row',
        on_select='rerun'
    )

    rows = files_stdf.selection.get('rows')
    if rows:
        file_path = files_df['file'].iloc[rows[0]]

        ## OPTIONS
        with st.popover('OPTIONS', icon='⚙️'):
            if st.button('Refresh', use_container_width=True, icon='🔄'):
                st.rerun()
            st.button('Audio Converter', use_container_width=True)

        # Mostrar miniatura si es video
        st.write(Path(file_path).stem)
        jpg_path = os.path.join(yutuf_path, Path(file_path).stem + '.jpg')
        st.write(jpg_path)
        if os.path.exists(jpg_path):
            st.image(
                jpg_path,
                caption='Miniatura',
                use_container_width=True
            )

        ## AUDIO
        audio_file = open(file_path, "rb")
        audio_bytes = audio_file.read()
        st.audio(audio_bytes)



