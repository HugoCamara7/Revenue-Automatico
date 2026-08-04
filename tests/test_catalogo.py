from catalogo import (
    APLICA_COLECCIONES,
    APLICA_PRODUCTOS,
    APLICA_TODOS,
    buscar_variantes,
    construir_items,
    listar_colecciones,
    resolver_colecciones,
    resolver_en_tiendas,
    resolver_para_tienda,
    resolver_variantes,
)


COLECCIONES = {
    "columbia": [
        {"id": "gid://shopify/Collection/11", "handle": "sale", "title": "Sale"},
        {"id": "gid://shopify/Collection/12", "handle": "zapatillas", "title": "Zapatillas"},
    ],
    "rockford": [
        {"id": "gid://shopify/Collection/99", "handle": "sale", "title": "Sale Rockford"},
    ],
}

VARIANTES = {
    "columbia": [
        {"id": "gid://shopify/ProductVariant/1", "sku": "ABC123-001", "displayName": "Polo azul", "price": "129.00", "product": {"id": "gid://shopify/Product/1", "title": "Polo"}},
    ],
    "rockford": [],
}


def graphql_tienda(clave: str):
    def ejecutar(query, variables=None):
        variables = variables or {}
        filtro = str(variables.get("query") or "")
        if "collections(" in query:
            nodos = COLECCIONES.get(clave, [])
            if filtro.startswith("handle:"):
                buscado = filtro.split("handle:")[1].strip()
                nodos = [nodo for nodo in nodos if nodo["handle"] == buscado]
            elif filtro:
                termino = filtro.replace("title:*", "").replace("*", "").lower()
                nodos = [nodo for nodo in nodos if termino in nodo["title"].lower()]
            return {"collections": {"nodes": nodos}}
        if "productVariants(" in query:
            nodos = VARIANTES.get(clave, [])
            if filtro.startswith("sku:") and " OR " not in filtro:
                # busqueda exacta que usa resolver_variantes
                buscado = filtro.split("sku:")[1].strip()
                nodos = [nodo for nodo in nodos if nodo["sku"] == buscado]
            elif filtro:
                # busqueda con comodines que usa buscar_variantes
                termino = filtro.replace("sku:*", "").split("*")[0].lower()
                nodos = [
                    nodo
                    for nodo in nodos
                    if termino in nodo["sku"].lower() or termino in nodo["displayName"].lower()
                ]
            return {"productVariants": {"nodes": nodos}}
        raise AssertionError("Query inesperada")

    return ejecutar


def test_listar_colecciones_devuelve_handle_y_titulo():
    colecciones = listar_colecciones(graphql_tienda("columbia"))
    assert [coleccion["handle"] for coleccion in colecciones] == ["sale", "zapatillas"]
    assert colecciones[0]["titulo"] == "Sale"


def test_listar_colecciones_filtra_por_texto():
    colecciones = listar_colecciones(graphql_tienda("columbia"), "zapa")
    assert len(colecciones) == 1
    assert colecciones[0]["handle"] == "zapatillas"


def test_buscar_variantes_devuelve_sku_y_nombre():
    variantes = buscar_variantes(graphql_tienda("columbia"), "ABC123-001")
    assert variantes[0]["sku"] == "ABC123-001"
    assert variantes[0]["nombre"] == "Polo azul"


def test_resolver_colecciones_traduce_handles_a_ids():
    ids, faltantes = resolver_colecciones(graphql_tienda("columbia"), ["sale", "zapatillas"])
    assert ids == ["gid://shopify/Collection/11", "gid://shopify/Collection/12"]
    assert faltantes == []


def test_resolver_colecciones_reporta_las_que_no_existen():
    ids, faltantes = resolver_colecciones(graphql_tienda("rockford"), ["sale", "zapatillas"])
    assert ids == ["gid://shopify/Collection/99"]
    assert faltantes == ["zapatillas"]


def test_el_mismo_handle_da_ids_distintos_por_tienda():
    ids_columbia, _ = resolver_colecciones(graphql_tienda("columbia"), ["sale"])
    ids_rockford, _ = resolver_colecciones(graphql_tienda("rockford"), ["sale"])
    assert ids_columbia != ids_rockford


def test_resolver_variantes_por_sku():
    ids, faltantes = resolver_variantes(graphql_tienda("columbia"), ["ABC123-001", "NO-EXISTE"])
    assert ids == ["gid://shopify/ProductVariant/1"]
    assert faltantes == ["NO-EXISTE"]


def test_construir_items_por_coleccion():
    items = construir_items(APLICA_COLECCIONES, ["gid://c/1"], [])
    assert items == {"collections": {"add": ["gid://c/1"]}}


def test_construir_items_por_variante():
    items = construir_items(APLICA_PRODUCTOS, [], ["gid://v/1"])
    assert items == {"products": {"productVariantsToAdd": ["gid://v/1"]}}


def test_construir_items_cae_a_todos_si_no_hay_seleccion():
    assert construir_items(APLICA_COLECCIONES, [], []) == {"all": True}
    assert construir_items(APLICA_TODOS, ["gid://c/1"], []) == {"all": True}


def test_resolver_para_tienda_avisa_cuando_queda_sin_alcance():
    items, avisos = resolver_para_tienda(graphql_tienda("rockford"), APLICA_PRODUCTOS, [], ["ABC123-001"])
    assert items == {"all": True}
    assert any("sin alcance" in aviso for aviso in avisos)
    assert any("ABC123-001" in aviso for aviso in avisos)


def test_resolver_en_tiendas_resuelve_cada_una_por_separado():
    resultado = resolver_en_tiendas(
        ["columbia", "rockford"],
        graphql_tienda,
        APLICA_COLECCIONES,
        ["sale"],
        [],
    )
    assert resultado["columbia"]["items"] == {"collections": {"add": ["gid://shopify/Collection/11"]}}
    assert resultado["rockford"]["items"] == {"collections": {"add": ["gid://shopify/Collection/99"]}}
    assert resultado["columbia"]["avisos"] == []


def test_resolver_en_tiendas_no_explota_si_una_falla():
    def crear(clave):
        if clave == "rockford":
            raise RuntimeError("401 token invalido")
        return graphql_tienda(clave)

    resultado = resolver_en_tiendas(["columbia", "rockford"], crear, APLICA_COLECCIONES, ["sale"], [])
    assert resultado["columbia"]["items"]["collections"]["add"]
    assert resultado["rockford"]["items"] == {"all": True}
    assert any("No pude leer el catalogo" in aviso for aviso in resultado["rockford"]["avisos"])
