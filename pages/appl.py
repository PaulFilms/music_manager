
import os
import subprocess
import shutil
from pathlib import Path
# from tinytag import TinyTag
import pandas as pd
# from io import StringIO

from functions import APPL

path_appl = r'/Users/mbair/Desktop/[MUSIC CONSOLIDED]'

## PAGE
import streamlit as st

if not 'running' in st.session_state:
    st.session_state.running = False

if not 'cookie' in st.session_state:
    st.session_state.cookie = None

if "proc" not in st.session_state:
    st.session_state.proc = None

path_logo = r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fwww.pngarts.com%2Ffiles%2F8%2FApple-Music-Logo-PNG-Photo.png&f=1&nofb=1&ipt=e1b53e796e2f7e19a300a29fe5d05a076a8641f06b7a52514f1cc8da7962234b',

with st.sidebar:
    st.image(
        path_logo,
        width=100
    )
    st.text('⚙️ SETTINGS')
    st.button('GET COOKIE 🍪', use_container_width=True)

# st.image(path_logo, width=100)
# st.logo(path_logo)
# st.title('APPL')

# st.header(
#     'APPL',
#     divider=True
# )


## FUNCTIONS

def download_url(url: str, console_placeholder=None):
    comando = ["gamdl", url]
    with subprocess.Popen(comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
        ) as proc:
        lines = []
        for line in proc.stdout:
            lines.append(line.rstrip())
            if len(lines) > 5: # Mantener solo las últimas 5 líneas
                lines = lines[-5:]
            if console_placeholder: 
                console_placeholder.text_area("Salida:", "\n".join(lines), height=300)
        proc.wait()

## DOWNLOAD FROM URL
with st.expander('DOWNLOAD FROM URL', expanded=False):
    st.text('')

    if not st.session_state.cookie:
        st.text('GET COOKIE 🍪')

        tab1, tab2, tab3 = st.tabs([
            'By *.txt file',
            'By AM Login',
            'By Text'
        ])

        with tab1:
            cookie_str1 = st.file_uploader("Choose a TXT file", accept_multiple_files=False)
            if cookie_str1:
                # stringio = StringIO(cookie_str1.getvalue().decode("utf-8"))
                # st.write(stringio)
                cookie_str = cookie_str1.getvalue().decode("utf-8")
                st.session_state.cookie = cookie_str
                st.rerun()
        
        with tab2:
            if st.button('MAGIX'):
                st.balloons()
        
        with tab3:
            cookie_str = st.text_input(
                "COOKIE TEXT",
                label_visibility='visible',
                # disabled=st.session_state.disabled,
                # placeholder=st.session_state.placeholder,
                # key = 'path_source'
            )
        
        if cookie_str: 
            st.session_state.cookie = cookie_str
            st.rerun()
    else:
        url_appl = st.text_input(
            "WRITE THE SOURCE URL 🔗",
            label_visibility='visible',
            disabled=st.session_state.running,
            key = 'url_appl'
        )

        if url_appl:
            if st.button('APPL RUN', use_container_width=True, disabled=st.session_state.running):
                st.session_state.running = True

                url_type = APPL.Type.get_type(url_appl)
                if url_type == APPL.Type.PLAYLIST or url_type == APPL.Type.ALBUM or url_type == APPL.Type.ARTIST:
                    tracks = APPL.get_tracks(url_appl)
                    tracks = APPL.get_not_duplicates(url_appl, path=path_appl)
                    
                    item_placeholder = st.empty()
                    console_placeholder = st.empty()
                    
                    i = 1
                    for track in tracks:
                        item_placeholder.write(f'NEW ({i}/{len(tracks)}): {track["artistName"]} | {track["name"]}')
                        track_url = track['url']
                        download_url(track['url'], console_placeholder)
                        i += 1
                    console_placeholder = st.empty()
                    item_placeholder.write('FINISHED!')
                else:
                    download_url(url_appl)

                st.session_state.running = False


