from __future__ import annotations

import io
import json
import smtplib
import tempfile
from email.message import EmailMessage
from datetime import date, time
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

import pandas as pd
import streamlit as st

from coupon_config import QUICK_TEMPLATES
from coupon_parser import default_coupon_data, parse_bulk_codes, parse_coupon_text, unique_sites
from coupon_validation import validate_coupon_data
from compare_at_best_wins import PRICE_BASIS_COMPARE_AT_BEST_WINS, PRICE_BASIS_CURRENT, build_preview_rows
from generar_matrixify_descuentos import (
    build_discount_workbook,
    extract_revenue_lookup_values,
    normalize_key,
    read_matrixify,
)
from shopify_coupon_service import create_coupon_for_multiple_sites
from ui_kit import ancho, aviso, encabezado, fila_kpis, imagen_data_uri, inject_css, panel, seccion


SITES = {
    "Rockford.pe": {
        "shop_key": "rockford",
        "brands": ["COLUMBIA", "ROCKFORD", "PATAGONIA", "SOREL", "MOUNTAIN HARDWEAR"],
        "output": "matrixify_revenue_rockford.xlsx",
    },
    "Columbia.pe": {
        "shop_key": "columbia",
        "brands": ["COLUMBIA"],
        "output": "matrixify_revenue_columbia.xlsx",
    },
    "Hushpuppies.pe": {
        "shop_key": "hushpuppies",
        "brands": ["HUSH PUPPIES"],
        "output": "matrixify_revenue_hushpuppies.xlsx",
    },
    "Vans.pe": {
        "shop_key": "vans",
        "brands": ["VANS"],
        "output": "matrixify_revenue_vans.xlsx",
    },
    "Supermall.pe": {
        "shop_key": "supermall",
        "brands": ["COLUMBIA", "HUSH PUPPIES", "ROCKFORD", "PATAGONIA", "SOREL", "MOUNTAIN HARDWEAR", "VANS"],
        "output": "matrixify_revenue_supermall.xlsx",
    },
}


st.set_page_config(page_title="Matrixify Revenue", layout="wide")

inject_css()


def save_upload(uploaded_file, folder: Path) -> Path:
    path = folder / uploaded_file.name
    path.write_bytes(uploaded_file.getbuffer())
    return path


def can_read_matrixify(path: Path) -> tuple[bool, str]:
    try:
        read_matrixify(path)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def can_read_revenue(path: Path) -> tuple[bool, str]:
    try:
        _ids, modcols = extract_revenue_lookup_values(path)
        if not modcols:
            return False, "No encontre COD MOD COL con valores."
        return True, ""
    except Exception as exc:
        return False, str(exc)


def resolve_uploaded_roles(revenue_path: Path, matrixify_path: Path) -> tuple[Path, Path, list[str]]:
    messages: list[str] = []
    revenue_ok, revenue_error = can_read_revenue(revenue_path)
    matrixify_ok, matrixify_error = can_read_matrixify(matrixify_path)
    if revenue_ok and matrixify_ok:
        return revenue_path, matrixify_path, messages

    swapped_revenue_ok, _swapped_revenue_error = can_read_revenue(matrixify_path)
    swapped_matrixify_ok, _swapped_matrixify_error = can_read_matrixify(revenue_path)
    if swapped_revenue_ok and swapped_matrixify_ok:
        messages.append(
            "Detecte que los archivos estaban invertidos: use el archivo Matrixify como catalogo y el archivo Revenue como input."
        )
        return matrixify_path, revenue_path, messages

    if not revenue_ok:
        raise ValueError(
            "El primer archivo no parece ser Revenue/input comercial. "
            "Debe traer COD MOD COL. Detalle: " + revenue_error
        )
    if not matrixify_ok:
        raise ValueError(
            "El segundo archivo no parece ser el ultimo Matrixify del sitio. "
            "Debe traer ID, Handle, Variant SKU, Variant Price y Variant Compare At Price. "
            "Detalle: " + matrixify_error
        )
    return revenue_path, matrixify_path, messages


def excel_bytes_from_df(df: pd.DataFrame, sheet_name: str = "Hoja1") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.book[sheet_name]
        ws.freeze_panes = "A2"
        for column_cells in ws.columns:
            ws.column_dimensions[column_cells[0].column_letter].width = 24
    buffer.seek(0)
    return buffer.getvalue()


def read_coupon_codes_upload(uploaded_file) -> list[str]:
    if uploaded_file is None:
        return []
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, dtype=object)
    else:
        df = pd.read_excel(uploaded_file, dtype=object)
    if df.empty:
        return []
    preferred = None
    for column in df.columns:
        if str(column).strip().lower() in ("codigo", "codigo cupon", "cupon", "coupon", "code"):
            preferred = column
            break
    column = preferred or df.columns[0]
    return parse_bulk_codes("\n".join(df[column].dropna().map(str).tolist()))


