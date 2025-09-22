# MUSIC MANAGER

Quiero hacer un software de gestion de playlist y organización de ficheros de musica locales.
Incluyendo plataformas como Apple Music, Spotify, Tidal, y archivos locales


Librerias y herramientas usadas:

- [TINYTAG](https://github.com/tinytag/tinytag.git)
- [GAMDL](https://github.com/glomatico/gamdl.git)
- [FFMPEG](https://ffmpeg.org/)

Para instalar FFmpeg lo mas recomendable hasta el momento es:

```bash
brew install ffmpeg
```

Formato avanzado de tablas para Streamlit:

[streamlit-aggrid (Git)](https://github.com/PablocFonseca/streamlit-aggrid?tab=readme-ov-file)

## TAREAS
 - Añadir con appl el control de duplicados (el codigo esta en el jupyter)
 - No descarga appl videos
 - ChatGPT:

para poder mostrar el proceso lo tengo con with:

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
                    # output = ""
                    # for line in proc.stdout:
                    #     output += line
                    #     # output_area.text(output)  # Actualiza la salida progresivamente
                    #     output_area.text_area("Salida:", output, height=300)

                    # proc.wait()

                    lines = []
                    for line in proc.stdout:
                        lines.append(line.rstrip())
                        # Mantener solo las últimas 5 líneas
                        if len(lines) > 5:
                            lines = lines[-5:]
                        output_area.text_area("Salida:", "\n".join(lines), height=300)

                    proc.wait()

como puedo incluir el boton de stop
ChatGPT Plus
Perfecto, tu implementación es clara y eficiente para mostrar la salida en tiempo real. Para añadir un botón de "Stop" (⏹️) en este flujo, necesitas mover la ejecución del proceso a un hilo separado, porque Streamlit no puede escuchar eventos (como botones) mientras está bloqueado dentro de Popen.
✅ Objetivo: Ejecutar el proceso en segundo plano y detenerlo con un botón
🧠 ¿Por qué necesitas un hilo?
Mientras estás dentro de for line in proc.stdout, Streamlit no puede escuchar eventos como st.button("⏹️ Detener"), porque el script está bloqueado esperando líneas del proceso.
Al usar threading, puedes mantener el proceso activo en segundo plano y seguir interactuando con la interfaz.
✅ Solución completa con threading y botón de parada
import streamlit as st
import subprocess
import threading
import time
from pathlib import Path

# Inicialización de estados
if "process" not in st.session_state:
    st.session_state.process = None
if "process_output" not in st.session_state:
    st.session_state.process_output = []
if "running" not in st.session_state:
    st.session_state.running = False

# Función para ejecutar el proceso en segundo plano
def run_process(url):
    comando = ["gamdl", url]
    st.session_state.process = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
    )
    st.session_state.running = True
    output_lines = []

    for line in st.session_state.process.stdout:
        if not st.session_state.running:
            break
        output_lines.append(line.strip())
        if len(output_lines) > 10:
            output_lines = output_lines[-10:]
        st.session_state.process_output = output_lines
        time.sleep(0.1)  # permite refresco sin sobrecarga

    st.session_state.running = False
    st.session_state.process = None

# UI
st.title("🎵 Descargar desde Apple Music")

url_appl = st.text_input("URL de Apple Music")

col1, col2 = st.columns(2)

with col1:
    if st.button("▶️ Iniciar", use_container_width=True) and url_appl:
        if not st.session_state.running:
            threading.Thread(target=run_process, args=(url_appl,), daemon=True).start()

with col2:
    if st.button("⏹️ Detener", use_container_width=True):
        if st.session_state.process and st.session_state.running:
            st.session_state.running = False
            st.session_state.process.terminate()
            st.session_state.process = None
            st.success("Proceso detenido.")

# Mostrar salida
if st.session_state.process_output:
    st.text_area("Salida:", "\n".join(st.session_state.process_output), height=300)
elif st.session_state.running:
    st.info("⏳ Ejecutando proceso...")
✅ Qué hace este código
Lanza gamdl en un hilo separado.
Muestra las últimas 10 líneas de salida en un text_area.
Permite detener el proceso usando el botón "⏹️ Detener", sin bloquear la UI.
Usa st.session_state para controlar el estado entre recargas.
⚠️ Requisitos
gamdl debe estar disponible en el entorno del servidor.
No se recomienda en Streamlit Cloud (por políticas de ejecución de subprocessos), pero funciona perfectamente en local. 