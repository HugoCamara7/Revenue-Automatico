"""Sistema de diseno unico de Revenue Control Center.

Todo el CSS de la app vive aca. `app.py` solo llama a `inject_css()` una vez y usa
los helpers para armar tarjetas, encabezados y badges, en lugar de repetir HTML.

Reglas del sistema:

- Un solo set de tokens (`:root`): colores, radios, sombras, espaciado y tipografia.
- Los componentes legacy (`coupon-*`, `step-*`, `source-*`, `result-*`) siguen
  existiendo con los mismos nombres de clase, para no romper el HTML ya escrito,
  pero repintados con los tokens nuevos.
- Nada de anchos completos por defecto: el contenido vive dentro de `main-card`.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

MARCA = "Revenue Control Center"
SUBMARCA = "Sistema de descuentos y cupones Shopify"

TOKENS = """
:root {
  --azul: #1e5eff;
  --azul-fuerte: #1748cc;
  --azul-suave: #eaf0ff;
  --navy: #0f1b34;
  --navy-medio: #24324f;
  --texto: #16243d;
  --texto-suave: #64748b;
  --texto-tenue: #94a3b8;
  --linea: #e3e9f2;
  --linea-fuerte: #cfd9e8;
  --fondo: #f4f7fc;
  --superficie: #ffffff;
  --superficie-2: #f8fafd;
  --verde: #0f9d58;
  --verde-fondo: #e8f6ee;
  --ambar: #b45309;
  --ambar-fondo: #fdf4e3;
  --rojo: #d93025;
  --rojo-fondo: #fdecea;
  --radio-xs: 8px;
  --radio-sm: 10px;
  --radio: 14px;
  --radio-lg: 20px;
  --sombra-sm: 0 1px 2px rgba(15, 27, 52, .06);
  --sombra: 0 2px 10px rgba(15, 27, 52, .07);
  --sombra-lg: 0 12px 32px rgba(15, 27, 52, .12);
  --fuente: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
}
"""

BASE_CSS = """
header[data-testid="stHeader"] { display: none; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stDecoration"] { display: none; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

html, body, [class*="css"], .stApp, button, input, select, textarea {
  font-family: var(--fuente) !important;
}
.stApp { background: var(--fondo); color: var(--texto); }

.block-container {
  max-width: 1180px !important;
  padding: 26px 30px 70px !important;
}

h1, h2, h3, h4 { color: var(--navy) !important; font-weight: 700 !important; letter-spacing: -.01em; }
h1 { font-size: 28px !important; line-height: 1.2 !important; margin-bottom: 2px !important; }
h2 { font-size: 20px !important; }
h3 { font-size: 17px !important; }
p, label, span, li { color: var(--texto); }

/* ---------- Widgets nativos ---------- */

div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stTimeInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-baseweb="select"] > div {
  background: var(--superficie) !important;
  border: 1px solid var(--linea-fuerte) !important;
  border-radius: var(--radio-sm) !important;
  color: var(--texto) !important;
  font-size: 14px !important;
  box-shadow: none !important;
  min-height: 40px;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
  border-color: var(--azul) !important;
  box-shadow: 0 0 0 3px rgba(30, 94, 255, .14) !important;
}
div[data-testid="stWidgetLabel"] label p,
div[data-testid="stWidgetLabel"] label {
  font-size: 12.5px !important;
  font-weight: 600 !important;
  color: var(--texto-suave) !important;
  letter-spacing: .01em;
}

div[data-testid="stForm"] { border: 0; padding: 0; }

.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: var(--radio-sm) !important;
  font-weight: 600 !important;
  font-size: 14px !important;
  padding: 9px 18px !important;
  border: 1px solid var(--linea-fuerte) !important;
  background: var(--superficie) !important;
  color: var(--navy) !important;
  box-shadow: var(--sombra-sm) !important;
  transition: all .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--azul) !important;
  color: var(--azul) !important;
  transform: translateY(-1px);
}
.stButton > button[kind="primary"],
.stFormSubmitButton > button,
.stDownloadButton > button[kind="primary"] {
  background: var(--azul) !important;
  border-color: var(--azul) !important;
  color: #fff !important;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover {
  background: var(--azul-fuerte) !important;
  border-color: var(--azul-fuerte) !important;
  color: #fff !important;
}
.stButton > button:disabled, .stButton > button[disabled] {
  opacity: .5 !important;
  transform: none !important;
}