def build_input_template_bytes() -> bytes:
    template = pd.DataFrame(
        [
            ["Inicio", "2026-06-06 20:00", "2026-06-15 10:00", "2026-06-01 10:00"],
            ["Fin", "2026-06-07 23:59", "2026-06-30 23:59", "2026-06-30 23:59"],
            ["Cod Mod Col", "CLB 40", "SALE", "RESTO DEL MES"],
            ["ABC123-001", "40%", "30%", "0%"],
        ]
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        template.to_excel(writer, index=False, header=False, sheet_name="Formato Revenue")
        ws = writer.book["Formato Revenue"]
        ws.freeze_panes = "A4"
        for column_cells in ws.columns:
            ws.column_dimensions[column_cells[0].column_letter].width = 24
    buffer.seek(0)
    return buffer.getvalue()


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


def get_shopify_config(shop_key: str) -> dict:
    def as_plain_dict(value) -> dict:
        if not value:
            return {}
        try:
            return dict(value)
        except Exception:
            return {}

    try:
        for section in ("shopify_sites", "shopify"):
            config = as_plain_dict(st.secrets.get(section, {}))
            site_config = as_plain_dict(config.get(shop_key, {}))
            if site_config:
                return site_config
            if config.get("shop_domain") or config.get("access_token") or config.get("admin_access_token"):
                return config
    except Exception:
        return {}
    return {}


def shopify_config_status(shop_key: str) -> dict:
    config = get_shopify_config(shop_key)
    token = config.get("access_token") or config.get("admin_access_token")
    return {
        "shop_domain": bool(str(config.get("shop_domain", "")).strip()),
        "admin_access_token": bool(str(token or "").strip()),
        "api_version": str(config.get("api_version", "2026-04")).strip(),
        "function_handle": bool(str(config.get("compare_at_best_wins_function_handle", "")).strip()),
        "function_id": bool(str(config.get("compare_at_best_wins_function_id", "")).strip()),
    }


def shopify_is_configured(shop_key: str) -> bool:
    config = get_shopify_config(shop_key)
    token = config.get("access_token") or config.get("admin_access_token")
    return bool(str(config.get("shop_domain", "")).strip() and str(token or "").strip())


def shopify_function_id(shop_key: str, function_key: str = "compare_at_best_wins_function_id") -> str:
    config = get_shopify_config(shop_key)
    return str(config.get(function_key, "")).strip()


def shopify_function_handle(shop_key: str, function_key: str = "compare_at_best_wins_function_handle") -> str:
    config = get_shopify_config(shop_key)
    return str(config.get(function_key, "")).strip()


def shopify_graphql(shop_key: str, query: str, variables: dict | None = None) -> dict:
    config = get_shopify_config(shop_key)
    shop_domain = str(config.get("shop_domain", "")).strip().replace("https://", "").replace("http://", "").strip("/")
    token = str(config.get("access_token") or config.get("admin_access_token") or "").strip()
    api_version = str(config.get("api_version", "2026-04")).strip()
    if not shop_domain or not token:
        raise RuntimeError(f"Faltan secrets de Shopify para [{shop_key}]: shop_domain y admin_access_token.")

    url = f"https://{shop_domain}/admin/api/{api_version}/graphql.json"
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Shopify respondio {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"No pude conectar con Shopify: {exc.reason}") from exc
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return data.get("data", {})


@st.cache_data(ttl=600, show_spinner=False)
def load_shopify_segments(shop_key: str) -> list[dict]:
    query = """
    query CustomerSegments {
      segments(first: 50) {
        nodes {
          id
          name
        }
      }
    }
    """
    try:
        data = shopify_graphql(shop_key, query)
        return data.get("segments", {}).get("nodes", [])
    except Exception:
        return []


def build_iso_datetime(date_value, time_value) -> str:
    return f"{date_value.isoformat()}T{time_value.strftime('%H:%M:%S')}-05:00"


def create_shopify_coupon(shop_key: str, payload: dict) -> dict:
    if payload.get("functionHandle") or payload.get("functionId"):
        return create_shopify_app_coupon(shop_key, payload)
    mutation = """
    mutation CreateDiscountCode($basicCodeDiscount: DiscountCodeBasicInput!) {
      discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
        codeDiscountNode {
          id
          codeDiscount {
            ... on DiscountCodeBasic {
              title
              startsAt
              endsAt
              codes(first: 10) {
                nodes {
                  code
                }
              }
            }
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    data = shopify_graphql(shop_key, mutation, {"basicCodeDiscount": payload})
    result = data.get("discountCodeBasicCreate", {})
    errors = result.get("userErrors") or []
    if errors:
        messages = "; ".join(error.get("message", "") for error in errors)
        raise RuntimeError(messages or "Shopify no permitio crear el cupon.")
    return result


def create_shopify_app_coupon(shop_key: str, payload: dict) -> dict:
    mutation = """
    mutation CreateDiscountCodeApp($codeAppDiscount: DiscountCodeAppInput!) {
      discountCodeAppCreate(codeAppDiscount: $codeAppDiscount) {
        codeAppDiscount {
          discountId
          title
          startsAt
          endsAt
          status
          usageLimit
          appDiscountType {
            functionId
          }
          codes(first: 10) {
            nodes {
              code
            }
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    data = shopify_graphql(shop_key, mutation, {"codeAppDiscount": payload})
    result = data.get("discountCodeAppCreate", {})
    errors = result.get("userErrors") or []
    if errors:
        messages = "; ".join(error.get("message", "") for error in errors)
        raise RuntimeError(messages or "Shopify no permitio crear el cupon App.")
    return result


def plain_secret(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {key: plain_secret(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain_secret(item) for item in value]
    if hasattr(value, "items"):
        return {key: plain_secret(item) for key, item in value.items()}
    return value


def clean_auth_text(value) -> str:
    text = str(value or "")
    for char in ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060", "\u00a0"):
        text = text.replace(char, "")
    return text.strip()


def get_auth_config() -> dict:
    try:
        secrets = plain_secret(st.secrets)
        config = plain_secret(secrets.get("auth", {})) if isinstance(secrets, dict) else {}
        if config:
            return config
        users = plain_secret(secrets.get("auth.users", {})) if isinstance(secrets, dict) else {}
        if users:
            return {"users": users}
        root_users = plain_secret(secrets.get("users", {})) if isinstance(secrets, dict) else {}
        if root_users:
            return {"users": root_users}
        return {}
    except Exception:
        return {}


def valid_login(email: str, password: str) -> bool:
    config = get_auth_config()
    login_email = clean_auth_text(email).lower()
    login_password = clean_auth_text(password)
    user_list = config.get("users_list", [])
    if isinstance(user_list, list):
        for user in user_list:
            if not isinstance(user, dict):
                continue
            stored_email = clean_auth_text(user.get("email", "")).lower()
            stored_password = clean_auth_text(user.get("password", ""))
            if stored_email == login_email and stored_password == login_password:
                return True
    users_config = config.get("users", {})
    if isinstance(users_config, list):
        for user in users_config:
            if not isinstance(user, dict):
                continue
            stored_email = clean_auth_text(user.get("email", "")).lower()
            stored_password = clean_auth_text(user.get("password", ""))
            if stored_email == login_email and stored_password == login_password:
                return True
    users = dict(users_config) if hasattr(users_config, "items") else {}
    if users:
        normalized_users = {clean_auth_text(key).lower(): clean_auth_text(value) for key, value in users.items()}
        return normalized_users.get(login_email) == login_password
    allowed = [clean_auth_text(value).lower() for value in config.get("allowed_emails", [])]
    shared_password = clean_auth_text(config.get("password", ""))
    return bool(login_email in allowed and login_password == shared_password)


def render_login() -> None:
    inject_css(login=True)
    forus_src = imagen_data_uri("forus_logo.png")
    shopify_src = imagen_data_uri("shopify_logo.png")
    forus_html = (
        '<img class="login-logo" src="' + forus_src + '" alt="FORUS">'
        if forus_src
        else '<div class="login-title">FORUS</div>'
    )
    shopify_html = (
        '<img class="login-shopify" src="' + shopify_src + '" alt="Shopify">' if shopify_src else ""
    )
    st.markdown(
        '<div class="login-hero">'
        '<div class="login-brand-row">' + forus_html + '<div class="login-divider"></div>' + shopify_html + "</div>"
        '<div class="login-title">Revenue Control Center</div>'
        '<div class="login-sub">Cupones y descuentos para las tiendas Shopify</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        mensaje = st.empty()
        email = st.text_input("Correo electronico", placeholder="nombre@forus.pe")
        password = st.text_input("Contrasena", type="password")
        enviado = st.form_submit_button("Ingresar", type="primary")

    if not get_auth_config():
        mensaje.markdown(
            '<div class="login-message">Configura usuarios en Secrets para habilitar el ingreso.</div>',
            unsafe_allow_html=True,
        )
    elif enviado:
        if valid_login(email, password):
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = clean_auth_text(email).lower()
            st.rerun()
        else:
            mensaje.markdown(
                '<div class="login-message">Correo o contrasena incorrectos.</div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="login-foot">Acceso exclusivo para personal autorizado</div>',
        unsafe_allow_html=True,
    )



def render_sidebar_logo() -> None:
    logo_src = imagen_data_uri("forus_logo.png")
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


def render_sidebar_identidad() -> None:
    """Tarjeta de usuario y cierre de sesion, arriba del menu."""
    correo = str(st.session_state.get("user_email", "")).strip()
    nombre = correo.split("@")[0].replace(".", " ").replace("_", " ").title() if correo else "Usuario"
    partes = [parte for parte in nombre.split() if parte]
    iniciales = "".join(parte[0] for parte in partes[:2]).upper() or "US"
    st.sidebar.markdown(
        '<div class="nav-card user-card">'
        '<div class="user-avatar">' + iniciales + "</div>"
        "<div>"
        '<div class="user-rol">Administrador</div>'
        '<div class="user-nombre">' + nombre + "</div>"
        '<div class="user-mail">' + correo + "</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Cerrar sesion", **ancho()):
        for clave in ("authenticated", "user_email"):
            st.session_state.pop(clave, None)
        st.rerun()


def render_top_header(site_name: str) -> None:
    bigquery_badge = "BigQuery obligatorio" if bigquery_is_configured() else "Falta BigQuery"
    matrixify_badge = "IDs Matrixify"
    shopify_html = ""
    shopify_src = imagen_data_uri("shopify_logo.png")
    if shopify_src:
        shopify_html = f'<img class="shopify-mini" src="{shopify_src}" alt="Shopify">'
    st.markdown(
        f"""
        <div class="top-hero">
          <div>
            <div class="eyebrow">REVENUE DISCOUNT CENTER</div>
            <h1>{site_name}<span class="hero-arrow">&rsaquo;</span>Matrixify</h1>
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
              <div><div class="step-title">Validacion</div><div class="step-sub">Marca y descuentos</div></div>
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
def load_product_lookup_from_bigquery(
    ids: tuple[str, ...],
    modcols: tuple[str, ...],
    selected_brands: tuple[str, ...] = (),
) -> dict[str, dict]:
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

    def pick_schema_column(schema_names: list[str], configured: str, candidates: list[str], label: str) -> str:
        by_normalized = {normalize_key(name): name for name in schema_names}
        for candidate in [configured, *candidates]:
            if not candidate:
                continue
            found = by_normalized.get(normalize_key(candidate))
            if found:
                return found
        sample = ", ".join(schema_names[:25])
        raise RuntimeError(f"No encontre la columna {label} en BigQuery. Columnas disponibles: {sample}")

    id_column = str(config.get("id_column", "CODINT_MA")).strip()
    modcol_column = str(config.get("modcol_column", "COD MOD COL")).strip()
    brand_column = str(config.get("brand_column", "MARCA_MA")).strip()
    modcol_expr = f"CAST(`{modcol_column}` AS STRING)"
    if table and not query:
        schema_names = [field.name for field in client.get_table(table).schema]
        schema_by_normalized = {normalize_key(name): name for name in schema_names}
        id_column = pick_schema_column(
            schema_names,
            id_column,
            ["CODINT_MA", "ID PRODUCTO", "SKU", "VARIANT SKU", "CODIGO", "CODIGO_SKU"],
            "SKU / ID PRODUCTO",
        )
        modcol_candidates = ["COD MOD COL", "COD_MOD_COL", "MODCOL", "MOD-COL", "MOD COL", "MODELO COLOR", "MODELO_COLOR"]
        try:
            modcol_column = pick_schema_column(schema_names, modcol_column, modcol_candidates, "COD MOD COL")
            modcol_expr = f"CAST(`{modcol_column}` AS STRING)"
        except RuntimeError:
            model_column = schema_by_normalized.get("CODMODMA")
            color_column = schema_by_normalized.get("CODCOLMA")
            if not model_column or not color_column:
                sample = ", ".join(schema_names[:25])
                raise RuntimeError(f"No encontre como armar COD MOD COL en BigQuery. Columnas disponibles: {sample}")
            color_expr = (
                f"CASE "
                f"WHEN REGEXP_CONTAINS(CAST(`{color_column}` AS STRING), r'^\\d+$') "
                f"THEN LPAD(CAST(`{color_column}` AS STRING), 3, '0') "
                f"ELSE CAST(`{color_column}` AS STRING) "
                f"END"
            )
            modcol_expr = f"CONCAT(CAST(`{model_column}` AS STRING), '-', {color_expr})"
        brand_column = pick_schema_column(
            schema_names,
            brand_column,
            ["MARCA_MA", "MARCA", "BRAND", "VENDOR"],
            "MARCA",
        )
    base_sql = f"({query})" if query else f"`{table}`"
    sql = f"""
    SELECT
      CAST(`{id_column}` AS STRING) AS id_producto,
      {modcol_expr} AS modcol,
      CAST(`{brand_column}` AS STRING) AS marca
    FROM {base_sql}
    WHERE
      REGEXP_REPLACE(UPPER(CAST(`{id_column}` AS STRING)), r'[^A-Z0-9]', '') IN UNNEST(@ids)
      OR REGEXP_REPLACE(UPPER({modcol_expr}), r'[^A-Z0-9]', '') IN UNNEST(@modcols)
    """
    job_config = bigquery.QueryJobConfig(
        use_legacy_sql=False,
        query_parameters=[
            bigquery.ArrayQueryParameter("ids", "STRING", [normalize_key(value) for value in ids]),
            bigquery.ArrayQueryParameter("modcols", "STRING", [normalize_key(value) for value in modcols]),
        ],
    )
    rows = client.query(
        sql,
        job_config=job_config,
        location=str(config.get("location", "")).strip() or None,
    ).result(timeout=int(config.get("timeout_seconds", 45)))

    by_id: dict[str, dict[str, str]] = {}
    by_modcol: dict[str, dict] = {}
    selected_norm = {normalize_key(brand) for brand in selected_brands}
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
        info = by_modcol.setdefault(modcol_key, {"ids": [], "brand": "", "modcol": modcol, "brand_counts": {}})
        if sku and sku not in info["ids"]:
            info["ids"].append(sku)
        if brand:
            counts = info.setdefault("brand_counts", {})
            brand_norm = normalize_key(brand)
            counts[brand_norm] = {
                "brand": brand,
                "count": counts.get(brand_norm, {}).get("count", 0) + 1,
            }
            if selected_norm and brand_norm in selected_norm:
                info["brand"] = brand
            elif not info.get("brand"):
                info["brand"] = brand
    for info in by_modcol.values():
        counts = info.get("brand_counts", {})
        if counts and not (selected_norm and normalize_key(info.get("brand")) in selected_norm):
            best = max(counts.values(), key=lambda item: item["count"])
            info["brand"] = best["brand"]
        for sku in info.get("ids", []):
            sku_key = normalize_key(sku)
            if sku_key and info.get("brand"):
                by_id.setdefault(sku_key, {"modcol": info.get("modcol", ""), "brand": ""})
                by_id[sku_key]["brand"] = info["brand"]
                by_id[sku_key]["modcol"] = info.get("modcol", by_id[sku_key].get("modcol", ""))
    return {"by_id": by_id, "by_modcol": by_modcol}


if not st.session_state.get("authenticated"):
    render_login()
    st.stop()


render_sidebar_logo()
render_sidebar_identidad()

with st.sidebar:
    st.markdown('<div class="sidebar-label">Modulo</div>', unsafe_allow_html=True)
    module = st.radio(
        "Modulo",
        ["Carga de descuentos", "Generar cupones"],
        label_visibility="collapsed",
    )

    st.markdown('<div class="sidebar-label">Sitio activo</div>', unsafe_allow_html=True)
    site_name = st.selectbox("Sitio activo", list(SITES.keys()), label_visibility="collapsed")
    site = SITES[site_name]

    chips = "".join('<span class="marca-chip">' + marca + "</span>" for marca in site["brands"])
    st.markdown('<div class="sidebar-label">Marcas del sitio</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-card"><div class="marca-chip-row">' + chips + "</div></div>", unsafe_allow_html=True)

    if module == "Carga de descuentos":
        st.markdown('<div class="sidebar-label">Operacion</div>', unsafe_allow_html=True)
        selected_brands = st.multiselect(
            "Marcas a afectar",
            site["brands"],
            default=site["brands"][:1],
            help="La marca se trae desde BigQuery usando el COD MOD COL del Revenue.",
        )
        conectado = bigquery_is_configured()
        st.markdown(
            '<div class="estado-pill' + ("" if conectado else " warn") + '">'
            '<span class="estado-punto"></span>'
            + ("BigQuery conectado" if conectado else "Falta configurar BigQuery")
            + "</div>",
            unsafe_allow_html=True,
        )
        st.caption("Salida: " + site["output"])
    else:
        selected_brands = list(site["brands"])
        conectado = shopify_is_configured(site["shop_key"])
        st.markdown(
            '<div class="estado-pill' + ("" if conectado else " warn") + '">'
            '<span class="estado-punto"></span>'
            + ("Shopify conectado" if conectado else "Falta token de Shopify")
            + "</div>",
            unsafe_allow_html=True,
        )



def a_fecha(valor, defecto=None):
    """Convierte 'YYYY-MM-DD' en date, tolerando basura."""
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except Exception:
        return defecto or date.today()


def a_hora(valor, defecto_hora: int = 0, defecto_min: int = 0):
    """Convierte 'HH:MM' en time, tolerando basura."""
    try:
        partes = str(valor).strip().split(":")
        return time(int(partes[0]), int(partes[1]) if len(partes) > 1 else 0)
    except Exception:
        return time(defecto_hora, defecto_min)


def bloque_vigencia(data: dict) -> None:
    """Fecha y hora juntas: un bloque para el inicio y otro para el fin."""
    inicio_col, fin_col = st.columns(2)

    with inicio_col:
        st.markdown('<div class="rango-tag">Inicio de la vigencia</div>', unsafe_allow_html=True)
        dia_col, hora_col = st.columns([1.35, 1])
        fecha_inicio = dia_col.date_input(
            "Dia de inicio",
            value=a_fecha(data.get("fechaInicio")),
            format="DD/MM/YYYY",
            key="vigencia_fecha_inicio",
        )
        hora_inicio = hora_col.time_input(
            "Hora de inicio",
            value=a_hora(data.get("horaInicio"), 0, 0),
            step=300,
            key="vigencia_hora_inicio",
        )

    with fin_col:
        st.markdown('<div class="rango-tag">Fin de la vigencia</div>', unsafe_allow_html=True)
        dia_col, hora_col = st.columns([1.35, 1])
        fecha_fin = dia_col.date_input(
            "Dia de fin",
            value=a_fecha(data.get("fechaFin")),
            format="DD/MM/YYYY",
            min_value=fecha_inicio,
            key="vigencia_fecha_fin",
        )
        hora_fin = hora_col.time_input(
            "Hora de fin",
            value=a_hora(data.get("horaFin"), 23, 59),
            step=300,
            key="vigencia_hora_fin",
        )

    data["fechaInicio"] = fecha_inicio.isoformat()
    data["horaInicio"] = hora_inicio.strftime("%H:%M")
    data["fechaFin"] = fecha_fin.isoformat()
    data["horaFin"] = hora_fin.strftime("%H:%M")

    dias = (fecha_fin - fecha_inicio).days + 1
    duracion = "mismo dia" if dias <= 1 else str(dias) + " dias"
    st.markdown(
        '<div class="rango-resumen">Del '
        + fecha_inicio.strftime("%d/%m/%Y")
        + " a las "
        + data["horaInicio"]
        + " hasta el "
        + fecha_fin.strftime("%d/%m/%Y")
        + " a las "
        + data["horaFin"]
        + "  &middot;  "
        + duracion
        + "</div>",
        unsafe_allow_html=True,
    )


CLAVES_WIDGETS_CUPON = (
    "stable_codigo",
    "stable_nombre",
    "stable_tipo",
    "stable_valor",
    "stable_price_basis",
    "stable_minimo",
    "stable_tope",
    "stable_limite",
    "stable_aplica",
    "stable_once",
    "stable_comb_prod",
    "stable_comb_order",
    "stable_comb_ship",
    "stable_selected_sites",
    "stable_function_message",
    "vigencia_fecha_inicio",
    "vigencia_fecha_fin",
    "vigencia_hora_inicio",
    "vigencia_hora_fin",
)


def reiniciar_widgets_cupon() -> None:
    """Borra las keys de los widgets del cupon.

    Streamlit ignora el parametro `value=` cuando la key ya existe en session_state.
    Sin esto, "Interpretar promocion" parseaba bien pero los campos seguian mostrando
    lo anterior. Al borrar las keys, cada widget vuelve a leer el valor del dato.
    """
    for clave in CLAVES_WIDGETS_CUPON:
        st.session_state.pop(clave, None)


def render_coupon_builder_stable(site_name: str, selected_site: dict) -> None:
    shop_key = selected_site["shop_key"]
    if "coupon_data" not in st.session_state:
        st.session_state["coupon_data"] = default_coupon_data()
    if "coupon_results" not in st.session_state:
        st.session_state["coupon_results"] = []

    head_left, head_right = st.columns([3, 1])
    with head_left:
        encabezado(
            "Smart Coupon Builder",
            "Crea cupones Shopify para varias tiendas desde una sola pantalla.",
            chip="CUPONES",
        )
    with head_right:
        st.write("")
        if st.button("Nuevo cupon", type="primary", **ancho()):
            st.session_state["coupon_data"] = default_coupon_data()
            st.session_state["coupon_results"] = []
            st.session_state["promotion_text"] = ""
            reiniciar_widgets_cupon()
            st.rerun()

    mode = st.radio(
        "Metodo de creacion",
        ["Individual", "Masivo"],
        horizontal=True,
        key="coupon_creation_mode_stable",
    )
    st.session_state["coupon_data"]["creationMode"] = mode

    seccion("1", "Describe la promocion", "Escribe la instruccion y la app completa los campos. Despues puedes editar todo.")
    prompt_col, interpret_col = st.columns([4.4, 1.2])
    with prompt_col:
        promotion_text = st.text_area(
            "Describe la promocion",
            value=st.session_state.get("promotion_text", ""),
            placeholder=(
                "Crear cupon CLUBTOYOTA20 con 20% de descuento para BCP, BBVA e Interbank "
                "en Columbia, Hushpuppies y Rockford. Valido hoy desde 00:00 hasta 23:59, "
                "una vez por cliente."
            ),
            height=110,
            key="promotion_text",
            label_visibility="collapsed",
        )
    with interpret_col:
        interpret_clicked = st.button("Interpretar", type="primary", **ancho())
        with st.popover("Plantillas", **ancho()):
            for chip, template in QUICK_TEMPLATES.items():
                if st.button(chip, key="stable_template_" + chip, **ancho()):
                    st.session_state["promotion_text"] = template
                    st.rerun()

    if interpret_clicked:
        with st.spinner("Interpretando promocion..."):
            interpretado = parse_coupon_text(promotion_text)
            interpretado["creationMode"] = mode
            st.session_state["coupon_data"] = interpretado
            st.session_state["coupon_results"] = []
            st.session_state["promocion_interpretada"] = True
            reiniciar_widgets_cupon()
        st.rerun()

    if st.session_state.pop("promocion_interpretada", False):
        st.success("Promocion interpretada. Revisa los campos antes de crear.")

    data = st.session_state["coupon_data"].copy()
    data["creationMode"] = mode

    if mode == "Masivo":
        seccion("1B", "Codigos masivos", "Un codigo por linea o un Excel/CSV. Todos comparten la misma configuracion.")
        bulk_col, upload_col = st.columns([1.5, 1])
        with bulk_col:
            bulk_text = st.text_area(
                "Codigos de cupon",
                value="\n".join(data.get("couponCodes") or ([data.get("codigoCupon")] if data.get("codigoCupon") else [])),
                height=120,
                placeholder="TATI15\nJUAN15\nMARIA15",
                key="stable_bulk_codes",
            )
        with upload_col:
            bulk_file = st.file_uploader("Cargar codigos Excel/CSV", type=["xlsx", "csv"], key="coupon_bulk_file_stable")
            uploaded_codes = read_coupon_codes_upload(bulk_file) if bulk_file else []
        bulk_codes = uploaded_codes or parse_bulk_codes(bulk_text)
        data["couponCodes"] = bulk_codes
        if bulk_codes:
            data["codigoCupon"] = bulk_codes[0]
            data["nombreInterno"] = data.get("nombreInterno") or "Campana " + bulk_codes[0]
    else:
        data["couponCodes"] = [data.get("codigoCupon", "").strip().upper()] if data.get("codigoCupon") else []

    discount_label = (
        f"{data['valorDescuento']:.0f}%"
        if data["tipoDescuento"] == "Porcentaje"
        else f"S/ {data['valorDescuento']:.2f}"
    )
    min_label = "S/ 0.00" if float(data["compraMinima"] or 0) == 0 else f"S/ {float(data['compraMinima']):,.2f}"
    enabled_sites = [site_cfg for site_cfg in unique_sites() if site_cfg["enabled"]]

    fila_kpis(
        [
            ("Codigo", data["codigoCupon"] or "-", str(len(data.get("couponCodes") or [])) + " codigo(s)"),
            ("Descuento", discount_label, data["tipoDescuento"]),
            ("Tiendas", str(len(data["selectedSites"])), "de " + str(len(enabled_sites)) + " disponibles"),
            ("Vigencia", data["fechaInicio"], data["horaInicio"] + " a " + data["horaFin"]),
        ]
    )

    seccion("2", "Configuracion del cupon", "Cada bloque agrupa un tipo de decision. Obligatorios: codigo, valor y tiendas.")
    tab_descuento, tab_vigencia, tab_limites, tab_tiendas = st.tabs(
        ["Descuento", "Vigencia", "Restricciones", "Tiendas"]
    )

    with tab_descuento:
        izq, der = st.columns(2)
        with izq:
            data["codigoCupon"] = st.text_input("Codigo del cupon", value=data["codigoCupon"], key="stable_codigo")
            data["tipoDescuento"] = st.selectbox(
                "Tipo de descuento",
                ["Porcentaje", "Monto fijo"],
                index=["Porcentaje", "Monto fijo"].index(data.get("tipoDescuento", "Porcentaje")),
                key="stable_tipo",
            )
        with der:
            data["nombreInterno"] = st.text_input("Nombre interno", value=data["nombreInterno"], key="stable_nombre")
            data["valorDescuento"] = st.number_input(
                "Valor del descuento",
                min_value=0.0,
                value=float(data["valorDescuento"]),
                step=1.0,
                key="stable_valor",
            )

        data["priceBasis"] = st.selectbox(
            "Base de calculo",
            [PRICE_BASIS_CURRENT, PRICE_BASIS_COMPARE_AT_BEST_WINS],
            format_func=lambda value: "Price actual" if value == PRICE_BASIS_CURRENT else "Compare At Price - Best Wins",
            index=[PRICE_BASIS_CURRENT, PRICE_BASIS_COMPARE_AT_BEST_WINS].index(
                data.get("priceBasis", PRICE_BASIS_CURRENT)
            ),
            key="stable_price_basis",
        )
        if data["priceBasis"] == PRICE_BASIS_COMPARE_AT_BEST_WINS:
            aviso(
                "El cupon se calcula desde el precio original. Si el producto ya tiene una promocion mejor, "
                "se conserva el precio mas bajo. Sin Compare At Price se usa el Variant Price."
            )
            data["missingCompareAtBehavior"] = "use_current_price"
            data["functionMessage"] = st.text_input(
                "Mensaje del descuento",
                value=data.get("functionMessage", "Se aplico el mejor precio disponible"),
                key="stable_function_message",
            )

    with tab_vigencia:
        bloque_vigencia(data)

    with tab_limites:
        izq, der = st.columns(2)
        with izq:
            data["compraMinima"] = st.number_input(
                "Compra minima (S/)",
                min_value=0.0,
                value=float(data["compraMinima"] or 0),
                step=10.0,
                key="stable_minimo",
            )
            data["limiteTotalUsos"] = st.number_input(
                "Limite total de usos",
                min_value=0,
                value=int(data["limiteTotalUsos"] or 0),
                step=1,
                help="0 = sin limite.",
                key="stable_limite",
            )
        with der:
            data["descuentoMaximo"] = st.number_input(
                "Descuento maximo (S/)",
                min_value=0.0,
                value=float(data.get("descuentoMaximo") or 0),
                step=10.0,
                help="0 = sin tope.",
                key="stable_tope",
            )
            data["appliesTo"] = st.selectbox(
                "Aplicabilidad",
                ["Todos los productos", "Productos seleccionados", "Colecciones seleccionadas"],
                index=["Todos los productos", "Productos seleccionados", "Colecciones seleccionadas"].index(
                    data.get("appliesTo", "Todos los productos")
                ),
                key="stable_aplica",
            )
        data["unaVezPorCliente"] = st.checkbox(
            "Un solo uso por cliente", value=bool(data["unaVezPorCliente"]), key="stable_once"
        )

        st.markdown('<div class="rango-tag">Combinaciones permitidas en Shopify</div>', unsafe_allow_html=True)
        comb_cols = st.columns(3)
        with comb_cols[0]:
            data["combinaProducto"] = st.toggle("Descuentos de producto", value=bool(data.get("combinaProducto")), key="stable_comb_prod")
        with comb_cols[1]:
            data["combinaPedido"] = st.toggle("Descuentos de pedido", value=bool(data.get("combinaPedido")), key="stable_comb_order")
        with comb_cols[2]:
            data["combinaEnvio"] = st.toggle("Descuentos de envio", value=bool(data.get("combinaEnvio")), key="stable_comb_ship")

    with tab_tiendas:
        all_site_ids = [site_cfg["id"] for site_cfg in enabled_sites]
        site_options = {site_cfg["name"]: site_cfg["id"] for site_cfg in enabled_sites}
        selected_site_names = [
            site_cfg["name"] for site_cfg in enabled_sites if site_cfg["id"] in data.get("selectedSites", [])
        ]
        selected_site_names = st.multiselect(
            "Tiendas donde se creara el cupon",
            list(site_options),
            default=selected_site_names,
            key="stable_selected_sites",
        )
        data["selectedSites"] = [site_options[name] for name in selected_site_names]

        acciones = st.columns([1, 1, 2])
        if acciones[0].button("Todas", key="stable_all_sites", **ancho()):
            data["selectedSites"] = all_site_ids
            st.session_state["coupon_data"] = data
            st.session_state.pop("stable_selected_sites", None)
            st.rerun()
        if acciones[1].button("Limpiar", key="stable_clear_sites", **ancho()):
            data["selectedSites"] = []
            st.session_state["coupon_data"] = data
            st.session_state.pop("stable_selected_sites", None)
            st.rerun()

        chips_tiendas = "".join(
            '<span class="pill ' + ("green" if shopify_is_configured(site_cfg["shop_key"]) else "orange") + '">'
            + site_cfg["name"]
            + ("" if shopify_is_configured(site_cfg["shop_key"]) else " sin token")
            + "</span>"
            for site_cfg in enabled_sites
            if site_cfg["id"] in data["selectedSites"]
        )
        if chips_tiendas:
            st.markdown('<div class="coupon-chip-row">' + chips_tiendas + "</div>", unsafe_allow_html=True)

    if mode == "Individual":
        data["couponCodes"] = [data.get("codigoCupon", "").strip().upper()] if data.get("codigoCupon") else []
    selected_shop_keys = {
        site_cfg["id"]: site_cfg["shop_key"]
        for site_cfg in enabled_sites
        if site_cfg["id"] in data["selectedSites"]
    }
    data["selectedShopKeys"] = list(selected_shop_keys.values())
    data["functionHandlesByShop"] = {
        clave_tienda: shopify_function_handle(clave_tienda) for clave_tienda in data["selectedShopKeys"]
    }
    data["functionIdsByShop"] = {
        clave_tienda: shopify_function_id(clave_tienda) for clave_tienda in data["selectedShopKeys"]
    }
    st.session_state["coupon_data"] = data

    codes_for_preview = data.get("couponCodes") or ([data.get("codigoCupon")] if data.get("codigoCupon") else [])
    preview_rows = []
    for site_cfg in enabled_sites:
        if site_cfg["id"] in data["selectedSites"]:
            for code in codes_for_preview:
                preview_rows.append(
                    {
                        "Sitio": site_cfg["name"],
                        "Codigo": code,
                        "Descuento": discount_label,
                        "Compra minima": min_label,
                        "Tope": "Sin tope" if float(data.get("descuentoMaximo") or 0) == 0 else f"S/ {float(data['descuentoMaximo']):,.2f}",
                        "Desde": data["fechaInicio"] + " " + data["horaInicio"],
                        "Hasta": data["fechaFin"] + " " + data["horaFin"],
                        "1 uso x cliente": "Si" if data["unaVezPorCliente"] else "No",
                        "Estado": "Listo",
                    }
                )

    seccion("3", "Vista previa", str(len(preview_rows)) + " cupon(es) listos para crear en Shopify.")
    if preview_rows:
        st.dataframe(pd.DataFrame(preview_rows), hide_index=True, **ancho())
    else:
        aviso("Selecciona al menos una tienda y completa el codigo para ver la vista previa.")

    if data.get("priceBasis") == PRICE_BASIS_COMPARE_AT_BEST_WINS:
        with st.expander("Simulacion Best Wins por producto", expanded=False):
            st.caption(
                "Compara el Compare At Price contra el Price actual. Nunca sube un precio ni descuenta de mas "
                "cuando la promocion vigente ya es mejor."
            )
            st.dataframe(pd.DataFrame(build_preview_rows(data)), hide_index=True, **ancho())

    for alert in data.get("parserAlerts", []):
        aviso(alert.get("message", ""), "error" if alert.get("blocking") else "info")

    errors = validate_coupon_data(
        data,
        function_ids_by_shop=data.get("functionIdsByShop", {}),
        function_handles_by_shop=data.get("functionHandlesByShop", {}),
    )
    for error in errors:
        aviso(error, "error")

    total_to_create = len(codes_for_preview) * len(data["selectedSites"])
    button_label = "Crear 1 cupon" if total_to_create == 1 else "Crear " + str(total_to_create) + " cupones"

    resumen_col, accion_col = st.columns([2, 1])
    with resumen_col:
        st.markdown(
            '<div class="coupon-bottom-bar"><div>'
            '<div class="coupon-bottom-title">'
            + str(total_to_create)
            + " cupon(es) en "
            + str(len(data["selectedSites"]))
            + " tienda(s)</div>"
            '<div class="coupon-bottom-sub">Revisa la vista previa antes de continuar. La creacion no tiene deshacer.</div>'
            "</div></div>",
            unsafe_allow_html=True,
        )
    with accion_col:
        st.write("")
        crear = st.button(
            button_label,
            type="primary",
            disabled=bool(errors) or total_to_create == 0,
            key="stable_create",
            **ancho(),
        )

    if crear:
        with st.status("Creando cupones en Shopify...", expanded=True) as status:
            results = create_coupon_for_multiple_sites(
                data,
                segment_ids_by_site={},
                shopify_create=create_shopify_coupon,
                configured_checker=shopify_is_configured,
            )
            st.session_state["coupon_results"] = results
            status.update(label="Proceso terminado.", state="complete")

    if st.session_state["coupon_results"]:
        resultados = pd.DataFrame(st.session_state["coupon_results"])
        exitosos = int((resultados["status"] == "success").sum()) if "status" in resultados else 0
        fallidos = len(resultados) - exitosos
        seccion("4", "Resultados", str(exitosos) + " creados, " + str(fallidos) + " con problema")
        st.dataframe(resultados, hide_index=True, **ancho())
        st.download_button(
            "Descargar resultados",
            data=excel_bytes_from_df(resultados, "Resultados"),
            file_name="cupones_resultado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with st.expander("Secrets necesarios para Shopify"):
        secret_example = (
            "[shopify_sites." + shop_key + "]\n"
            'shop_domain = "' + shop_key + '.myshopify.com"\n'
            'client_id = ""\n'
            'admin_access_token = "shpat_xxxxxxxxxxxxxxxxx"\n'
            'api_version = "2026-04"\n'
            'compare_at_best_wins_function_handle = "compare-at-best-wins"'
        )
        st.code(secret_example, language="toml")
        st.caption("Compare At Price - Best Wins necesita la Discount Function desplegada y permiso write_discounts.")


if module == "Generar cupones":
    render_coupon_builder_stable(site_name, site)
    st.stop()
render_top_header(site_name)
steps_placeholder = st.empty()

seccion(
    "1",
    "Archivos de entrada",
    "Revenue comercial con COD MOD COL y el ultimo Matrixify del sitio. Se genera una hoja por campana.",
)

upload_left, upload_right = st.columns(2)
with upload_left:
    revenue_file = st.file_uploader("Revenue / input comercial", type=["xlsx", "xlsm"], key="revenue")
with upload_right:
    matrixify_file = st.file_uploader(
        "Ultimo Matrixify de " + site_name,
        type=["xlsx", "xlsm"],
        key="matrixify",
        help="Debe ser del mismo sitio destino para conservar Product ID y Variant ID.",
    )

render_steps(revenue_file is not None, matrixify_file is not None, target=steps_placeholder)

estado_fuentes = [
    ("Revenue", "Cargado" if revenue_file else "Pendiente", bool(revenue_file)),
    ("Matrixify", "Cargado" if matrixify_file else "Pendiente", bool(matrixify_file)),
    ("BigQuery", "Conectado" if bigquery_is_configured() else "Sin configurar", bigquery_is_configured()),
    ("Salida", site["output"], True),
]
chips_fuentes = "".join(
    '<span class="pill ' + ("green" if ok else "muted") + '">' + titulo + ": " + valor + "</span>"
    for titulo, valor, ok in estado_fuentes
)
st.markdown(
    '<div class="coupon-builder-card tight">'
    '<div class="coupon-step-title">Estado de preparacion</div>'
    '<div class="coupon-chip-row">' + chips_fuentes + "</div>"
    "</div>",
    unsafe_allow_html=True,
)

ayuda_izq, ayuda_der = st.columns(2)
with ayuda_izq:
    with st.expander("Aviso al brand manager"):
        notify_email = st.text_input(
            "Enviar faltantes de Matrixify a",
            value="",
            placeholder="correo@empresa.com",
            help="Opcional. Solo se envia si hay codigos del input que faltan crear en Matrixify.",
        )
with ayuda_der:
    with st.expander("Formato comercial esperado"):
        st.download_button(
            "Descargar formato",
            data=build_input_template_bytes(),
            file_name="formato_input_revenue.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            **ancho(),
        )
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
            **ancho(),
        )

listo_para_generar = bool(revenue_file) and bool(matrixify_file)
accion_izq, accion_der = st.columns([2, 1])
with accion_izq:
    if not listo_para_generar:
        st.caption("Carga los dos archivos para habilitar la generacion.")
with accion_der:
    generate = st.button(
        "Generar Matrixify Revenue",
        type="primary",
        disabled=not listo_para_generar,
        **ancho(),
    )


if generate:
    if not selected_brands:
        st.error("Selecciona al menos una marca a afectar.")
        st.stop()
    if not bigquery_is_configured():
        st.error("BigQuery es obligatorio. Configura [bigquery] en Secrets antes de generar.")
        st.stop()

    brand_counts = {}
    email_status = ""
    email_detail = ""
    try:
        with st.status("Generando archivo Matrixify...", expanded=True) as status:
            with tempfile.TemporaryDirectory() as temp_dir:
                workdir = Path(temp_dir)
                status.write("1. Guardando archivos cargados...")
                revenue_path = save_upload(revenue_file, workdir)
                matrixify_path = save_upload(matrixify_file, workdir)
                output_path = workdir / site["output"]

                status.write("2. Validando si cada archivo es Revenue o Matrixify...")
                revenue_path, matrixify_path, role_messages = resolve_uploaded_roles(revenue_path, matrixify_path)
                for message in role_messages:
                    st.warning(message)
                    status.write(message)

                status.write("3. Leyendo ultimo catalogo Matrixify...")
                matrixify_df = read_matrixify(matrixify_path)
                status.write(f"Matrixify reconocido: {len(matrixify_df):,} filas.")

                status.write("4. Leyendo COD MOD COL del Revenue...")
                revenue_ids, revenue_modcols = extract_revenue_lookup_values(revenue_path)
                if not revenue_modcols:
                    raise ValueError("El Revenue debe traer la columna COD MOD COL. Ya no se procesa solo con SKU.")
                status.write(f"Revenue reconocido: {len(revenue_modcols):,} COD MOD COL unicos.")

                status.write("5. Consultando BigQuery para convertir COD MOD COL en SKUs y marca...")
                product_lookup = load_product_lookup_from_bigquery(
                    tuple(revenue_ids),
                    tuple(revenue_modcols),
                    tuple(selected_brands),
                )
                found_ids = len(product_lookup.get("by_id", {}))
                found_modcols = len(product_lookup.get("by_modcol", {}))
                if not found_ids or not found_modcols:
                    raise ValueError(
                        "BigQuery no devolvio SKUs para los COD MOD COL del Revenue. "
                        "Revisa que los codigos existan en ARTI antes de generar."
                    )
                status.write(f"BigQuery encontro {found_ids:,} SKUs y {found_modcols:,} COD MOD COL.")

                missing_bq_modcols = [
                    modcol
                    for modcol in revenue_modcols
                    if normalize_key(modcol) not in product_lookup.get("by_modcol", {})
                ]
                if missing_bq_modcols:
                    raise ValueError(
                        "Hay COD MOD COL del Revenue que no existen en BigQuery/ARTI. "
                        "Corrige estos codigos antes de generar: "
                        + ", ".join(missing_bq_modcols[:30])
                        + ("..." if len(missing_bq_modcols) > 30 else "")
                    )

                brand_counts = {}
                for info in product_lookup.get("by_modcol", {}).values():
                    brand = str(info.get("brand") or "SIN MARCA").strip().upper()
                    brand_counts[brand] = brand_counts.get(brand, 0) + 1
                selected_norm = {normalize_key(brand) for brand in selected_brands}
                detected_norm = {normalize_key(brand) for brand in brand_counts}
                if selected_norm and not selected_norm.intersection(detected_norm):
                    raise ValueError(
                        "La marca seleccionada no aparece en los COD MOD COL del input. "
                        f"Seleccionaste: {', '.join(selected_brands)}. "
                        f"BigQuery detecto: {', '.join(sorted(brand_counts))}."
                    )

                status.write("6. Armando hojas Matrixify por campana...")
                result = build_discount_workbook(
                    matrixify_path=matrixify_path,
                    revenue_path=revenue_path,
                    output_path=output_path,
                    selected_brands=selected_brands,
                    product_lookup=product_lookup,
                )
                status.write("7. Preparando archivo para descarga...")
                output_bytes = output_path.read_bytes()
                if notify_email.strip() and not result["missing"].empty:
                    status.write("8. Enviando aviso de faltantes al brand manager...")
                    missing_email_bytes = excel_bytes_from_df(result["missing"], "Faltan crear")
                    try:
                        send_finish_email(
                            to_email=notify_email.strip(),
                            subject=f"Codigos faltantes Matrixify - {site_name}",
                            body=(
                                "Hola,\n\n"
                                f"Se encontraron {len(result['missing']):,} codigos del input que no existen en el ultimo Matrixify de {site_name}.\n"
                                "Se adjunta el detalle para revisar o crear esos productos antes de la carga.\n\n"
                                "Mensaje automatico de la app Matrixify Revenue."
                            ),
                            attachment_name=f"codigos_faltantes_{site_name.lower().replace('.', '_')}.xlsx",
                            attachment_bytes=missing_email_bytes,
                        )
                        email_status = "sent"
                        email_detail = f"Correo enviado a {notify_email.strip()} con los codigos faltantes."
                    except Exception as email_exc:
                        email_status = "failed"
                        email_detail = f"El Excel fue generado, pero no se pudo enviar el correo de faltantes: {email_exc}"
                elif notify_email.strip() and result["missing"].empty:
                    email_status = "skipped_no_missing"
                    email_detail = "No se envio correo porque no hubo codigos faltantes en Matrixify."
                elif not notify_email.strip() and not result["missing"].empty:
                    email_status = "skipped_no_email"
                    email_detail = "No se envio correo porque no ingresaste destinatario en Aviso al brand manager."
                status.update(label="Archivo generado correctamente. Descarga disponible abajo.", state="complete")

        total_rows = int(result["summary"]["Filas Matrixify generadas"].sum()) if not result["summary"].empty else 0
        total_discounted = int(result["summary"]["Filas con descuento"].sum()) if not result["summary"].empty else 0
        total_missing = len(result["missing"])
        total_not_affected = len(result["not_affected"])
        if email_status == "sent":
            st.success(email_detail)
        elif email_status == "failed":
            st.warning(email_detail)
        elif email_status in ("skipped_no_missing", "skipped_no_email"):
            st.info(email_detail)
        st.markdown(
            f"""
            <div class="result-grid">
              <div class="result-card good">
                <div class="result-label">Archivo generado</div>
                <div class="result-value">{total_rows:,}</div>
                <div class="source-sub">filas Matrixify</div>
              </div>
              <div class="result-card">
                <div class="result-label">Con descuento</div>
                <div class="result-value">{total_discounted:,}</div>
                <div class="source-sub">variantes afectadas</div>
              </div>
              <div class="result-card {'bad' if total_missing else 'good'}">
                <div class="result-label">Faltan crear</div>
                <div class="result-value">{total_missing:,}</div>
                <div class="source-sub">codigos no encontrados</div>
              </div>
              <div class="result-card warn">
                <div class="result-label">Fuera de marca</div>
                <div class="result-value">{total_not_affected:,}</div>
                <div class="source-sub">se dejan sin cambios</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.success("Archivo generado correctamente. Ya puedes descargarlo.")
        st.download_button(
            "Descargar Matrixify generado",
            data=output_bytes,
            file_name=site["output"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_matrixify_top",
        )

        if brand_counts:
            brand_df = pd.DataFrame(
                [{"Marca BigQuery": brand, "COD MOD COL": count} for brand, count in sorted(brand_counts.items())]
            )
            panel("Marcas detectadas por BigQuery", "Sirve para validar si el input corresponde a la marca que elegiste afectar.")
            st.dataframe(brand_df, hide_index=True, **ancho())

        panel("Resumen de hojas a programar", "Cada fila representa una hoja/campana que saldra en el Excel final.")
        st.dataframe(result["summary"], hide_index=True, **ancho())

        if not result["percent"].empty:
            panel("Distribucion por descuento", "Cantidad de modelo-color y variantes afectadas por porcentaje.")
            st.dataframe(result["percent"], hide_index=True, **ancho())

        if not result["missing"].empty:
            panel("Codigos que faltan crear en Matrixify", "Estos COD MOD COL vienen en el input, pero no aparecen en el ultimo Matrixify cargado.")
            st.dataframe(result["missing"].head(200), hide_index=True, **ancho())

        if not result["not_affected"].empty:
            panel("Codigos fuera de la marca seleccionada", "BigQuery detecto otra marca; la app no modifica estos productos.")
            st.dataframe(result["not_affected"].head(200), hide_index=True, **ancho())

        st.download_button(
            "Descargar Matrixify generado",
            data=output_bytes,
            file_name=site["output"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_matrixify_bottom",
        )
    except Exception as exc:
        st.error(f"No pude generar el archivo: {exc}")
else:
    st.info("Carga ambos archivos para comenzar.")
