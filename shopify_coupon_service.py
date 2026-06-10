from __future__ import annotations

from typing import Callable

from coupon_config import COUPON_SHOPIFY_SITES


def build_shopify_discount_payload(data: dict, customer_segment_id: str = "") -> dict:
    customer_context = {"all": True}
    if customer_segment_id:
        customer_context = {"customerSegments": {"add": [customer_segment_id]}}

    payload = {
        "title": data["nombreInterno"].strip() or data["codigoCupon"].strip(),
        "code": data["codigoCupon"].strip().upper(),
        "startsAt": build_iso_datetime(data["fechaInicio"], data["horaInicio"]),
        "endsAt": build_iso_datetime(data["fechaFin"], data["horaFin"]),
        "appliesOncePerCustomer": bool(data.get("unaVezPorCliente")),
        "customerSelection": customer_context,
        "customerGets": {
            "items": {"all": True},
            "value": build_discount_value(data),
        },
    }
    if int(data.get("limiteTotalUsos") or 0) > 0:
        payload["usageLimit"] = int(data["limiteTotalUsos"])
    if float(data.get("compraMinima") or 0) > 0:
        payload["minimumRequirement"] = {
            "subtotal": {"greaterThanOrEqualToSubtotal": str(round(float(data["compraMinima"]), 2))}
        }
    return payload


def create_coupon_for_multiple_sites(
    data: dict,
    segment_ids_by_site: dict[str, str],
    shopify_create: Callable[[str, dict], dict],
    configured_checker: Callable[[str], bool],
) -> list[dict]:
    results = []
    selected_sites = set(data.get("selectedSites", []))
    for site in COUPON_SHOPIFY_SITES:
        if site["id"] not in selected_sites:
            continue
        if not configured_checker(site["shop_key"]):
            results.append(result_row(site, data, "error", "Falta configurar Shopify API para este sitio."))
            continue
        try:
            payload = build_shopify_discount_payload(data, segment_ids_by_site.get(site["id"], ""))
            response = shopify_create(site["shop_key"], payload)
            discount_id = response.get("codeDiscountNode", {}).get("id")
            results.append(result_row(site, data, "success", "Cupon creado correctamente.", discount_id))
        except Exception as exc:
            results.append(result_row(site, data, "error", str(exc)))
    return results


def build_discount_value(data: dict) -> dict:
    tipo = data.get("tipoDescuento")
    value = float(data.get("valorDescuento") or 0)
    if tipo == "Monto fijo":
        return {"discountAmount": {"amount": str(round(value, 2)), "appliesOnEachItem": False}}
    return {"percentage": value / 100}


def build_iso_datetime(date_text: str, time_text: str) -> str:
    return f"{date_text}T{time_text}:00-05:00"


def result_row(site: dict, data: dict, status: str, message: str, discount_id: str | None = None) -> dict:
    return {
        "siteId": site["id"],
        "siteName": site["name"],
        "couponCode": data.get("codigoCupon", ""),
        "status": status,
        "message": message,
        "shopifyDiscountId": discount_id or "",
    }