div[data-testid="stExpander"] {
  border: 1px solid var(--linea) !important;
  border-radius: var(--radio) !important;
  background: var(--superficie) !important;
  box-shadow: var(--sombra-sm);
  overflow: hidden;
}
div[data-testid="stExpander"] summary { font-weight: 600 !important; font-size: 14px !important; }

div[data-testid="stTabs"] button[data-baseweb="tab"] {
  font-weight: 600 !important;
  font-size: 14px !important;
  color: var(--texto-suave) !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] { color: var(--azul) !important; }
div[data-testid="stTabs"] div[data-baseweb="tab-highlight"] { background: var(--azul) !important; }

div[data-testid="stDataFrame"], div[data-testid="stTable"] {
  border: 1px solid var(--linea) !important;
  border-radius: var(--radio) !important;
  overflow: hidden;
  box-shadow: var(--sombra-sm);
}

div[data-testid="stFileUploaderDropzone"] {
  background: var(--superficie-2) !important;
  border: 1.5px dashed var(--linea-fuerte) !important;
  border-radius: var(--radio) !important;
  padding: 14px 16px !important;
}
div[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--azul) !important; }

div[data-testid="stAlert"] { border-radius: var(--radio-sm) !important; border: 0 !important; }

div[data-testid="stRadio"] label, div[data-testid="stCheckbox"] label { font-size: 14px !important; }
div[data-testid="stRadio"] div[role="radiogroup"] { gap: 14px; }

hr { border-color: var(--linea) !important; margin: 18px 0 !important; }

/* ---------- Sidebar ---------- */

section[data-testid="stSidebar"] {
  background: var(--fondo) !important;
  border-right: 1px solid var(--linea);
  width: 306px !important;
}
section[data-testid="stSidebar"] > div { padding-top: 14px; }
section[data-testid="stSidebar"] .block-container { padding: 12px !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { font-size: 15px !important; }

.sidebar-logo-card, .sidebar-brand-card, .sidebar-status-card, .nav-card {
  background: var(--superficie);
  border: 1px solid var(--linea);
  border-radius: var(--radio);
  box-shadow: var(--sombra-sm);
  padding: 14px 16px;
  margin-bottom: 12px;
}
.sidebar-logo-card { text-align: center; padding: 16px; }
.sidebar-logo-card img { max-width: 168px; width: 100%; }
.sidebar-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--texto-tenue);
  margin: 16px 0 8px;
}
.user-card { display: flex; align-items: center; gap: 12px; }
.user-avatar {
  width: 42px; height: 42px; flex: 0 0 42px;
  border-radius: 12px;
  background: var(--azul);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 15px;
}
.user-rol {
  font-size: 10.5px; font-weight: 700; letter-spacing: .09em;
  text-transform: uppercase; color: var(--azul);
}
.user-nombre { font-size: 14.5px; font-weight: 700; color: var(--navy); line-height: 1.25; }
.user-mail { font-size: 12px; color: var(--texto-tenue); word-break: break-all; }

.estado-pill {
  display: flex; align-items: center; gap: 8px;
  background: var(--verde-fondo); color: var(--verde);
  border-radius: 999px; padding: 7px 14px;
  font-size: 12.5px; font-weight: 600; margin-bottom: 12px;
}
.estado-pill.warn { background: var(--ambar-fondo); color: var(--ambar); }
.estado-pill.bad { background: var(--rojo-fondo); color: var(--rojo); }
.estado-punto { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }

.sitio-activo { text-align: center; }
.sitio-activo-tag { font-size: 12px; color: var(--texto-suave); margin-bottom: 8px; }
.marca-chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.marca-chip {
  background: var(--azul-suave); color: var(--azul-fuerte);
  border-radius: 999px; padding: 5px 12px;
  font-size: 12px; font-weight: 700; letter-spacing: .02em;
}

/* ---------- Cabecera y contenedores ---------- */

.page-head { margin-bottom: 18px; }
.page-title { font-size: 27px; font-weight: 800; color: var(--navy); letter-spacing: -.02em; }
.page-sub { font-size: 14px; color: var(--texto-suave); margin-top: 2px; }
.eyebrow {
  font-size: 11px; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--azul);
}

