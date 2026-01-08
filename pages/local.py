import streamlit as st
import os
from pathlib import Path
import pandas as pd
from enum import Enum
from dataclasses import dataclass, fields
# import music_tag
from tinytag import TinyTag
from functions import get_waveform, show_cover, get_audio_properties
from frontend import song_player
from easy_st_aggrid import col_base, col_text, col_date, col_checkbox, easy_table


st.image(
    r'assets/download_folder_file_icon_219533.ico',
    width=100
)

st.logo(
    r'assets/download_folder_file_icon_219533.ico',
)

if not 'source_path' in st.session_state:
    st.session_state.source_path = None

if not 'fields' in st.session_state:
    st.session_state.source_path = ['artist', 'title', 'album', 'year', 'genre']
    st.session_state.source_path = None

path_file = '.path'
if not os.path.exists(path_file):
    with open(path_file, 'w') as f:
        f.write('')

try:
    with open(path_file, 'r') as f:
        st.session_state.source_path = f.read().strip()
        if st.session_state.source_path == str():
            st.session_state.source_path = None
except FileNotFoundError:
    st.session_state.source_path = None

@st.dialog("SET LOCAL FILES PATH 📂")
def set_source_path(old_path: str):
    new_path = st.text_input(
        label='LOCAL FILES FOLDER 📂',
        value=old_path,
        # key='source_path'
    )
    if new_path != old_path and st.button("Submit"):
        st.session_state.source_path = new_path
        with open(path_file, 'w') as f:
            f.write(new_path)
        st.rerun()

st.sidebar.button(
    'SET LOCAL FILES', 
    width='stretch', 
    # on_click=lambda: st.session_state.update(source_path=None)
    on_click=lambda: set_source_path(st.session_state.source_path),
    icon="📂",
)

# st.text(f"LOCAL FILES PATH: {st.session_state.source_path}")


# with st.expander(f'LOCAL FILES PATH 📂 | {st.session_state.source_path}', expanded=False):
#     st.text("")
#     new_path = st.text_input(
#         label='SET LOCAL FILES PATH 📂',
#         value=st.session_state.source_path,
#     )
#     if new_path:
#         if st.button("Submit"):
#             st.session_state.source_path = new_path
#             with open(path_file, 'w') as f:
#                 f.write(new_path)
#             st.rerun()

# col1, col2 = st.columns(2)

# with col1:
# st.write(f'LOCAL FILES 📂:  {st.session_state.source_path}')

# with col2:
# if st.button(
#     'SET LOCAL FILES PATH 📂', 
#     # use_container_width=True, 
#     # on_click=lambda: st.session_state.update(source_path=r'/Users/mbair/Desktop/[MUSIC CONSOLIDATED]')
#     # on_click=set_source_path(st.session_state.source_path)
#     ):
#     set_source_path(st.session_state.source_path)

def list_to_string(value):
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return value

def get_songs(path: str):
    songs = [file for file in Path(path).rglob('*') if file.is_file() and file.suffix.lower() in TinyTag.SUPPORTED_FILE_EXTENSIONS]
    data_songs = [TinyTag.get(file).as_dict() for file in songs]
    df_songs = pd.DataFrame(data_songs)
    df = st.dataframe(
        df_songs,
        hide_index=True,
        selection_mode='single-row',
        on_select='rerun'
    )
    df = df.applymap(list_to_string)
    return df

