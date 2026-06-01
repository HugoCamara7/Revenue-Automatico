from __future__ import annotations

import smtplib
import tempfile
from email.message import EmailMessage
from pathlib import Path

import pandas as pd
import streamlit as st

from generar_matrixify_descuentos import (
    build_discount_workbook,
    extract_revenue_lookup_values,
    normalize_key,
    read_matrixify,
    validate_matrixify_vendor,
)


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


def get_email_config() -> dict[str, str]:
    try:
        return dict(st.secrets.get("email", {}))
    except Exception:
        return {}


def send_finish_email(to_email: str, subject: str, body: str, attachment_name: str, attachment_bytes: bytes) -> None:
    config = get_email_config()
    required = ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "from_email"]
    missing = [key for key in required if not str(config.get(key, "")).strip()]
    if missing:
        raise RuntimeError(f"Faltan secrets de correo: {', '.join(missing)}")

    message = EmailMessage()
    message["From"] = str(config["from_email"]).strip()
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    message.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=attachment_name,
    )

    smtp_host = str(config["smtp_host"]).strip()
    smtp_port = int(config["smtp_port"])
    use_ssl = str(config.get("use_ssl", "false")).strip().lower() in ("1", "true", "yes", "si")
    use_tls = str(config.get("use_tls", "true")).strip().lower() in ("1", "true", "yes", "si")

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(smtp_host, smtp_port, timeout=30) as server:
        if use_tls and not use_ssl:
            server.starttls()
        server.login(str(config["smtp_user"]).strip(), str(config["smtp_password"]))
        server.send_message(message)


def get_bigquery_config() -> dict:
    config = {}
    try:
        if "bigquery" in st.secrets:
            config.update(dict(st.secrets["bigquery"]))
        if "gcp_service_account" in st.secrets:
            config["service_account_info"] = dict(st.secrets["gcp_service_account"])
    except Exception:
        return {}
    return config


@st.cache_data(ttl=3600, show_spinner=False)
def load_product_lookup_from_bigquery(ids: tuple[str, ...], modcols: tuple[str, ...]) -> dict[str, dict]:
    if not ids and not modcols:
        return {"by_id": {}, "by_modcol": {}}
    try:
        from google.cloud import bigquery
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("Faltan dependencias para BigQuery en requirements.txt.") from exc

    config = get_bigquery_config()
    enabled = str(config.get("enabled", "true")).strip().lower()
    if enabled in ("0", "false", "no", "off"):
        return {}

    table = str(config.get("table", "")).strip()
    query = str(config.get("query", "")).strip().rstrip(";")
    if not table and not query:
        return {}

    credentials_info = config.get("service_account_info")
    credentials = service_account.Credentials.from_service_account_info(dict(credentials_info)) if credentials_info else None
    project_id = str(config.get("project_id") or (credentials.project_id if credentials else "")).strip()
    job_project_id = str(config.get("job_project_id") or project_id).strip() or None
    client = bigquery.Client(project=job_project_id, credentials=credentials)

    id_column = str(config.get("id_column", "CODINT_MA")).strip()
    modcol_column = str(config.get("modcol_column", "COD MOD COL")).strip()
    brand_column = str(config.get("brand_column", "MARCA_MA")).strip()
    base_sql = f"({query})" if query else f"`{table}`"
    sql = f"""
    SELECT
      CAST(`{id_column}` AS STRING) AS id_producto,
      CAST(`{modcol_column}` AS STRING) AS modcol,
      CAST(`{brand_column}` AS STRING) AS marca
    FROM {base_sql}
    WHERE
      CAST(`{id_column}` AS STRING) IN UNNEST(@ids)
      OR CAST(`{modcol_column}` AS STRING) IN UNNEST(@modcols)
    """
    job_config = bigquery.QueryJobConfig(
        use_legacy_sql=False,
        query_parameters=[
            bigquery.ArrayQueryParameter("ids", "STRING", list(ids)),
            bigquery.ArrayQueryParameter("modcols", "STRING", list(modcols)),
        ],
    )
    rows = client.query(
        sql,
        job_config=job_config,
        location=str(config.get("location", "")).strip() or None,
    ).result(timeout=int(config.get("timeout_seconds", 45)))

    by_id: dict[str, dict[str, str]] = {}
    by_modcol: dict[str, dict] = {}
    for row in rows:
        row_dict = dict(row.items())
        sku = str(row_dict.get("id_producto") or "").strip()
        modcol = str(row_dict.get("modcol") or "").strip()
        brand = str(row_dict.get("marca") or "").strip()
        sku_key = normalize_key(sku)
        modcol_key = normalize_key(modcol)
        if sku_key:
            by_id[sku_key] = {"modcol": modcol, "brand": brand}
        if not modcol_key:
            continue
        info = by_modcol.setdefault(modcol_key, {"ids": [], "brand": brand, "modcol": modcol})
        if sku and sku not in info["ids"]:
            info["ids"].append(sku)
        if brand and not info.get("brand"):
            info["brand"] = brand
    return {"by_id": by_id, "by_modcol": by_modcol}


