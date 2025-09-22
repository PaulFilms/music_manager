import os
import subprocess
import re
import tempfile
import librosa
import pandas as pd
import numpy as np
import librosa.display
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from functions import common_formats, get_waveform, get_audio_properties

## BUG: Manejar con el browser
if os.path.exists('temp') is False:
    os.mkdir('temp')

def convert_file(input_file: str, output_format: str, output_file: str):
    # Elimina el punto si existe
    fmt = output_format.lstrip('.')
    cmd = [
        "ffmpeg",
        "-i", input_file,
        "-f", fmt,
        output_file
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during conversion: {e}")
        return False

## PAGE
import streamlit as st

st.cache_resource()
def get_ffmpeg_formats():
    result = subprocess.run(
        ["ffmpeg", "-formats"],
        capture_output=True,
        text=True
    )

    lines = result.stdout.splitlines()
    inputs = set()
    outputs = set()

    for line in lines:
        if len(line) < 5:
            continue

        flags = line[0:3].strip()
        parts = line.split()
        if len(parts) < 2:
            continue

        fmt = parts[1]

        if "D" in flags:
            inputs.add(fmt)
        if "E" in flags:
            outputs.add(fmt)

    return sorted(inputs), sorted(outputs)

common_formats = ['.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus']

with st.sidebar:
    waveform = st.checkbox('Waveform', value=False, disabled=False)

st.subheader('SELECT FILE', divider='orange')

uploaded_file = st.file_uploader(
    'CHOOSE AN AUDIO FILE',
    # type=get_ffmpeg_formats()[0],
    type=common_formats,
    accept_multiple_files=False
)
if uploaded_file:

    st.subheader('SONG', divider='orange')

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
        tmp_file.write(uploaded_file.read())
        temp_path = tmp_file.name

    # # Cargar audio
    # y, sr = librosa.load(temp_path, sr=None, mono=True)

    # # Número de "barras"
    # num_windows = 1000
    # hop_length = len(y) // num_windows

    # # Calcular solo máximos (parte positiva de la señal)
    # envelope = []
    # for i in range(num_windows):
    #     start = i * hop_length
    #     end = start + hop_length
    #     segment = y[start:end]
    #     if len(segment) > 0:
    #         envelope.append(segment.max())

    # envelope = np.array(envelope)
    # times = np.linspace(0, len(y)/sr, num_windows)

    # # Crear figura Plotly
    # fig = go.Figure()

    # # Forma de onda positiva en amarillo
    # fig.add_trace(go.Scatter(
    #     x=np.concatenate([times, times[::-1]]),
    #     y=np.concatenate([np.zeros_like(envelope), envelope[::-1]]),  # desde 0 hasta max
    #     fill="toself",
    #     line=dict(color="yellow"),
    #     fillcolor="yellow",
    #     hoverinfo="skip",
    #     showlegend=False
    # ))

    # # Configuración limpia y altura fija (100px)
    # fig.update_layout(
    #     xaxis=dict(visible=False),
    #     yaxis=dict(visible=False),
    #     margin=dict(l=0, r=0, t=0, b=0),
    #     plot_bgcolor="rgba(0,0,0,0)",
    #     paper_bgcolor="rgba(0,0,0,0)",
    #     dragmode=False,
    #     height=100  # altura de 100px
    # )

    with st.container(border=True):
        # Render en Streamlit
        if waveform:
            get_waveform(temp_path)

        # Reproductor
        st.audio(uploaded_file)

    col1, col2 = st.columns(2)
    output_format = col2.selectbox(
        'Select Format',
        # options=get_ffmpeg_formats()[1],
        options=common_formats,
        index=0,
        key='format_select',
        label_visibility='collapsed'
    )
    if col1.button('Process File', use_container_width=True):
        input_file = uploaded_file.name
        output_file = f"{input_file.rsplit('.', 1)[0]}{output_format}"
        output_file = os.path.join('temp', output_file)

        # st.write(uploaded_file)
        # st.write(f"Input File: {input_file}")
        # st.write(f"Output File: {output_file}")
        # st.write(f"Archivo guardado temporalmente en: {temp_path}")

        if convert_file(temp_path, output_format, output_file):
            st.success(f"File converted successfully to {output_file}")
        else:
            st.error("Error during file conversion")