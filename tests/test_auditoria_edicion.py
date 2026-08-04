import json

from auditoria import (
    MUTACION_ACTUALIZAR_APP,
    MUTACION_ACTUALIZAR_BASICO,
    actualizar_cupon,
    construir_actualizacion,
    leer_detalle,
)


DETALLE_BASICO = {
    "id": "gid://shopify/DiscountCodeNode/1",
    "tipo": "DiscountCodeBasic",
    "titulo": "BCP30",
    "porcentaje": 30.0,
    "compra_minima": 299.0,
    "limite_usos": None,
    "una_vez_por_cliente": True,
    "codigos": ["BCP30"],
    "configuracion": {},
    "metafield_id": "",
}

DETALLE_APP = {
    "id": "gid://shopify/DiscountCodeNode/2",
    "tipo": "DiscountCodeApp",
    "titulo": "BBVA40",
    "porcentaje": 40.0,
    "compra_minima": 0.0,
    "limite_usos": 100,
    "una_vez_por_cliente": False,
    "codigos": ["BBVA40"],
    "configuracion": {"percentage": 40, "strategy": "best_wins", "message": "Mejor precio"},
    "metafield_id": "gid://shopify/Metafield/99",
}


def graphql_detalle(tipo="DiscountCodeBasic"):
    def ejecutar(query, variables=None):
        descuento = {
            "__typename": tipo,
            "title": "BCP30",
            "status": "ACTIVE",
            "startsAt": "2026-08-10T00:00:00-05:00",
            "endsAt": "2026-08-20T23:59:00-05:00",
            "usageLimit": 50,
            "appliesOncePerCustomer": True,
            "codes": {"nodes": [{"code": "BCP30"}]},
        }
        nodo = {"id": "gid://shopify/DiscountCodeNode/1", "codeDiscount": descuento, "metafield": None}
        if tipo == "DiscountCodeBasic":
            descuento["customerGets"] = {"value": {"percentage": 0.3}}
            descuento["minimumRequirement"] = {"greaterThanOrEqualToSubtotal": {"amount": "299.0"}}
        else:
            nodo["metafield"] = {
                "id": "gid://shopify/Metafield/99",
                "jsonValue": {"percentage": 30, "strategy": "best_wins"},
            }
        return {"codeDiscountNode": nodo}

    return ejecutar


def test_leer_detalle_cupon_nativo():
    detalle = leer_detalle(graphql_detalle(), "gid://1")
    assert detalle["tipo"] == "DiscountCodeBasic"
    assert detalle["porcentaje"] == 30.0
    assert detalle["compra_minima"] == 299.0
    assert detalle["limite_usos"] == 50
    assert detalle["codigos"] == ["BCP30"]


def test_leer_detalle_cupon_function_lee_el_metafield():
    detalle = leer_detalle(graphql_detalle("DiscountCodeApp"), "gid://2")
    assert detalle["tipo"] == "DiscountCodeApp"
    assert detalle["porcentaje"] == 30.0
    assert detalle["metafield_id"] == "gid://shopify/Metafield/99"
    assert detalle["configuracion"]["strategy"] == "best_wins"


def test_leer_detalle_con_error_devuelve_vacio():
    def graphql_roto(query, variables=None):
        raise RuntimeError("401")

    assert leer_detalle(graphql_roto, "gid://1") == {}


def test_actualizacion_basica_solo_manda_lo_que_cambia():
    mutacion, entrada = construir_actualizacion(DETALLE_BASICO, {"titulo": "BCP30", "limite_usos": 500})
    assert mutacion is MUTACION_ACTUALIZAR_BASICO
    assert entrada == {"usageLimit": 500}
    assert "title" not in entrada


def test_actualizacion_basica_con_porcentaje_nuevo():
    _mutacion, entrada = construir_actualizacion(DETALLE_BASICO, {"porcentaje": 45})
    assert entrada["customerGets"]["value"]["percentage"] == 0.45
    assert entrada["customerGets"]["items"] == {"all": True}


def test_actualizacion_basica_limite_cero_es_sin_limite():
    _mutacion, entrada = construir_actualizacion(DETALLE_BASICO, {"limite_usos": 0})
    assert entrada["usageLimit"] is None


def test_actualizacion_app_escribe_el_metafield_y_conserva_lo_demas():
    mutacion, entrada = construir_actualizacion(DETALLE_APP, {"porcentaje": 25, "compra_minima": 299})
    assert mutacion is MUTACION_ACTUALIZAR_APP
    assert "minimumRequirement" not in entrada
    metafield = entrada["metafields"][0]
    assert metafield["id"] == "gid://shopify/Metafield/99"
    configuracion = json.loads(metafield["value"])
    assert configuracion["percentage"] == 25
    assert configuracion["minimum_subtotal"] == 299
    assert configuracion["strategy"] == "best_wins"
    assert configuracion["message"] == "Mejor precio"


def test_actualizacion_app_sin_metafield_previo_manda_namespace():
    detalle = {**DETALLE_APP, "metafield_id": ""}
    _mutacion, entrada = construir_actualizacion(detalle, {"porcentaje": 25})
    metafield = entrada["metafields"][0]
    assert metafield["namespace"] == "$app:compare-at-best-wins"
    assert metafield["key"] == "function-configuration"
    assert metafield["type"] == "json"


def test_actualizar_sin_cambios_no_llama_a_shopify():
    def graphql(query, variables=None):
        raise AssertionError("No deberia llamar a Shopify sin cambios.")

    assert actualizar_cupon(graphql, DETALLE_BASICO, {}) == "No hay cambios que guardar."


def test_actualizar_usa_la_variable_correcta_por_tipo():
    llamadas = []

    def graphql(query, variables=None):
        llamadas.append((query, variables))
        clave = "discountCodeAppUpdate" if "AppUpdate" in query else "discountCodeBasicUpdate"
        return {clave: {"codeDiscountNode": {"id": "gid://1"}, "userErrors": []}}

    assert actualizar_cupon(graphql, DETALLE_BASICO, {"limite_usos": 10}) == ""
    assert "basicCodeDiscount" in llamadas[0][1]

    assert actualizar_cupon(graphql, DETALLE_APP, {"porcentaje": 10}) == ""
    assert "codeAppDiscount" in llamadas[1][1]


def test_actualizar_devuelve_el_error_de_shopify():
    def graphql(query, variables=None):
        return {"discountCodeBasicUpdate": {"userErrors": [{"message": "Discount is expired"}]}}

    assert actualizar_cupon(graphql, DETALLE_BASICO, {"limite_usos": 10}) == "Discount is expired"
