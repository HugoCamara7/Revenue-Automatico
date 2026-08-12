import pandas as pd

from promociones import (
    APLICA,
    ERROR_DATO,
    NO_ENCONTRADO,
    SIN_CAMBIO_MEJOR,
    SIN_CAMBIO_SIN_REGLA,
    armar_plan,
    calcular_precio,
    dinero,
    leer_reglas,
    payload_actualizacion,
    payload_reversion,
    resumen_plan,
)


def regla(**kwargs):
    base = {"porcentaje": None, "precio_objetivo": None, "tope_maximo": None, "piso_minimo": None}
    base.update({clave: dinero(valor) for clave, valor in kwargs.items()})
    return base


# --------------------------------------------------------------- base de calculo


def test_el_porcentaje_se_calcula_sobre_el_compare_at_no_sobre_el_precio_rebajado():
    # Producto ya en promo: lista 100, vigente 70. Un 40% debe dar 60, no 42.
    resultado = calcular_precio("70.00", "100.00", regla(porcentaje=40))
    assert resultado["estado"] == APLICA
    assert float(resultado["base"]) == 100.0
    assert float(resultado["precio_nuevo"]) == 60.0


def test_sin_compare_at_la_base_es_el_precio_vigente():
    resultado = calcular_precio("100.00", None, regla(porcentaje=40))
    assert float(resultado["base"]) == 100.0
    assert float(resultado["precio_nuevo"]) == 60.0


def test_compare_at_menor_que_el_precio_se_ignora():
    # Dato sucio: compare at mas barato que el precio. Se usa el precio vigente.
    resultado = calcular_precio("100.00", "80.00", regla(porcentaje=50))
    assert float(resultado["base"]) == 100.0
    assert float(resultado["precio_nuevo"]) == 50.0


def test_el_compare_at_nuevo_es_siempre_el_precio_de_lista():
    resultado = calcular_precio("70.00", "100.00", regla(porcentaje=40))
    assert float(resultado["compare_at_nuevo"]) == 100.0


# --------------------------------------------------------------- reglas


def test_precio_objetivo_manda_sobre_el_porcentaje():
    resultado = calcular_precio("300.00", "400.00", regla(porcentaje=10, precio_objetivo=199))
    assert float(resultado["precio_nuevo"]) == 199.0


def test_tope_maximo_baja_el_precio_cuando_lo_supera():
    # 10% sobre 400 da 360, pero el tope obliga a 199.
    resultado = calcular_precio("400.00", "400.00", regla(porcentaje=10, tope_maximo=199))
    assert float(resultado["precio_nuevo"]) == 199.0


def test_tope_maximo_no_hace_nada_si_el_calculo_ya_esta_por_debajo():
    resultado = calcular_precio("400.00", "400.00", regla(porcentaje=60, tope_maximo=199))
    assert float(resultado["precio_nuevo"]) == 160.0


def test_piso_minimo_protege_el_margen():
    # 80% sobre 100 daria 20, pero el piso lo deja en 49.90.
    resultado = calcular_precio("100.00", "100.00", regla(porcentaje=80, piso_minimo="49.90"))
    assert float(resultado["precio_nuevo"]) == 49.9


def test_piso_y_tope_juntos():
    resultado = calcular_precio("500.00", "500.00", regla(porcentaje=90, tope_maximo=299, piso_minimo=99))
    assert float(resultado["precio_nuevo"]) == 99.0


# --------------------------------------------------------------- protecciones


def test_nunca_sube_un_precio():
    # El producto ya esta a 50; un 10% sobre la lista de 100 daria 90, mas caro.
    resultado = calcular_precio("50.00", "100.00", regla(porcentaje=10))
    assert resultado["estado"] == SIN_CAMBIO_MEJOR
    assert "precio_nuevo" not in resultado


def test_precio_objetivo_mas_caro_que_el_actual_no_toca_nada():
    resultado = calcular_precio("150.00", "300.00", regla(precio_objetivo=199))
    assert resultado["estado"] == SIN_CAMBIO_MEJOR


def test_fila_sin_reglas_no_hace_nada():
    resultado = calcular_precio("100.00", "200.00", regla())
    assert resultado["estado"] == SIN_CAMBIO_SIN_REGLA


def test_producto_sin_precio_es_error():
    resultado = calcular_precio(None, "100.00", regla(porcentaje=20))
    assert resultado["estado"] == ERROR_DATO


