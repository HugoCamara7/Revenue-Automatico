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
APLICA_FILTRO = "Filtro por marca, tipo o genero"

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


def construir_items(
    aplica_a: str,
    ids_colecciones: list[str],
    ids_variantes: list[str],
    ids_productos: list[str] | None = None,
) -> dict:
    """Arma `customerGets.items` para el cupon nativo."""
    if aplica_a == APLICA_COLECCIONES and ids_colecciones:
        return {"collections": {"add": list(ids_colecciones)}}
    if aplica_a == APLICA_PRODUCTOS and ids_variantes:
        return {"products": {"productVariantsToAdd": list(ids_variantes)}}
    if aplica_a == APLICA_FILTRO and ids_productos:
        return {"products": {"productsToAdd": list(ids_productos)}}
    return {"all": True}


def resolver_para_tienda(
    graphql,
    aplica_a: str,
    handles: list[str],
    skus: list[str],
    consulta: str = "",
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

    if aplica_a == APLICA_FILTRO:
        ids, avisos = resolver_por_filtro(graphql, consulta)
        if ids:
            avisos.insert(0, str(len(ids)) + " producto(s) alcanzados por el filtro.")
        return construir_items(aplica_a, [], [], ids), avisos

    return {"all": True}, []


def resolver_en_tiendas(
    shop_keys: list[str],
    crear_graphql: Callable[[str], object],
    aplica_a: str,
    handles: list[str],
    skus: list[str],
    consulta: str = "",
    para_function: bool = False,
) -> dict[str, dict]:
    """Resuelve el targeting en cada tienda antes de crear los cupones.

    Con `para_function=True` ademas se traduce el alcance a IDs de producto/variante,
    que es lo unico que una Shopify Function puede evaluar.
    """
    resultado = {}
    for shop_key in shop_keys or []:
        try:
            graphql = crear_graphql(shop_key)
            items, avisos = resolver_para_tienda(graphql, aplica_a, handles, skus, consulta)
            datos = {"items": items, "avisos": list(avisos)}
            if para_function:
                alcance = resolver_para_function(graphql, aplica_a, handles, skus, consulta)
                datos["function"] = alcance
                datos["avisos"] = list(alcance.get("avisos") or [])
        except Exception as exc:
            datos = {"items": {"all": True}, "avisos": ["No pude leer el catalogo: " + str(exc)[:120]]}
        resultado[shop_key] = datos
    return resultado


# ---------------------------------------------------------------------------
# Filtro avanzado
#
# Shopify solo sabe apuntar un descuento a colecciones o a productos/variantes
# concretos: no existe "todos los productos donde vendor = VANS". Lo que si es
# portable entre tiendas es la **consulta de busqueda**: `vendor:'VANS' AND
# product_type:'Zapatillas'` se ejecuta en cada tienda y devuelve los IDs de esa
# tienda. Por eso guardamos el filtro, no los IDs.
#
# Ojo con dos limites reales:
#   1. La lista queda congelada al crear el cupon. Un producto que entre despues
#      no va a estar incluido. Para segmentos permanentes conviene una coleccion
#      automatica de Shopify, que se mantiene sola.
#   2. Un descuento no puede apuntar a una cantidad ilimitada de productos. Si el
#      filtro devuelve demasiados, avisamos en vez de mandar una lista gigante.
# ---------------------------------------------------------------------------

LIMITE_PRODUCTOS_DESCUENTO = 250

QUERY_FACETAS = """
query Facetas {
  shop {
    productVendors(first: 250) { nodes }
    productTypes(first: 250) { nodes }
  }
}
"""

QUERY_MUESTRA_PRODUCTOS = """
query MuestraProductos($first: Int!) {
  products(first: $first) {
    nodes {
      vendor
      productType
      tags
    }
  }
}
"""

QUERY_PRODUCTOS_FILTRO = """
query ProductosPorFiltro($first: Int!, $query: String) {
  products(first: $first, query: $query) {
    nodes {
      id
      title
      vendor
      productType
      tags
      totalInventory
    }
  }
}
"""


def escapar(valor: str) -> str:
    return str(valor).replace("'", "").strip()


def construir_query_busqueda(marca: str = "", tipo: str = "", etiquetas=None, texto: str = "") -> str:
    """Arma la consulta de busqueda de Shopify a partir de los filtros elegidos."""
    partes = []
    if str(marca or "").strip():
        partes.append("vendor:'" + escapar(marca) + "'")
    if str(tipo or "").strip():
        partes.append("product_type:'" + escapar(tipo) + "'")
    for etiqueta in etiquetas or []:
        if str(etiqueta).strip():
            partes.append("tag:'" + escapar(etiqueta) + "'")
    if str(texto or "").strip():
        partes.append("title:*" + escapar(texto) + "*")
    return " AND ".join(partes)


def listar_facetas(graphql, muestra: int = 250) -> dict:
    """Marcas, tipos y etiquetas disponibles en la tienda.

    Primero se piden los catalogos de la tienda; si esa consulta no esta disponible,
    se deducen desde una muestra de productos.
    """
    try:
        datos = graphql(QUERY_FACETAS, None)
        shop = (datos or {}).get("shop") or {}
        marcas = sorted({str(v).strip() for v in ((shop.get("productVendors") or {}).get("nodes") or []) if str(v).strip()})
        tipos = sorted({str(v).strip() for v in ((shop.get("productTypes") or {}).get("nodes") or []) if str(v).strip()})
        if marcas or tipos:
            return {"marcas": marcas, "tipos": tipos, "etiquetas": listar_etiquetas(graphql, muestra)}
    except Exception:
        pass

    try:
        datos = graphql(QUERY_MUESTRA_PRODUCTOS, {"first": int(muestra)})
    except Exception:
        return {"marcas": [], "tipos": [], "etiquetas": []}
    nodos = ((datos or {}).get("products") or {}).get("nodes") or []
    marcas, tipos, etiquetas = set(), set(), set()
    for nodo in nodos:
        if str(nodo.get("vendor") or "").strip():
            marcas.add(str(nodo["vendor"]).strip())
        if str(nodo.get("productType") or "").strip():
            tipos.add(str(nodo["productType"]).strip())
        for etiqueta in nodo.get("tags") or []:
            if str(etiqueta).strip():
                etiquetas.add(str(etiqueta).strip())
    return {"marcas": sorted(marcas), "tipos": sorted(tipos), "etiquetas": sorted(etiquetas)}


def listar_etiquetas(graphql, muestra: int = 250) -> list[str]:
    try:
        datos = graphql(QUERY_MUESTRA_PRODUCTOS, {"first": int(muestra)})
    except Exception:
        return []
    nodos = ((datos or {}).get("products") or {}).get("nodes") or []
    etiquetas = set()
    for nodo in nodos:
        for etiqueta in nodo.get("tags") or []:
            if str(etiqueta).strip():
                etiquetas.add(str(etiqueta).strip())
    return sorted(etiquetas)


def buscar_por_filtro(graphql, consulta: str, limite: int = 50) -> list[dict]:
    """Productos que cumplen el filtro, para la vista previa."""
    datos = graphql(QUERY_PRODUCTOS_FILTRO, {"first": int(limite), "query": consulta or None})
    nodos = ((datos or {}).get("products") or {}).get("nodes") or []
    return [
        {
            "id": nodo.get("id", ""),
            "titulo": nodo.get("title", ""),
            "marca": nodo.get("vendor", ""),
            "tipo": nodo.get("productType", ""),
            "etiquetas": ", ".join(nodo.get("tags") or []),
        }
        for nodo in nodos
    ]


def resolver_por_filtro(graphql, consulta: str, limite: int = LIMITE_PRODUCTOS_DESCUENTO) -> tuple[list[str], list[str]]:
    """Ejecuta el filtro en esta tienda y devuelve (ids_de_producto, avisos)."""
    if not str(consulta or "").strip():
        return [], ["El filtro esta vacio."]
    try:
        productos = buscar_por_filtro(graphql, consulta, limite + 1)
    except Exception as exc:
        return [], ["No pude ejecutar el filtro: " + str(exc)[:140]]

    ids = [producto["id"] for producto in productos if producto.get("id")]
    avisos = []
    if not ids:
        avisos.append("El filtro no encontro productos en esta tienda.")
    elif len(ids) > limite:
        ids = ids[:limite]
        avisos.append(
            "El filtro devuelve mas de " + str(limite) + " productos. Se tomaron los primeros "
            + str(limite) + ": conviene crear una coleccion automatica en Shopify y apuntar a ella."
        )
    return ids, avisos


# ---------------------------------------------------------------------------
# Expansion para Shopify Functions
#
# En un cupon nativo, Shopify aplica el alcance por su cuenta. En uno con Function
# el alcance viaja en el metafield y lo evalua la Function, que solo ve `product.id`
# y `variant.id` de cada linea del carrito. Por eso una coleccion hay que convertirla
# a la lista de productos que contiene, al momento de crear el cupon.
#
# Consecuencia a tener presente: la lista queda congelada. Un producto que entre a la
# coleccion despues no va a estar incluido hasta que se vuelva a crear el cupon.
# ---------------------------------------------------------------------------

LIMITE_PRODUCTOS_FUNCTION = 500

QUERY_PRODUCTOS_DE_COLECCION = """
query ProductosDeColeccion($id: ID!, $first: Int!, $cursor: String) {
  collection(id: $id) {
    title
    products(first: $first, after: $cursor) {
      nodes { id }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def expandir_colecciones_a_productos(
    graphql,
    ids_colecciones: list[str],
    limite: int = LIMITE_PRODUCTOS_FUNCTION,
) -> tuple[list[str], list[str]]:
    """Devuelve (ids_de_producto, avisos) de todas las colecciones indicadas."""
    productos: list[str] = []
    avisos: list[str] = []
    for id_coleccion in ids_colecciones or []:
        cursor = None
        while True:
            try:
                datos = graphql(
                    QUERY_PRODUCTOS_DE_COLECCION,
                    {"id": id_coleccion, "first": 250, "cursor": cursor},
                )
            except Exception as exc:
                avisos.append("No pude leer los productos de la coleccion: " + str(exc)[:120])
                break
            coleccion = (datos or {}).get("collection") or {}
            conexion = coleccion.get("products") or {}
            for nodo in conexion.get("nodes") or []:
                if nodo.get("id") and nodo["id"] not in productos:
                    productos.append(nodo["id"])
            pagina = conexion.get("pageInfo") or {}
            if not pagina.get("hasNextPage") or len(productos) >= limite:
                break
            cursor = pagina.get("endCursor")

    if len(productos) > limite:
        avisos.append(
            "La coleccion tiene mas de " + str(limite) + " productos. Se enviaron los primeros "
            + str(limite) + " a la Function."
        )
        productos = productos[:limite]
    return productos, avisos


def resolver_para_function(
    graphql,
    aplica_a: str,
    handles: list[str],
    skus: list[str],
    consulta: str = "",
) -> dict:
    """Alcance para un cupon Best Wins: siempre en IDs de producto o de variante."""
    if aplica_a == APLICA_TODOS:
        return {"applies_to": "all_products", "product_ids": [], "variant_ids": [], "avisos": []}

    if aplica_a == APLICA_COLECCIONES:
        ids_colecciones, faltantes = resolver_colecciones(graphql, handles)
        avisos = ["Coleccion no encontrada: " + handle for handle in faltantes]
        productos, avisos_expansion = expandir_colecciones_a_productos(graphql, ids_colecciones)
        avisos.extend(avisos_expansion)
        if productos:
            avisos.insert(0, str(len(productos)) + " producto(s) de la coleccion enviados a la Function.")
        else:
            avisos.append("La coleccion no tiene productos en esta tienda; el cupon no descontaria nada.")
        return {
            "applies_to": "products",
            "product_ids": productos,
            "variant_ids": [],
            "collection_ids": ids_colecciones,
            "avisos": avisos,
        }

    if aplica_a == APLICA_PRODUCTOS:
        ids, faltantes = resolver_variantes(graphql, skus)
        avisos = ["SKU no encontrado: " + sku for sku in faltantes]
        if not ids:
            avisos.append("Ningun SKU existe en esta tienda; el cupon no descontaria nada.")
        return {"applies_to": "variants", "product_ids": [], "variant_ids": ids, "avisos": avisos}

    ids, avisos = resolver_por_filtro(graphql, consulta, LIMITE_PRODUCTOS_FUNCTION)
    if ids:
        avisos.insert(0, str(len(ids)) + " producto(s) del filtro enviados a la Function.")
    return {"applies_to": "products", "product_ids": ids, "variant_ids": [], "avisos": avisos}
