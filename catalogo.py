"""Catalogo por tienda: buscar colecciones y productos para apuntar un cupon.

**El punto clave**: los IDs de Shopify son por tienda. `gid://shopify/Collection/123`
en Columbia no es la misma coleccion en Rockford. Como un cupon se crea en varias
tiendas a la vez, no se pueden guardar IDs.

Por eso se selecciona con claves que si son estables entre tiendas:

- colecciones -> por **handle** (`sale`, `zapatillas-hombre`)
- productos   -> por **SKU** de la variante

y al momento de crear el cupon se resuelve el ID real en cada tienda. Si un handle o
un SKU no existe en alguna tienda, se reporta en el resultado en vez de fallar callado.

Requiere el permiso `read_products` en la app de Shopify.
"""

from __future__ import annotations

from typing import Callable

APLICA_TODOS = "Todos los productos"
APLICA_PRODUCTOS = "Productos seleccionados"
APLICA_COLECCIONES = "Colecciones seleccionadas"

QUERY_COLECCIONES = """
query BuscarColecciones($first: Int!, $query: String) {
  collections(first: $first, query: $query, sortKey: TITLE) {
    nodes {
      id
      handle
      title
    }
  }
}
"""

QUERY_COLECCIONES_SIMPLE = """
query BuscarColeccionesSimple($first: Int!, $query: String) {
  collections(first: $first, query: $query) {
    nodes {
      id
      handle
      title
    }
  }
}
"""

QUERY_VARIANTES = """
query BuscarVariantes($first: Int!, $query: String) {
  productVariants(first: $first, query: $query) {
    nodes {
      id
      sku
      displayName
      price
      product {
        id
        title
      }
    }
  }
}
"""


def listar_colecciones(graphql, texto: str = "", limite: int = 100) -> list[dict]:
    """Colecciones de la tienda, opcionalmente filtradas por titulo."""
    filtro = ("title:*" + str(texto).strip() + "*") if str(texto).strip() else None
    variables = {"first": int(limite), "query": filtro}
    try:
        datos = graphql(QUERY_COLECCIONES, variables)
    except Exception:
        datos = graphql(QUERY_COLECCIONES_SIMPLE, variables)
    nodos = ((datos or {}).get("collections") or {}).get("nodes") or []
    return [
        {
            "id": nodo.get("id", ""),
            "handle": nodo.get("handle", ""),
            "titulo": nodo.get("title", ""),
        }
        for nodo in nodos
        if nodo.get("handle")
    ]


def buscar_variantes(graphql, texto: str = "", limite: int = 50) -> list[dict]:
    """Variantes por SKU o por nombre de producto."""
    busqueda = str(texto or "").strip()
    filtro = ("sku:*" + busqueda + "* OR title:*" + busqueda + "*") if busqueda else None
    datos = graphql(QUERY_VARIANTES, {"first": int(limite), "query": filtro})
    nodos = ((datos or {}).get("productVariants") or {}).get("nodes") or []
    return [
        {
            "id": nodo.get("id", ""),
            "sku": str(nodo.get("sku") or "").strip(),
            "nombre": nodo.get("displayName") or (nodo.get("product") or {}).get("title", ""),
            "precio": nodo.get("price", ""),
            "producto_id": (nodo.get("product") or {}).get("id", ""),
        }
        for nodo in nodos
    ]


def resolver_colecciones(graphql, handles: list[str]) -> tuple[list[str], list[str]]:
    """Traduce handles a IDs de esta tienda. Devuelve (ids, handles_no_encontrados)."""
    ids = []
    faltantes = []
    for handle in handles or []:
        limpio = str(handle).strip()
        if not limpio:
            continue
        try:
            datos = graphql(QUERY_COLECCIONES_SIMPLE, {"first": 5, "query": "handle:" + limpio})
            nodos = ((datos or {}).get("collections") or {}).get("nodes") or []
        except Exception:
            faltantes.append(limpio)
            continue
        encontrado = next((nodo for nodo in nodos if str(nodo.get("handle", "")).strip() == limpio), None)
        if encontrado and encontrado.get("id"):
            ids.append(encontrado["id"])
        else:
            faltantes.append(limpio)
    return ids, faltantes


def resolver_variantes(graphql, skus: list[str]) -> tuple[list[str], list[str]]:
    """Traduce SKUs a IDs de variante de esta tienda. Devuelve (ids, skus_no_encontrados)."""
    ids = []
    faltantes = []
    for sku in skus or []:
        limpio = str(sku).strip()
        if not limpio:
            continue
        try:
            datos = graphql(QUERY_VARIANTES, {"first": 5, "query": "sku:" + limpio})
            nodos = ((datos or {}).get("productVariants") or {}).get("nodes") or []
        except Exception:
            faltantes.append(limpio)
            continue
        encontrado = next(
            (nodo for nodo in nodos if str(nodo.get("sku") or "").strip().upper() == limpio.upper()),
            None,
        )
        if encontrado and encontrado.get("id"):
            ids.append(encontrado["id"])
        else:
            faltantes.append(limpio)
    return ids, faltantes


def construir_items(aplica_a: str, ids_colecciones: list[str], ids_variantes: list[str]) -> dict:
    """Arma `customerGets.items` para el cupon nativo."""
    if aplica_a == APLICA_COLECCIONES and ids_colecciones:
        return {"collections": {"add": list(ids_colecciones)}}
    if aplica_a == APLICA_PRODUCTOS and ids_variantes:
        return {"products": {"productVariantsToAdd": list(ids_variantes)}}
    return {"all": True}


def resolver_para_tienda(
    graphql,
    aplica_a: str,
    handles: list[str],
    skus: list[str],
) -> tuple[dict, list[str]]:
    """Resuelve el targeting en una tienda concreta.

    Devuelve (items, avisos). `items` sirve tanto para el cupon nativo como para
    alimentar el metafield de la Function.
    """
    if aplica_a == APLICA_COLECCIONES:
        ids, faltantes = resolver_colecciones(graphql, handles)
        avisos = ["Coleccion no encontrada: " + handle for handle in faltantes]
        if not ids:
            avisos.append("Ninguna coleccion existe en esta tienda; el cupon quedaria sin alcance.")
        return construir_items(aplica_a, ids, []), avisos

    if aplica_a == APLICA_PRODUCTOS:
        ids, faltantes = resolver_variantes(graphql, skus)
        avisos = ["SKU no encontrado: " + sku for sku in faltantes]
        if not ids:
            avisos.append("Ningun SKU existe en esta tienda; el cupon quedaria sin alcance.")
        return construir_items(aplica_a, [], ids), avisos

    return {"all": True}, []


def resolver_en_tiendas(
    shop_keys: list[str],
    crear_graphql: Callable[[str], object],
    aplica_a: str,
    handles: list[str],
    skus: list[str],
) -> dict[str, dict]:
    """Resuelve el targeting en cada tienda antes de crear los cupones."""
    resultado = {}
    for shop_key in shop_keys or []:
        try:
            items, avisos = resolver_para_tienda(crear_graphql(shop_key), aplica_a, handles, skus)
        except Exception as exc:
            items, avisos = {"all": True}, ["No pude leer el catalogo: " + str(exc)[:120]]
        resultado[shop_key] = {"items": items, "avisos": avisos}
    return resultado
