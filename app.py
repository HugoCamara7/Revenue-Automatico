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

from coupon_config import COUPON_SHOPIFY_SITES, QUICK_TEMPLATES
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
        background:
            radial-gradient(circle at 90% 10%, rgba(255,255,255,.18), transparent 26%),
            linear-gradient(135deg, #1426a8, #2d74ff);
        color: white;
        border-radius: 28px;
        padding: 34px 38px;
        margin-bottom: 24px;
        box-shadow: 0 22px 48px rgba(22, 84, 239, .18);
        display: flex;
        justify-content: space-between;
        gap: 24px;
        align-items: center;
    }
    .coupon-hero h2 {
        margin: 0 0 10px;
        font-size: 34px;
        letter-spacing: 0;
    }
    .coupon-hero p {
        margin: 0;
        opacity: .9;
        max-width: 720px;
    }
    .coupon-hero-mini {
        display: grid;
        grid-template-columns: repeat(2, minmax(120px, 1fr));
        gap: 12px;
        min-width: 280px;
    }
    .coupon-hero-chip {
        border: 1px solid rgba(255,255,255,.34);
        background: rgba(255,255,255,.14);
        border-radius: 18px;
        padding: 14px 16px;
        font-weight: 900;
        color: #ffffff;
        backdrop-filter: blur(10px);
    }
    .coupon-hero-chip span {
        display: block;
        font-size: 12px;
        opacity: .78;
        margin-top: 4px;
        font-weight: 700;
    }
    .coupon-card {
        background: white;
        border: 1px solid #d7e4f5;
        border-radius: 24px;
        padding: 28px;
        margin: 18px 0;
        box-shadow: 0 18px 42px rgba(16, 58, 120, 0.06);
    }
    .coupon-card.soft {
        background: linear-gradient(180deg, #ffffff, #f8fbff);
    }
    .coupon-section-head {
        display: flex;
        justify-content: space-between;
        gap: 18px;
        align-items: flex-start;
        margin-bottom: 20px;
    }
    .coupon-section-head h3 {
        margin: 0 0 8px;
        color: #031b4e;
        font-size: 24px;
        letter-spacing: 0;
    }
    .coupon-section-head p {
        margin: 0;
        color: #5f7194;
        font-size: 14px;
    }
    .coupon-badge {
        border-radius: 999px;
        padding: 9px 14px;
        background: #eef6ff;
        border: 1px solid #b9d7ff;
        color: #1238bf;
        font-weight: 900;
        font-size: 12px;
        white-space: nowrap;
    }
    .coupon-kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin: 8px 0 18px;
    }
    .coupon-kpi {
        background: #f8fbff;
        border: 1px solid #d7e4f5;
        border-radius: 18px;
        padding: 16px;
    }
    .coupon-kpi b {
        display: block;
        color: #031b4e;
        font-size: 20px;
        margin-bottom: 4px;
    }
    .coupon-kpi span {
        color: #5f7194;
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: .04em;
    }
    .coupon-chip-row {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: 12px;
        margin: 14px 0 18px;
    }
    .coupon-note {
        border: 1px solid #cde8d7;
        background: #edfbf2;
        color: #0a6336;
        border-radius: 16px;
        padding: 14px 16px;
        font-weight: 800;
        margin: 10px 0 0;
    }
    .coupon-warning {
        border: 1px solid #ffd1d1;
        background: #fff2f2;
        color: #bc2727;
        border-radius: 16px;
        padding: 14px 16px;
        font-weight: 800;
        margin: 12px 0;
    }
    .coupon-site-count {
        color: #536b92;
        font-weight: 800;
        margin-top: 8px;
    }
    .coupon-page-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 18px;
        margin: 8px 0 24px;
    }
    .coupon-page-head h1 {
        color: #111b46;
        font-size: 34px;
        line-height: 1.05;
        margin: 0 0 8px;
        letter-spacing: 0;
    }
    .coupon-page-head p {
        color: #5c6780;
        margin: 0;
        font-size: 15px;
    }
    .coupon-head-actions {
        display: flex;
        gap: 12px;
        white-space: nowrap;
    }
    .coupon-ghost-action,
    .coupon-red-action {
        border-radius: 10px;
        padding: 14px 22px;
        font-weight: 950;
        border: 1px solid #d7deec;
        background: #ffffff;
        color: #1f2b62;
        box-shadow: 0 12px 26px rgba(24, 38, 82, .06);
    }
    .coupon-red-action {
        border-color: #ff3c3c;
        background: #ff3838;
        color: #ffffff;
    }
    .coupon-builder-card {
        background: #ffffff;
        border: 1px solid #dbe3f1;
        border-radius: 16px;
        padding: 22px;
        margin: 16px 0;
        box-shadow: 0 18px 44px rgba(31, 45, 86, .07);
    }
    .coupon-builder-card.tight {
        padding: 18px 20px;
    }
    .coupon-step-line {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 14px;
    }
    .coupon-step-num {
        width: 24px;
        height: 24px;
        border-radius: 8px;
        display: grid;
        place-items: center;
        background: #2b2faa;
        color: #ffffff;
        font-size: 12px;
        font-weight: 950;
        flex: 0 0 auto;
    }
    .coupon-step-title {
        color: #111b46;
        font-size: 16px;
        font-weight: 950;
        margin: 0;
    }
    .coupon-step-sub {
        color: #5f6f8d;
        font-size: 13px;
        margin: -6px 0 14px 36px;
    }
    .coupon-summary-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin: 16px 0;
    }
    .coupon-summary-card {
        display: flex;
        align-items: center;
        gap: 16px;
        background: #ffffff;
        border: 1px solid #e1e7f2;
        border-radius: 16px;
        padding: 20px;
        min-height: 94px;
        box-shadow: 0 16px 34px rgba(31, 45, 86, .06);
    }
    .coupon-summary-icon {
        width: 48px;
        height: 48px;
        border-radius: 16px;
        display: grid;
        place-items: center;
        background: #eef0ff;
        color: #2b2faa;
        font-weight: 950;
        font-size: 20px;
        flex: 0 0 auto;
    }
    .coupon-summary-icon.red { background:#fff0f2; color:#ff3434; }
    .coupon-summary-icon.green { background:#e9fbf2; color:#00a35b; }
    .coupon-summary-icon.orange { background:#fff5e8; color:#ff7a00; }
    .coupon-summary-label {
        color: #8a94aa;
        font-size: 11px;
        font-weight: 950;
        letter-spacing: .04em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .coupon-summary-value {
        color: #111b46;
        font-size: 22px;
        line-height: 1.1;
        font-weight: 950;
    }
    .coupon-summary-sub {
        color: #5f6f8d;
        font-size: 12px;
        margin-top: 4px;
    }
    .coupon-form-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.35fr) minmax(330px, .95fr);
        gap: 18px;
        align-items: start;
    }
    .coupon-site-pill {
        float: right;
        border-radius: 999px;
        padding: 8px 14px;
        background: #e9fbf1;
        color: #05a060;
        font-weight: 950;
        font-size: 12px;
        margin-top: -42px;
    }
    .coupon-bottom-bar {
        background: #ffffff;
        border: 1px solid #e1e7f2;
        border-radius: 18px;
        padding: 18px 20px;
        margin: 16px 0 2px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
        box-shadow: 0 18px 44px rgba(31, 45, 86, .08);
    }
    .coupon-bottom-title {
        color: #111b46;
        font-weight: 950;
        margin-bottom: 4px;
    }
    .coupon-bottom-sub {
        color: #6a7691;
        font-size: 13px;
    }
    .coupon-preview-card {
        background: linear-gradient(135deg, #101b46, #2332b7);
        border-radius: 24px;
        color: #ffffff;
        padding: 28px;
        margin: 18px 0;
        box-shadow: 0 22px 46px rgba(35, 50, 183, .22);
    }
    .coupon-preview-code {
        font-size: 16px;
        font-weight: 900;
        letter-spacing: .08em;
        opacity: .85;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    .coupon-preview-discount {
        font-size: 42px;
        line-height: 1;
        font-weight: 950;
        margin-bottom: 18px;
    }
    .coupon-preview-meta {
        border-top: 1px solid rgba(255,255,255,.18);
        padding-top: 10px;
        margin-top: 10px;
        color: rgba(255,255,255,.88);
        font-weight: 750;
    }
    div[data-testid="stTextArea"] textarea {
        min-height: 118px !important;
        border-radius: 12px !important;
        border: 1px solid #ccd6e8 !important;
        background: #ffffff !important;
        color: #111b46 !important;
        font-weight: 700;
        line-height: 1.55;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-baseweb="select"] > div {
        border-radius: 10px !important;
        border-color: #dbe3f1 !important;
        background: #ffffff !important;
        min-height: 44px;
    }
    label, .stCheckbox label {
        color: #263252 !important;
        font-weight: 800 !important;
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
        .steps-grid, .source-grid, .result-grid, .coupon-kpi-grid, .coupon-chip-row, .coupon-summary-grid, .coupon-form-grid { grid-template-columns: 1fr; }
        .top-hero { flex-direction: column; align-items: flex-start; }
        .coupon-hero { flex-direction: column; align-items: flex-start; }
        .coupon-hero-mini { min-width: 0; width: 100%; }
        .coupon-page-head, .coupon-bottom-bar { flex-direction: column; align-items: stretch; }
        .coupon-head-actions { width: 100%; }
        .coupon-ghost-action, .coupon-red-action { flex: 1; text-align: center; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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


def image_data_uri(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    suffix = file_path.suffix.lower().replace(".", "")
    mime = "jpeg" if suffix in ("jpg", "jpeg") else "png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"


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
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        .stApp {
            background: #142238;
        }
        header[data-testid="stHeader"] {
            display: none !important;
        }
        section.main > div[data-testid="stMainBlockContainer"],
        .block-container {
            max-width: 620px !important;
            min-height: 100vh;
            padding: 70px 24px 38px !important;
        }
        .block-container > div:first-child {
            width: min(520px, 92vw) !important;
            margin: 0 auto !important;
        }
        .block-container div[data-testid="stVerticalBlock"] {
            gap: 0 !important;
        }
        .block-container div[data-testid="stElementContainer"] {
            margin: 0 !important;
            box-sizing: border-box !important;
        }
        .block-container div[data-testid="stVerticalBlockBorderWrapper"] {
            box-sizing: border-box !important;
            width: min(520px, 92vw) !important;
            max-width: 520px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            border: 0 !important;
            box-shadow: none !important;
            padding: 0 !important;
            background: transparent !important;
        }
        .block-container div[data-testid="stVerticalBlockBorderWrapper"] > div {
            background: transparent !important;
            padding: 0 !important;
        }
        .login-card-anchor {
            display: none;
        }
        .login-hero {
            box-sizing: border-box !important;
            width: min(520px, 92vw) !important;
            margin: 0 auto !important;
            border-radius: 18px 18px 0 0;
            padding: 34px 34px 36px;
            background: linear-gradient(145deg, #2d73ff, #1756f0) !important;
            text-align: center;
            box-shadow: none;
        }
        .login-brand-row {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 20px;
            margin-bottom: 24px;
        }
        .login-logo {
            width: 200px;
            min-height: 58px;
            padding: 7px 14px;
            background: #ffffff;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-logo img {
            max-width: 178px;
            max-height: 50px;
        }
        .login-shopify {
            width: 56px;
            height: 56px;
            min-height: 56px;
            padding: 8px;
            background: #ffffff;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-shopify img {
            width: 46px;
            height: 46px;
        }
        .shopify-fallback {
            width: 50px;
            height: 50px;
            border-radius: 10px;
            background: #8ec63f;
            color: white;
            font-size: 34px;
            font-weight: 950;
            display: grid;
            place-items: center;
            font-family: Arial, sans-serif;
        }
        .login-title {
            font-size: 30px;
            line-height: 1.1;
            white-space: nowrap;
            color: #ffffff;
            font-weight: 950;
        }
        .login-sub {
            font-size: 16px;
            color: #ffffff;
            font-weight: 850;
            opacity: .95;
            margin-top: 12px;
        }
        div[data-testid="stForm"] {
            box-sizing: border-box !important;
            background: #ffffff !important;
            border: 0 !important;
            border-radius: 0 0 18px 18px !important;
            padding: 30px 40px 34px !important;
            margin: 0 !important;
            box-shadow: 0 28px 70px rgba(0, 0, 0, .24) !important;
        }
        div[data-testid="stForm"] {
            width: min(520px, 92vw) !important;
            max-width: min(520px, 92vw) !important;
        }
        div[data-testid="stForm"] > div {
            gap: 14px !important;
            box-sizing: border-box !important;
        }
        div[data-testid="stForm"]::after {
            content: "Sistema exclusivo para personal autorizado";
            display: block;
            margin-top: 26px;
            color: #62718a;
            text-align: center;
            font-weight: 900;
        }
        .block-container div[data-testid="stElementContainer"]:has(.login-hero) + div[data-testid="stElementContainer"] {
            box-sizing: border-box !important;
            width: min(520px, 92vw) !important;
            max-width: min(520px, 92vw) !important;
            margin: 0 auto !important;
            background: #ffffff !important;
            border-radius: 0 0 18px 18px;
            padding: 0 !important;
            box-shadow: 0 28px 70px rgba(0, 0, 0, .24);
        }
        div[data-testid="stForm"] label,
        div[data-testid="stForm"] p {
            color: #031b4e !important;
        }
        div[data-testid="stFormSubmitButton"] button {
            background: #ff454b !important;
            border-color: #ff454b !important;
            color: #ffffff !important;
            border-radius: 9px !important;
            min-height: 48px !important;
            font-weight: 900 !important;
            padding: 0 20px !important;
            width: auto !important;
            min-width: 92px !important;
            box-shadow: none !important;
        }
        div[data-testid="stFormSubmitButton"] {
            width: fit-content !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] button {
            background: #eef2f7 !important;
            border-color: #eef2f7 !important;
            color: #031b4e !important;
            min-height: 44px !important;
            box-shadow: none !important;
            border-radius: 0 9px 9px 0 !important;
            width: 52px !important;
            padding: 0 !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] button:hover,
        div[data-testid="stForm"] div[data-testid="stTextInput"] button:focus {
            background: #eef2f7 !important;
            border-color: #eef2f7 !important;
            color: #031b4e !important;
            box-shadow: none !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input {
            border: 1px solid #dce3ee !important;
            background: #f7f9fc !important;
            color: #031b4e !important;
            min-height: 46px !important;
            border-radius: 9px !important;
            box-shadow: none !important;
        }
        div[data-testid="stForm"] div[data-testid="stTextInput"] input:focus {
            border-color: #b8c8df !important;
            box-shadow: 0 0 0 2px rgba(45, 115, 255, .12) !important;
        }
        .login-body {
            display: none;
        }
        .login-foot {
            display: none;
        }
        .login-brands-foot {
            margin: 34px auto 0;
            width: min(520px, 92vw);
            color: #ffffff;
            text-align: center;
            font-weight: 950;
            line-height: 1.9;
        }
        .login-message {
            box-sizing: border-box;
            width: min(520px, 92vw);
            margin: 12px auto 0;
            border-radius: 10px;
            padding: 13px 18px;
            font-size: 14px;
            font-weight: 750;
            line-height: 1.4;
        }
        .login-message.error {
            background: rgba(255, 69, 75, .13);
            color: #ff6970;
            border: 1px solid rgba(255, 69, 75, .24);
        }
        .login-message.warn {
            background: rgba(255, 213, 79, .12);
            color: #c49415;
            border: 1px solid rgba(255, 213, 79, .25);
        }
        @media (max-width: 620px) {
            .block-container { padding: 28px 16px !important; }
            .login-brand-row { gap: 14px; }
            .login-logo { width: 176px; }
            .login-shopify { width: 52px; height: 52px; min-height: 52px; }
            .login-title { font-size: 26px; white-space: normal; }
            .login-sub { font-size: 15px; }
            .login-hero { padding: 30px 24px 34px; }
            div[data-testid="stForm"] { padding: 28px 24px 32px !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    forus_src = image_data_uri("forus_logo.png")
    shopify_src = image_data_uri("shopify_logo.png")
    forus_html = f'<img src="{forus_src}" alt="FORUS">' if forus_src else "<b>FORUS</b>"
    shopify_html = f'<img src="{shopify_src}" alt="Shopify">' if shopify_src else '<div class="shopify-fallback">S</div>'
    auth_config = get_auth_config()
    login_error = False
    with st.container(border=True):
        st.markdown('<div class="login-card-anchor"></div>', unsafe_allow_html=True)
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
            submitted = st.form_submit_button("Ingresar", use_container_width=True)
        if submitted:
            if valid_login(email, password):
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = email.strip().lower()
                st.rerun()
            else:
                login_error = True
        st.markdown(
            '<div class="login-foot">Sistema exclusivo para personal autorizado</div>',
            unsafe_allow_html=True,
        )
    if login_error:
        st.markdown(
            '<div class="login-message error">Correo o contrasena incorrectos.</div>',
            unsafe_allow_html=True,
        )
    if not auth_config:
        st.markdown(
            '<div class="login-message warn">Configura usuarios en Secrets para habilitar el ingreso.</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="login-brands-foot">Gestion de catalogos para multiples marcas<br>Columbia &bull; Hush Puppies &bull; Vans &bull; Patagonia &bull; Mas</div>',
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


def render_coupon_builder(site_name: str, selected_site: dict) -> None:
    shop_key = selected_site["shop_key"]
    st.markdown(
        """
        <div class="coupon-page-head">
          <div>
            <h1>Smart Coupon Builder</h1>
            <p>Crea cupones Shopify para multiples marcas desde una sola pantalla.</p>
          </div>
          <div class="coupon-head-actions">
            <div class="coupon-ghost-action">Historial</div>
            <div class="coupon-red-action">Nuevo cupon</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "coupon_data" not in st.session_state:
        st.session_state["coupon_data"] = default_coupon_data()
    if "coupon_results" not in st.session_state:
        st.session_state["coupon_results"] = []
    if "coupon_site_version" not in st.session_state:
        st.session_state["coupon_site_version"] = 0

    mode = st.radio(
        "Metodo de creacion",
        ["Individual", "Masivo"],
        horizontal=True,
        key="coupon_creation_mode",
    )
    st.session_state["coupon_data"]["creationMode"] = mode

    st.markdown(
        """
        <div class="coupon-builder-card">
          <div class="coupon-step-line">
            <div class="coupon-step-num">1</div>
            <div class="coupon-step-title">Describe la promocion</div>
          </div>
          <div class="coupon-step-sub">Escribe una instruccion y deja que la app complete los campos.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    prompt_col, interpret_col = st.columns([5.2, 1.05])
    with prompt_col:
        promotion_text = st.text_area(
            "Describe la promocion",
            value=st.session_state.get("promotion_text", ""),
            placeholder=(
                "Crear cupon CLUBTOYOTA20 con 20% de descuento para BCP, BBVA e Interbank "
                "en Columbia, Hushpuppies y Rockford. Valido hoy desde 00:00 hasta 23:59, "
                "una vez por cliente."
            ),
            height=118,
            key="promotion_text",
            label_visibility="collapsed",
        )
    with interpret_col:
        st.write("")
        st.write("")
        interpret_clicked = st.button("Interpretar promocion", type="primary", use_container_width=True)

    quick_label, *quick_cols = st.columns([1.1, 1, 1, 1, 1, 1, 1, 1])
    quick_label.caption("Sugerencias rapidas:")
    for column, (chip, template) in zip(quick_cols, QUICK_TEMPLATES.items()):
        if column.button(chip, use_container_width=True):
            st.session_state["promotion_text"] = template
            st.rerun()

    if interpret_clicked:
        with st.spinner("Interpretando promocion..."):
            st.session_state["coupon_data"] = parse_coupon_text(promotion_text)
            st.session_state["coupon_data"]["creationMode"] = mode
            st.session_state["coupon_results"] = []
            st.session_state["coupon_site_version"] += 1
        st.markdown(
            '<div class="coupon-note">Promocion interpretada. Puedes editar cualquier campo antes de crear.</div>',
            unsafe_allow_html=True,
        )

    data = st.session_state["coupon_data"].copy()
    data["creationMode"] = mode
    if mode == "Masivo":
        st.markdown(
            """
            <div class="coupon-builder-card tight">
              <div class="coupon-step-line">
                <div class="coupon-step-num">1B</div>
                <div class="coupon-step-title">Codigos masivos</div>
              </div>
              <div class="coupon-step-sub">Pega un codigo por linea o carga un Excel/CSV. Todos usaran la misma configuracion.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        bulk_col, upload_col = st.columns([1.4, .8])
        with bulk_col:
            bulk_text = st.text_area(
                "Codigos de cupon",
                value="\n".join(data.get("couponCodes") or ([data.get("codigoCupon")] if data.get("codigoCupon") else [])),
                height=130,
                placeholder="TATI15\nJUAN15\nMARIA15\nSOFIA15",
            )
        with upload_col:
            bulk_file = st.file_uploader("Cargar codigos Excel/CSV", type=["xlsx", "csv"], key="coupon_bulk_file")
            uploaded_codes = read_coupon_codes_upload(bulk_file) if bulk_file else []
        bulk_codes = uploaded_codes or parse_bulk_codes(bulk_text)
        data["couponCodes"] = bulk_codes
        if bulk_codes:
            data["codigoCupon"] = bulk_codes[0]
            data["nombreInterno"] = data.get("nombreInterno") or f"Campana {bulk_codes[0]}"
    else:
        data["couponCodes"] = [data.get("codigoCupon", "").strip().upper()] if data.get("codigoCupon") else []

    discount_label = (
        f"{data['valorDescuento']:.0f}%"
        if data["tipoDescuento"] == "Porcentaje"
        else f"S/ {data['valorDescuento']:.2f}"
    )
    min_label = "S/ 0.00" if float(data["compraMinima"] or 0) == 0 else f"S/ {float(data['compraMinima']):,.2f}"
    date_label = "Hoy" if data["fechaInicio"] == data["fechaFin"] else f"{data['fechaInicio']} - {data['fechaFin']}"
    enabled_sites = [site_cfg for site_cfg in unique_sites() if site_cfg["enabled"]]

    st.markdown(
        f"""
        <div class="coupon-summary-grid">
          <div class="coupon-summary-card">
            <div class="coupon-summary-icon">#</div>
            <div><div class="coupon-summary-label">Codigo cupon</div><div class="coupon-summary-value">{data['codigoCupon'] or '-'}</div><div class="coupon-summary-sub">{len(data.get('couponCodes') or [])} codigo(s)</div></div>
          </div>
          <div class="coupon-summary-card">
            <div class="coupon-summary-icon red">%</div>
            <div><div class="coupon-summary-label">Descuento</div><div class="coupon-summary-value">{discount_label}</div><div class="coupon-summary-sub">{data['tipoDescuento']}</div></div>
          </div>
          <div class="coupon-summary-card">
            <div class="coupon-summary-icon green">S</div>
            <div><div class="coupon-summary-label">Sitios seleccionados</div><div class="coupon-summary-value">{len(data['selectedSites'])}</div><div class="coupon-summary-sub">de {len(enabled_sites)} disponibles</div></div>
          </div>
          <div class="coupon-summary-card">
            <div class="coupon-summary-icon orange">F</div>
            <div><div class="coupon-summary-label">Vigencia</div><div class="coupon-summary-value">{date_label}</div><div class="coupon-summary-sub">{data['horaInicio']} - {data['horaFin']}</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    form_col, sites_col = st.columns([1.35, .95])
    with form_col:
        st.markdown(
            """
            <div class="coupon-builder-card tight">
              <div class="coupon-step-line">
                <div class="coupon-step-num">2</div>
                <div class="coupon-step-title">Condiciones del cupon</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        left, right = st.columns(2)
        with left:
            data["nombreInterno"] = st.text_input("Nombre interno", value=data["nombreInterno"])
            data["tipoDescuento"] = st.selectbox(
                "Tipo descuento",
                ["Porcentaje", "Monto fijo"],
                index=["Porcentaje", "Monto fijo"].index(data.get("tipoDescuento", "Porcentaje")),
            )
            data["priceBasis"] = st.selectbox(
                "Base de calculo",
                [PRICE_BASIS_CURRENT, PRICE_BASIS_COMPARE_AT_BEST_WINS],
                format_func=lambda value: "Price actual" if value == PRICE_BASIS_CURRENT else "Compare At Price - Best Wins",
                index=[PRICE_BASIS_CURRENT, PRICE_BASIS_COMPARE_AT_BEST_WINS].index(
                    data.get("priceBasis", PRICE_BASIS_CURRENT)
                ),
            )
            if data["priceBasis"] == PRICE_BASIS_COMPARE_AT_BEST_WINS:
                st.markdown(
                    '<div class="coupon-note">El cupon se calcula desde el precio original. Si el producto ya tiene una promocion mejor, se conserva automaticamente el precio mas bajo.</div>',
                    unsafe_allow_html=True,
                )
                data["missingCompareAtBehavior"] = st.selectbox(
                    "Cuando no existe Compare At Price",
                    ["use_current_price", "do_not_apply"],
                    format_func=lambda value: "Usar Price actual como base" if value == "use_current_price" else "No aplicar cupon",
                    index=["use_current_price", "do_not_apply"].index(
                        data.get("missingCompareAtBehavior", "use_current_price")
                    ),
                )
                data["functionMessage"] = st.text_input(
                    "Mensaje del descuento",
                    value=data.get("functionMessage", "Se aplico el mejor precio disponible"),
                )
            data["compraMinima"] = st.number_input(
                "Compra minima (S/)",
                min_value=0.0,
                value=float(data["compraMinima"] or 0),
                step=10.0,
            )
            data["descuentoMaximo"] = st.number_input(
                "Descuento maximo (S/)",
                min_value=0.0,
                value=float(data.get("descuentoMaximo") or 0),
                step=10.0,
            )
            data["fechaInicio"] = st.text_input("Fecha inicio", value=data["fechaInicio"], help="Formato YYYY-MM-DD")
            data["fechaFin"] = st.text_input("Fecha fin", value=data["fechaFin"], help="Formato YYYY-MM-DD")
            data["unaVezPorCliente"] = st.checkbox("Una vez por cliente", value=bool(data["unaVezPorCliente"]))
        with right:
            data["codigoCupon"] = st.text_input("Codigo cupon", value=data["codigoCupon"])
            data["valorDescuento"] = st.number_input(
                "Valor descuento",
                min_value=0.0,
                value=float(data["valorDescuento"]),
                step=1.0,
            )
            data["limiteTotalUsos"] = st.number_input(
                "Limite total de usos",
                min_value=0,
                value=int(data["limiteTotalUsos"] or 0),
                step=1,
            )
            data["horaInicio"] = st.text_input("Hora inicio", value=data["horaInicio"], help="Formato HH:MM")
            data["horaFin"] = st.text_input("Hora fin", value=data["horaFin"], help="Formato HH:MM")
            data["appliesTo"] = st.selectbox(
                "Aplicabilidad",
                ["Todos los productos", "Productos seleccionados", "Colecciones seleccionadas"],
                index=["Todos los productos", "Productos seleccionados", "Colecciones seleccionadas"].index(
                    data.get("appliesTo", "Todos los productos")
                ),
            )
        st.markdown("**Combinaciones permitidas en Shopify**")
        comb_cols = st.columns(3)
        with comb_cols[0]:
            data["combinaProducto"] = st.toggle("Descuentos de producto", value=bool(data.get("combinaProducto")))
        with comb_cols[1]:
            data["combinaPedido"] = st.toggle("Descuentos de pedido", value=bool(data.get("combinaPedido")))
        with comb_cols[2]:
            data["combinaEnvio"] = st.toggle("Descuentos de envio", value=bool(data.get("combinaEnvio")))

    with sites_col:
        st.markdown(
            f"""
            <div class="coupon-builder-card tight">
              <div class="coupon-step-line">
                <div class="coupon-step-num">3</div>
                <div class="coupon-step-title">Sitios Shopify</div>
              </div>
              <div class="coupon-site-pill">{len(data['selectedSites'])} seleccionados</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        all_site_ids = [site_cfg["id"] for site_cfg in enabled_sites]
        chosen_sites = []
        version = st.session_state["coupon_site_version"]
        for site_cfg in enabled_sites:
            checked = site_cfg["id"] in data["selectedSites"]
            if st.checkbox(
                f"{site_cfg['name']}    {site_cfg['id']}.pe",
                value=checked,
                key=f"coupon_site_{site_cfg['id']}_{version}",
            ):
                chosen_sites.append(site_cfg["id"])
        data["selectedSites"] = chosen_sites
        site_actions = st.columns(2)
        if site_actions[0].button("Seleccionar todos", use_container_width=True):
            data["selectedSites"] = all_site_ids
            st.session_state["coupon_data"] = data
            st.session_state["coupon_site_version"] += 1
            st.rerun()
        if site_actions[1].button("Limpiar", use_container_width=True):
            data["selectedSites"] = []
            st.session_state["coupon_data"] = data
            st.session_state["coupon_site_version"] += 1
            st.rerun()

    if mode == "Individual":
        data["couponCodes"] = [data.get("codigoCupon", "").strip().upper()] if data.get("codigoCupon") else []
    selected_shop_keys = {
        site_cfg["id"]: site_cfg["shop_key"]
        for site_cfg in enabled_sites
        if site_cfg["id"] in data["selectedSites"]
    }
    data["selectedShopKeys"] = list(selected_shop_keys.values())
    data["functionHandlesByShop"] = {
        shop_key: shopify_function_handle(shop_key)
        for shop_key in data["selectedShopKeys"]
    }
    data["functionIdsByShop"] = {
        shop_key: shopify_function_id(shop_key)
        for shop_key in data["selectedShopKeys"]
    }
    st.session_state["coupon_data"] = data
    min_label = "S/ 0.00" if float(data["compraMinima"] or 0) == 0 else f"S/ {float(data['compraMinima']):,.2f}"
    codes_for_preview = data.get("couponCodes") or ([data.get("codigoCupon")] if data.get("codigoCupon") else [])
    preview_rows = []
    for site_cfg in enabled_sites:
        if site_cfg["id"] in data["selectedSites"]:
            for code in codes_for_preview:
                preview_rows.append(
                    {
                        "Sitio": site_cfg["name"],
                        "Codigo": code,
                        "Descuento": f"{data['valorDescuento']:.0f}%" if data["tipoDescuento"] == "Porcentaje" else f"S/ {data['valorDescuento']:.2f}",
                        "Compra minima": min_label,
                        "Tope maximo": "Sin tope" if float(data.get("descuentoMaximo") or 0) == 0 else f"S/ {float(data['descuentoMaximo']):,.2f}",
                        "Vigencia": f"{data['fechaInicio']} {data['horaInicio']} - {data['fechaFin']} {data['horaFin']}",
                        "Uso por cliente": "Si" if data["unaVezPorCliente"] else "No",
                        "Combina": f"P:{'Si' if data.get('combinaProducto') else 'No'} / O:{'Si' if data.get('combinaPedido') else 'No'} / E:{'Si' if data.get('combinaEnvio') else 'No'}",
                        "Estado": "Listo",
                    }
                )

    st.markdown(
        f"""
        <div class="coupon-builder-card tight">
          <div class="coupon-step-line">
            <div class="coupon-step-num">4</div>
            <div class="coupon-step-title">Vista previa por sitio</div>
          </div>
          <div class="coupon-site-pill">{len(preview_rows)} sitios listos para crear</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if preview_rows:
        st.dataframe(pd.DataFrame(preview_rows), hide_index=True, use_container_width=True)

    if data.get("priceBasis") == PRICE_BASIS_COMPARE_AT_BEST_WINS:
        st.markdown(
            """
            <div class="coupon-builder-card tight">
              <div class="coupon-step-line">
                <div class="coupon-step-num">BW</div>
                <div class="coupon-step-title">Vista previa Best Wins por producto</div>
              </div>
              <div class="coupon-step-sub">Simula la logica de Compare At Price contra el Price actual. Nunca aumenta el precio ni descuenta si la promocion vigente ya gana.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame(build_preview_rows(data)), hide_index=True, use_container_width=True)

    for alert in data.get("parserAlerts", []):
        css_class = "coupon-warning" if alert.get("blocking") else "coupon-note"
        st.markdown(f'<div class="{css_class}">{alert.get("message")}</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="coupon-preview-card">
          <div class="coupon-preview-code">{data['codigoCupon'] or '-'}</div>
          <div class="coupon-preview-discount">{discount_label} OFF</div>
          <div class="coupon-preview-meta">Base de calculo: {'Compare At Price - Best Wins' if data.get('priceBasis') == PRICE_BASIS_COMPARE_AT_BEST_WINS else 'Price actual'}</div>
          <div class="coupon-preview-meta">Vigencia: {data['fechaInicio']} {data['horaInicio']} hasta {data['fechaFin']} {data['horaFin']}</div>
          <div class="coupon-preview-meta">Aplicabilidad: {data.get('appliesTo', 'Todos los productos')}</div>
          <div class="coupon-preview-meta">Combinaciones: Producto {'Si' if data.get('combinaProducto') else 'No'} · Pedido {'Si' if data.get('combinaPedido') else 'No'} · Envio {'Si' if data.get('combinaEnvio') else 'No'}</div>
          <div class="coupon-preview-meta">{len(codes_for_preview)} cupon(es) x {len(data['selectedSites'])} sitio(s) listos para revisar</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    errors = validate_coupon_data(
        data,
        function_ids_by_shop=data.get("functionIdsByShop", {}),
        function_handles_by_shop=data.get("functionHandlesByShop", {}),
    )
    for error in errors:
        st.markdown(f'<div class="coupon-warning">{error}</div>', unsafe_allow_html=True)

    total_to_create = len(codes_for_preview) * len(data["selectedSites"])
    button_label = f"Crear {total_to_create} cupon" if total_to_create == 1 else f"Crear {total_to_create} cupones"
    create_disabled = bool(errors)
    st.markdown(
        f"""
        <div class="coupon-bottom-bar">
          <div>
            <div class="coupon-bottom-title">Se crearan {total_to_create} cupones en Shopify</div>
            <div class="coupon-bottom-sub">Revisa la vista previa antes de continuar.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    draft_col, create_col = st.columns([1, 1])
    if draft_col.button("Guardar borrador", use_container_width=True):
        st.info("Borrador conservado en esta sesion.")
    if create_col.button(button_label, type="primary", use_container_width=True, disabled=create_disabled):
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
        st.markdown(
            '<div class="coupon-builder-card tight"><div class="coupon-step-line"><div class="coupon-step-num">OK</div><div class="coupon-step-title">Resultados de creacion</div></div></div>',
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame(st.session_state["coupon_results"]), hide_index=True, use_container_width=True)

    with st.expander("Secrets necesarios para Shopify"):
        secret_example = (
            "[shopify_sites." + shop_key + "]\n"
            'shop_domain = "' + shop_key + '.myshopify.com"\n'
            'client_id = ""\n'
            'client_secret = ""\n'
            'admin_access_token = "shpat_xxxxxxxxxxxxxxxxx"\n'
            'api_version = "2026-04"\n'
            'compare_at_best_wins_function_handle = "compare-at-best-wins"'
        )
        st.code(secret_example, language="toml")
        st.caption("Para Compare At Price - Best Wins necesitas una Shopify Discount Function desplegada y permisos write_discounts.")


if module == "Generar cupones":
    render_coupon_builder(site_name, site)
    st.stop()
    render_top_header(site_name)
    shop_key = site["shop_key"]
    st.markdown(
        """
        <div class="coupon-hero">
          <div>
            <h2>Smart Coupon Builder</h2>
            <p>Interpreta el texto comercial, valida fechas y crea cupones Shopify por sitio sin repetir trabajo manual.</p>
          </div>
          <div class="coupon-hero-mini">
            <div class="coupon-hero-chip">Texto inteligente<span>Codigo, % y vigencia</span></div>
            <div class="coupon-hero-chip">Shopify API<span>Creacion por tienda</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "coupon_data" not in st.session_state:
        st.session_state["coupon_data"] = default_coupon_data()
    if "coupon_results" not in st.session_state:
        st.session_state["coupon_results"] = []

    st.markdown(
        """
        <div class="coupon-card soft">
          <div class="coupon-section-head">
            <div>
              <h3>1. Pega la promocion</h3>
              <p>La app reconoce codigo, descuento, fechas, minimo de compra, uso por cliente y sitios mencionados.</p>
            </div>
            <div class="coupon-badge">Editable despues</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    promotion_text = st.text_area(
        "Describe la promocion",
        value=st.session_state.get("promotion_text", ""),
        placeholder="Crear cupon BBVA40 con 40% de descuento para todos los sitios, valido del 15 al 30 de junio, una vez por cliente y compra minima S/299.",
        height=120,
        key="promotion_text",
    )
    st.markdown('<div class="coupon-chip-row">', unsafe_allow_html=True)
    chip_cols = st.columns(len(QUICK_TEMPLATES))
    for column, (chip, template) in zip(chip_cols, QUICK_TEMPLATES.items()):
        if column.button(chip, use_container_width=True):
            st.session_state["promotion_text"] = template
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("Interpretar promocion", type="primary", use_container_width=True):
        with st.spinner("Interpretando promocion..."):
            st.session_state["coupon_data"] = parse_coupon_text(promotion_text)
            st.session_state["coupon_results"] = []
        st.markdown('<div class="coupon-note">Promocion interpretada. Puedes editar cualquier campo antes de crear.</div>', unsafe_allow_html=True)

    data = st.session_state["coupon_data"].copy()
    st.markdown(
        """
        <div class="coupon-card">
          <div class="coupon-section-head">
            <div>
              <h3>2. Configura el cupon</h3>
              <p>Todo queda editable antes de enviarlo a Shopify.</p>
            </div>
            <div class="coupon-badge">Validacion activa</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        data["nombreInterno"] = st.text_input("Nombre interno", value=data["nombreInterno"])
        data["codigoCupon"] = st.text_input("Codigo cupon", value=data["codigoCupon"])
        data["tipoDescuento"] = st.selectbox(
            "Tipo descuento",
            ["Porcentaje", "Monto fijo"],
            index=["Porcentaje", "Monto fijo"].index(data.get("tipoDescuento", "Porcentaje")),
        )
        data["valorDescuento"] = st.number_input("Valor descuento", min_value=0.0, value=float(data["valorDescuento"]), step=1.0)
        data["compraMinima"] = st.number_input("Compra minima", min_value=0.0, value=float(data["compraMinima"] or 0), step=10.0)
    with right:
        data["fechaInicio"] = st.text_input("Fecha inicio", value=data["fechaInicio"], help="Formato YYYY-MM-DD")
        data["horaInicio"] = st.text_input("Hora inicio", value=data["horaInicio"], help="Formato HH:MM")
        data["fechaFin"] = st.text_input("Fecha fin", value=data["fechaFin"], help="Formato YYYY-MM-DD")
        data["horaFin"] = st.text_input("Hora fin", value=data["horaFin"], help="Formato HH:MM")
        data["limiteTotalUsos"] = st.number_input("Limite total de usos (0 = sin limite)", min_value=0, value=int(data["limiteTotalUsos"] or 0), step=1)
        data["unaVezPorCliente"] = st.checkbox("Una vez por cliente", value=bool(data["unaVezPorCliente"]))

    st.markdown(
        """
        <div class="coupon-card">
          <div class="coupon-section-head">
            <div>
              <h3>3. Selecciona sitios Shopify</h3>
              <p>La seleccion define en que tiendas se creara el mismo codigo.</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    all_site_ids = [site["id"] for site in COUPON_SHOPIFY_SITES if site["enabled"]]
    site_options = {site["name"]: site["id"] for site in COUPON_SHOPIFY_SITES if site["enabled"]}
    selected_names = [name for name, site_id in site_options.items() if site_id in data["selectedSites"]]
    selected_names = st.multiselect("Sitios Shopify", list(site_options), default=selected_names)
    data["selectedSites"] = [site_options[name] for name in selected_names]
    site_actions = st.columns([1, 1, 3])
    if site_actions[0].button("Seleccionar todos"):
        data["selectedSites"] = all_site_ids
        st.session_state["coupon_data"] = data
        st.rerun()
    if site_actions[1].button("Limpiar"):
        data["selectedSites"] = []
        st.session_state["coupon_data"] = data
        st.rerun()
    st.markdown(f'<div class="coupon-site-count">{len(data["selectedSites"])} sitios seleccionados</div>', unsafe_allow_html=True)

    st.session_state["coupon_data"] = data
    preview_rows = []
    for site in COUPON_SHOPIFY_SITES:
        if site["id"] in data["selectedSites"]:
            preview_rows.append(
                {
                    "Sitio": site["name"],
                    "Codigo": data["codigoCupon"],
                    "Descuento": f"{data['valorDescuento']:.0f}%" if data["tipoDescuento"] == "Porcentaje" else f"S/ {data['valorDescuento']:.2f}",
                    "Vigencia": f"{data['fechaInicio']} {data['horaInicio']} - {data['fechaFin']} {data['horaFin']}",
                    "Estado": "Listo",
                }
            )

    discount_label = f"{data['valorDescuento']:.0f}%" if data["tipoDescuento"] == "Porcentaje" else f"S/ {data['valorDescuento']:.2f}"
    min_label = "Sin minimo" if float(data["compraMinima"] or 0) == 0 else f"S/ {float(data['compraMinima']):,.2f}"
    usage_label = "1 por cliente" if data["unaVezPorCliente"] else "Sin restriccion"
    st.markdown(
        f"""
        <div class="coupon-card soft">
          <div class="coupon-section-head">
            <div>
              <h3>4. Vista previa</h3>
              <p>Resumen final antes de crear el cupon en Shopify.</p>
            </div>
            <div class="coupon-badge">{len(data['selectedSites'])} tiendas</div>
          </div>
          <div class="coupon-kpi-grid">
            <div class="coupon-kpi"><b>{data['codigoCupon'] or '-'}</b><span>Codigo</span></div>
            <div class="coupon-kpi"><b>{discount_label}</b><span>Descuento</span></div>
            <div class="coupon-kpi"><b>{min_label}</b><span>Compra minima</span></div>
            <div class="coupon-kpi"><b>{usage_label}</b><span>Uso</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if preview_rows:
        st.markdown('<div class="preview-panel"><div class="preview-title">Detalle por sitio</div><div class="preview-sub">Estos son los cupones que se enviaran a Shopify.</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(preview_rows), hide_index=True, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    errors = validate_coupon_data(data)
    for error in errors:
        st.markdown(f'<div class="coupon-warning">{error}</div>', unsafe_allow_html=True)

    button_label = f"Crear {len(data['selectedSites'])} cupon" if len(data["selectedSites"]) == 1 else f"Crear {len(data['selectedSites'])} cupones"
    create_disabled = bool(errors)
    if st.button(button_label, type="primary", use_container_width=True, disabled=create_disabled):
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
        st.markdown('<div class="coupon-card"><div class="coupon-section-head"><div><h3>Resultados de creacion</h3><p>Estado devuelto por cada tienda Shopify.</p></div></div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(st.session_state["coupon_results"]), hide_index=True, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Secrets necesarios para Shopify"):
        secret_example = (
            "[shopify_sites." + shop_key + "]\n"
            'shop_domain = "' + shop_key + '.myshopify.com"\n'
            'client_id = ""\n'
            'client_secret = ""\n'
            'admin_access_token = "shpat_xxxxxxxxxxxxxxxxx"\n'
            'api_version = "2026-04"'
        )
        st.code(
            secret_example,
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
    revenue_file = st.file_uploader("1. Subir Revenue / input comercial", type=["xlsx", "xlsm"], key="revenue")
with upload_right:
    matrixify_file = st.file_uploader(
        f"2. Subir ultimo catalogo Matrixify de {site_name}",
        type=["xlsx", "xlsm"],
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
            use_container_width=True,
            key="download_matrixify_top",
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
            key="download_matrixify_bottom",
        )
    except Exception as exc:
        st.error(f"No pude generar el archivo: {exc}")
else:
    st.info("Carga ambos archivos para comenzar.")
