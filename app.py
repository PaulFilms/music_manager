import streamlit as st
import pandas as pd
from pathlib import Path
from tinytag import TinyTag



st.set_page_config(
    page_title="MUSIC MAKER",
    page_icon="🧊",
    layout="wide", # "wide", "centered"
    initial_sidebar_state="auto",
    # menu_items={
    #     'Get Help': 'https://www.extremelycoolapp.com/help',
    #     'Report a bug': "https://www.extremelycoolapp.com/bug",
    #     'About': "# This is a header. This is an *extremely* cool app!"
    # }
)

st.title('MUSIC MANAGER')

st.text('')

# col1, col2 = st.columns([1,9])

# with col1:
st.image(
    r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fstatic.vecteezy.com%2Fsystem%2Fresources%2Fpreviews%2F009%2F346%2F267%2Foriginal%2F3d-render-icon-yellow-folder-illustration-free-png.png&f=1&nofb=1&ipt=6673e80b08edcd684d1f4a84e4ca57e2fc646404d5017bd0a1e2453f04f72b71',
    width=50
)
# with col2:
#     st.write('LOCAL FILES')


# st.image(
#     r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fwww.pngarts.com%2Ffiles%2F8%2FApple-Music-Logo-PNG-Photo.png&f=1&nofb=1&ipt=e1b53e796e2f7e19a300a29fe5d05a076a8641f06b7a52514f1cc8da7962234b',
#     width=100
# )

# st.image(
#     r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fpnghq.com%2Fwp-content%2Fuploads%2F2023%2F02%2Flisten-on-tidal-logo-png-4767.png&f=1&nofb=1&ipt=cd43ce191bf041ba3137387c9906f9bf881d342a2726fc6df28259bec9903276',
#     width=100
# )

# st.image(
# r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fstatic.vecteezy.com%2Fsystem%2Fresources%2Fpreviews%2F018%2F930%2F640%2Fnon_2x%2Fspotify-app-logo-spotify-icon-transparent-free-png.png&f=1&nofb=1&ipt=a0db9575f2b57558d02f9bbf8f2b4572f0d4e665b610ceefc80517871009c929',
#     width=100
# )

path_souce = st.text_input(
    'SOURCE PATH 🔗',
    value=r'/Users/mbair/Desktop/[MUSIC CONSOLIDED]'
    )

if path_souce:
    path = Path(path_souce)
    playlist = [folder for folder in path.rglob('*') if folder.is_dir()]
    playlist.insert(0, 'All ...')
    obj = st.dataframe(
        playlist,
        hide_index=True,
        selection_mode='single-row',
        on_select='rerun'
    )

    folder = path_souce

    if obj.selection['rows'] and obj.selection['rows'][0] > 0:
        # st.write(obj.selection)
        row = obj.selection['rows'][0]
        folder = playlist[row]
        st.write(folder)
    
    if st.button('READ PATH'):
        # row = 0
        # df = pd.DataFrame(None)
        lista = []
        for file in Path(folder).rglob('*'):
            if file.is_file() and file.suffix in TinyTag.SUPPORTED_FILE_EXTENSIONS:
                tag = TinyTag.get(file)
                # st.write(tag)
                # df.iloc[row] = tag.as_dict()
                # row += 1
                # tag_fields = tag.as_dict()
                # tag_fields['bpm'] = tag.other.bpm
                # other_fields = tag.other
                # catalog_numbers: list[str] | None = other_fields.get('catalog_number')
                # st.write(other_fields)
                st.write(tag.other.get('BPM'))
                lista.append(tag.as_dict())
        # df = pd.DataFrame(lista)
        st.dataframe(
            lista
        )
        st.text(f'Tracks: {len(lista)}')
