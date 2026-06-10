from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from coupon_config import BANK_KEYWORDS, COUPON_SHOPIFY_SITES


MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

SITE_ALIASES = {
    "columbia": ["columbia"],
    "rockford": ["rockford"],
    "hushpuppies": ["hush puppies", "hushpuppies"],
    "vans": ["vans"],
    "supermall": ["supermall"],
}


def default_coupon_data(today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    today_text = today.isoformat()
    return {
        "nombreInterno": "",
        "codigoCupon": "",
        "tipoDescuento": "Porcentaje",
        "valorDescuento": 0.0,
        "compraMinima": 0.0,
        "fechaInicio": today_text,
        "horaInicio": "00:00",
        "fechaFin": today_text,
        "horaFin": "23:59",
        "limiteTotalUsos": 0,
        "unaVezPorCliente": False,
        "customerSelection": "Todos los clientes",
        "appliesTo": "Todos los productos",
        "selectedSites": [],
    }


def parse_coupon_text(text: str, now: date | None = None) -> dict[str, Any]:
    now = now or date.today()
    lower = normalize(text)
    data = default_coupon_data(now)

    code = detect_coupon_code(text)
    percent = detect_percentage(lower)
    minimum = detect_minimum_purchase(lower)
    date_range = detect_date_range(lower, now)
    time_range = detect_time_range(lower)

    data["codigoCupon"] = code
    data["nombreInterno"] = f"Campana {code}" if code else ""
    if percent is not None:
        data["tipoDescuento"] = "Porcentaje"
        data["valorDescuento"] = percent
    if minimum is not None:
        data["compraMinima"] = minimum
    if date_range:
        data["fechaInicio"], data["fechaFin"] = date_range
    if time_range:
        data["horaInicio"], data["horaFin"] = time_range
    data["unaVezPorCliente"] = bool(re.search(r"una vez por cliente|1 uso por cliente|un uso por cliente", lower))
    data["selectedSites"] = detect_sites(lower, code)
    return data


def detect_coupon_code(text: str) -> str:
    match = re.search(r"\b[A-Z]{2,}[A-Z0-9]*\d{1,3}\b", text.upper())
    return match.group(0) if match else ""


def detect_percentage(text: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*%", text)
    if not match:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:por ciento|porciento)", text)
    return float(match.group(1).replace(",", ".")) if match else None


def detect_minimum_purchase(text: str) -> float | None:
    text = normalize(text)
    match = re.search(r"(?:compra minima|compra mínima|minimo|mínimo|minima|mínima)\s*(?:s/|s\.|soles)?\s*(\d+(?:[.,]\d+)?)", text)
    return float(match.group(1).replace(",", ".")) if match else None


def detect_sites(text: str, coupon_code: str = "") -> list[str]:
    hay_banco = any(keyword.lower() in text or keyword in coupon_code.upper() for keyword in BANK_KEYWORDS)
    if "todos los sitios" in text or "todas las tiendas" in text or hay_banco:
        return [site["id"] for site in COUPON_SHOPIFY_SITES if site["enabled"]]
    selected = []
    for site_id, aliases in SITE_ALIASES.items():
        if any(alias in text for alias in aliases):
            selected.append(site_id)
    return selected


def detect_date_range(text: str, now: date) -> tuple[str, str] | None:
    if "hoy" in text:
        return now.isoformat(), now.isoformat()
    if "manana" in text or "mañana" in text:
        tomorrow = now + timedelta(days=1)
        return tomorrow.isoformat(), tomorrow.isoformat()
    match = re.search(r"del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+([a-záéíóúñ]+)", text)
    if not match:
        return None
    month = MONTHS.get(remove_accents(match.group(3)))
    if not month:
        return None
    start = date(now.year, month, int(match.group(1)))
    end = date(now.year, month, int(match.group(2)))
    return start.isoformat(), end.isoformat()


def detect_time_range(text: str) -> tuple[str, str] | None:
    match = re.search(r"(?:desde\s*)?(\d{1,2}:\d{2})\s*(?:hasta|a|-)\s*(\d{1,2}:\d{2})", text)
    if not match:
        return None
    return normalize_time(match.group(1)), normalize_time(match.group(2))


def normalize(text: str) -> str:
    return remove_accents(text.lower())


def remove_accents(text: str) -> str:
    return (
        text.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )


def normalize_time(value: str) -> str:
    hour, minute = value.split(":")
    return f"{hour.zfill(2)}:{minute}"


def combine_datetime(date_text: str, time_text: str) -> datetime:
    return datetime.fromisoformat(f"{date_text}T{time_text}:00")