.main-card, .top-hero, .status-card, .steps-card, .source-box, .preview-panel,
.coupon-builder-card, .coupon-card, .coupon-hero, .coupon-page-head,
.coupon-summary-card, .coupon-preview-card, .result-card, .step-box, .coupon-bottom-bar {
  background: var(--superficie);
  border: 1px solid var(--linea);
  border-radius: var(--radio);
  box-shadow: var(--sombra-sm);
  padding: 18px 20px;
  margin-bottom: 14px;
}
.coupon-builder-card.tight, .tight { padding: 14px 18px; margin-bottom: 10px; }

.top-hero, .coupon-hero {
  background: linear-gradient(135deg, var(--navy) 0%, var(--navy-medio) 100%);
  border: 0;
  color: #fff;
  padding: 22px 26px;
}
.top-hero h1, .top-hero .page-title, .coupon-hero h1, .coupon-hero .page-title { color: #fff !important; }
.top-hero .page-sub, .coupon-hero .page-sub, .hero-right { color: rgba(255, 255, 255, .78); }
.hero-arrow { color: rgba(255, 255, 255, .5); }
.coupon-hero-chip, .coupon-hero-mini {
  display: inline-block;
  background: rgba(255, 255, 255, .14);
  border-radius: 999px; padding: 5px 13px;
  font-size: 12px; font-weight: 600; color: #fff;
  margin-right: 6px;
}

/* ---------- Secciones numeradas ---------- */

.coupon-step-line, .coupon-section-head {
  display: flex; align-items: center; gap: 11px; margin-bottom: 4px;
}
.coupon-step-num, .step-num {
  width: 27px; height: 27px; flex: 0 0 27px;
  border-radius: 9px;
  background: var(--azul-suave); color: var(--azul-fuerte);
  display: flex; align-items: center; justify-content: center;
  font-size: 12.5px; font-weight: 800;
}
.coupon-step-title, .step-title, .source-title, .preview-title, .result-label {
  font-size: 15px; font-weight: 700; color: var(--navy);
}
.coupon-step-sub, .step-sub, .source-sub, .preview-sub {
  font-size: 13px; color: var(--texto-suave); line-height: 1.5;
}
.coupon-step-sub, .step-sub { margin-top: 3px; }

/* ---------- Grillas ---------- */

.steps-grid, .source-grid, .result-grid, .coupon-kpi-grid, .coupon-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}
.steps-grid > *, .source-grid > *, .result-grid > *, .coupon-summary-grid > * { margin-bottom: 0; }

.result-card, .coupon-summary-card, .coupon-kpi {
  background: var(--superficie-2);
  border: 1px solid var(--linea);
  border-radius: var(--radio-sm);
  padding: 14px 16px;
  margin-bottom: 0;
}
.result-value, .coupon-summary-value {
  font-size: 25px; font-weight: 800; color: var(--navy); line-height: 1.15;
}
.result-label, .coupon-summary-label {
  font-size: 11.5px; font-weight: 700; letter-spacing: .07em;
  text-transform: uppercase; color: var(--texto-tenue);
}
.coupon-summary-sub { font-size: 12.5px; color: var(--texto-suave); }
.coupon-summary-icon { font-size: 17px; margin-bottom: 6px; }
.result-card.good { border-left: 4px solid var(--verde); }
.result-card.bad { border-left: 4px solid var(--rojo); }

/* ---------- Badges, pills y avisos ---------- */

.pill, .coupon-badge, .step-badge, .coupon-site-pill, .coupon-site-count, .marca-chip {
  display: inline-flex; align-items: center; gap: 6px;
  border-radius: 999px; padding: 5px 12px;
  font-size: 12px; font-weight: 700;
  background: var(--azul-suave); color: var(--azul-fuerte);
}
.pill.green, .green, .connection-ok { background: var(--verde-fondo) !important; color: var(--verde) !important; }
.pill.orange, .orange { background: var(--ambar-fondo) !important; color: var(--ambar) !important; }
.pill.red, .red, .error { background: var(--rojo-fondo) !important; color: var(--rojo) !important; }
.pill.blue, .blue { background: var(--azul-suave) !important; color: var(--azul-fuerte) !important; }
.pill.muted, .muted, .soft { background: var(--superficie-2) !important; color: var(--texto-suave) !important; }
.pill.active, .active { background: var(--azul) !important; color: #fff !important; }

.coupon-note, .coupon-warning, .status-card.warn {
  border-radius: var(--radio-sm);
  padding: 11px 15px;
  font-size: 13.5px;
  line-height: 1.5;
  margin-bottom: 9px;
  border: 0;
  box-shadow: none;
}
.coupon-note { background: var(--azul-suave); color: var(--azul-fuerte); }
.coupon-warning { background: var(--rojo-fondo); color: var(--rojo); font-weight: 600; }

.shopify-mini, .shopify-fallback {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--texto-suave);
}
.shopify-mini img, .shopify-fallback img { height: 16px; }

