"""Lectura Documentos Forus: Comex, Contabilidad y Recursos Humanos.

Este archivo es solo el arranque: configura la pagina, pide el acceso y decide
que pantalla mostrar. La logica de cada area vive en modules/.
"""
import streamlit as st

from forus_auth import current_user_modules, require_login
from forus_ui import inject_css, render_sidebar_header
from modules import arriendos, comex, contabilidad

st.set_page_config(
    page_title="Lectura Documentos Forus",
    page_icon="PDF",
    layout="wide",
)

inject_css()

require_login()

# Cada destino es un sitio al que se llega en un solo paso desde el desplegable.
# El primer campo es el modulo que da permiso para verlo.
DESTINOS = [
    ("comex", "Comex", comex.render_sidebar, comex.render),
    ("contabilidad", "Contabilidad - Pagos", contabilidad.render_sidebar_pagos, contabilidad.render_pagos),
    ("contabilidad", "Contabilidad - Costos", contabilidad.render_sidebar_costos, contabilidad.render_costos),
    ("rrhh", "Recursos Humanos - Arriendos", arriendos.render_sidebar, arriendos.render),
]

render_sidebar_header()

modulos_permitidos = current_user_modules()
destinos = [destino for destino in DESTINOS if destino[0] in modulos_permitidos]

if not destinos:
    st.error("Tu usuario no tiene ningun modulo asignado. Avisa al administrador del portal.")
    st.stop()

etiquetas = [etiqueta for _, etiqueta, _, _ in destinos]

with st.sidebar:
    st.markdown('<div class="side-nav-title">Sitio destino</div>', unsafe_allow_html=True)

    if len(etiquetas) == 1:
        etiqueta_activa = etiquetas[0]
        st.markdown(f'<div class="side-card">{etiqueta_activa}</div>', unsafe_allow_html=True)
    else:
        if st.session_state.get("destino_activo") not in etiquetas:
            st.session_state["destino_activo"] = etiquetas[0]
        etiqueta_activa = st.selectbox(
            "Sitio destino",
            etiquetas,
            key="destino_activo",
            label_visibility="collapsed",
        )

_, _, render_panel_lateral, render_pantalla = next(
    destino for destino in destinos if destino[1] == etiqueta_activa
)
render_panel_lateral()
render_pantalla()
