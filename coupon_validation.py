from __future__ import annotations

from compare_at_best_wins import PRICE_BASIS_COMPARE_AT_BEST_WINS
from coupon_parser import combine_datetime


def validate_coupon_data(
    data: dict,
    function_ids_by_shop: dict[str, str] | None = None,
    function_handles_by_shop: dict[str, str] | None = None,
) -> list[str]:
    errors = []
    codes = data.get("couponCodes") or []
    if not codes and str(data.get("codigoCupon", "")).strip():
        codes = [str(data.get("codigoCupon", "")).strip()]
    if not codes:
        errors.append("El codigo del cupon es obligatorio.")
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        errors.append("Hay codigos duplicados en la lista: " + ", ".join(duplicates[:10]))
    if not data.get("selectedSites"):
        errors.append("Selecciona al menos un sitio Shopify.")
    tipo = data.get("tipoDescuento")
    value = float(data.get("valorDescuento") or 0)
    if tipo != "Envio gratis" and value <= 0:
        errors.append("El valor de descuento debe ser mayor a 0.")
    if tipo == "Porcentaje" and value > 100:
        errors.append("El porcentaje no puede ser mayor a 100.")
    if data.get("priceBasis") == PRICE_BASIS_COMPARE_AT_BEST_WINS:
        if tipo != "Porcentaje":
            errors.append("Compare At Price - Best Wins solo esta disponible para descuentos porcentuales.")
        if not data.get("selectedSites"):
            pass
        elif function_handles_by_shop is not None or function_ids_by_shop is not None:
            missing = []
            for shop_key in data.get("selectedShopKeys", []):
                handle = (function_handles_by_shop or {}).get(shop_key)
                function_id = (function_ids_by_shop or {}).get(shop_key)
                if not handle and not function_id:
                    missing.append(shop_key)
            if missing:
                errors.append(
                    "Falta compare_at_best_wins_function_handle en Secrets para: "
                    + ", ".join(sorted(missing))
                    + "."
                )
    if float(data.get("compraMinima") or 0) < 0:
        errors.append("La compra minima no puede ser negativa.")
    if float(data.get("descuentoMaximo") or 0) < 0:
        errors.append("El descuento maximo no puede ser negativo.")
    if int(data.get("limiteTotalUsos") or 0) < 0:
        errors.append("El limite total de usos no puede ser negativo.")
    for alert in data.get("parserAlerts", []):
        if alert.get("blocking"):
            errors.append(alert.get("message", "Hay un error critico detectado en el texto."))
    try:
        ends_at = combine_datetime(data["fechaFin"], data["horaFin"])
        starts_at = combine_datetime(data["fechaInicio"], data["horaInicio"])
    except Exception:
        errors.append("Fecha u hora invalida. Usa formato YYYY-MM-DD y HH:MM.")
        return errors
    if ends_at <= starts_at:
        errors.append("La fecha/hora fin debe ser mayor que la fecha/hora inicio.")
    return errors
