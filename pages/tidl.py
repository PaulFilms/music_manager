import streamlit as st

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
