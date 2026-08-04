from shopify_coupon_service import (
    build_shopify_app_discount_payload,
    build_shopify_discount_payload,
)
from shopify_multisite import (
    ESTADO_ERROR,
    ESTADO_LISTO,
    ESTADO_SIN_CONFIG,
    ESTADO_SOLO_BASICO,
    bloque_secrets,
    diagnosticar_tienda,
    diagnosticar_tiendas,
    elegir_funcion,
    expandir_tokens,
    filas_tabla,
    recomendar_tokens,
    normalizar_dominio,
    resumen_por_estado,
    scopes_faltantes,
    texto_tabla,
    token_enmascarado,
)


SITIO_VANS = {"id": "vans", "name": "Vans.pe", "shop_key": "vans", "enabled": True}

CLIENT_ID_VANS = "1a2b3c4d5e6f"

CONFIG_OK = {
    "shop_domain": "vanspe.myshopify.com",
    "client_id": CLIENT_ID_VANS,
    "admin_access_token": "shpat_1234567890abcdef",
    "api_version": "2026-04",
    "compare_at_best_wins_function_handle": "compare-at-best-wins",
}


def graphql_falso(scopes=("write_discounts", "read_discounts"), funciones=None, dominio="vanspe.myshopify.com"):
    if funciones is None:
        funciones = [
            {
                "id": "gid://shopify/ShopifyFunction/abc123",
                "handle": "compare-at-best-wins",
                "title": "Compare At Price - Best Wins",
                "apiType": "discount",
                "appKey": CLIENT_ID_VANS,
                "app": {"title": "Revenue Automatico"},
            }
        ]

    def ejecutar(query: str, variables: dict | None = None) -> dict:
        if "shop {" in query:
            return {
                "shop": {
                    "name": "Vans Peru",
                    "myshopifyDomain": dominio,
                    "currencyCode": "PEN",
                    "plan": {"displayName": "Shopify Plus", "partnerDevelopment": False, "shopifyPlus": True},
                }
            }
        if "currentAppInstallation" in query:
            return {
                "currentAppInstallation": {
                    "accessScopes": [{"handle": scope} for scope in scopes],
                    "app": {"title": "Revenue Automatico", "handle": "revenue-automatico"},
                }
            }
        if "shopifyFunctions" in query:
            return {"shopifyFunctions": {"nodes": list(funciones)}}
        raise AssertionError("Query inesperada: " + query)

    return ejecutar


def test_normalizar_dominio_quita_protocolo_y_barra():
    assert normalizar_dominio("https://VANSPE.myshopify.com/") == "vanspe.myshopify.com"


def test_token_enmascarado_no_muestra_el_token_completo():
    enmascarado = token_enmascarado("shpat_1234567890abcdef")
    assert enmascarado.startswith("shpat_")
    assert "1234567890" not in enmascarado


def test_scopes_faltantes_detecta_write_discounts():
    assert scopes_faltantes(["read_products"]) == ["write_discounts"]
    assert scopes_faltantes(["write_discounts"]) == []


def test_elegir_funcion_por_handle_exacto():
    nodos = [
        {"id": "1", "handle": "otra-function", "apiType": "discount"},
        {"id": "2", "handle": "compare-at-best-wins", "apiType": "discount"},
    ]
    funcion, motivo = elegir_funcion(nodos)
    assert funcion["id"] == "2"
    assert motivo == "handle_exacto"


def test_elegir_funcion_cuando_solo_hay_una_con_otro_handle():
    funcion, motivo = elegir_funcion([{"id": "9", "handle": "best-wins", "apiType": "discount"}])
    assert funcion["id"] == "9"
    assert motivo == "unica_funcion"


def test_elegir_funcion_sin_funciones():
    funcion, motivo = elegir_funcion([])
    assert funcion is None
    assert motivo == "sin_funciones"


def test_elegir_funcion_con_varias_y_ninguna_coincide():
    nodos = [
        {"id": "1", "handle": "a", "apiType": "discount"},
        {"id": "2", "handle": "b", "apiType": "discount"},
    ]
    funcion, motivo = elegir_funcion(nodos)
    assert funcion is None
    assert motivo == "varias_funciones"


