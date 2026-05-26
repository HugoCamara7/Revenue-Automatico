from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from generar_matrixify_descuentos import build_discount_workbook, read_matrixify, validate_matrixify_vendor


SITES = {
    "Rockford.pe": {
        "brands": ["COLUMBIA", "ROCKFORD", "PATAGONIA", "SOREL", "MOUNTAIN HARDWEAR"],
        "vendor": "rockfordpe",
        "output": "matrixify_revenue_rockford.xlsx",
    },
    "Columbia.pe": {
        "brands": ["COLUMBIA"],
        "vendor": "columbiape",
        "output": "matrixify_revenue_columbia.xlsx",
    },
    "Hushpuppies.pe": {
        "brands": ["HUSH PUPPIES"],
        "vendor": "hushpuppiespe",
        "output": "matrixify_revenue_hushpuppies.xlsx",
    },
    "Vans.pe": {
        "brands": ["VANS"],
        "vendor": "vanspe",
        "output": "matrixify_revenue_vans.xlsx",
    },
    "Supermall.pe": {
        "brands": ["COLUMBIA", "HUSH PUPPIES", "ROCKFORD", "PATAGONIA", "SOREL", "MOUNTAIN HARDWEAR", "VANS"],
        "vendor": "supermallpe",
        "output": "matrixify_revenue_supermall.xlsx",
    },
}


st.set_page_config(page_title="Matrixify Revenue", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #ffffff; color: #001f4f; }
    [data-testid="stSidebar"] { background: #eef2f7; }
    .block-container { max-width: 1120px; padding-top: 42px; }
    .brand-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:42px; gap:24px; }
    .hero h1 { color:#001f4f; font-size:32px; margin-bottom:14px; }
    .hero p { color:#4d6383; }
    .info-box { border:1px solid #cfe2ff; background:#f2f8ff; border-radius:8px; padding:18px 22px; margin:24px 0 30px; }
    .section-card { border:1px solid #d9e6f7; border-radius:8px; padding:22px; margin:18px 0; background:white; }
    div[data-testid="stFileUploader"] { border:1px dashed #9cc3ff; border-radius:8px; padding:16px; background:#fbfdff; }
    .stButton button, .stDownloadButton button { border-radius:8px; font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)


def save_upload(uploaded_file, folder: Path) -> Path:
    path = folder / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return path


with st.sidebar:
    site_name = st.selectbox("Sitio destino", list(SITES.keys()))
    site = SITES[site_name]
    st.markdown("**Marcas permitidas**")
    st.write(", ".join(site["brands"]))
    selected_brands = st.multiselect(
        "Marcas a afectar",
        site["brands"],
        default=site["brands"][:1],
        help="Se usa la columna MARCA del Revenue/input comercial.",
    )
    st.caption(f"Vendor: {site['vendor']} | Salida: {site['output']}")
    st.info("Version rapida: no usa BigQuery. La marca debe venir en el Revenue.")


st.markdown('<div class="brand-row">', unsafe_allow_html=True)
left, right = st.columns([3, 1])
with left:
    if Path("forus_logo.png").exists():
        st.image("forus_logo.png", width=230)
    else:
        st.markdown("### FORUS")
with right:
    if Path("shopify_logo.png").exists():
        st.image("shopify_logo.png", width=90)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="hero">
      <h1>Matrixify Revenue {site_name} - Shopify</h1>
      <p>Sube el Revenue comercial y el ultimo Matrixify del sitio. La app genera una hoja por campana/fecha.</p>
    </div>
    <div class="info-box">
      <b>Regla principal:</b><br>
      El Revenue debe traer <code>ID PRODUCTO</code>, <code>MODCOL</code> y <code>MARCA</code>.
      Solo se modifican las marcas seleccionadas; las demas quedan en la hoja <code>No afectados por marca</code>.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-card"><h3>Cargar archivos obligatorios</h3>', unsafe_allow_html=True)
revenue_file = st.file_uploader("1. Subir Revenue / input comercial", type=["xlsx"], key="revenue")
matrixify_file = st.file_uploader(
    f"2. Subir ultimo catalogo Matrixify de {site_name}",
    type=["xlsx"],
    key="matrixify",
    help="Debe corresponder al mismo sitio destino para conservar Product ID y Variant ID.",
)
st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Formato comercial esperado"):
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID PRODUCTO": "SKU123",
                    "MODCOL": "MODELO-COLOR",
                    "MARCA": selected_brands[0] if selected_brands else "COLUMBIA",
                    "RESTO DEL MES": "0%",
                    "CLB 40": "40%",
                }
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )

generate = st.button(
    "Generar Matrixify Revenue",
    type="primary",
    use_container_width=True,
    disabled=not revenue_file or not matrixify_file,
)

if generate:
    if not selected_brands:
        st.error("Selecciona al menos una marca a afectar.")
        st.stop()

    try:
        with st.status("Procesando archivos...", expanded=True) as status:
            with tempfile.TemporaryDirectory() as temp_dir:
                workdir = Path(temp_dir)
                revenue_path = save_upload(revenue_file, workdir)
                matrixify_path = save_upload(matrixify_file, workdir)
                output_path = workdir / site["output"]

                st.write("Validando vendor del Matrixify...")
                matrixify_df = read_matrixify(matrixify_path)
                ok, message = validate_matrixify_vendor(matrixify_df, site["vendor"])
                if not ok:
                    st.error(message)
                    st.stop()
                if message:
                    st.warning(message)

                st.write("Cruzando Revenue con Matrixify y generando hojas...")
                result = build_discount_workbook(
                    matrixify_path=matrixify_path,
                    revenue_path=revenue_path,
                    output_path=output_path,
                    selected_brands=selected_brands,
                )
                output_bytes = output_path.read_bytes()
                status.update(label="Archivo generado correctamente.", state="complete")

        st.success("Archivo generado correctamente.")
        st.subheader("Resumen")
        st.dataframe(result["summary"], hide_index=True, use_container_width=True)

        if not result["percent"].empty:
            st.subheader("Distribucion por descuento")
            st.dataframe(result["percent"], hide_index=True, use_container_width=True)

        if not result["missing"].empty:
            st.warning(f"{len(result['missing']):,} codigos no se encontraron en Matrixify.")
            st.dataframe(result["missing"].head(200), hide_index=True, use_container_width=True)

        if not result["not_affected"].empty:
            st.info(f"{len(result['not_affected']):,} codigos quedaron fuera por marca.")
            st.dataframe(result["not_affected"].head(200), hide_index=True, use_container_width=True)

        st.download_button(
            "Descargar Matrixify generado",
            data=output_bytes,
            file_name=site["output"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"No pude generar el archivo: {exc}")
else:
    st.info("Carga ambos archivos para comenzar.")

