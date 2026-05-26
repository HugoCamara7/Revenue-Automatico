from __future__ import annotations

import json
import tempfile
from pathlib import Path

import openpyxl
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

from generar_matrixify_descuentos import analyze_discount_preview, build_discount_workbook


SITES = {
    "Rockford.pe": {
        "brand": "COLUMBIA, ROCKFORD, PATAGONIA, SOREL, MOUNTAIN HARDWEAR",
        "brands": ["COLUMBIA", "ROCKFORD", "PATAGONIA", "SOREL", "MOUNTAIN HARDWEAR"],
        "vendor": "rockfordpe",
        "output": "matrixify_revenue_rockford.xlsx",
    },
    "Columbia.pe": {
        "brand": "COLUMBIA",
        "brands": ["COLUMBIA"],
        "vendor": "columbiape",
        "output": "matrixify_revenue_columbia.xlsx",
    },
    "Hushpuppies.pe": {
        "brand": "HUSH PUPPIES",
        "brands": ["HUSH PUPPIES"],
        "vendor": "hushpuppiespe",
        "output": "matrixify_revenue_hushpuppies.xlsx",
    },
    "Vans.pe": {
        "brand": "VANS",
        "brands": ["VANS"],
        "vendor": "vanspe",
        "output": "matrixify_revenue_vans.xlsx",
    },
    "Supermall.pe": {
        "brand": "MULTIMARCA",
        "brands": ["COLUMBIA", "HUSH PUPPIES", "ROCKFORD", "PATAGONIA", "SOREL", "MOUNTAIN HARDWEAR", "VANS"],
        "vendor": "supermallpe",
        "output": "matrixify_revenue_supermall.xlsx",
    },
}