if st.session_state.source_path:
    path = Path(st.session_state.source_path)

    # st.header('📂 PLAYLIST & FOLDERS', divider=True)

    playlist = [str(folder) for folder in path.rglob('*') if folder.is_dir()]
    # st.write(playlist)
    playlist_folders = [folder.replace(st.session_state.source_path, "").replace('/', '') for folder in sorted(playlist)]
    # st.write(playlist_folders)
    # playlist.insert(0, 'All ...')
    playlist_folders.insert(0, 'All ...')
    # obj = st.dataframe(
    #     playlist,
    #     hide_index=True,
    #     selection_mode='single-row',
    #     on_select='rerun'
    # )

    playlist = st.selectbox(
        'PLAYLIST & FOLDERS',
        options=playlist_folders,
        index=0,
        # key='playlist_folders',
        # on_change=lambda: st.session_state.update(source_path=playlist_folders[st.session_state.playlist_folders])
    )

    if playlist == playlist_folders[0]:
        songs_path = st.session_state.source_path
    else:
        songs_path = os.path.join(st.session_state.source_path, playlist)
    st.write(songs_path)
    
    # st.header('🎹 SONGS', divider=True)

    if not os.path.exists(songs_path):
        st.warning(f"⚠ Folder {playlist} does not exist.")
    else:
        st.write('SONGS:')
        # df_songs = get_songs(songs_path)
        # st.write(df_songs)
        songs = [file for file in Path(songs_path).rglob('*') if file.is_file() and file.suffix.lower() in TinyTag.SUPPORTED_FILE_EXTENSIONS]
        data_songs = [TinyTag.get(file).as_dict() for file in songs]
        df_songs = pd.DataFrame(data_songs)
        df_songs = df_songs.map(list_to_string)

        # col1, col2 = st.columns([3,1])
        # with col1.popover('Fields', icon='🗄️'): #, use_container_width=True): # expanded=False, 
        #         default_fields = ['artist', 'title', 'album', 'year', 'genre']
        #         default_fields = [field for field in default_fields if field in df_songs.columns]
        #         fields1 = st.multiselect('FIELDS', options=df_songs.columns, default=default_fields)
        
        # with col2:
        #     rows = st.segmented_control(
        #         'Lines', 
        #         options=[10, 50, 100],
        #         default=10,
        #         selection_mode='single',
        #         label_visibility='collapsed',
        #     )

        col1, col2, col3 = st.columns([4, 3, 1])

        with col3.popover('OPTIONS', icon='⚙️', type='secondary', width='stretch'):

            n_rows = st.segmented_control(
                'Lines', 
                options=[10, 50, 100],
                default=10,
                selection_mode='single',
                label_visibility='visible',
            )

            default_fields = ['artist', 'title', 'album', 'year', 'genre']
            default_fields = [field for field in default_fields if field in df_songs.columns]
            
            tbl_fields = st.multiselect(
                'FIELDS',
                options=df_songs.columns,
                default=default_fields,
                # key='fields1',
                label_visibility='visible',
                width='stretch',
            )

            filter = st.text_input(
                'FILTER',
                placeholder='Filter by artist, title, album, year, genre ...',
                label_visibility='visible',
                icon='🔍',
            )


        dividers = len(df_songs)/n_rows
        counter = 0

        if not 'counter' in st.session_state:
            st.session_state.counter = 0

        # st.write(f"Showing {len(df_songs)} songs, {dividers:.0f} dividers per page, count: {st.session_state.counter}, n_rows: {n_rows}")

        # filtered_df = df_songs[tbl_fields].iloc[n_rows*st.session_state.counter:n_rows*(st.session_state.counter+1)]
        filtered_df = df_songs[tbl_fields]

        st_song = st.dataframe(
            filtered_df,
            hide_index=True,
            selection_mode='single-row',
            on_select='rerun'
        )

        columns_list = [col_text(f, filter=True) for f in tbl_fields]
        columns_list.insert(0, col_checkbox())

        selection = easy_table(
            dataframe=filtered_df, 
            height=700,
            columns_list=columns_list
        )

        # col1, col2, col3 = st.columns([4,1,1])
        # from_ = st.session_state.counter * n_rows
        # to_ = from_ + n_rows
        # if to_ > len(df_songs):
        #     to_ = len(df_songs)
        # with col1: st.write(f'From {from_} to {to_} of {len(df_songs)} songs')
        # if st.session_state.counter > 0 and col2.button('', use_container_width=True, icon='⬅️'):
        #     if st.session_state.counter > 0:
        #         st.session_state.counter -= 1
        # if st.session_state.counter < int(f'{dividers:.0f}') and col3.button('', use_container_width=True, icon='➡️'):
        #     if st.session_state.counter < int(f'{dividers:.0f}'):
        #         st.session_state.counter += 1

        ## PLAYER
        # if len(st_song.selection['rows']) > 0:
        #     indx = st_song.selection['rows'][0]
        #     path_song = df_songs.iloc[indx]['filename']

        #     song_player(path_song)

        if selection.selected_rows_id:
            indx = selection.selected_rows_id[0]
            print(indx)
            path_song = df_songs.iloc[int(indx)]['filename']

            song_player(path_song)



st.empty()
# st.info(f"LOCAL FILES PATH: {st.session_state.source_path}", icon="📂")

import streamlit as st
import streamlit.components.v1 as components

# Lectura del archivo HTML local
# html_code = open("check-file-manager.html", "r", encoding="utf-8").read()
# components.html(html_code, height=600)

import streamlit.components.v1 as components
import uuid
from pathlib import Path

def wavesurfer_player(audio_path: str, height=120):
    element_id = f"waveform-{uuid.uuid4().hex}"
    audio_path = Path(audio_path).as_posix()

    html = f"""
    <div style="width:100%;">
        <div id="{element_id}" style="height:{height}px;"></div>

        <div style="margin-top:6px;">
            <button id="{element_id}-play">▶️ / ⏸</button>
        </div>
    </div>

    <script src="https://unpkg.com/wavesurfer.js@7"></script>
    <script>
      const ws_{element_id} = WaveSurfer.create({{
        container: "#{element_id}",
        waveColor: "#555",
        progressColor: "#facc15",
        cursorColor: "#facc15",
        barWidth: 2,
        barGap: 1,
        height: {height},
        normalize: true,
      }});

      ws_{element_id}.load("{audio_path}");

      document.getElementById("{element_id}-play")
        .addEventListener("click", () => {{
          ws_{element_id}.playPause();
        }});
    </script>
    """

    components.html(html, height=height + 50)
    print('pass')

st.title("🎧 DJ Player")

wavesurfer_player(
    "/Volumes/BK250_APFS/[MUSIC DJ]/[ELECTRO]/02 Bushido.m4a"
)