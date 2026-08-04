import pandas as pd

from auditoria import (
    aplanar_cupones,
    cambiar_estado_cupon,
    filas_registro,
    filtrar_cupones,
    leer_registro,
    registrar_creacion,
    resumen_cupones,
)


RESULTADOS = [
    {
        "siteId": "columbia",
        "siteName": "Columbia.pe",
        "couponCode": "BCP30",
        "status": "success",
        "message": "Cupon creado correctamente.",
        "shopifyDiscountId": "gid://shopify/DiscountCodeNode/1",
    },
    {
        "siteId": "vans",
        "siteName": "Vans.pe",
        "couponCode": "BCP30",
        "status": "error",
        "message": "Falta configurar Shopify API para este sitio.",
        "shopifyDiscountId": "",
    },
]

DATA = {
    "priceBasis": "compare_at_price_best_wins",
    "tipoDescuento": "Porcentaje",
    "valorDescuento": 30,
    "fechaInicio": "2026-08-10",
    "horaInicio": "00:00",
    "fechaFin": "2026-08-20",
    "horaFin": "23:59",
}

NODOS = [
    {
        "id": "gid://shopify/DiscountCodeNode/1",
        "codeDiscount": {
            "__typename": "DiscountCodeApp",
            "title": "BCP30",
            "status": "ACTIVE",
            "startsAt": "2026-08-10T00:00:00-05:00",
            "endsAt": "2026-08-20T23:59:00-05:00",
            "usageLimit": 100,
            "asyncUsageCount": 7,
            "codes": {"nodes": [{"code": "BCP30"}]},
        },
    },
    {
        "id": "gid://shopify/DiscountCodeNode/2",
        "codeDiscount": {
            "__typename": "DiscountCodeBasic",
            "title": "Cyber viejo",
            "status": "EXPIRED",
            "startsAt": "2026-01-01T00:00:00-05:00",
            "endsAt": None,
            "usageLimit": None,
            "asyncUsageCount": None,
            "codes": {"nodes": [{"code": "CYBER20"}]},
        },
    },
]


def test_filas_registro_arma_una_fila_por_resultado():
    filas = filas_registro(RESULTADOS, DATA, "hugo.camara@forus.pe", momento="2026-08-04 10:00:00")
    assert len(filas) == 2
    assert filas[0]["codigo"] == "BCP30"
    assert filas[0]["usuario"] == "hugo.camara@forus.pe"
    assert filas[0]["inicio"] == "2026-08-10 00:00"
    assert filas[1]["estado"] == "error"


def test_registrar_y_leer_el_registro(tmp_path):
    ruta = tmp_path / "auditoria.csv"
    assert registrar_creacion(RESULTADOS, DATA, "hugo.camara@forus.pe", ruta) == 2
    assert registrar_creacion(RESULTADOS, DATA, "otro@forus.pe", ruta) == 2
    tabla = leer_registro(ruta)
    assert len(tabla) == 4
    assert set(tabla["usuario"]) == {"hugo.camara@forus.pe", "otro@forus.pe"}


def test_registrar_sin_resultados_no_crea_archivo(tmp_path):
    ruta = tmp_path / "vacio.csv"
    assert registrar_creacion([], DATA, "hugo", ruta) == 0
    assert not ruta.exists()


def test_leer_registro_inexistente_devuelve_vacio(tmp_path):
    tabla = leer_registro(tmp_path / "no_existe.csv")
    assert isinstance(tabla, pd.DataFrame)
    assert tabla.empty


def test_aplanar_cupones_traduce_estado_y_codigos():
    filas = aplanar_cupones(NODOS, "Columbia.pe")
    assert filas[0]["Codigo"] == "BCP30"
    assert filas[0]["Estado"] == "Activo"
    assert filas[0]["Tipo"] == "Function (Best Wins)"
    assert filas[0]["Usos"] == 7
    assert filas[0]["Limite"] == 100
    assert filas[1]["Estado"] == "Expirado"
    assert filas[1]["Fin"] == "Sin fin"
    assert filas[1]["Usos"] == 0
    assert filas[1]["Limite"] == "Sin limite"


def test_resumen_cuenta_por_estado():
    resumen = resumen_cupones(aplanar_cupones(NODOS, "Columbia.pe"))
    assert resumen["total"] == 2
    assert resumen["activos"] == 1
    assert resumen["expirados"] == 1
    assert resumen["usos"] == 7


def test_filtrar_por_estado_y_texto():
    filas = aplanar_cupones(NODOS, "Columbia.pe")
    assert len(filtrar_cupones(filas, "Activo")) == 1
    assert len(filtrar_cupones(filas, "Todos", "cyber")) == 1
    assert len(filtrar_cupones(filas, "Todos", "no existe")) == 0


def test_desactivar_cupon_devuelve_error_de_shopify():
    def graphql(query, variables=None):
        return {"discountCodeDeactivate": {"userErrors": [{"message": "No se puede desactivar"}]}}

    assert cambiar_estado_cupon(graphql, "gid://1", activar=False) == "No se puede desactivar"


def test_desactivar_cupon_ok():
    llamadas = []

    def graphql(query, variables=None):
        llamadas.append((query, variables))
        return {"discountCodeDeactivate": {"codeDiscountNode": {"id": "gid://1"}, "userErrors": []}}

    assert cambiar_estado_cupon(graphql, "gid://1", activar=False) == ""
    assert "discountCodeDeactivate" in llamadas[0][0]
    assert llamadas[0][1] == {"id": "gid://1"}


def test_activar_usa_la_otra_mutacion():
    llamadas = []

    def graphql(query, variables=None):
        llamadas.append(query)
        return {"discountCodeActivate": {"codeDiscountNode": {"id": "gid://1"}, "userErrors": []}}

    assert cambiar_estado_cupon(graphql, "gid://1", activar=True) == ""
    assert "discountCodeActivate" in llamadas[0]


def test_sin_id_no_llama_a_shopify():
    def graphql(query, variables=None):
        raise AssertionError("No deberia llamar a Shopify sin ID.")

    assert cambiar_estado_cupon(graphql, "", activar=False) == "Falta el ID del cupon."