st.set_page_config(page_title="Matrixify Descuentos", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background: #ffffff;
        color: #001f4f;
    }
    [data-testid="stSidebar"] {
        background: #eef2f7;
    }
    .main-block {
        max-width: 960px;
        margin: 0 auto;
        padding-top: 28px;
    }
    .brand-logo {
        font-size: 58px;
        line-height: 1;
        font-weight: 800;
        color: #15329b;
        letter-spacing: 1px;
    }
    .brand-subtitle {
        color: #15329b;
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 7px;
        margin-bottom: 64px;
    }
    .shopify-badge {
        height: 84px;
        width: 84px;
        border-radius: 12px;
        background: #95bf47;
        color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 48px;
        font-weight: 800;
        transform: rotate(4deg);
        margin-left: auto;
    }
    .info-box {
        background: #eef6ff;
        border: 1px solid #c3ddff;
        border-radius: 8px;
        padding: 20px 24px;
        margin: 34px 0 40px 0;
    }
    .section-card {
        border: 1px solid #d7e1ef;
        border-radius: 8px;
        padding: 28px 24px;
        margin-bottom: 18px;
    }
    .upload-card {
        border: 1px dashed #8ab4ff;
        border-radius: 8px;
        padding: 20px 18px;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def save_upload(uploaded_file, folder: Path) -> Path:
    path = folder / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return path


def read_summary(output_path: Path) -> tuple[list[str], list[list[object]], int]:
    workbook = openpyxl.load_workbook(output_path, data_only=True, read_only=True)
    summary = workbook["Resumen"]
    headers = [summary.cell(row=1, column=col).value for col in range(1, summary.max_column + 1)]
    rows = [
        [summary.cell(row=row, column=col).value for col in range(1, summary.max_column + 1)]
        for row in range(2, summary.max_row + 1)
    ]
    missing_count = workbook["No encontrados"].max_row - 1 if "No encontrados" in workbook.sheetnames else 0
    workbook.close()
    return headers, rows, missing_count


@st.cache_data(ttl=3600, show_spinner=False)
def load_brand_lookup_from_bigquery() -> dict[str, str]:
    config = {}
    try:
        if "bigquery" in st.secrets:
            config.update(dict(st.secrets["bigquery"]))
        if "gcp_service_account" in st.secrets:
            config["service_account_info"] = dict(st.secrets["gcp_service_account"])
    except Exception:
        return {}

    service_account_json = config.pop("service_account_json", None)
    if service_account_json and "service_account_info" not in config:
        config["service_account_info"] = json.loads(service_account_json)

    enabled = str(config.get("enabled", "true")).strip().lower()
    if enabled in ("0", "false", "no", "off"):
        return {}

    credentials_info = config.get("service_account_info")
    credentials = service_account.Credentials.from_service_account_info(dict(credentials_info)) if credentials_info else None
    project_id = str(config.get("project_id") or (credentials.project_id if credentials else "")).strip()
    job_project_id = str(config.get("job_project_id") or project_id).strip() or None
    client = bigquery.Client(project=job_project_id, credentials=credentials)

    query = str(config.get("query", "")).strip()
    if not query:
        table = str(config.get("table", "")).strip()
        dataset = str(config.get("dataset", "")).strip()
        if not table:
            return {}
        table_id = table if table.count(".") == 2 else f"{project_id}.{dataset}.{table}"
        query = f"SELECT * FROM `{table_id}`"

    rows = client.query(
        query,
        job_config=bigquery.QueryJobConfig(use_legacy_sql=False),
        location=str(config.get("location", "")).strip() or None,
    ).result()

    lookup: dict[str, str] = {}
    for row in rows:
        row_dict = dict(row.items())
        brand = ""
        for field in ("MARCA", "marca", "Marca", "brand", "BRAND", "vendor", "VENDOR"):
            if row_dict.get(field) not in (None, ""):
                brand = str(row_dict.get(field)).strip()
                break
        if not brand:
            continue
        for field in (
            "ID_PRODUCTO",
            "ID PRODUCTO",
            "id_producto",
            "CODINT_MA",
            "codint_ma",
            "sku",
            "SKU",
            "MODCOL",
            "modcol",
            "COD MOD COL",
            "COD_MOD_COL",
            "Mod-Col",
            "codmodcol",
        ):
            value = row_dict.get(field)
            if value not in (None, ""):
                key = "".join(ch for ch in str(value).upper() if ch.isalnum())
                lookup[key] = brand
    return lookup


with st.sidebar:
    site_name = st.selectbox("Sitio destino", list(SITES.keys()))
    site = SITES[site_name]
    st.markdown("**Marcas permitidas**")
    st.write(site["brand"])
    selected_brands = st.multiselect(
        "Marcas a afectar",
        site["brands"],
        default=site["brands"][:1],
        help="Se filtra con el maestro de BigQuery. Si no hay maestro configurado, se usa solo el alcance del input.",
    )
    st.caption(f"Vendor: {site['vendor']} | Salida: {site['output']}")

brand_lookup = {}
try:
    brand_lookup = load_brand_lookup_from_bigquery()
except Exception as exc:
    st.sidebar.warning(f"No se pudo cargar el maestro BigQuery: {exc}")

if brand_lookup:
    st.sidebar.success(f"Maestro BigQuery cargado: {len(brand_lookup):,} llaves")
else:
    st.sidebar.info("Sin maestro BigQuery: se procesara solo el alcance del input.")


st.markdown('<div class="main-block">', unsafe_allow_html=True)
top_left, top_right = st.columns([3, 1])
with top_left:
    st.image("forus_logo.png", width=230)
with top_right:
    st.image("shopify_logo.png", width=90)

st.header(f"Matrixify {site_name} - Shopify")
st.write(
    "Sube el input comercial y el ultimo catalogo Matrixify del sitio para conservar IDs y evitar duplicados."
)

st.markdown(
    """
    <div class="info-box">
      <strong>Flujo obligatorio:</strong><br>
      Elige el sitio destino, sube el Revenue comercial y sube el ultimo catalogo Matrixify del mismo sitio.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-card"><h3>Cargar archivos obligatorios</h3></div>', unsafe_allow_html=True)

st.markdown('<div class="upload-card">', unsafe_allow_html=True)
revenue_file = st.file_uploader(
    "1. Subir input comercial / Revenue",
    type=["xlsx", "xls"],
    help="Debe incluir ID PRODUCTO, MODCOL y columnas como DCTO ANT, NUEVO DCTO o DESCUENTO.",
)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="upload-card">', unsafe_allow_html=True)
matrixify_file = st.file_uploader(
    f"2. Subir ultimo catalogo Matrixify de {site_name}",
    type=["xlsx", "xls"],
    help="Debe tener las columnas Matrixify de Products, incluyendo ID, Handle, Variant SKU, Variant Price y Compare At Price.",
)
st.markdown("</div>", unsafe_allow_html=True)

with st.expander("Regla de calculo"):
    st.write(
        "Primero se busca el SKU del Revenue en `Variant SKU`. Cuando encuentra un SKU con descuento, "
        "la app aplica ese mismo descuento a todas las variantes del mismo producto Matrixify, usando el `ID` "
        "del producto como grupo modelo-color. Cada hoja incluye todo el catalogo Matrixify, no solo los SKUs con descuento."
    )
    st.write(
        "`Variant Price` queda como precio original menos descuento. "
        "`Variant Compare At Price` solo se llena con el precio original cuando hay descuento real; "
        "si no hay descuento, queda vacio."
    )

generate = st.button(
    "Generar Matrixify de descuentos",
    type="primary",
    disabled=not matrixify_file or not revenue_file,
    use_container_width=True,
)

if generate:
    with st.spinner("Procesando archivos y armando hojas por fecha/campana..."):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                workdir = Path(temp_dir)
                revenue_path = save_upload(revenue_file, workdir)
                matrixify_path = save_upload(matrixify_file, workdir)
                output_path = workdir / site["output"]

                preview_rows, percent_rows, preview_missing = analyze_discount_preview(matrixify_path, revenue_path)
                build_discount_workbook(matrixify_path, revenue_path, output_path)
                headers, rows, missing_count = read_summary(output_path)
                output_bytes = output_path.read_bytes()

            st.success("Archivo generado correctamente.")
            st.subheader("Vista previa comercial")

            if preview_rows:
                total_products = sum(row["Cod MODCOL / productos afectados"] for row in preview_rows)
                total_variants = sum(row["Variantes Matrixify afectadas"] for row in preview_rows)
                col1, col2, col3 = st.columns(3)
                col1.metric("Cargas detectadas", len(preview_rows))
                col2.metric("Cod MODCOL / productos afectados", f"{total_products:,}")
                col3.metric("Variantes afectadas", f"{total_variants:,}")

                st.write("**Resumen por carga**")
                st.dataframe(preview_rows, hide_index=True, use_container_width=True)

            if percent_rows:
                st.write("**Distribucion por porcentaje de descuento**")
                st.dataframe(percent_rows, hide_index=True, use_container_width=True)

            if preview_missing:
                st.warning(
                    f"Vista previa: {preview_missing} SKUs del input no hicieron match contra Variant SKU. "
                    "El archivo igual se genera con el catalogo completo."
                )

            st.subheader("Resumen")
            st.dataframe([dict(zip(headers, row)) for row in rows], hide_index=True, use_container_width=True)

            if missing_count:
                st.warning(
                    f"Hay {missing_count} SKUs del Revenue que no se encontraron en Matrixify. "
                    "Quedaron documentados en la hoja `No encontrados`."
                )

            st.download_button(
                "Descargar Matrixify generado",
                data=output_bytes,
                file_name=site["output"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"No pude generar el archivo: {exc}")

st.markdown("</div>", unsafe_allow_html=True)