/* ---------- Vista previa del cupon ---------- */

.coupon-preview-card {
  background: linear-gradient(135deg, var(--azul) 0%, var(--azul-fuerte) 100%);
  border: 0; color: #fff; text-align: center; padding: 24px;
}
.coupon-preview-code {
  font-size: 30px; font-weight: 800; letter-spacing: .07em; color: #fff;
}
.coupon-preview-discount {
  font-size: 15px; font-weight: 700; color: rgba(255, 255, 255, .92); margin-bottom: 10px;
}
.coupon-preview-meta { font-size: 12.5px; color: rgba(255, 255, 255, .8); line-height: 1.7; }

.coupon-bottom-bar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 14px; background: var(--superficie-2);
}
.coupon-bottom-title { font-size: 15px; font-weight: 700; color: var(--navy); }
.coupon-bottom-sub { font-size: 12.5px; color: var(--texto-suave); }
.coupon-chip-row { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 8px; }

/* ---------- Bloque de fecha y hora ---------- */

.rango-box {
  background: var(--superficie-2);
  border: 1px solid var(--linea);
  border-radius: var(--radio-sm);
  padding: 13px 15px 4px;
  margin-bottom: 10px;
}
.rango-tag {
  font-size: 11px; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--texto-tenue); margin-bottom: 8px;
}
.rango-resumen {
  font-size: 13px; color: var(--texto-suave);
  background: var(--azul-suave); color: var(--azul-fuerte);
  border-radius: var(--radio-xs); padding: 8px 12px; margin-top: 2px;
  font-weight: 600;
}

/* ---------- Responsive ---------- */

