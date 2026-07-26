import os
from pathlib import Path
import pandas as pd

import streamlit as st
from frontend import *
from easy_st_aggrid import *
from streamlit_wavesurfer import wavesurfer, Region
from streamlit_wavesurfer import WaveSurferPluginConfiguration, OverlayPluginOptions



def build_dataframe(base_path):
    base = Path(base_path)

    rows = []
    for p in base.iterdir():  # 👈 solo primer nivel
        stat = p.stat()

        # Nombre
        nombre = p.name

        # Tipo o icono
        if p.is_dir():
            tipo = "📁"
        else:
            tipo = p.suffix.lower() if p.suffix else "sin extensión"

        # Tamaño en MB
        size_mb = stat.st_size / (1024 * 1024) if p.is_file() else None

        # Fecha modificación
        fecha_mod = pd.to_datetime(stat.st_mtime, unit="s")

        rows.append({
            "nombre": nombre,
            "tipo": tipo,
            "size_mb": round(size_mb, 2) if size_mb else None,
            "fecha_modificacion": fecha_mod
        })

    return pd.DataFrame(rows)

config = config_load()

if not config.get('path_music'):
    path_music = st.text_input('SET YOUR MUSIC PATH', icon=':material/folder:')
    if path_music:
        st.write(path_music)
        if st.button('SET MUSIC PATH', icon=':material/save:'):
            config['path_music'] = path_music
            config_save(config)
            st.rerun()
    st.stop()


## PAGE ______________________________________________________________________________________________

with st.sidebar:
    st.write('OPTIONS:')
    if st.button('RESET MUSIC PATH', icon=':material/reset_settings:', width='stretch'):
        config['path_music'] = None
        config_save(config)
        st.rerun()

Path_music = Path(config['path_music'])

if 'path' not in st.session_state: st.session_state.path = config['path_music']

with st.container(horizontal=True):
    st.text(st.session_state.path)
    st.space(size='stretch')
    holder_back = st.empty()
    holder_go = st.empty()

df = build_dataframe(st.session_state.path)
# df['fecha_modificacion'] = df['fecha_modificacion'].dt.strftime(r"%Y-%m-%d %M:%S")
# st.write(df.head())

# st.dataframe(
#     df,
#     hide_index=True
# )

if Path(st.session_state.path) != Path(config['path_music']):
    # print('no igual', st.session_state.path, config['path_music'])
    if holder_back.button('Volver', icon=':material/chevron_backward:'):
        st.session_state.path = Path(st.session_state.path).parent
        st.rerun()

columns_list = [
    col_base(alias='FILE', children=[
        col_base(id='nombre', width=200),
        col_base(id='tipo', width=100),
        col_base(id='size_mb', width=100),
        # col_str_date(id='fecha_modificacion', width=150),
        col_base(id='fecha_modificacion', width=150),
    ]),
]

result = easy_table(
    df.sort_values('nombre'),
    columns_list=columns_list,
    select_checkbox=True,
    statusbar=True,
    height=500,
    enterprise=True
)

# st.write(result.selected_data)
# st.write(result.data)
# print(result.selected_rows)

if result.selected_rows is not None:
    data = result.selected_rows.iloc[0]
    # st.write(data)
    nombre = data['nombre']
    ftype = data['tipo']
    
    if ftype == '📁':
        if holder_go.button('Ir', icon=':material/chevron_forward:'):
            st.session_state.path = os.path.join(st.session_state.path, nombre)
            st.rerun()
    if ftype in ['.m4a', '.mp4', '.mp3']:
        # with st.container(border=True):
        st.audio(os.path.join(st.session_state.path, nombre))
        # Define regions
        regions = [
            Region(start=0, end=5, content="Intro"),
            Region(start=5, end=10, content="Verse"),
        ]
        # Display the waveform
        wavesurfer(
            audio_src=os.path.join(st.session_state.path, nombre),
            regions=regions,
            plugins=[
                # "regions", 
                # "timeline", 
                # "zoom"
            ],  # Enable desired plugins
            show_controls=False,
            wave_options={
                "waveColor": "#9aa0a6",
                "progressColor": "#1db954",
                "barWidth": 2,
                "barGap": 1,
                "barRadius": 2,
                "height": 120,
            }
        )