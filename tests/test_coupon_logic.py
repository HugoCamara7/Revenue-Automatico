from datetime import date

from coupon_config import COUPON_SHOPIFY_SITES
from coupon_parser import detect_coupon_code, detect_percentage, parse_bulk_codes, parse_coupon_text
from coupon_validation import validate_coupon_data
from compare_at_best_wins import (
    PRICE_BASIS_COMPARE_AT_BEST_WINS,
    best_wins_line_result,
    build_function_configuration,
)
from shopify_coupon_service import build_shopify_app_discount_payload


def test_detecta_codigo_bbva40():
    assert detect_coupon_code("Crear cupon BBVA40 para todos") == "BBVA40"


def test_detecta_porcentaje_40():
    assert detect_percentage("crear cupon con 40% de descuento") == 40


def test_detecta_compra_minima_299():
    parsed = parse_coupon_text("Codigo: BBVA40 40% compra minima S/299", now=date(2026, 6, 10))
    assert parsed["compraMinima"] == 299


def test_bbva_selecciona_todos_los_sitios():
    parsed = parse_coupon_text("Crear cupon BBVA40 con 40% de descuento", now=date(2026, 6, 10))
    expected = [site["id"] for site in COUPON_SHOPIFY_SITES if site["enabled"]]
    assert parsed["selectedSites"] == expected


def test_error_cuando_no_hay_codigo():
    parsed = parse_coupon_text("Crear descuento de 40% para todos los sitios", now=date(2026, 6, 10))
    errors = validate_coupon_data(parsed)
    assert "El codigo del cupon es obligatorio." in errors


def test_error_cuando_no_hay_sitios():
    parsed = parse_coupon_text("Crear cupon CLB40 con 40% de descuento", now=date(2026, 6, 10))
    parsed["selectedSites"] = []
    errors = validate_coupon_data(parsed)
    assert "Selecciona al menos un sitio Shopify." in errors


def test_munisurco_detecta_fecha_invalida_y_sites():
    parsed = parse_coupon_text(
        """20% OFF TODA LA WEB
Cupón: MUNISURCO
Sites: www.vans.pe y www.hushpuppies.pe
Vigencia: Desde el 1 de julio hasta el 31 de setiembre del 2026.
Descuento máximo de S/150
Sin límite de un (1) uso por mes.""",
        now=date(2026, 7, 10),
    )
    assert parsed["codigoCupon"] == "MUNISURCO"
    assert parsed["valorDescuento"] == 20
    assert parsed["selectedSites"] == ["hushpuppies", "vans"]
    assert any(alert["blocking"] for alert in parsed["parserAlerts"])


def test_parse_bulk_codes_preserva_duplicados_para_validar():
    assert parse_bulk_codes("TATI15\nJUAN15\nTATI15") == ["TATI15", "JUAN15", "TATI15"]


def test_best_wins_promocion_actual_es_mejor():
    result = best_wins_line_result(current_price=70, compare_at_price=100, percentage=20)
    assert str(result.coupon_target_price) == "80.00"
    assert str(result.final_price) == "70.00"
    assert str(result.unit_discount) == "0.00"
    assert result.status == "Gana promocion actual"


def test_best_wins_cupon_es_mejor():
    result = best_wins_line_result(current_price=90, compare_at_price=100, percentage=20)
    assert str(result.coupon_target_price) == "80.00"
    assert str(result.final_price) == "80.00"
    assert str(result.unit_discount) == "10.00"
    assert result.status == "Gana cupon"


def test_best_wins_price_y_compare_at_iguales():
    result = best_wins_line_result(current_price=100, compare_at_price=100, percentage=20)
    assert str(result.final_price) == "80.00"
    assert str(result.unit_discount) == "20.00"


def test_best_wins_compare_at_null_usa_price_actual():
    result = best_wins_line_result(current_price=100, compare_at_price=None, percentage=20)
    assert str(result.final_price) == "80.00"
    assert result.status == "Gana cupon"


def test_best_wins_compare_at_null_no_aplica():
    result = best_wins_line_result(
        current_price=100,
        compare_at_price=None,
        percentage=20,
        missing_compare_at_behavior="do_not_apply",
    )
    assert str(result.final_price) == "100.00"
    assert str(result.unit_discount) == "0.00"
    assert result.status == "Sin Compare At Price"


def test_discount_code_app_payload_guarda_metafield_config():
    data = {
        "nombreInterno": "Campana CLB40",
        "codigoCupon": "CLB40",
        "fechaInicio": "2026-07-14",
        "horaInicio": "00:00",
        "fechaFin": "2026-07-15",
        "horaFin": "23:59",
        "unaVezPorCliente": True,
        "combinaProducto": False,
        "combinaPedido": True,
        "combinaEnvio": False,
        "limiteTotalUsos": 10,
        "compraMinima": 299,
        "valorDescuento": 40,
        "descuentoMaximo": 150,
        "priceBasis": PRICE_BASIS_COMPARE_AT_BEST_WINS,
    }
    payload = build_shopify_app_discount_payload(data, function_handle="compare-at-best-wins")
    assert payload["functionHandle"] == "compare-at-best-wins"
    assert payload["metafields"][0]["key"] == "function-configuration"
    config = build_function_configuration(data)
    assert config["percentage"] == 40
    assert config["maximum_discount_amount"] == 150
