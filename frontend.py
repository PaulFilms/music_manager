import io
import streamlit as st
from functions import get_waveform, get_audio_properties
from tinytag import TinyTag
from PIL import Image

def show_cover(uploaded_file, default_cover: str = None, size: int = 200):
    """
    Muestra el cover de un archivo de audio si está embebido en los metadatos.
    
    Args:
        uploaded_file: archivo subido en st.file_uploader
        default_cover: ruta a una imagen por defecto si no hay carátula
        size: tamaño en píxeles del cover mostrado
    """
    try:
        # TinyTag necesita el path o un buffer
        tag = TinyTag.get(uploaded_file, image=True)

        if tag.get_image():
            image_data = tag.get_image()
            image = Image.open(io.BytesIO(image_data))
            return st.image(image, width='stretch') # size)
        elif default_cover:
            return st.image(default_cover, width='stretch') # size)
        else:
            # st.write("🎵 No se encontró portada")
            return None
    except Exception as e:
        # st.write(f"⚠️ No se pudo leer la portada: {e}")
        if default_cover:
            return st.image(default_cover, width='stretch') # size)

def song_player(path_song: str):
    with st.container(border=True):
        col_cover, col_waveform = st.columns([1,5])
        # with col_cover:
        #     show_cover(path_song, size=100)
        # with col_waveform:
        #     get_waveform(path_song)
        # st.audio(path_song)
        props = get_audio_properties(path_song)
        props_str = " | ".join([f"{k.upper()}: {v}" for k, v in props.items()])
        # # st.text(props_str, text_alignment='left')
        # st.caption(props_str, text_alignment='center')
        with col_cover:
            show_cover(path_song,)
        with col_waveform:
            st.audio(path_song, format='')
            with st.expander('polla'):
                st.text('ARTIST')
                st.text('TITLE')
                st.text('ALBUM')
                st.caption(props_str)