@media (max-width: 900px) {
  .block-container { padding: 16px 14px 60px !important; }
  .steps-grid, .source-grid, .result-grid, .coupon-summary-grid, .coupon-kpi-grid {
    grid-template-columns: 1fr;
  }
  .coupon-bottom-bar { flex-direction: column; align-items: flex-start; }
  .page-title { font-size: 22px; }
  .coupon-preview-code { font-size: 24px; }
}
"""

LOGIN_CSS = """
section[data-testid="stSidebar"] { display: none !important; }
.stApp {
  background:
    radial-gradient(1100px 520px at 50% -12%, #1c3f8f 0%, transparent 60%),
    linear-gradient(180deg, #0f1b34 0%, #0b1428 100%);
}
.block-container {
  max-width: 460px !important;
  padding: 0 18px 40px !important;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.login-hero {
  background: linear-gradient(135deg, var(--azul) 0%, var(--azul-fuerte) 100%);
  border-radius: var(--radio-lg) var(--radio-lg) 0 0;
  padding: 30px 30px 26px;
  text-align: center;
}
.login-brand-row {
  display: flex; align-items: center; justify-content: center; gap: 16px; margin-bottom: 16px;
}
.login-logo { height: 34px; background: #fff; padding: 7px 12px; border-radius: 10px; }
.login-shopify { height: 34px; }
.login-divider { width: 1px; height: 30px; background: rgba(255, 255, 255, .35); }
.login-title { font-size: 21px; font-weight: 800; color: #fff; letter-spacing: -.01em; }
.login-sub { font-size: 12.5px; color: rgba(255, 255, 255, .8); margin-top: 4px; }
.login-card-anchor { display: none; }

div[data-testid="stForm"] {
  background: var(--superficie);
  border-radius: 0 0 var(--radio-lg) var(--radio-lg);
  padding: 24px 30px 26px !important;
  box-shadow: var(--sombra-lg);
  border: 0 !important;
}
div[data-testid="stForm"] .stFormSubmitButton > button { width: 100%; padding: 11px !important; }
.login-message {
  background: var(--rojo-fondo); color: var(--rojo);
  border-radius: var(--radio-sm); padding: 10px 14px;
  font-size: 13px; font-weight: 600; margin-bottom: 14px;
}
.login-foot {
  text-align: center; font-size: 12px;
  color: rgba(255, 255, 255, .55); margin-top: 18px;
}
.login-brands-foot {
  text-align: center; font-size: 11.5px;
  color: rgba(255, 255, 255, .4); margin-top: 5px; letter-spacing: .03em;
}
"""


def inject_css(login: bool = False) -> None:
    """Inyecta el sistema de diseno. `login=True` agrega el modo pantalla de acceso."""
    hoja = TOKENS + BASE_CSS + (LOGIN_CSS if login else "")
    st.markdown("<style>" + hoja + "</style>", unsafe_allow_html=True)


def imagen_data_uri(ruta: str) -> str:
    archivo = Path(ruta)
    if not archivo.exists():
        return ""
    sufijo = archivo.suffix.lower().replace(".", "")
    mime = "jpeg" if sufijo in ("jpg", "jpeg") else "png"
    return "data:image/" + mime + ";base64," + base64.b64encode(archivo.read_bytes()).decode("ascii")


def encabezado(titulo: str, subtitulo: str = "", chip: str = "", hero: bool = False) -> None:
    """Encabezado de pantalla. `hero=True` usa el bloque oscuro de marca."""
    clase = "top-hero" if hero else "page-head"
    partes = ['<div class="' + clase + '">']
    if chip:
        partes.append('<div class="' + ("coupon-hero-chip" if hero else "eyebrow") + '">' + chip + "</div>")
    partes.append('<div class="page-title">' + titulo + "</div>")
    if subtitulo:
        partes.append('<div class="page-sub">' + subtitulo + "</div>")
    partes.append("</div>")
    st.markdown("".join(partes), unsafe_allow_html=True)


def seccion(numero: str, titulo: str, subtitulo: str = "", compacta: bool = True) -> None:
    """Encabezado de bloque numerado, con el mismo look en toda la app."""
    clase = "coupon-builder-card tight" if compacta else "coupon-builder-card"
    partes = [
        '<div class="' + clase + '">',
        '<div class="coupon-step-line">',
        '<div class="coupon-step-num">' + numero + "</div>",
        '<div class="coupon-step-title">' + titulo + "</div>",
        "</div>",
    ]
    if subtitulo:
        partes.append('<div class="coupon-step-sub">' + subtitulo + "</div>")
    partes.append("</div>")
    st.markdown("".join(partes), unsafe_allow_html=True)


def panel(titulo: str, subtitulo: str = "") -> None:
    """Cabecera de un panel de resultados (tabla debajo)."""
    partes = ['<div class="preview-panel">', '<div class="preview-title">' + titulo + "</div>"]
    if subtitulo:
        partes.append('<div class="preview-sub">' + subtitulo + "</div>")
    partes.append("</div>")
    st.markdown("".join(partes), unsafe_allow_html=True)


def badge(texto: str, tono: str = "blue") -> str:
    return '<span class="pill ' + tono + '">' + texto + "</span>"


def kpi(etiqueta: str, valor: str, detalle: str = "") -> str:
    partes = [
        '<div class="coupon-summary-card">',
        '<div class="coupon-summary-label">' + etiqueta + "</div>",
        '<div class="coupon-summary-value">' + valor + "</div>",
    ]
    if detalle:
        partes.append('<div class="coupon-summary-sub">' + detalle + "</div>")
    partes.append("</div>")
    return "".join(partes)


def fila_kpis(items: list[tuple[str, str, str]]) -> None:
    tarjetas = "".join(kpi(etiqueta, valor, detalle) for etiqueta, valor, detalle in items)
    st.markdown('<div class="coupon-summary-grid">' + tarjetas + "</div>", unsafe_allow_html=True)


def aviso(mensaje: str, tono: str = "info") -> None:
    clase = "coupon-warning" if tono in ("error", "warning") else "coupon-note"
    st.markdown('<div class="' + clase + '">' + mensaje + "</div>", unsafe_allow_html=True)


def ancho() -> dict:
    """`use_container_width` esta deprecado; `width` no existe en Streamlit viejo."""
    try:
        mayor, menor = (int(parte) for parte in str(st.__version__).split(".")[:2])
    except Exception:
        return {"use_container_width": True}
    return {"width": "stretch"} if (mayor, menor) >= (1, 49) else {"use_container_width": True}