## MANAGE FILES
with st.expander('MOVE FILES', expanded=False):
    # st.header('MOVE FILES', divider=True)

    path_source = st.text_input(
        "SOURCE PATH 🔗",
        label_visibility='visible',
        # disabled=st.session_state.disabled,
        # placeholder=st.session_state.placeholder,
        key = 'path_source'
    )

    path_target = st.text_input(
        "TARGET PATH 🔗",
        label_visibility='visible',
        # disabled=st.session_state.disabled,
        # placeholder=st.session_state.placeholder,
        key = 'path_target'
    )

    if path_target:
        if st.button('MOVE FILES', use_container_width=True):
            path = Path(path_source)
            for file in path.rglob('*.m4a'):
                # print(file)
                only_file = file.name.split('/')[-1]
                st.text(only_file)
                shutil.move(
                    file,
                    os.path.join(path_target, only_file)
                )
        ## BUG: Eliminar carpeta source

# st.header('READ FILES', divider=True)

## READ APPL PLAYLIST
with st.expander('READ APPL PLAYLIST 📋'):
    tab1, tab2 = st.tabs([
        'By File',
        'By Text'
    ])

    with tab1:
        uploaded_file = st.file_uploader(
            'Choose a *.txt file',
            type=['txt'],
            accept_multiple_files=False
        )
        if uploaded_file:
            # stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
            # st.write(stringio)

            tab3, tab4 = st.tabs([
                'DATA', 'FIELDS'
            ])
        # 
            dataframe = pd.read_csv(uploaded_file, encoding='utf-8', delimiter='\t')
            
            with tab4:
                # fields = pd.DataFrame(dataframe.columns.to_list())
                # fields['VISIBLE'] = True
                fields_visible = st.data_editor(
                    # fields,
                    # zip(
                    #     dataframe.columns.to_list(), 
                    #     (True for e in range(len(dataframe.columns)))
                    # ),
                    pd.DataFrame({'FIELDS': dataframe.columns.to_list(), 'VISIBLE': True}),
                    hide_index=True,
                    # selection_mode='multi-row'
                    column_config={
                        'FIELDS': st.column_config.Column('FIELD', disabled=True),
                        'VISIBLE': st.column_config.CheckboxColumn('VISIBLE', default=True, width='small'),
                    },
                    num_rows='fixed' # 'dynamic'
                )
                # st.write(['11','22'])
                st.write(fields_visible['FIELDS'][fields_visible['VISIBLE']==True].to_list())
                fields_visible_list = fields_visible['FIELDS'][fields_visible['VISIBLE']==True].to_list()
            
            with tab3:
                st.dataframe(
                    dataframe[fields_visible_list],
                    hide_index=True
                )
                # st.write(fields_visible[])

    with tab2:
        playlist = st.text_input(
            "PLAYLIST TEST 🗒️",
            label_visibility='visible',
            # disabled=st.session_state.disabled,
            # placeholder=st.session_state.placeholder,
            key = 'path_db'
        )
        if playlist:
            if st.button('GET PLAYLIST DATA'):
                st.balloons()

# fields = [
#     'filename',
#     'filesize',
#     'duration',
#     'channels',
#     'bitrate',
#     'bitdepth',
#     'samplerate',
#     'artist',
#     'albumartist',
#     'composer',
#     'album',
#     'disc',
#     'disc_total',
#     'title',
#     'track',
#     'track_total',
#     'genre',
#     'year',
#     'comment',
# ]

# if path_db:
#     if st.button('RUN'):
#         path = Path(path_db)
#         l = []
#         for file in path.rglob('*.m4a'):
#             tag: TinyTag = TinyTag.get(file)
#             fiels = {f:getattr(tag, f) for f in fields}
#             # st.write(file)
#             # st.write(fiels)
#             l.append(fiels)
#         st.dataframe(l)
