from __future__ import annotations

from coupon_parser import combine_datetime


def validate_coupon_data(data: dict) -> list[str]:
    errors = []
    if not str(data.get("codigoCupon", "")).strip():
        errors.append("El codigo del cupon es obligatorio.")
    if not data.get("selectedSites"):
        errors.append("Selecciona al menos un sitio Shopify.")
    tipo = data.get("tipoDescuento")
    value = float(data.get("valorDescuento") or 0)
    if tipo != "Envio gratis" and value <= 0:
        errors.append("El valor de descuento debe ser mayor a 0.")
    if tipo == "Porcentaje" and value > 100:
        errors.append("El porcentaje no puede ser mayor a 100.")
    if float(data.get("compraMinima") or 0) < 0:
        errors.append("La compra minima no puede ser negativa.")
    if int(data.get("limiteTotalUsos") or 0) < 0:
        errors.append("El limite total de usos no puede ser negativo.")
    if combine_datetime(data["fechaFin"], data["horaFin"]) <= combine_datetime(data["fechaInicio"], data["horaInicio"]):
        errors.append("La fecha/hora fin debe ser mayor que la fecha/hora inicio.")
    return errors