def test_tienda_lista_para_best_wins():
    fila = diagnosticar_tienda(SITIO_VANS, CONFIG_OK, graphql_falso())
    assert fila["estado"] == ESTADO_LISTO
    assert fila["funcion_id"] == "gid://shopify/ShopifyFunction/abc123"
    assert fila["funcion_handle"] == "compare-at-best-wins"
    assert fila["detalles"] == []


def test_tienda_sin_function_queda_en_solo_precio_actual():
    fila = diagnosticar_tienda(SITIO_VANS, CONFIG_OK, graphql_falso(funciones=[]))
    assert fila["estado"] == ESTADO_SOLO_BASICO
    assert any("Discount Function" in detalle for detalle in fila["detalles"])


def test_tienda_sin_write_discounts_queda_en_error():
    fila = diagnosticar_tienda(SITIO_VANS, CONFIG_OK, graphql_falso(scopes=("read_products",)))
    assert fila["estado"] == ESTADO_ERROR
    assert fila["scopes_faltantes"] == ["write_discounts"]


def test_tienda_sin_secrets_no_llama_a_shopify():
    def graphql_que_explota(query, variables=None):
        raise AssertionError("No deberia llamar a Shopify sin secrets.")

    fila = diagnosticar_tienda(SITIO_VANS, {}, graphql_que_explota)
    assert fila["estado"] == ESTADO_SIN_CONFIG
    assert "shopify_sites.vans" in fila["secrets_sugeridos"]


def test_token_invalido_devuelve_error_con_mensaje():
    def graphql_401(query, variables=None):
        raise RuntimeError("Shopify respondio 401: Invalid API key or access token")

    fila = diagnosticar_tienda(SITIO_VANS, CONFIG_OK, graphql_401)
    assert fila["estado"] == ESTADO_ERROR
    assert any("401" in detalle for detalle in fila["detalles"])


def test_avisa_cuando_el_token_es_de_otra_tienda():
    fila = diagnosticar_tienda(SITIO_VANS, CONFIG_OK, graphql_falso(dominio="columbiape.myshopify.com"))
    assert any("columbiape.myshopify.com" in detalle for detalle in fila["detalles"])
    assert fila["dominio"] == "columbiape.myshopify.com"


def test_avisa_cuando_el_handle_de_secrets_no_coincide():
    funciones = [
        {
            "id": "gid://shopify/ShopifyFunction/zzz",
            "handle": "best-wins-v2",
            "title": "Best Wins",
            "apiType": "discount",
        }
    ]
    fila = diagnosticar_tienda(SITIO_VANS, CONFIG_OK, graphql_falso(funciones=funciones))
    assert fila["estado"] == ESTADO_LISTO
    assert "best-wins-v2" in fila["secrets_sugeridos"]
    assert any("best-wins-v2" in detalle for detalle in fila["detalles"])


def test_diagnosticar_tiendas_recorre_todas_y_resume():
    sitios = [
        SITIO_VANS,
        {"id": "columbia", "name": "Columbia.pe", "shop_key": "columbia", "enabled": True},
    ]
    configs = {"vans": CONFIG_OK, "columbia": {}}
    resultados = diagnosticar_tiendas(
        sitios,
        obtener_config=lambda shop_key: configs.get(shop_key, {}),
        crear_graphql=lambda shop_key, config: graphql_falso(),
    )
    resumen = resumen_por_estado(resultados)
    assert resumen[ESTADO_LISTO] == 1
    assert resumen[ESTADO_SIN_CONFIG] == 1
    assert len(filas_tabla(resultados)) == 2
    assert "Vans.pe" in texto_tabla(resultados)


def test_columna_permisos_no_dice_si_cuando_no_se_pudo_leer():
    fila_sin_config = diagnosticar_tienda(SITIO_VANS, {}, lambda query, variables=None: {})
    fila_ok = diagnosticar_tienda(SITIO_VANS, CONFIG_OK, graphql_falso())
    fila_sin_permiso = diagnosticar_tienda(SITIO_VANS, CONFIG_OK, graphql_falso(scopes=("read_products",)))
    tabla = filas_tabla([fila_sin_config, fila_ok, fila_sin_permiso])
    assert tabla[0]["write_discounts"] == "-"
    assert tabla[1]["write_discounts"] == "Si"
    assert tabla[2]["write_discounts"] == "No"