with st.sidebar:
    site_name = st.selectbox("Sitio destino", list(SITES.keys()))
    site = SITES[site_name]
    st.markdown("**Marcas permitidas**")
    st.write(", ".join(site["brands"]))
    selected_brands = st.multiselect(
        "Marcas a afectar",
        site["brands"],
        default=site["brands"][:1],
        help="Se usa MARCA del Revenue. Si falta, se completa desde BigQuery por ID PRODUCTO o MODCOL.",
    )
    use_bigquery = st.checkbox(
        "Completar MODCOL/MARCA con BigQuery",
        value=True,
        help="Consulta ARTI por ID PRODUCTO y MODCOL del Revenue. No reemplaza los IDs de Matrixify.",
    )
    st.caption(f"Vendor: {site['vendor']} | Salida: {site['output']}")
    st.info("El Variant ID y Product ID se conservan desde el Matrixify cargado.")


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
      El Revenue puede traer <code>ID PRODUCTO</code> o <code>MODCOL</code>. Si trae <code>MODCOL</code>,
      BigQuery trae los SKUs asociados y esos SKUs cruzan contra <code>Variant SKU</code> del Matrixify.
      El <code>Variant ID</code> se conserva del Matrixify cargado.
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

with st.expander("Aviso por correo", expanded=False):
    notify_email = st.text_input(
        "Enviar Excel generado a",
        value="",
        placeholder="correo@empresa.com",
        help="Opcional. Requiere configurar [email] en Secrets de Streamlit.",
    )

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

                product_lookup = {}
                if use_bigquery:
                    st.write("Consultando BigQuery para completar SKUs/MODCOL/MARCA...")
                    revenue_ids, revenue_modcols = extract_revenue_lookup_values(revenue_path)
                    product_lookup = load_product_lookup_from_bigquery(tuple(revenue_ids), tuple(revenue_modcols))
                    found_ids = len(product_lookup.get("by_id", {}))
                    found_modcols = len(product_lookup.get("by_modcol", {}))
                    if found_ids or found_modcols:
                        st.write(
                            f"BigQuery encontro {found_ids:,} SKUs y {found_modcols:,} COD MOD COL."
                        )
                    else:
                        st.warning("BigQuery no devolvio datos. Se usara solo lo que venga en el Revenue.")

                st.write("Cruzando Revenue con Matrixify y generando hojas...")
                result = build_discount_workbook(
                    matrixify_path=matrixify_path,
                    revenue_path=revenue_path,
                    output_path=output_path,
                    selected_brands=selected_brands,
                    product_lookup=product_lookup,
                )
                output_bytes = output_path.read_bytes()
                if notify_email.strip():
                    st.write("Enviando correo de aviso...")
                    send_finish_email(
                        to_email=notify_email.strip(),
                        subject=f"Matrixify Revenue generado - {site_name}",
                        body=(
                            "Hola,\n\n"
                            f"El archivo Matrixify Revenue para {site_name} fue generado correctamente.\n"
                            "Se adjunta el Excel final.\n\n"
                            "Mensaje automatico de la app Matrixify Revenue."
                        ),
                        attachment_name=site["output"],
                        attachment_bytes=output_bytes,
                    )
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
