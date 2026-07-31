"""Estilos y piezas de interfaz compartidas por todos los modulos Forus."""
import base64
import html
from pathlib import Path

import streamlit as st


LOGO_PATH = Path("forus_logo_web.png")

def format_file_size(size_bytes):
    if size_bytes is None:
        return "PDF"
    mb = size_bytes / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB"
    return f"{size_bytes / 1024:.0f} KB"

def image_to_base64(path):
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode("utf-8")

def render_sidebar_header():
    """Logo, sesion activa y boton de salida. Igual para los tres modulos."""
    with st.sidebar:
        logo_base64 = image_to_base64(LOGO_PATH)
        if logo_base64:
            st.markdown(
                f'''
                <div class="side-logo">
                    <img src="data:image/png;base64,{logo_base64}" alt="Forus">
                </div>
                ''',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="side-logo">
                    <div style="font-size:2rem;font-weight:900;color:#082477;letter-spacing:.08em">FORUS</div>
                    <div style="font-size:.62rem;color:#082477;letter-spacing:.32em">CONSUMER FANATIC</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(f'<div class="user-chip">Sesion: {html.escape(st.session_state.get("auth_user", ""))}</div>', unsafe_allow_html=True)
        if st.button("Cerrar sesion"):
            st.session_state.pop("auth_ok", None)
            st.session_state.pop("auth_user", None)
            st.rerun()


GLOBAL_CSS = """
    <style>
    :root {
        --forus-blue: #082477;
        --forus-blue-2: #0b48d8;
        --forus-cyan: #14a8e8;
        --ink: #061938;
        --muted: #526484;
        --line: #d5e2f3;
        --panel: #ffffff;
        --soft: #f3f7fc;
        --good: #16a765;
        --warn: #df9800;
    }

    .stApp {
        background:
            radial-gradient(circle at 86% 4%, rgba(20,168,232,0.13), transparent 28%),
            linear-gradient(135deg, #eef4fb 0%, #f8fbff 45%, #ffffff 100%);
        color: var(--ink);
    }


    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    #MainMenu,
    footer {
        display: none !important;
        visibility: hidden !important;
    }
    .block-container {
        padding-top: 0.9rem;
        padding-bottom: 2.6rem;
        max-width: 1220px;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #eaf1f9 0%, #f6f9fd 100%);
        border-right: 1px solid #cfdbeb;
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 0.75rem;
    }

    [data-testid="stSidebarHeader"],
    [data-testid="stSidebarCollapseButton"],
    button[title="Collapse sidebar"],
    button[aria-label="Close sidebar"],
    button[aria-label="Open sidebar"] {
        display: none !important;
    }

    section[data-testid="stSidebar"] {
        min-width: 260px !important;
        width: 260px !important;
    }

    .side-logo {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.75rem 0.8rem;
        box-shadow: 0 16px 36px rgba(8,36,119,0.10);
        margin: 0 0 1.15rem;
    }

    .side-title {
        color: var(--ink);
        font-weight: 850;
        font-size: 0.84rem;
        margin: 0.95rem 0 0.45rem;
    }

    .side-logo img {
        display: block;
        width: 100%;
        max-height: 92px;
        object-fit: contain;
    }

    .side-card {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 14px 30px rgba(8,36,119,0.08);
        color: var(--forus-blue);
        font-weight: 850;
        line-height: 1.9;
        font-size: 0.82rem;
        margin-bottom: 1rem;
    }

    .side-note {
        background: #e8f8ef;
        color: #075329;
        border-radius: 8px;
        padding: 0.95rem;
        font-size: 0.86rem;
        line-height: 1.55;
        border: 1px solid #c6efd6;
    }

    .app-shell {
        display: flex;
        flex-direction: column;
        gap: 1.3rem;
    }

    .hero-card {
        background: rgba(255,255,255,0.93);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1.9rem 2rem;
        display: grid;
        grid-template-columns: 1fr 280px;
        gap: 1.4rem;
        align-items: center;
        box-shadow: 0 18px 50px rgba(8,36,119,0.07);
    }

    .eyebrow {
        color: #0077db;
        font-size: 0.72rem;
        font-weight: 850;
        letter-spacing: 0.42em;
        text-transform: uppercase;
        margin-bottom: 0.9rem;
    }

    .hero-card h1 {
        margin: 0;
        color: var(--ink);
        font-size: 2.05rem;
        line-height: 1.12;
        letter-spacing: 0;
    }

    .hero-card p {
        color: var(--muted);
        margin: 1rem 0 0;
        line-height: 1.65;
        font-size: 0.98rem;
    }

    .hero-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 0.7rem;
        justify-content: flex-end;
        align-items: center;
    }

    .tag {
        border-radius: 999px;
        padding: 0.55rem 0.9rem;
        border: 1px solid #bcd8ff;
        background: #edf6ff;
        color: var(--forus-blue);
        font-weight: 850;
        font-size: 0.76rem;
    }

    .tag.green {
        border-color: #a6e7bf;
        background: #e9faef;
        color: #077a37;
    }

    .pdf-symbol {
        width: 92px;
        height: 92px;
        border-radius: 8px;
        background: linear-gradient(135deg, #ffffff, #e7f1ff);
        border: 1px solid var(--line);
        display: grid;
        place-items: center;
        box-shadow: 0 18px 42px rgba(8,36,119,0.12);
    }

    .pipeline {
        background: rgba(255,255,255,0.94);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1.1rem;
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.85rem;
        box-shadow: 0 18px 45px rgba(8,36,119,0.07);
    }

    .step-card {
        border: 1px solid var(--line);
        background: #f9fbfe;
        border-radius: 8px;
        padding: 1rem;
        display: grid;
        grid-template-columns: 44px 1fr auto;
        gap: 0.85rem;
        align-items: center;
        min-height: 88px;
    }

    .step-card.active {
        background: #edf6ff;
        border-color: #8dbdff;
    }

    .step-card.ok {
        background: #f0fbf5;
        border-color: #aee8c2;
    }

    .step-card.warn {
        background: #fff8e9;
        border-color: #ffd37e;
    }

    .step-number {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #ffffff;
        color: #006fe8;
        display: grid;
        place-items: center;
        font-weight: 900;
        box-shadow: 0 10px 26px rgba(8,36,119,0.08);
    }

    .step-title {
        font-weight: 900;
        color: var(--ink);
        margin-bottom: 0.2rem;
    }

    .step-sub {
        color: var(--muted);
        font-size: 0.78rem;
    }

    .pill {
        border-radius: 999px;
        padding: 0.35rem 0.6rem;
        font-weight: 850;
        font-size: 0.72rem;
        border: 1px solid #a9caff;
        background: #edf4ff;
        color: #0754c8;
    }

    .pill.ok {
        border-color: #9ee2b7;
        background: #eaf9ef;
        color: #08743a;
    }

    .pill.warn {
        border-color: #ffc566;
        background: #fff3d3;
        color: #9a6500;
    }

    .work-card {
        background: rgba(255,255,255,0.94);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1.55rem;
        box-shadow: 0 18px 45px rgba(8,36,119,0.07);
        margin-bottom: 1.2rem;
    }

    .work-card h2, .work-card h3 {
        color: var(--ink);
        margin-top: 0;
        letter-spacing: 0;
    }

    .work-card p {
        color: var(--muted);
        line-height: 1.6;
    }

    .rules-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.8rem;
        margin-top: 1.1rem;
    }

    .rule-chip {
        border-radius: 8px;
        border: 1px solid #acd0ff;
        background: #eef6ff;
        padding: 0.95rem 1rem;
    }

    .rule-chip b {
        color: var(--forus-blue);
        display: block;
        margin-bottom: 0.4rem;
    }

    .upload-wrap div[data-testid="stFileUploader"] {
        border: 1px dashed #9fc2f3;
        background: #fbfdff;
        border-radius: 8px;
        padding: 1.15rem;
    }

    div[data-testid="stFileUploader"] section {
        border: 0;
        background: transparent;
    }


    .upload-wrap div[data-testid="stFileUploader"] button {
        background: linear-gradient(90deg, #082477, #0b48d8) !important;
        color: transparent !important;
        border: 0 !important;
        border-radius: 8px !important;
        min-height: 42px;
        min-width: 155px;
        box-shadow: 0 12px 26px rgba(8,36,119,0.20);
        position: relative;
    }

    .upload-wrap div[data-testid="stFileUploader"] button::after {
        content: "Sube tu factura";
        color: #ffffff;
        font-weight: 850;
        font-size: 0.88rem;
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
    }

    .upload-wrap div[data-testid="stFileUploader"] small,
    .upload-wrap div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] {
        color: var(--muted) !important;
    }
    .stButton button, .stDownloadButton button {
        background: linear-gradient(90deg, #082477, #0b48d8);
        color: #ffffff;
        border: 0;
        border-radius: 8px;
        padding: 0.72rem 1.15rem;
        font-weight: 850;
        box-shadow: 0 12px 26px rgba(8,36,119,0.20);
    }

    .stButton button:hover, .stDownloadButton button:hover {
        color: #ffffff;
        border: 0;
        filter: brightness(1.06);
    }

    .stButton button:disabled {
        opacity: 0.45;
        box-shadow: none;
    }

    div[data-testid="stMetric"] {
        background: #f7faff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.85rem;
    }

    .benefits {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.9rem;
        margin-top: 1.2rem;
    }

    .benefit {
        background: rgba(255,255,255,0.94);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 14px 34px rgba(8,36,119,0.06);
    }

    .benefit b {
        color: var(--ink);
    }

    .benefit p {
        margin: 0.35rem 0 0;
        color: var(--muted);
        font-size: 0.88rem;
        line-height: 1.5;
    }


    .section-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .section-head h3 {
        margin: 0;
    }

    .section-kicker {
        color: #0077db;
        font-size: 0.72rem;
        font-weight: 900;
        letter-spacing: 0.18em;
        text-transform: uppercase;
    }

    .stat-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.85rem;
        margin: 0.9rem 0 1rem;
    }

    .stat-card {
        background: linear-gradient(145deg, #ffffff 0%, #f4f8ff 100%);
        border: 1px solid #cfe0f5;
        border-radius: 8px;
        padding: 1rem;
        min-height: 96px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .stat-label {
        color: var(--muted);
        font-size: 0.8rem;
        font-weight: 750;
    }

    .stat-value {
        color: var(--ink);
        font-size: 2rem;
        font-weight: 900;
        line-height: 1;
    }

    .file-list {
        display: flex;
        flex-direction: column;
        gap: 0.65rem;
        margin-top: 0.9rem;
    }

    .file-row {
        display: grid;
        grid-template-columns: 42px 1fr auto auto;
        gap: 0.85rem;
        align-items: center;
        background: #ffffff;
        border: 1px solid #d7e4f3;
        border-radius: 8px;
        padding: 0.8rem 0.9rem;
        box-shadow: 0 10px 24px rgba(8,36,119,0.05);
    }

    .file-icon {
        width: 38px;
        height: 38px;
        border-radius: 8px;
        background: linear-gradient(135deg, #082477, #0b48d8);
        color: #ffffff;
        display: grid;
        place-items: center;
        font-weight: 900;
        font-size: 0.72rem;
    }

    .file-name {
        color: var(--ink);
        font-weight: 850;
        overflow-wrap: anywhere;
    }

    .file-meta {
        color: var(--muted);
        font-size: 0.78rem;
        margin-top: 0.15rem;
    }

    .brand-badge, .status-badge {
        border-radius: 999px;
        padding: 0.42rem 0.7rem;
        font-size: 0.72rem;
        font-weight: 900;
        white-space: nowrap;
    }

    .brand-badge {
        background: #edf6ff;
        border: 1px solid #b9d7ff;
        color: #0754c8;
    }

    .status-badge {
        background: #eaf9ef;
        border: 1px solid #a6e7bf;
        color: #08743a;
    }

    .empty-state {
        border: 1px dashed #bcd2ee;
        background: #f9fcff;
        border-radius: 8px;
        padding: 1.2rem;
        color: var(--muted);
    }

    .action-card {
        background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1.2rem;
        margin-top: 0.7rem;
    }

    .result-banner {
        margin: 1rem 0;
        background: linear-gradient(90deg, #e7f8ee, #f3fff8);
        border: 1px solid #bcebd0;
        color: #076735;
        border-radius: 8px;
        padding: 1rem 1.1rem;
        font-weight: 850;
    }

    .result-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.9rem;
        margin: 0.9rem 0 1rem;
    }

    .result-card {
        background: #ffffff;
        border: 1px solid #cfe0f5;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 12px 28px rgba(8,36,119,0.06);
    }

    .result-card span {
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 750;
    }

    .result-card strong {
        display: block;
        margin-top: 0.4rem;
        color: var(--ink);
        font-size: 2.15rem;
        line-height: 1;
    }




    .login-shell {
        width: 448px;
        max-width: 100%;
        margin: 0 auto;
        background: #ffffff;
        border-radius: 8px 8px 0 0;
        overflow: hidden;
        box-shadow: 0 26px 70px rgba(0,0,0,0.22);
    }

    .login-hero {
        background: linear-gradient(135deg, #2d6bff 0%, #0f53f5 100%);
        padding: 2rem 1.8rem 2.2rem;
        text-align: center;
        color: #ffffff;
    }

    .login-hero .login-logo {
        width: 180px;
        margin: 0 auto 1.55rem;
        background: #ffffff;
        border: 0;
        border-radius: 8px;
        padding: 0.55rem 0.8rem;
        box-shadow: none;
    }

    .login-hero .login-logo img {
        display: block;
        width: 100%;
        height: auto;
    }

    .login-title {
        font-size: 1.75rem;
        font-weight: 950;
        letter-spacing: 0;
        line-height: 1.16;
    }

    .login-subtitle {
        margin-top: 0.75rem;
        font-size: 0.95rem;
        font-weight: 850;
        color: #eaf2ff;
    }

    .login-footer {
        width: 448px;
        max-width: 100%;
        margin: 1.6rem auto 0;
        text-align: center;
        color: #eaf2ff;
        font-weight: 850;
        font-size: 0.82rem;
        line-height: 1.8;
    }

    .login-wrap {
        min-height: 72vh;
        display: grid;
        place-items: center;
        padding: 2rem 1rem 0;
    }

    .login-card {
        width: min(520px, 100%);
        background: rgba(255,255,255,0.96);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 2rem;
        box-shadow: 0 28px 70px rgba(8,36,119,0.12);
        text-align: left;
    }

    .login-logo {
        width: 220px;
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.75rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 12px 26px rgba(8,36,119,0.08);
    }

    .login-logo img {
        width: 100%;
        display: block;
    }

    .login-logo-text {
        color: var(--forus-blue);
        font-size: 2rem;
        font-weight: 900;
        letter-spacing: 0.08em;
    }

    .login-logo-sub {
        color: var(--forus-blue);
        font-size: 0.58rem;
        letter-spacing: 0.28em;
    }

    .login-card h1 {
        margin: 0.35rem 0 0.6rem;
        color: var(--ink);
        font-size: 2rem;
        letter-spacing: 0;
    }

    .login-card p {
        color: var(--muted);
        line-height: 1.6;
        margin-bottom: 0;
    }

    div[data-testid="stForm"] {
        max-width: 520px;
        margin: -1rem auto 0;
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1.4rem;
        box-shadow: 0 18px 45px rgba(8,36,119,0.08);
    }

    div[data-testid="stForm"] button {
        width: 100%;
        background: linear-gradient(90deg, #082477, #0b48d8) !important;
        color: #ffffff !important;
        border: 0 !important;
        border-radius: 8px !important;
        min-height: 44px;
        font-weight: 900;
    }

    .user-chip {
        background: #eef6ff;
        border: 1px solid #bdd7ff;
        color: var(--forus-blue);
        border-radius: 8px;
        padding: 0.7rem 0.8rem;
        font-size: 0.78rem;
        font-weight: 850;
        overflow-wrap: anywhere;
        margin-bottom: 0.8rem;
    }



    /* Modern Comex UI polish */
    .stApp {
        background:
            radial-gradient(circle at 83% 8%, rgba(20,168,232,0.20), transparent 30%),
            radial-gradient(circle at 12% 18%, rgba(11,72,216,0.10), transparent 28%),
            linear-gradient(135deg, #f4f8fd 0%, #ffffff 48%, #eef6ff 100%);
    }

    .block-container {
        max-width: 1160px;
        padding-top: 1rem;
    }

    .app-shell {
        gap: 1rem;
    }

    .hero-card {
        position: relative;
        overflow: hidden;
        background:
            radial-gradient(circle at 84% 34%, rgba(20,168,232,0.34), transparent 26%),
            linear-gradient(135deg, #061938 0%, #082477 54%, #0b48d8 100%);
        border: 0;
        color: #ffffff;
        padding: 2rem 2.15rem;
        min-height: 230px;
        box-shadow: 0 28px 70px rgba(8,36,119,0.20);
    }

    .hero-card::after {
        content: "";
        position: absolute;
        inset: auto -70px -115px auto;
        width: 280px;
        height: 280px;
        border: 1px solid rgba(255,255,255,0.18);
        border-radius: 50%;
        background: rgba(255,255,255,0.05);
    }

    .hero-card > div {
        position: relative;
        z-index: 1;
    }

    .hero-card .eyebrow {
        color: #82d9ff;
        font-size: 0.7rem;
        letter-spacing: 0.34em;
        margin-bottom: 0.9rem;
    }

    .hero-card h1 {
        color: #ffffff;
        font-size: clamp(2rem, 3vw, 3rem);
        max-width: 760px;
    }

    .hero-card p {
        color: #dceaff;
        font-size: 1.02rem;
        max-width: 660px;
    }

    .hero-tags {
        align-self: stretch;
        justify-content: center;
        flex-direction: column;
    }

    .hero-tags .tag {
        background: rgba(255,255,255,0.13);
        border-color: rgba(255,255,255,0.28);
        color: #ffffff;
        backdrop-filter: blur(8px);
    }

    .hero-tags .tag.green {
        background: rgba(234,249,239,0.16);
        border-color: rgba(166,231,191,0.45);
        color: #e9fff1;
    }

    .pdf-symbol {
        width: 118px;
        height: 118px;
        background: rgba(255,255,255,0.14);
        border-color: rgba(255,255,255,0.24);
        box-shadow: 0 24px 60px rgba(0,0,0,0.22);
        backdrop-filter: blur(10px);
    }

    .pdf-symbol svg {
        transform: scale(1.08);
    }

    .pipeline {
        margin-top: -1.7rem;
        position: relative;
        z-index: 2;
        background: rgba(255,255,255,0.86);
        backdrop-filter: blur(14px);
        border-color: rgba(189,215,255,0.78);
        box-shadow: 0 22px 55px rgba(8,36,119,0.12);
    }

    .step-card {
        min-height: 86px;
        background: rgba(255,255,255,0.92);
        border-color: #d8e6f8;
        box-shadow: 0 10px 24px rgba(8,36,119,0.05);
    }

    .step-card.active {
        background: linear-gradient(135deg, #eaf4ff, #ffffff);
        border-color: #76adff;
    }

    .step-card.ok {
        background: linear-gradient(135deg, #eaf9ef, #ffffff);
        border-color: #9ee2b7;
    }

    .step-card.warn {
        background: linear-gradient(135deg, #fff4d8, #ffffff);
        border-color: #ffc566;
    }

    .work-card {
        background: rgba(255,255,255,0.92);
        border-color: rgba(203,219,242,0.90);
        box-shadow: 0 20px 56px rgba(8,36,119,0.08);
    }

    .work-card h2 {
        font-size: 2rem;
        margin-bottom: 0.35rem;
    }

    .rules-grid {
        gap: 0.9rem;
    }

    .rule-chip {
        min-height: 92px;
        background: linear-gradient(145deg, #ffffff, #eef6ff);
        border-color: #bdd7ff;
        box-shadow: 0 12px 28px rgba(8,36,119,0.06);
        position: relative;
        overflow: hidden;
    }

    .rule-chip::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #082477, #14a8e8);
    }

    .upload-wrap {
        background:
            linear-gradient(135deg, rgba(8,36,119,0.96), rgba(11,72,216,0.92)),
            #082477;
        border: 0;
        color: #ffffff;
        box-shadow: 0 26px 70px rgba(8,36,119,0.20);
    }

    .upload-wrap h3 {
        color: #ffffff;
        font-size: 1.45rem;
        margin-bottom: 0.8rem;
    }

    .upload-wrap h3::after {
        content: "Arrastra o selecciona tus facturas comerciales";
        display: block;
        margin-top: 0.45rem;
        color: #cfe2ff;
        font-size: 0.92rem;
        font-weight: 600;
    }

    .upload-wrap div[data-testid="stFileUploader"] {
        min-height: 132px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px dashed rgba(255,255,255,0.48);
        background: rgba(255,255,255,0.10);
        border-radius: 8px;
    }

    .upload-wrap div[data-testid="stFileUploader"] section {
        color: #ffffff;
    }

    .upload-wrap div[data-testid="stFileUploader"] button {
        min-width: 190px;
        min-height: 48px;
        background: #ffffff !important;
        box-shadow: 0 18px 38px rgba(0,0,0,0.18);
    }

    .upload-wrap div[data-testid="stFileUploader"] button::after {
        content: "Sube tu factura";
        color: #082477;
        font-size: 0.94rem;
    }

    .section-head h3 {
        font-size: 1.55rem;
    }

    .empty-state {
        background: linear-gradient(145deg, #ffffff, #f3f8ff);
        border-color: #b9d7ff;
        min-height: 72px;
        display: flex;
        align-items: center;
    }

    .stat-card, .file-row, .result-card, .benefit {
        box-shadow: 0 16px 36px rgba(8,36,119,0.07);
    }

    .benefit {
        min-height: 116px;
        background: linear-gradient(145deg, #ffffff, #f7fbff);
    }

    .benefit b {
        display: block;
        font-size: 0.98rem;
        margin-bottom: 0.35rem;
    }

    @media (max-width: 980px) {
        .hero-card, .pipeline, .rules-grid, .benefits, .stat-grid, .result-grid {
            grid-template-columns: 1fr;
        }
        .hero-tags {
            justify-content: flex-start;
        }
    }
    </style>
    """


# CSS anadido para la navegacion entre modulos y los acentos de color por area.
# Ojo: es una cadena normal, no un f-string. Las llaves van simples.
MODULES_CSS = """
<style>
.side-nav-title {
    color: #061938;
    font-weight: 850;
    font-size: 0.84rem;
    margin: 0.35rem 0 0.55rem;
}

section[data-testid="stSidebar"] div[role="radiogroup"] {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
}

section[data-testid="stSidebar"] div[role="radiogroup"] > label {
    background: #ffffff;
    border: 1px solid #d5e2f3;
    border-radius: 8px;
    padding: 0.6rem 0.7rem;
    margin: 0;
    box-shadow: 0 8px 20px rgba(8,36,119,0.05);
    transition: border-color .15s ease, box-shadow .15s ease;
}

section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
    border-color: #8dbdff;
    box-shadow: 0 10px 24px rgba(8,36,119,0.10);
}

section[data-testid="stSidebar"] div[role="radiogroup"] > label p {
    font-weight: 850;
    font-size: 0.84rem;
    color: #061938;
    margin: 0;
}

.hero-card.acct {
    background:
        radial-gradient(circle at 84% 34%, rgba(58,214,168,0.30), transparent 26%),
        linear-gradient(135deg, #05261f 0%, #0a5c47 54%, #10916d 100%);
}

.hero-card.acct .eyebrow {
    color: #8ff0cf;
}

.hero-card.hr {
    background:
        radial-gradient(circle at 84% 34%, rgba(196,148,255,0.32), transparent 26%),
        linear-gradient(135deg, #21103f 0%, #46248c 54%, #6d3fd1 100%);
}

.hero-card.hr .eyebrow {
    color: #d9c2ff;
}

.rule-chip.acct::before {
    background: linear-gradient(90deg, #0a5c47, #3ad6a8);
}

.rule-chip.hr::before {
    background: linear-gradient(90deg, #46248c, #a97cff);
}

.upload-wrap.acct {
    background: linear-gradient(135deg, rgba(10,92,71,0.96), rgba(16,145,109,0.92)), #0a5c47;
}

.upload-wrap.hr {
    background: linear-gradient(135deg, rgba(70,36,140,0.96), rgba(109,63,209,0.92)), #46248c;
}

.upload-wrap.acct div[data-testid="stFileUploader"] button::after {
    content: "Sube tus comprobantes";
    color: #0a5c47;
}

.upload-wrap.hr div[data-testid="stFileUploader"] button::after {
    content: "Sube tus boletas";
    color: #46248c;
}

.file-icon.acct {
    background: linear-gradient(135deg, #05261f, #10916d);
}

.file-icon.hr {
    background: linear-gradient(135deg, #21103f, #6d3fd1);
}

.privacy-note {
    background: #fff8e9;
    border: 1px solid #ffd37e;
    color: #7a5200;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    font-size: 0.86rem;
    line-height: 1.5;
    margin-top: 0.9rem;
}

.warn-banner {
    margin: 1rem 0;
    background: linear-gradient(90deg, #fff4d8, #fffaf0);
    border: 1px solid #ffd37e;
    color: #7a5200;
    border-radius: 8px;
    padding: 1rem 1.1rem;
    font-weight: 850;
}
</style>
"""


def inject_css():
    """Inyecta la hoja de estilos completa. Se llama una sola vez por ejecucion."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.markdown(MODULES_CSS, unsafe_allow_html=True)


def _esc(value):
    return html.escape(str(value)) if value is not None else ""


def render_hero(kicker, titulo, texto, tags=None, variante="", icono_svg=None):
    """Cabecera azul (o verde/violeta) con titulo, bajada y etiquetas."""
    clase = f"hero-card {variante}".strip()
    tags_html = "".join(
        f'<span class="tag {estilo}">{_esc(etiqueta)}</span>'
        for etiqueta, estilo in (tags or [])
    )
    simbolo = f'<div class="pdf-symbol">{icono_svg}</div>' if icono_svg else ""
    st.markdown(
        f"""
        <div class="{clase}">
            <div>
                <div class="eyebrow">{_esc(kicker)}</div>
                <h1>{titulo}</h1>
                <p>{_esc(texto)}</p>
            </div>
            <div class="hero-tags">
                {tags_html}
                {simbolo}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pipeline(pasos):
    """Franja de 4 pasos. Cada paso es (titulo, subtitulo, estado, texto_pill)."""
    tarjetas = []
    for numero, (titulo, subtitulo, estado, pill) in enumerate(pasos, start=1):
        tarjetas.append(
            f'<div class="step-card {estado}">'
            f'<div class="step-number">{numero}</div>'
            f'<div><div class="step-title">{_esc(titulo)}</div>'
            f'<div class="step-sub">{_esc(subtitulo)}</div></div>'
            f'<span class="pill {estado}">{_esc(pill)}</span>'
            f"</div>"
        )
    st.markdown('<div class="pipeline">' + "".join(tarjetas) + "</div>", unsafe_allow_html=True)


def render_rules(titulo, texto, reglas, variante=""):
    """Tarjeta blanca con titulo y una rejilla de chips explicativos."""
    chips = "".join(
        f'<div class="rule-chip {variante}"><b>{_esc(cabeza)}</b>{_esc(cuerpo)}</div>'
        for cabeza, cuerpo in reglas
    )
    st.markdown(
        f"""
        <div class="work-card">
            <h2>{_esc(titulo)}</h2>
            <p>{_esc(texto)}</p>
            <div class="rules-grid">{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_grid(items):
    """Rejilla de metricas. Cada item es (etiqueta, valor)."""
    tarjetas = "".join(
        f'<div class="stat-card"><div class="stat-label">{_esc(etiqueta)}</div>'
        f'<div class="stat-value">{_esc(valor)}</div></div>'
        for etiqueta, valor in items
    )
    st.markdown(f'<div class="stat-grid">{tarjetas}</div>', unsafe_allow_html=True)


def render_result_grid(items):
    """Rejilla de resultados grandes. Cada item es (etiqueta, valor)."""
    tarjetas = "".join(
        f'<div class="result-card"><span>{_esc(etiqueta)}</span>'
        f"<strong>{_esc(valor)}</strong></div>"
        for etiqueta, valor in items
    )
    st.markdown(f'<div class="result-grid">{tarjetas}</div>', unsafe_allow_html=True)


def render_file_list(filas, variante=""):
    """Lista de archivos cargados. Cada fila es (nombre, meta, insignia, estado)."""
    html_filas = []
    for nombre, meta, insignia, estado in filas:
        html_filas.append(
            f'<div class="file-row">'
            f'<div class="file-icon {variante}">PDF</div>'
            f'<div><div class="file-name">{_esc(nombre)}</div>'
            f'<div class="file-meta">{_esc(meta)}</div></div>'
            f'<div class="brand-badge">{_esc(insignia)}</div>'
            f'<div class="status-badge">{_esc(estado)}</div>'
            f"</div>"
        )
    st.markdown('<div class="file-list">' + "".join(html_filas) + "</div>", unsafe_allow_html=True)


def open_card(titulo, kicker=None, texto=None):
    """Abre una tarjeta blanca de seccion. Hay que cerrarla con close_card()."""
    bajada = f"<p>{_esc(texto)}</p>" if texto else ""
    lado = f'<div class="section-kicker">{_esc(kicker)}</div>' if kicker else ""
    st.markdown(
        f"""
        <div class="work-card">
            <div class="section-head">
                <div><h3>{_esc(titulo)}</h3>{bajada}</div>
                {lado}
            </div>
        """,
        unsafe_allow_html=True,
    )


def close_card():
    st.markdown("</div>", unsafe_allow_html=True)


def render_empty(texto):
    st.markdown(f'<div class="empty-state">{_esc(texto)}</div>', unsafe_allow_html=True)


def render_banner(texto, tipo="ok"):
    clase = "result-banner" if tipo == "ok" else "warn-banner"
    st.markdown(f'<div class="{clase}">{_esc(texto)}</div>', unsafe_allow_html=True)


def render_benefits(items):
    """Tres tarjetas de cierre. Cada item es (titulo, texto)."""
    tarjetas = "".join(
        f'<div class="benefit"><b>{_esc(titulo)}</b><p>{_esc(texto)}</p></div>'
        for titulo, texto in items
    )
    st.markdown(f'<div class="benefits">{tarjetas}</div>', unsafe_allow_html=True)