def test_dinero_limpia_simbolos_y_rechaza_negativos():
    assert float(dinero("S/ 1,299.90")) == 1299.9
    assert float(dinero("40%")) == 40.0
    assert dinero("-10") is None
    assert dinero("") is None
    assert dinero("abc") is None


# --------------------------------------------------------------- lectura del archivo


def test_lee_el_archivo_detectando_las_columnas_solas():
    tabla = pd.DataFrame(
        {
            "SKU": ["ABC-1", "ABC-2"],
            "Descuento %": [40, None],
            "Precio objetivo": [None, 199],
        }
    )
    reglas, avisos = leer_reglas(tabla)
    assert avisos == []
    assert len(reglas) == 2
    assert float(reglas[0]["porcentaje"]) == 40.0
    assert float(reglas[1]["precio_objetivo"]) == 199.0


def test_acepta_nombres_alternativos_de_columna():
    tabla = pd.DataFrame({"id": ["A"], "todo a": [149]})
    reglas, _avisos = leer_reglas(tabla)
    assert float(reglas[0]["precio_objetivo"]) == 149.0


def test_archivo_sin_columna_de_id():
    tabla = pd.DataFrame({"Descuento": [40]})
    reglas, avisos = leer_reglas(tabla)
    assert reglas == []
    assert "ID o SKU" in avisos[0]


def test_archivo_sin_ninguna_regla():
    tabla = pd.DataFrame({"SKU": ["A"], "Comentario": ["algo"]})
    reglas, avisos = leer_reglas(tabla)
    assert reglas == []
    assert "regla" in avisos[0]


def test_avisa_de_los_repetidos_y_usa_el_primero():
    tabla = pd.DataFrame({"SKU": ["A", "A"], "Descuento": [40, 10]})
    reglas, avisos = leer_reglas(tabla)
    assert len(reglas) == 1
    assert float(reglas[0]["porcentaje"]) == 40.0
    assert any("Repetido" in aviso for aviso in avisos)


# --------------------------------------------------------------- plan completo


VARIANTES = {
    "ABC-1": {"id": "gid://v/1", "nombre": "Polo azul", "price": "70.00", "compare_at": "100.00"},
    "ABC-2": {"id": "gid://v/2", "nombre": "Short gris", "price": "300.00", "compare_at": None},
}


def test_plan_cruza_archivo_con_tienda():
    reglas = [
        {"identificador": "ABC-1", "porcentaje": dinero(40), "precio_objetivo": None, "tope_maximo": None, "piso_minimo": None},
        {"identificador": "ABC-2", "porcentaje": None, "precio_objetivo": dinero(199), "tope_maximo": None, "piso_minimo": None},
        {"identificador": "NO-EXISTE", "porcentaje": dinero(30), "precio_objetivo": None, "tope_maximo": None, "piso_minimo": None},
    ]
    plan = armar_plan(reglas, VARIANTES)
    assert plan[0]["Estado"] == APLICA
    assert plan[0]["Precio nuevo"] == 60.0
    assert plan[0]["Descuento real %"] == 40.0
    assert plan[1]["Precio nuevo"] == 199.0
    assert plan[2]["Estado"] == NO_ENCONTRADO


def test_resumen_cuenta_bien():
    reglas = [
        {"identificador": "ABC-1", "porcentaje": dinero(40), "precio_objetivo": None, "tope_maximo": None, "piso_minimo": None},
        {"identificador": "NO-EXISTE", "porcentaje": dinero(30), "precio_objetivo": None, "tope_maximo": None, "piso_minimo": None},
    ]
    resumen = resumen_plan(armar_plan(reglas, VARIANTES))
    assert resumen["total"] == 2
    assert resumen["aplican"] == 1
    assert resumen["no_encontrados"] == 1


# --------------------------------------------------------------- payloads


def test_payload_de_actualizacion():
    fila = {"_variant_id": "gid://v/1", "Precio nuevo": 60.0, "Compare At nuevo": 100.0}
    assert payload_actualizacion(fila) == {
        "id": "gid://v/1",
        "price": "60.0",
        "compareAtPrice": "100.0",
    }


def test_payload_de_reversion_devuelve_el_precio_de_lista():
    fila = {"_variant_id": "gid://v/1", "Precio nuevo": 60.0, "Compare At nuevo": 100.0}
    revertido = payload_reversion(fila)
    assert revertido["price"] == "100.0"
    assert revertido["compareAtPrice"] is None