def test_elegir_funcion_prefiere_la_del_client_id():
    nodos = [
        {"id": "1", "handle": "otra-app-function", "apiType": "discount", "appKey": "otra-app"},
        {"id": "2", "handle": "best-wins-forus", "apiType": "discount", "appKey": CLIENT_ID_VANS},
    ]
    funcion, motivo = elegir_funcion(nodos, "compare-at-best-wins", CLIENT_ID_VANS)
    assert funcion["id"] == "2"
    assert motivo == "por_client_id"


def test_sin_saber_el_handle_lo_resuelve_por_client_id():
    funciones = [
        {
            "id": "gid://shopify/ShopifyFunction/xyz",
            "handle": "descuento-best-wins",
            "title": "Best Wins",
            "apiType": "discount",
            "appKey": CLIENT_ID_VANS,
        },
        {
            "id": "gid://shopify/ShopifyFunction/otra",
            "handle": "app-de-terceros",
            "title": "Otra app",
            "apiType": "discount",
            "appKey": "otra-app",
        },
    ]
    config = {key: valor for key, valor in CONFIG_OK.items() if key != "compare_at_best_wins_function_handle"}
    fila = diagnosticar_tienda(SITIO_VANS, config, graphql_falso(funciones=funciones), handle_esperado="")
    assert fila["estado"] == ESTADO_LISTO
    assert fila["funcion_handle"] == "descuento-best-wins"
    assert 'compare_at_best_wins_function_handle = "descuento-best-wins"' in fila["secrets_sugeridos"]
    assert 'client_id = "' + CLIENT_ID_VANS + '"' in fila["secrets_sugeridos"]


def test_sin_secrets_el_bloque_avisa_que_falta_el_handle():
    fila = diagnosticar_tienda(SITIO_VANS, {}, lambda query, variables=None: {}, handle_esperado="")
    assert "Falta el handle" in fila["secrets_sugeridos"]


SITIO_COLUMBIA = {"id": "columbia", "name": "Columbia.pe", "shop_key": "columbia", "enabled": True}

CONFIG_DOS_APPS = {
    "shop_domain": "columbiape.myshopify.com",
    "api_version": "2026-04",
    "tokens": {
        "catalogo_digital": "shpat_catalogo",
        "app_cupones": {"admin_access_token": "shpat_cupones", "client_id": CLIENT_ID_VANS},
    },
}


def test_expandir_tokens_formato_simple_y_con_tabla():
    pares = expandir_tokens(SITIO_COLUMBIA, CONFIG_DOS_APPS)
    assert len(pares) == 2
    nombres = [sitio["token_nombre"] for sitio, _config in pares]
    assert nombres == ["catalogo_digital", "app_cupones"]
    configs = {sitio["token_nombre"]: config for sitio, config in pares}
    assert configs["catalogo_digital"]["admin_access_token"] == "shpat_catalogo"
    assert configs["app_cupones"]["admin_access_token"] == "shpat_cupones"
    assert configs["app_cupones"]["client_id"] == CLIENT_ID_VANS
    assert "tokens" not in configs["app_cupones"]
    assert configs["catalogo_digital"]["shop_domain"] == "columbiape.myshopify.com"


def test_expandir_tokens_sin_tokens_devuelve_la_config_tal_cual():
    pares = expandir_tokens(SITIO_VANS, CONFIG_OK)
    assert pares == [(SITIO_VANS, CONFIG_OK)]


class MappingFalso:
    """Imita el AttrDict de st.secrets: es Mapping pero NO hereda de dict."""

    def __init__(self, datos):
        self._datos = dict(datos)

    def items(self):
        return self._datos.items()

    def get(self, clave, defecto=None):
        return self._datos.get(clave, defecto)

    def keys(self):
        return self._datos.keys()

    def __getitem__(self, clave):
        return self._datos[clave]

    def __iter__(self):
        return iter(self._datos)

    def __len__(self):
        return len(self._datos)


