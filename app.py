from __future__ import annotations

import base64
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
    header[data-testid="stHeader"] { display: none; }
    [data-testid="stToolbar"] { display: none; }
    [data-testid="stDecoration"] { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stApp { background: #f4f7fb; color: #031b4e; }
    [data-testid="stSidebar"] {
        background: #eef3fa;
        border-right: 1px solid #dce7f5;
        min-width: 300px !important;
        width: 300px !important;
        transform: translateX(0) !important;
        visibility: visible !important;
    }
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"],
    button[title="Close sidebar"],
    button[title="Open sidebar"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
    [data-testid="stSidebar"] > div:first-child { padding: 64px 24px 28px; }
    .block-container {
        max-width: 1180px;
        padding-top: 30px;
        padding-bottom: 42px;
    }
    .sidebar-logo-card {
        background: #ffffff;
        border: 1px solid #d7e4f5;
        border-radius: 24px;
        padding: 24px 22px;
        margin-bottom: 34px;
        box-shadow: 0 20px 45px rgba(16, 58, 120, 0.08);
        min-height: 92px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .sidebar-logo-card img {
        max-width: 210px;
        width: 100%;
        display: block;
        object-fit: contain;
    }
    .sidebar-label {
        color: #031b4e;
        font-weight: 800;
        margin: 24px 0 10px;
        font-size: 15px;
    }
    .sidebar-brand-card {
        background: #ffffff;
        border: 1px solid #d7e4f5;
        border-radius: 20px;
        padding: 24px;
        margin: 12px 0 28px;
        color: #1328a0;
        font-weight: 900;
        letter-spacing: .02em;
        box-shadow: 0 14px 32px rgba(16, 58, 120, 0.06);
    }
    .sidebar-status-card {
        background: #ffffff;
        border: 1px solid #d7e4f5;
        border-radius: 22px;
        padding: 20px;
        margin-top: 28px;
        box-shadow: 0 16px 36px rgba(16, 58, 120, 0.07);
    }
    .connection-ok {
        background: #e6f8ee;
        color: #064e2a;
        border-radius: 8px;
        padding: 14px 16px;
        margin: 14px 0;
    }
    .top-hero {
        background: #ffffff;
        border: 1px solid #d7e4f5;
        border-radius: 0;
        padding: 28px 32px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        margin-bottom: 36px;
    }
    .eyebrow {
        color: #0086d9;
        font-weight: 900;
        font-size: 12px;
        letter-spacing: .38em;
        margin-bottom: 10px;
    }
    .top-hero h1 {
        color: #031b4e;
        font-size: 32px;
        line-height: 1.05;
        margin: 0 0 10px;
        letter-spacing: 0;
    }
    .top-hero p {
        color: #536b92;
        margin: 0;
        font-size: 15px;
    }
    .hero-right {
        display: flex;
        align-items: center;
        gap: 14px;
        white-space: nowrap;
    }
    .pill {
        border-radius: 999px;
        padding: 9px 16px;
        font-size: 12px;
        font-weight: 900;
        border: 1px solid #b9d7ff;
        background: #eef6ff;
        color: #1238bf;
    }
    .pill.green {
        border-color: #9ee7bf;
        background: #eafaf2;
        color: #007a3d;
    }
    .shopify-mini {
        width: 52px;
        height: 52px;
        object-fit: contain;
    }
    .steps-card {
        background: #ffffff;
        border: 1px solid #d7e4f5;
        border-radius: 28px;
        padding: 22px;
        margin-bottom: 34px;
        box-shadow: 0 22px 48px rgba(16, 58, 120, 0.08);
    }
    .steps-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
    }
    .step-box {
        border: 1px solid #dce7f5;
        background: #f9fbfe;
        border-radius: 18px;
        padding: 22px 18px;
        display: flex;
        align-items: center;
        gap: 16px;
        min-height: 96px;
    }
    .step-box.active {
        background: #eef6ff;
        border-color: #9dc8ff;
    }
    .step-num {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        display: grid;
        place-items: center;
        color: #006bd6;
        font-weight: 900;
        background: #ffffff;
        box-shadow: 0 10px 22px rgba(15, 55, 110, 0.10);
        flex: 0 0 auto;
    }
    .step-title {
        font-weight: 900;
        font-size: 18px;
        color: #031b4e;
        margin-bottom: 4px;
    }
    .step-sub {
        color: #5f7194;
        font-size: 13px;
    }
    .step-badge {
        margin-left: auto;
        border-radius: 999px;
        padding: 7px 11px;
        border: 1px solid #a7e8c4;
        background: #e9fbf1;
        color: #007a3d;
        font-weight: 900;
        font-size: 12px;
    }
    .step-badge.warn {
        border-color: #ffd16a;
        background: #fff8df;
        color: #a76700;
    }
    .step-badge.blue {
        border-color: #a9c9ff;
        background: #eef6ff;
        color: #173bbd;
    }
    .main-card {
        background: #ffffff;
        border: 1px solid #d7e4f5;
        border-radius: 28px;
        padding: 34px 34px 30px;
        margin-bottom: 28px;
        box-shadow: 0 22px 48px rgba(16, 58, 120, 0.06);
    }
    .main-card h2 {
        margin: 0 0 12px;
        color: #031b4e;
        font-size: 28px;
        letter-spacing: 0;
    }
    .muted {
        color: #536b92;
        font-size: 15px;
        margin-bottom: 26px;
    }
    .source-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 16px;
        margin: 24px 0;
    }
    .source-box {
        border: 1px solid #d7e4f5;
        background: #f9fbfe;
        border-radius: 18px;
        padding: 22px;
        min-height: 98px;
    }
    .source-box.active {
        background: #eef6ff;
        border-color: #9dc8ff;
    }
    .source-box.green {
        background: #eafaf2;
        border-color: #9ee7bf;
    }
    .source-box.warn {
        background: #fff8df;
        border-color: #ffd16a;
    }
    .source-title {
        font-weight: 900;
        color: #031b4e;
        margin-bottom: 12px;
    }
    .source-sub {
        color: #5f7194;
        font-size: 14px;
    }
    .status-card {
        background: #ffffff;
        border: 1px solid #d7e4f5;
        border-radius: 22px;
        padding: 22px;
        margin: 22px 0;
    }
    div[data-testid="stFileUploader"] {
        border: 1px dashed #9cc3ff;
        border-radius: 18px;
        padding: 18px;
        background: #fbfdff;
    }
    .stButton button, .stDownloadButton button {
        border-radius: 18px;
        font-weight: 900;
        min-height: 56px;
    }
    .stButton button[kind="primary"] {
        background: #252aaa;
        border-color: #252aaa;
        box-shadow: 0 18px 36px rgba(37,42,170,.24);
    }
    @media (max-width: 900px) {
        .steps-grid, .source-grid { grid-template-columns: 1fr; }
        .top-hero { flex-direction: column; align-items: flex-start; }
    }
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


def bigquery_is_configured() -> bool:
    config = get_bigquery_config()
    enabled = str(config.get("enabled", "true")).strip().lower()
    return enabled not in ("0", "false", "no", "off") and bool(config.get("table") or config.get("query"))


def image_data_uri(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    suffix = file_path.suffix.lower().replace(".", "")
    mime = "jpeg" if suffix in ("jpg", "jpeg") else "png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"


def render_sidebar_logo() -> None:
    logo_src = image_data_uri("forus_logo.png")
    if logo_src:
        st.sidebar.markdown(
            f'<div class="sidebar-logo-card"><img src="{logo_src}" alt="FORUS"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            '<div class="sidebar-logo-card"><h2>FORUS</h2><div>CONSUMER FANATIC</div></div>',
            unsafe_allow_html=True,
        )


def render_top_header(site_name: str) -> None:
    bigquery_badge = "BigQuery obligatorio" if bigquery_is_configured() else "Falta BigQuery"
    matrixify_badge = "IDs Matrixify"
    shopify_html = ""
    shopify_src = image_data_uri("shopify_logo.png")
    if shopify_src:
        shopify_html = f'<img class="shopify-mini" src="{shopify_src}" alt="Shopify">'
    st.markdown(
        f"""
        <div class="top-hero">
          <div>
            <div class="eyebrow">REVENUE DISCOUNT CENTER</div>
            <h1>{site_name} -> Matrixify</h1>
            <p>Genera cargas de descuentos desde COD MOD COL, cruzando BigQuery con el ultimo Matrixify del sitio.</p>
          </div>
          <div class="hero-right">
            <span class="pill">{bigquery_badge}</span>
            <span class="pill green">{matrixify_badge}</span>
            {shopify_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_steps(revenue_loaded: bool, matrixify_loaded: bool, target=st) -> None:
    input_badge = "Actual" if revenue_loaded else "Pend."
    bq_badge = "OK" if bigquery_is_configured() else "Falta"
    validation_badge = "Revisar" if not matrixify_loaded else "OK"
    target.markdown(
        f"""
        <div class="steps-card">
          <div class="steps-grid">
            <div class="step-box active">
              <div class="step-num">1</div>
              <div><div class="step-title">Input</div><div class="step-sub">Archivo comercial</div></div>
              <div class="step-badge blue">{input_badge}</div>
            </div>
            <div class="step-box">
              <div class="step-num">2</div>
              <div><div class="step-title">BigQuery</div><div class="step-sub">MODCOL a SKUs</div></div>
              <div class="step-badge">{bq_badge}</div>
            </div>
            <div class="step-box">
              <div class="step-num">3</div>
              <div><div class="step-title">Validacion</div><div class="step-sub">Vendor y descuentos</div></div>
              <div class="step-badge warn">{validation_badge}</div>
            </div>
            <div class="step-box">
              <div class="step-num">4</div>
              <div><div class="step-title">Salida</div><div class="step-sub">Excel Matrixify</div></div>
              <div class="step-badge blue">Pend.</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_product_lookup_from_bigquery(ids: tuple[str, ...], modcols: tuple[str, ...]) -> dict[str, dict]:
    if not ids and not modcols:
        raise RuntimeError("El Revenue debe traer al menos un COD MOD COL para consultar BigQuery.")
    try:
        from google.cloud import bigquery
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("Faltan dependencias para BigQuery en requirements.txt.") from exc

    config = get_bigquery_config()
    enabled = str(config.get("enabled", "true")).strip().lower()
    if enabled in ("0", "false", "no", "off"):
        raise RuntimeError("BigQuery esta desactivado en Secrets. Para Revenue Automatico es obligatorio.")

    table = str(config.get("table", "")).strip()
    query = str(config.get("query", "")).strip().rstrip(";")
    if not table and not query:
        raise RuntimeError("Falta configurar [bigquery].table o [bigquery].query en Secrets.")

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


render_sidebar_logo()

with st.sidebar:
    st.markdown('<div class="sidebar-label">Sitio destino</div>', unsafe_allow_html=True)
    site_name = st.selectbox("Sitio destino", list(SITES.keys()))
    site = SITES[site_name]
    st.markdown('<div class="sidebar-label">Marca(s) permitidas</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sidebar-brand-card">{", ".join(site["brands"])}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sidebar-label">Operacion</div>', unsafe_allow_html=True)
    selected_brands = st.multiselect(
        "Marcas a afectar",
        site["brands"],
        default=site["brands"][:1],
        help="La marca se trae desde BigQuery usando el COD MOD COL del Revenue.",
    )
    st.markdown(
        '<div class="connection-ok">BigQuery obligatorio para COD MOD COL</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Vendor: {site['vendor']} | Salida: {site['output']}")
    st.markdown(
        f"""
        <div class="sidebar-status-card">
          <div style="font-weight:900;color:#031b4e;margin-bottom:12px;">Reglas de carga</div>
          <div class="connection-ok">Conserva IDs del Matrixify subido</div>
          <div style="color:#6b7894;font-size:13px;">Vendor esperado: {site['vendor']}</div>
          <div style="color:#6b7894;font-size:13px;margin-top:12px;">Salida: {site['output']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


render_top_header(site_name)
steps_placeholder = st.empty()

st.markdown(
    """
    <div class="main-card">
      <h2>Preparar carga de descuentos</h2>
      <div class="muted">Sube el Revenue comercial y el ultimo Matrixify del sitio. La app arma una hoja por campana.</div>
      <div class="source-grid">
        <div class="source-box active">
          <div class="source-title">Revenue comercial</div>
          <div class="source-sub">Trae COD MOD COL y descuentos por campana</div>
        </div>
        <div class="source-box green">
          <div class="source-title">BigQuery maestro</div>
          <div class="source-sub">Convierte COD MOD COL en SKUs y marca</div>
        </div>
        <div class="source-box warn">
          <div class="source-title">Control de precios</div>
          <div class="source-sub">Sin descuento: precio original y Compare At vacio</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

upload_left, upload_right = st.columns(2)
with upload_left:
    revenue_file = st.file_uploader("1. Subir Revenue / input comercial", type=["xlsx"], key="revenue")
with upload_right:
    matrixify_file = st.file_uploader(
        f"2. Subir ultimo catalogo Matrixify de {site_name}",
        type=["xlsx"],
        key="matrixify",
        help="Debe corresponder al mismo sitio destino para conservar Product ID y Variant ID.",
    )

render_steps(revenue_file is not None, matrixify_file is not None, target=steps_placeholder)

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
                ["Inicio", "2026-06-06 20:00", "2026-06-15 10:00", "2026-06-01 10:00"],
                ["Fin", "2026-06-07 23:59", "2026-06-30 23:59", "2026-06-30 23:59"],
                ["Cod Mod Col", "CLB 40", "SALE", "RESTO DEL MES"],
                ["MODELO-COLOR", "40%", "30%", "0%"],
            ]
        ).rename(columns={0: "", 1: "Campana 1", 2: "Campana 2", 3: "Campana 3"}),
        hide_index=True,
        use_container_width=True,
    )

st.markdown(
    f"""
    <div class="status-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
        <div style="font-size:20px;font-weight:900;color:#031b4e;">Estado de preparacion</div>
        <span class="pill">Fuentes listas</span>
      </div>
      <div class="source-grid">
        <div class="source-box">
          <div class="source-title">Revenue</div>
          <div class="source-sub">Input de descuentos comercial</div>
        </div>
        <div class="source-box">
          <div class="source-title">Cruce BigQuery</div>
          <div class="source-sub">Obligatorio para convertir MODCOL en SKUs</div>
        </div>
        <div class="source-box">
          <div class="source-title">Archivo final</div>
          <div class="source-sub">{site["output"]}</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
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
    if not bigquery_is_configured():
        st.error("BigQuery es obligatorio. Configura [bigquery] en Secrets antes de generar.")
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

                st.write("Consultando BigQuery para convertir COD MOD COL en SKUs/MARCA...")
                revenue_ids, revenue_modcols = extract_revenue_lookup_values(revenue_path)
                if not revenue_modcols:
                    st.error("El Revenue debe traer la columna COD MOD COL. Ya no se procesa solo con SKU.")
                    st.stop()
                product_lookup = load_product_lookup_from_bigquery(tuple(revenue_ids), tuple(revenue_modcols))
                found_ids = len(product_lookup.get("by_id", {}))
                found_modcols = len(product_lookup.get("by_modcol", {}))
                if not found_ids or not found_modcols:
                    st.error(
                        "BigQuery no devolvio SKUs para los COD MOD COL del Revenue. "
                        "Revisa que los codigos existan en ARTI antes de generar."
                    )
                    st.stop()
                missing_bq_modcols = [
                    modcol
                    for modcol in revenue_modcols
                    if normalize_key(modcol) not in product_lookup.get("by_modcol", {})
                ]
                if missing_bq_modcols:
                    st.error(
                        "Hay COD MOD COL del Revenue que no existen en BigQuery/ARTI. "
                        "Corrige estos codigos antes de generar: "
                        + ", ".join(missing_bq_modcols[:30])
                        + ("..." if len(missing_bq_modcols) > 30 else "")
                    )
                    st.stop()
                st.write(f"BigQuery encontro {found_ids:,} SKUs y {found_modcols:,} COD MOD COL.")

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
