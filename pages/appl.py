import streamlit as st
import os
import subprocess
import shutil
from pathlib import Path
from tinytag import TinyTag


st.image(
    r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fwww.pngarts.com%2Ffiles%2F8%2FApple-Music-Logo-PNG-Photo.png&f=1&nofb=1&ipt=e1b53e796e2f7e19a300a29fe5d05a076a8641f06b7a52514f1cc8da7962234b',
    width=100
)

st.logo(
    r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fwww.pngarts.com%2Ffiles%2F8%2FApple-Music-Logo-PNG-Photo.png&f=1&nofb=1&ipt=e1b53e796e2f7e19a300a29fe5d05a076a8641f06b7a52514f1cc8da7962234b',
)

# st.title('APPL')

# st.header(
#     'APPL',
#     divider=True
# )

# col1, col2 = st.columns(2)

# with col1:
#     st.image(
#         r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fwww.pngarts.com%2Ffiles%2F8%2FApple-Music-Logo-PNG-Photo.png&f=1&nofb=1&ipt=e1b53e796e2f7e19a300a29fe5d05a076a8641f06b7a52514f1cc8da7962234b',
#         width=100
#     )

# with col2:
    

with st.expander('DOWNLOAD FROM URL', expanded=False):

    # st.header('Download from URL', divider=True)

    # tab1, tab2 = st.tabs(["By Text", "By File"])

    # with tab1:
    #     cookie = st.text_input(
    #         "Cookies 🍪",
    #         label_visibility='visible',
    #         # disabled=st.session_state.disabled,
    #         # placeholder=st.session_state.placeholder,
    #     )

    # with tab2:
    #     st.file_uploader('Cookies 🍪')


    url_appl = st.text_input(
        "URL 🔗",
        label_visibility='visible',
        # disabled=st.session_state.disabled,
        # placeholder=st.session_state.placeholder,
        key = 'url_appl'
    )

    if url_appl:
        if st.button('APPL RUN', use_container_width=True):

            st.write("Ejecutando comando...")

            # Construir el comando
            comando = ["gamdl", url_appl]

            # Crear un placeholder en Streamlit para ir actualizando la salida
            output_area = st.empty()

            # Ejecutar el proceso en tiempo real
            with subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
            ) as proc:
                output = ""
                for line in proc.stdout:
                    output += line
                    # output_area.text(output)  # Actualiza la salida progresivamente
                    output_area.text_area("Salida:", output, height=300)

                proc.wait()
    

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

st.header('READ FILES', divider=True)

path_db = st.text_input(
    "SOURCE PATH 🔗",
    label_visibility='visible',
    # disabled=st.session_state.disabled,
    # placeholder=st.session_state.placeholder,
    key = 'path_db'
)

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

if path_db:
    if st.button('RUN'):
        path = Path(path_db)
        l = []
        for file in path.rglob('*.m4a'):
            tag: TinyTag = TinyTag.get(file)
            fiels = {f:getattr(tag, f) for f in fields}
            # st.write(file)
            # st.write(fiels)
            l.append(fiels)
        st.dataframe(l)
