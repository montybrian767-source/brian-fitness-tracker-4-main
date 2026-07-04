import streamlit as st


def exercise_photo(photo_html, width="100%", height=320, key=None):
    """Render an exercise photo HTML blob with a responsive container and aspect ratio.

    photo_html should be an <img> tag or fallback HTML (already base64-embedded by `img_tag`).
    """
    if not photo_html:
        st.write("No image")
        return
    style = f"width:{width};height:{height}px;display:flex;align-items:center;justify-content:center;overflow:hidden;border-radius:12px;"
    st.markdown(f'<div class="exercise-photo-wrap" style="{style}">{photo_html}</div>', unsafe_allow_html=True)
