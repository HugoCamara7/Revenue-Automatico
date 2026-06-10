from __future__ import annotations

import base64
import io
import json
import smtplib
import tempfile
from email.message import EmailMessage
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

import pandas as pd
import streamlit as st

from generar_matrixify_descuentos import (
    build_discount_workbook,
    extract_revenue_lookup_values,
    normalize_key,
    read_matrixify,
)


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
    [data-testid="stSidebar"] > div:first-child { padding: 22px 24px 28px; }
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
        margin-bottom: 28px;
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
    .hero-arrow {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 34px;
        height: 34px;
        margin: 0 8px;
        border-radius: 999px;
        background: #eef6ff;
        color: #006bd6;
        font-size: 22px;
        font-weight: 900;
        vertical-align: middle;
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
    .result-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin: 24px 0;
    }
    .result-card {
        background: #ffffff;
        border: 1px solid #d7e4f5;
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 16px 34px rgba(16, 58, 120, 0.06);
    }
    .result-card.good { border-color: #9ee7bf; background: #f1fbf6; }
    .result-card.warn { border-color: #ffd16a; background: #fffaf0; }
    .result-card.bad { border-color: #ffb3b3; background: #fff4f4; }
    .result-label {
        color: #5f7194;
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: .05em;
        margin-bottom: 8px;
    }
    .result-value {
        color: #031b4e;
        font-size: 28px;
        font-weight: 950;
        line-height: 1;
    }
    .preview-panel {
        background: #ffffff;
        border: 1px solid #d7e4f5;
        border-radius: 22px;
        padding: 22px;
        margin: 20px 0;
    }
    .preview-title {
        color: #031b4e;
        font-weight: 950;
        font-size: 20px;
        margin-bottom: 6px;
    }
    .preview-sub {
        color: #5f7194;
        font-size: 14px;
        margin-bottom: 16px;
    }
    .login-shell {
        min-height: 92vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #142238;
        margin: -30px calc(50% - 50vw) -42px;
        padding: 28px;
    }
    .login-card {
        width: min(560px, 94vw);
        background: #ffffff;
        border-radius: 20px;
        overflow: hidden;
        box-shadow: 0 28px 70px rgba(0, 0, 0, .24);
    }
    .login-hero {
        background: linear-gradient(145deg, #2c73ff, #1654ef);
        color: white;
        padding: 40px 38px 44px;
        text-align: center;
    }
    .login-brand-row {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 26px;
        margin-bottom: 28px;
    }
    .login-logo, .login-shopify {
        background: #ffffff;
        border-radius: 10px;
        padding: 10px 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 62px;
    }
    .login-logo img { max-width: 210px; max-height: 62px; object-fit: contain; }
    .login-shopify img { width: 48px; height: 48px; object-fit: contain; }
    .login-divider {
        width: 1px;
        height: 54px;
        background: rgba(255,255,255,.52);
    }
    .login-title {
        font-size: 34px;
        font-weight: 950;
        margin: 0 0 12px;
        letter-spacing: 0;
    }
    .login-sub {
        font-size: 18px;
        font-weight: 800;
        opacity: .95;
    }
    .login-body {
        padding: 38px 40px 28px;
    }
    .login-foot {
        text-align: center;
        color: #62718a;
        font-weight: 900;
        padding: 12px 0 8px;
    }
    .coupon-hero {
        background: linear-gradient(135deg, #1328a0, #266cff);
        color: white;
        border-radius: 28px;
        padding: 34px;
        margin-bottom: 24px;
        box-shadow: 0 22px 48px rgba(22, 84, 239, .18);
    }
    .coupon-hero h2 {
        margin: 0 0 10px;
        font-size: 30px;
        letter-spacing: 0;
    }
    .coupon-hero p {
        margin: 0;
        opacity: .9;
    }
    .coupon-card {
        background: white;
        border: 1px solid #d7e4f5;
        border-radius: 24px;
        padding: 26px;
        margin: 18px 0;
        box-shadow: 0 18px 42px rgba(16, 58, 120, 0.06);
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
        .steps-grid, .source-grid, .result-grid { grid-template-columns: 1fr; }
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
    try:
        for section in ("shopify_sites", "shopify"):
            config = st.secrets.get(section, {})
            if isinstance(config, dict):
                site_config = config.get(shop_key, {})
                if isinstance(site_config, dict) and site_config:
                    return dict(site_config)
                if config.get("shop_domain") or config.get("access_token"):
                    return dict(config)
    except Exception:
        return {}
    return {}


def shopify_is_configured(shop_key: str) -> bool:
    config = get_shopify_config(shop_key)
    token = config.get("access_token") or config.get("admin_access_token")
    return bool(str(config.get("shop_domain", "")).strip() and str(token or "").strip())


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


def image_data_uri(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    suffix = file_path.suffix.lower().replace(".", "")
    mime = "jpeg" if suffix in ("jpg", "jpeg") else "png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"


def get_auth_config() -> dict:
    try:
        return dict(st.secrets.get("auth", {}))
    except Exception:
        return {}


def valid_login(email: str, password: str) -> bool:
    config = get_auth_config()
    login_email = email.strip().lower()
    login_password = str(password).strip()
    user_list = config.get("users_list", [])
    if isinstance(user_list, list):
        for user in user_list:
            if not isinstance(user, dict):
                continue
            stored_email = str(user.get("email", "")).strip().lower()
            stored_password = str(user.get("password", "")).strip()
            if stored_email == login_email and stored_password == login_password:
                return True
    users = dict(config.get("users", {})) if isinstance(config.get("users", {}), dict) else {}
    if users:
        normalized_users = {str(key).strip().lower(): str(value).strip() for key, value in users.items()}
        return normalized_users.get(login_email) == login_password
    allowed = [str(value).strip().lower() for value in config.get("allowed_emails", [])]
    shared_password = str(config.get("password", "")).strip()
    return bool(login_email in allowed and login_password == shared_password)


def render_login() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        .stApp { background: #142238; }
        .block-container { max-width: 448px; padding-top: 22px; padding-bottom: 30px; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border: 0 !important;
            border-radius: 16px !important;
            overflow: hidden !important;
            box-shadow: 0 28px 70px rgba(0, 0, 0, .24) !important;
            padding: 0 !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] > div,
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
            background: #ffffff !important;
        }
        .login-hero {
            margin: -1rem -1rem 0 !important;
            border-radius: 16px 16px 0 0;
            padding: 30px 28px 34px;
        }
        div[data-testid="stForm"] {
            background: #ffffff !important;
            border: 1px solid #d7dce5;
            border-radius: 10px;
            padding: 18px;
            margin: 26px 18px 10px;
        }
        div[data-testid="stForm"] label,
        div[data-testid="stForm"] p {
            color: #031b4e !important;
        }
        div[data-testid="stForm"] button {
            background: #235781;
            color: white;
            border-radius: 9px;
            min-height: 48px;
            font-weight: 900;
            padding: 0 22px;
        }
        .login-foot {
            margin: 26px 0 24px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    forus_src = image_data_uri("forus_logo.png")
    shopify_src = image_data_uri("shopify_logo.png")
    forus_html = f'<img src="{forus_src}" alt="FORUS">' if forus_src else "<b>FORUS</b>"
    shopify_html = f'<img src="{shopify_src}" alt="Shopify">' if shopify_src else "<b>S</b>"
    with st.container(border=True):
        st.markdown(
            f"""
            <div class="login-hero">
              <div class="login-brand-row">
                <div class="login-logo">{forus_html}</div>
                <div class="login-divider"></div>
                <div class="login-shopify">{shopify_html}</div>
              </div>
              <div class="login-title">Revenue Control Center</div>
              <div class="login-sub">Sistema de descuentos y cupones Shopify</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            email = st.text_input("Correo electronico", placeholder="hugo.camara@forus.pe")
            password = st.text_input("Contrasena", type="password")
            submitted = st.form_submit_button("Ingresar")
        if submitted:
            if valid_login(email, password):
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email.strip().lower()
                st.rerun()
            else:
                st.error("Correo o contrasena incorrectos.")
        if not get_auth_config():
            st.warning("Configura [auth] en Secrets para habilitar usuarios.")
        st.markdown(
            '<div class="login-foot">Sistema exclusivo para personal autorizado</div>',
            unsafe_allow_html=True,
        )


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

with st.sidebar:
    user_email = st.session_state.get("user_email", "")
    if user_email:
        st.caption(f"Sesion: {user_email}")
    module = st.radio(
        "Modulo",
        ["Carga de descuentos", "Generar cupones"],
        horizontal=False,
    )
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
    st.caption(f"Salida: {site['output']}")
    st.markdown(
        f"""
        <div class="sidebar-status-card">
          <div style="font-weight:900;color:#031b4e;margin-bottom:12px;">Reglas de carga</div>
          <div class="connection-ok">BigQuery define la marca a afectar</div>
          <div style="color:#6b7894;font-size:13px;">Las marcas no seleccionadas se dejan sin cambios.</div>
          <div style="color:#6b7894;font-size:13px;margin-top:12px;">Salida: {site['output']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if module == "Generar cupones":
    render_top_header(site_name)
    shop_key = site["shop_key"]
    shop_ready = shopify_is_configured(shop_key)
    st.markdown(
        """
        <div class="coupon-hero">
          <h2>Generador de cupones Shopify</h2>
          <p>Crea cupones directamente en Shopify con fechas, limites, minimo de compra y segmentos de clientes.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not shop_ready:
        st.error(
            f"Falta configurar Shopify API para {site_name}. "
            f"Agrega shop_domain y admin_access_token en [shopify_sites.{shop_key}] dentro de Secrets."
        )
    else:
        st.success("Shopify API configurado para este sitio.")

    segments = load_shopify_segments(shop_key) if shop_ready else []
    segment_options = {"Todos los clientes": ""}
    segment_options.update({segment["name"]: segment["id"] for segment in segments if segment.get("name") and segment.get("id")})

    with st.form("coupon_form"):
        st.markdown('<div class="coupon-card">', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            coupon_title = st.text_input("Nombre interno del descuento", value=f"{site_name} Campana")
            coupon_code = st.text_input("Codigo del cupon", placeholder="CLB40")
            discount_type = st.selectbox("Tipo de descuento", ["Porcentaje", "Monto fijo"])
            discount_value = st.number_input("Valor descuento", min_value=0.0, value=40.0, step=1.0)
            minimum_subtotal = st.number_input("Compra minima", min_value=0.0, value=0.0, step=10.0)
        with col_b:
            starts_date = st.date_input("Fecha inicio")
            starts_time = st.time_input("Hora inicio")
            ends_date = st.date_input("Fecha fin")
            ends_time = st.time_input("Hora fin")
            usage_limit = st.number_input("Limite total de usos (0 = sin limite)", min_value=0, value=0, step=1)
            once_per_customer = st.checkbox("Una vez por cliente", value=True)
        customer_segment_name = st.selectbox("Grupo / segmento de clientes", list(segment_options.keys()))
        applies_to = st.selectbox("Aplica a", ["Todos los productos"])
        st.markdown("</div>", unsafe_allow_html=True)
        create_coupon = st.form_submit_button("Crear cupon en Shopify", type="primary")

    if create_coupon:
        if not shop_ready:
            st.stop()
        if not coupon_code.strip():
            st.error("Ingresa el codigo del cupon.")
            st.stop()
        customer_context = {"all": True}
        selected_segment_id = segment_options.get(customer_segment_name)
        if selected_segment_id:
            customer_context = {"segments": {"add": [selected_segment_id]}}

        discount_payload = {
            "title": coupon_title.strip() or coupon_code.strip(),
            "code": coupon_code.strip().upper(),
            "startsAt": build_iso_datetime(starts_date, starts_time),
            "endsAt": build_iso_datetime(ends_date, ends_time),
            "appliesOncePerCustomer": once_per_customer,
            "customerSelection": customer_context,
            "customerGets": {
                "items": {"all": True},
                "value": (
                    {"percentage": discount_value / 100}
                    if discount_type == "Porcentaje"
                    else {"discountAmount": {"amount": str(round(discount_value, 2)), "appliesOnEachItem": False}}
                ),
            },
        }
        if usage_limit > 0:
            discount_payload["usageLimit"] = int(usage_limit)
        if minimum_subtotal > 0:
            discount_payload["minimumRequirement"] = {
                "subtotal": {"greaterThanOrEqualToSubtotal": str(round(minimum_subtotal, 2))}
            }
        try:
            result = create_shopify_coupon(shop_key, discount_payload)
            node = result.get("codeDiscountNode", {})
            st.success(f"Cupon creado correctamente en Shopify: {coupon_code.strip().upper()}")
            st.json(node)
        except Exception as exc:
            st.error(f"No pude crear el cupon en Shopify: {exc}")

    with st.expander("Secrets necesarios para Shopify"):
        st.code(
            f"""
[shopify_sites.{shop_key}]
shop_domain = "{shop_key}.myshopify.com"
client_id = ""
client_secret = ""
admin_access_token = "shpat_xxxxxxxxxxxxxxxxx"
api_version = "2026-04"
            """.strip(),
            language="toml",
        )
        st.caption("El token debe tener permisos write_discounts y permisos de lectura para segmentos/clientes si usaras grupos.")
    st.stop()


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

with st.expander("Aviso al brand manager", expanded=False):
    notify_email = st.text_input(
        "Enviar faltantes de Matrixify a",
        value="",
        placeholder="correo@empresa.com",
        help="Opcional. Solo se enviara si hay codigos del input que faltan crear en Matrixify.",
    )

with st.expander("Formato comercial esperado"):
    st.download_button(
        "Descargar formato input Revenue",
        data=build_input_template_bytes(),
        file_name="formato_input_revenue.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
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

    brand_counts = {}
    email_status = ""
    email_detail = ""
    try:
        with st.status("Generando archivo Matrixify...", expanded=False) as status:
            with tempfile.TemporaryDirectory() as temp_dir:
                workdir = Path(temp_dir)
                revenue_path = save_upload(revenue_file, workdir)
                matrixify_path = save_upload(matrixify_file, workdir)
                output_path = workdir / site["output"]

                matrixify_df = read_matrixify(matrixify_path)

                revenue_ids, revenue_modcols = extract_revenue_lookup_values(revenue_path)
                if not revenue_modcols:
                    st.error("El Revenue debe traer la columna COD MOD COL. Ya no se procesa solo con SKU.")
                    st.stop()
                product_lookup = load_product_lookup_from_bigquery(
                    tuple(revenue_ids),
                    tuple(revenue_modcols),
                    tuple(selected_brands),
                )
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
                brand_counts = {}
                for info in product_lookup.get("by_modcol", {}).values():
                    brand = str(info.get("brand") or "SIN MARCA").strip().upper()
                    brand_counts[brand] = brand_counts.get(brand, 0) + 1
                selected_norm = {normalize_key(brand) for brand in selected_brands}
                detected_norm = {normalize_key(brand) for brand in brand_counts}
                if selected_norm and not selected_norm.intersection(detected_norm):
                    st.error(
                        "La marca seleccionada no aparece en los COD MOD COL del input. "
                        f"Seleccionaste: {', '.join(selected_brands)}. "
                        f"BigQuery detecto: {', '.join(sorted(brand_counts))}."
                    )
                    st.stop()

                result = build_discount_workbook(
                    matrixify_path=matrixify_path,
                    revenue_path=revenue_path,
                    output_path=output_path,
                    selected_brands=selected_brands,
                    product_lookup=product_lookup,
                )
                output_bytes = output_path.read_bytes()
                if notify_email.strip() and not result["missing"].empty:
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
                status.update(label="Archivo generado correctamente.", state="complete")

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

        if brand_counts:
            brand_df = pd.DataFrame(
                [{"Marca BigQuery": brand, "COD MOD COL": count} for brand, count in sorted(brand_counts.items())]
            )
            st.markdown(
                '<div class="preview-panel"><div class="preview-title">Marcas detectadas por BigQuery</div>'
                '<div class="preview-sub">Sirve para validar si el input corresponde a la marca que elegiste afectar.</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(brand_df, hide_index=True, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            '<div class="preview-panel"><div class="preview-title">Resumen de hojas a programar</div>'
            '<div class="preview-sub">Cada fila representa una hoja/campana que saldra en el Excel final.</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(result["summary"], hide_index=True, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if not result["percent"].empty:
            st.markdown(
                '<div class="preview-panel"><div class="preview-title">Distribucion por descuento</div>'
                '<div class="preview-sub">Cantidad de modelo-color y variantes afectadas por porcentaje.</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(result["percent"], hide_index=True, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if not result["missing"].empty:
            st.markdown(
                '<div class="preview-panel"><div class="preview-title">Codigos que faltan crear en Matrixify</div>'
                '<div class="preview-sub">Estos COD MOD COL vienen en el input, pero no aparecen en el ultimo Matrixify cargado.</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(result["missing"].head(200), hide_index=True, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if not result["not_affected"].empty:
            st.markdown(
                '<div class="preview-panel"><div class="preview-title">Codigos fuera de la marca seleccionada</div>'
                '<div class="preview-sub">BigQuery detecto otra marca; la app no modifica estos productos.</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(result["not_affected"].head(200), hide_index=True, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

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
