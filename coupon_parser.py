from __future__ import annotations

import calendar
import re
import unicodedata
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
    "columbia": ["columbia", "clb", "columbia.pe", "www.columbia.pe"],
    "rockford": ["rockford", "rkf", "rockford.pe", "www.rockford.pe"],
    "hushpuppies": ["hush puppies", "hushpuppies", "hp", "hushpuppies.pe", "www.hushpuppies.pe"],
    "bsoul": ["bsoul", "b soul", "bsoul.pe", "www.bsoul.pe"],
    "rkslife": ["rkslife", "rks life", "rkslife.pe", "www.rkslife.pe"],
    "keds": ["keds", "keds.pe", "www.keds.pe"],
    "vans": ["vans", "vans.pe", "www.vans.pe"],
    "supermall": ["supermall", "sml", "supermall.pe", "www.supermall.pe"],
}


def default_coupon_data(today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    today_text = today.isoformat()
    return {
        "nombreInterno": "",
        "codigoCupon": "",
        "couponCodes": [],
        "creationMode": "Individual",
        "tipoDescuento": "Porcentaje",
        "valorDescuento": 0.0,
        "descuentoMaximo": 0.0,
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
        "combinaProducto": False,
        "combinaPedido": False,
        "combinaEnvio": False,
        "acumulaPromociones": None,
        "acumulaCupones": None,
        "condiciones": [],
        "exclusiones": [],
        "parserAlerts": [],
    }


def parse_coupon_text(text: str, now: date | None = None) -> dict[str, Any]:
    now = now or date.today()
    normalized = normalize(text)
    data = default_coupon_data(now)
    alerts: list[dict[str, Any]] = []

    code = detect_coupon_code(text)
    percent = detect_percentage(normalized)
    fixed_amount = detect_fixed_discount(normalized)
    minimum = detect_money_after(
        normalized,
        [
            r"compra minima",
            r"compra m.nima",
            r"minimo de compra",
            r"m.nimo de compra",
            r"monto minimo",
            r"monto m.nimo",
            r"minima",
            r"m.nima",
        ],
    )
    max_discount = detect_money_after(
        normalized,
        [
            r"descuento maximo",
            r"descuento m.ximo",
            r"tope maximo",
            r"tope m.ximo",
            r"dcto\.? maximo",
            r"dcto\.? m.ximo",
        ],
    )
    date_range = detect_date_range(normalized, now, alerts)
    time_range = detect_time_range(normalized)

    data["codigoCupon"] = code
    data["nombreInterno"] = code or ""
    data["couponCodes"] = [code] if code else []

    if percent is not None:
        data["tipoDescuento"] = "Porcentaje"
        data["valorDescuento"] = percent
    elif fixed_amount is not None:
        data["tipoDescuento"] = "Monto fijo"
        data["valorDescuento"] = fixed_amount

    if minimum is not None:
        data["compraMinima"] = minimum
    if max_discount is not None:
        data["descuentoMaximo"] = max_discount
        alerts.append(
            warning(
                "Se detecto descuento maximo. Shopify Basic Discount puede no soportar tope maximo para cupon porcentual; revisa antes de crear."
            )
        )
    if date_range:
        data["fechaInicio"], data["fechaFin"] = date_range
    if time_range:
        data["horaInicio"], data["horaFin"] = time_range

    data["selectedSites"] = detect_sites(normalized, code)
    data["appliesTo"] = detect_applicability(normalized)
    data["unaVezPorCliente"] = detect_once_per_customer(normalized, alerts)
    promo_acc, coupon_acc = detect_accumulation(normalized)
    data["acumulaPromociones"] = promo_acc
    data["acumulaCupones"] = coupon_acc
    data["combinaProducto"] = bool(promo_acc)
    data["combinaPedido"] = bool(coupon_acc)
    data["combinaEnvio"] = False
    data["condiciones"] = detect_conditions(text)
    data["exclusiones"] = detect_exclusions(text)

    if not code:
        alerts.append(blocking("No se pudo identificar el nombre o codigo del cupon."))
    if percent is None and fixed_amount is None:
        alerts.append(blocking("No se pudo identificar el valor del descuento."))
    if not data["selectedSites"]:
        alerts.append(warning("No se reconocio ningun sitio en el texto. Seleccionalo manualmente."))
    if not date_range:
        alerts.append(warning("No se pudo identificar una vigencia completa. Revisa fecha de inicio y termino."))
    if re.search(r"sin\s+l.?mite\s+de\s+un\s*(?:\(1\))?\s+uso\s+por\s+mes", normalized):
        alerts.append(warning('Se detecto una condicion ambigua: "Sin limite de un (1) uso por mes". Revisa limite de uso.'))

    data["parserAlerts"] = alerts
    return data


def parse_bulk_codes(text: str) -> list[str]:
    codes = []
    for raw in re.split(r"[\n,;|\t]+", text or ""):
        value = clean_code(raw)
        if value:
            codes.append(value)
    return codes


def detect_coupon_code(text: str) -> str:
    normalized = normalize(text)
    label_patterns = [
        r"(?:nombre\s+del\s+cupon|codigo\s+de\s+descuento|c.digo\s+de\s+descuento|codigo|c.digo|cupon|cup.n)\s*:?\s*([a-z0-9][a-z0-9_-]{2,})",
    ]
    for pattern in label_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return clean_code(match.group(1))
    match = re.search(r"\b[A-Z][A-Z0-9_-]{2,}\d{1,3}\b", remove_urls(text.upper()))
    return clean_code(match.group(0)) if match else ""


def detect_percentage(text: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|por ciento|porciento)", text)
    return float(match.group(1).replace(",", ".")) if match else None


def detect_fixed_discount(text: str) -> float | None:
    if "%" in text:
        return None
    return detect_money_after(text, [r"descuento", r"off", r"rebaja"])


def detect_money_after(text: str, labels: list[str]) -> float | None:
    for label in labels:
        patterns = [
            rf"{label}[^\d]{{0,25}}(?:s/|s\.|soles)?\s*(\d+(?:[.,]\d+)?)",
            rf"(?:s/|s\.|soles)\s*(\d+(?:[.,]\d+)?)\s*[^\n]{{0,25}}{label}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1).replace(",", "."))
    return None


def detect_sites(text: str, coupon_code: str = "") -> list[str]:
    has_bank = any(keyword.lower() in text or keyword in coupon_code.upper() for keyword in BANK_KEYWORDS)
    if "todos los sitios" in text or "todas las tiendas" in text or has_bank:
        return [site["id"] for site in unique_sites() if site["enabled"]]

    selected = []
    searchable = remove_urls(text) + " " + text
    for site_id, aliases in SITE_ALIASES.items():
        if any(alias in searchable for alias in aliases):
            selected.append(site_id)
    return dedupe_keep_order(selected)


def detect_applicability(text: str) -> str:
    if "toda la web" in text or "todo el catalogo" in text or "toda la tienda" in text:
        return "Todos los productos"
    if "productos seleccionados" in text:
        return "Productos seleccionados"
    if "colecciones seleccionadas" in text or "coleccion" in text:
        return "Colecciones seleccionadas"
    return "Todos los productos"


def detect_once_per_customer(text: str, alerts: list[dict[str, Any]]) -> bool:
    if re.search(r"sin\s+l.?mite\s+de\s+un\s*(?:\(1\))?\s+uso\s+por\s+mes", text):
        return False
    return bool(
        re.search(
            r"una vez por cliente|1 uso por cliente|un uso por cliente|un solo uso por usuario|un uso por usuario",
            text,
        )
    )


def detect_accumulation(text: str) -> tuple[bool | None, bool | None]:
    promo = None
    coupon = None
    if re.search(r"no\s+(?:es|son)?\s*acumulables?[^\n]*(?:promociones|descuentos)", text):
        promo = False
    elif re.search(r"acumulable[^\n]*(?:promociones|descuentos)", text):
        promo = True
    if re.search(r"no\s+(?:es|son)?\s*acumulables?[^\n]*(?:cupon|codigo)", text):
        coupon = False
    elif re.search(r"acumulable[^\n]*(?:cupon|codigo)", text):
        coupon = True
    return promo, coupon


def detect_conditions(text: str) -> list[str]:
    lines = [line.strip(" >-*") for line in text.splitlines() if line.strip()]
    return [
        line
        for line in lines
        if any(word in normalize(line) for word in ["acumulable", "uso", "limite", "minima", "maximo", "condicion"])
    ][:8]


def detect_exclusions(text: str) -> list[str]:
    lines = [line.strip(" >-*") for line in text.splitlines() if line.strip()]
    return [line for line in lines if "no aplica" in normalize(line) or "exclu" in normalize(line)][:8]


def detect_date_range(text: str, now: date, alerts: list[dict[str, Any]]) -> tuple[str, str] | None:
    if "hoy" in text:
        return now.isoformat(), now.isoformat()
    if "manana" in text:
        tomorrow = now + timedelta(days=1)
        return tomorrow.isoformat(), tomorrow.isoformat()
    if "fin de mes" in text:
        last_day = calendar.monthrange(now.year, now.month)[1]
        return now.isoformat(), date(now.year, now.month, last_day).isoformat()

    numeric = detect_numeric_date_range(text, now, alerts)
    if numeric:
        return numeric

    same_month = re.search(
        r"(?:del|desde\s+el)?\s*(\d{1,2})\s+(?:al|hasta\s+el)\s+(\d{1,2})\s+de\s+([a-z]+)(?:\s+(?:del|de)\s+(\d{4}))?",
        text,
    )
    if same_month:
        year = int(same_month.group(4) or now.year)
        return build_date_pair(
            int(same_month.group(1)),
            month_number(same_month.group(3)),
            year,
            int(same_month.group(2)),
            month_number(same_month.group(3)),
            year,
            alerts,
        )

    long_range = re.search(
        r"(?:desde\s+el|del)?\s*(\d{1,2})\s+de\s+([a-z]+)\s+(?:hasta\s+el|al|-)\s+(\d{1,2})\s+de\s+([a-z]+)(?:\s+(?:del|de)\s+(\d{4}))?",
        text,
    )
    if long_range:
        year = int(long_range.group(5) or now.year)
        return build_date_pair(
            int(long_range.group(1)),
            month_number(long_range.group(2)),
            year,
            int(long_range.group(3)),
            month_number(long_range.group(4)),
            year,
            alerts,
        )

    single = re.search(r"(\d{1,2})\s+de\s+([a-z]+)(?:\s+(?:del|de)\s+(\d{4}))?", text)
    if single:
        year = int(single.group(3) or now.year)
        start = safe_date(int(single.group(1)), month_number(single.group(2)), year, alerts)
        return (start.isoformat(), start.isoformat()) if start else None
    return None


def detect_numeric_date_range(text: str, now: date, alerts: list[dict[str, Any]]) -> tuple[str, str] | None:
    pattern = r"(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\s*(?:al|hasta|-|a)\s*(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?"
    match = re.search(pattern, text)
    if not match:
        return None
    start_year = normalize_year(match.group(3), now.year)
    end_year = normalize_year(match.group(6), start_year)
    return build_date_pair(
        int(match.group(1)),
        int(match.group(2)),
        start_year,
        int(match.group(4)),
        int(match.group(5)),
        end_year,
        alerts,
    )


def build_date_pair(
    start_day: int,
    start_month: int | None,
    start_year: int,
    end_day: int,
    end_month: int | None,
    end_year: int,
    alerts: list[dict[str, Any]],
) -> tuple[str, str] | None:
    start = safe_date(start_day, start_month, start_year, alerts)
    end = safe_date(end_day, end_month, end_year, alerts)
    if not start or not end:
        return None
    return start.isoformat(), end.isoformat()


def safe_date(day: int, month: int | None, year: int, alerts: list[dict[str, Any]]) -> date | None:
    if not month:
        alerts.append(blocking("Se detecto una fecha con mes no reconocido. Revisa la vigencia."))
        return None
    try:
        return date(year, month, day)
    except ValueError:
        month_name = next((name for name, number in MONTHS.items() if number == month), str(month))
        alerts.append(blocking(f"Se detecto una fecha invalida: {day} de {month_name} de {year}. Revisa y corrige la fecha."))
        return None


def detect_time_range(text: str) -> tuple[str, str] | None:
    match = re.search(
        r"(\d{1,2})(?::(\d{2}))?\s*(?:a\.?\s*m\.?|am|p\.?\s*m\.?|pm)?\s*(?:hasta|a|-)\s*(\d{1,2})(?::(\d{2}))?\s*(a\.?\s*m\.?|am|p\.?\s*m\.?|pm)?",
        text,
    )
    if not match:
        return None
    start = normalize_time_parts(match.group(1), match.group(2), "")
    end = normalize_time_parts(match.group(3), match.group(4), match.group(5) or "")
    if start and end:
        return start, end
    return None


def normalize_time_parts(hour_text: str, minute_text: str | None, meridian: str) -> str:
    hour = int(hour_text)
    minute = int(minute_text or 0)
    meridian = normalize(meridian)
    if "p" in meridian and hour < 12:
        hour += 12
    if "a" in meridian and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def normalize_year(value: str | None, fallback: int) -> int:
    if not value:
        return fallback
    year = int(value)
    return 2000 + year if year < 100 else year


def month_number(value: str) -> int | None:
    return MONTHS.get(normalize(value))


def clean_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9_-]", "", str(value or "").upper())


def unique_sites() -> list[dict[str, Any]]:
    seen = set()
    sites = []
    for site in COUPON_SHOPIFY_SITES:
        key = site["id"]
        if key in seen:
            continue
        seen.add(key)
        sites.append(site)
    return sites


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def warning(message: str) -> dict[str, Any]:
    return {"level": "warning", "message": message, "blocking": False}


def blocking(message: str) -> dict[str, Any]:
    return {"level": "error", "message": message, "blocking": True}


def normalize(text: str) -> str:
    return remove_accents(str(text or "").lower())


def remove_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def remove_urls(text: str) -> str:
    return re.sub(r"https?://|www\.", "", normalize(text))


def combine_datetime(date_text: str, time_text: str) -> datetime:
    return datetime.fromisoformat(f"{date_text}T{time_text}:00")