def test_expandir_tokens_soporta_attrdict_de_streamlit():
    config = MappingFalso(
        {
            "shop_domain": "columbiape.myshopify.com",
            "tokens": MappingFalso(
                {
                    "catalogo_digital": "shpat_catalogo",
                    "app_cupones": MappingFalso({"admin_access_token": "shpat_cupones", "client_id": CLIENT_ID_VANS}),
                }
            ),
        }
    )
    pares = expandir_tokens(SITIO_COLUMBIA, config)
    assert len(pares) == 2
    configs = {sitio["token_nombre"]: config_token for sitio, config_token in pares}
    assert configs["app_cupones"]["admin_access_token"] == "shpat_cupones"
    assert configs["app_cupones"]["client_id"] == CLIENT_ID_VANS
    assert configs["catalogo_digital"]["admin_access_token"] == "shpat_catalogo"
    assert configs["catalogo_digital"]["shop_domain"] == "columbiape.myshopify.com"


def test_expandir_tokens_ignora_access_token_heredado():
    config = {**CONFIG_DOS_APPS, "access_token": "shpat_viejo"}
    for _sitio, config_token in expandir_tokens(SITIO_COLUMBIA, config):
        assert "access_token" not in config_token


def test_dos_apps_por_tienda_recomienda_la_que_ve_la_function():
    def crear(shop_key, config):
        if config["admin_access_token"] == "shpat_cupones":
            return graphql_falso(dominio="columbiape.myshopify.com")
        return graphql_falso(dominio="columbiape.myshopify.com", funciones=[])

    resultados = diagnosticar_tiendas([SITIO_COLUMBIA], lambda shop_key: CONFIG_DOS_APPS, crear)
    assert len(resultados) == 2
    estados = {fila["token_nombre"]: fila["estado"] for fila in resultados}
    assert estados["app_cupones"] == ESTADO_LISTO
    assert estados["catalogo_digital"] == ESTADO_SOLO_BASICO
    mensajes = recomendar_tokens(resultados)
    assert len(mensajes) == 1
    assert "app_cupones" in mensajes[0]
    assert "compare-at-best-wins" in mensajes[0]


def test_si_ningun_token_ve_la_function_lo_dice():
    def crear(shop_key, config):
        return graphql_falso(dominio="columbiape.myshopify.com", funciones=[])

    resultados = diagnosticar_tiendas([SITIO_COLUMBIA], lambda shop_key: CONFIG_DOS_APPS, crear)
    mensajes = recomendar_tokens(resultados)
    assert len(mensajes) == 1
    assert "ningun token ve la Function" in mensajes[0]


DATA_CUPON = {
    "nombreInterno": "BCP30",
    "codigoCupon": "bcp30",
    "fechaInicio": "2026-08-01",
    "horaInicio": "10:00",
    "fechaFin": "2026-08-31",
    "horaFin": "23:59",
    "tipoDescuento": "Porcentaje",
    "valorDescuento": 30,
    "unaVezPorCliente": True,
}


def test_payload_basico_manda_el_enum_all_en_context():
    payload = build_shopify_discount_payload(dict(DATA_CUPON))
    assert payload["context"] == {"all": "ALL"}
    assert payload["code"] == "BCP30"


def test_payload_app_manda_el_enum_all_en_context():
    payload = build_shopify_app_discount_payload(dict(DATA_CUPON), function_handle="compare-at-best-wins")
    assert payload["context"] == {"all": "ALL"}
    assert payload["functionHandle"] == "compare-at-best-wins"


def test_payload_con_segmento_reemplaza_el_contexto():
    payload = build_shopify_discount_payload(dict(DATA_CUPON), "gid://shopify/Segment/1")
    assert payload["context"] == {"customerSegments": {"add": ["gid://shopify/Segment/1"]}}


def test_bloque_secrets_incluye_dominio_y_handle():
    bloque = bloque_secrets("keds", "https://kedspe.myshopify.com/", "compare-at-best-wins")
    assert "[shopify_sites.keds]" in bloque
    assert 'shop_domain = "kedspe.myshopify.com"' in bloque
    assert 'compare_at_best_wins_function_handle = "compare-at-best-wins"' in bloque
