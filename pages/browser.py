import os
import streamlit as st
from streamlit_file_browser import st_file_browser

st.title("Explorador de Archivos")

# Define el path inicial desde donde quieres empezar
start_path = '/Volumes/BK250_APFS/[MUSIC DJ]'  # <-- cámbialo a tu carpeta base

# event = st_file_browser(
#     start_path,        # carpeta inicial
#     key="file_browser" # clave única (necesaria si usas más de un browser)
# )

# st.write("Evento:", event)

if not 'selected_folder' in st.session_state:
    st.session_state['selected_folder'] = start_path

# placeholder = st.empty()

# placeholder.text(st.session_state['selected_folder'])

event = st_file_browser(
    start_path, 
    key="browser",    
    use_static_file_server=True,
    show_choose_file=True,
    show_delete_file=True,
    show_download_file=False,
    show_new_folder=True,
    show_upload_file=False,
)

# if event:
#     st.write("Evento:", event)
#     if event.get('target'):
        # if event['target'].get('path'):
        #     st.session_state['selected_folder'] = event['target']['path']

    # if event["type"] == "folder_changed":
    #     # Carpeta en la que el usuario hizo clic
    #     st.session_state["selected_path"] = event["path"]
    #     st.info(f"Carpeta seleccionada: {event['path']}")

    # elif event["type"] == "file_opened":
    #     # Archivo abierto → guardamos el archivo y también su carpeta
    #     filepath = event["path"]
    #     st.session_state["selected_path"] = os.path.dirname(filepath)
    #     st.success(f"Archivo abierto: {filepath}")
    #     st.write(f"📂 Carpeta del archivo: {st.session_state['selected_path']}")

# Mostrar siempre la última ruta seleccionada
# if "selected_path" in st.session_state:
#     st.write("📌 Última ruta seleccionada:", st.session_state["selected_path"])