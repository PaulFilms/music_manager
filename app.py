import streamlit as st



st.set_page_config(
    page_title="MUSIC MAKER",
    page_icon="🧊",
    layout="centered", # "wide",
    initial_sidebar_state="auto",
    # menu_items={
    #     'Get Help': 'https://www.extremelycoolapp.com/help',
    #     'Report a bug': "https://www.extremelycoolapp.com/bug",
    #     'About': "# This is a header. This is an *extremely* cool app!"
    # }
)

st.title('MUSIC MANAGER')

st.text('')

st.image(
    r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fwww.pngarts.com%2Ffiles%2F8%2FApple-Music-Logo-PNG-Photo.png&f=1&nofb=1&ipt=e1b53e796e2f7e19a300a29fe5d05a076a8641f06b7a52514f1cc8da7962234b',
    width=100
)



st.image(
    r'https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fpnghq.com%2Fwp-content%2Fuploads%2F2023%2F02%2Flisten-on-tidal-logo-png-4767.png&f=1&nofb=1&ipt=cd43ce191bf041ba3137387c9906f9bf881d342a2726fc6df28259bec9903276',
    width=100
)

with st.expander('TIDL', expanded=False):

    url_tidl = st.text_input(
        "URL 🔗",
        label_visibility='visible',
        # disabled=st.session_state.disabled,
        # placeholder=st.session_state.placeholder,
        key = 'url_tidl'
    )