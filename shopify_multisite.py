"""Diagnostico multitienda para cupones Shopify (Price actual y Compare At - Best Wins).

Este modulo no depende de Streamlit ni de red: recibe un callable GraphQL ya
autenticado por tienda, para que se pueda probar con pytest y reutilizar tanto
desde `app.py` como desde `diagnostico_multitienda.py`.

Que responde por cada tienda:

1. Estan el shop_domain y el admin_access_token en Secrets.
2. El token es valido y contra que tienda apunta.
3. El token tiene write_discounts (sin eso no se crea ningun cupon).
4. El token pertenece a la app que tiene desplegada la Discount Function
   `compare-at-best-wins`. Sin esto solo funciona `Price actual`, nunca
   `Compare At Price - Best Wins`.
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

# graphql(query, variables) -> data
GraphQLCaller = Callable[[str, dict | None], dict]

FUNCTION_HANDLE_POR_DEFECTO = "compare-at-best-wins"
API_TYPE_DESCUENTOS = "discount"
SCOPES_MINIMOS = ("write_discounts",)
SCOPES_RECOMENDADOS = ("write_discounts", "read_discounts")

ESTADO_LISTO = "listo"
ESTADO_SOLO_BASICO = "solo_precio_actual"
ESTADO_SIN_CONFIG = "sin_configurar"
ESTADO_ERROR = "error"

ETIQUETA_ESTADO = {
    ESTADO_LISTO: "LISTO (Best Wins)",
    ESTADO_SOLO_BASICO: "SOLO PRECIO ACTUAL",
    ESTADO_SIN_CONFIG: "SIN CONFIGURAR",
    ESTADO_ERROR: "ERROR",
}

QUERY_TIENDA = """
query DiagnosticoTienda {
  shop {
    name
    myshopifyDomain
    currencyCode
    plan {
      displayName
      partnerDevelopment
      shopifyPlus
    }
  }
}
"""

QUERY_INSTALACION = """
query DiagnosticoInstalacion {
  currentAppInstallation {
    accessScopes {
      handle
    }
    app {
      title
      handle
    }
  }
}
"""

QUERY_INSTALACION_SIMPLE = """
query DiagnosticoInstalacionSimple {
  currentAppInstallation {
    accessScopes {
      handle
    }
  }
}
"""

QUERY_FUNCIONES = """
query DiagnosticoFunciones($apiType: String, $first: Int!) {
  shopifyFunctions(apiType: $apiType, first: $first) {
    nodes {
      id
      handle
      title
      apiType
      appKey
      app {
        title
      }
    }
  }
}
"""

QUERY_FUNCIONES_SIMPLE = """
query DiagnosticoFuncionesSimple($apiType: String, $first: Int!) {
  shopifyFunctions(apiType: $apiType, first: $first) {
    nodes {
      id
      handle
      title
      apiType
      appKey
    }
  }
}
"""


CLAVE_TOKENS = "tokens"


def como_dict(valor) -> dict:
    """Convierte a dict plano.

    st.secrets devuelve AttrDict (un Mapping que NO hereda de dict) en las tablas
    anidadas, asi que `isinstance(valor, dict)` da False y el bloque se ignora en
    silencio. Por eso todo pasa por aca.
    """
    if isinstance(valor, dict):
        return valor
    if hasattr(valor, "items"):
        try:
            return dict(valor)
        except Exception:
            return {}
    return {}


def expandir_tokens(sitio: dict, config: dict) -> list[tuple[dict, dict]]:
    """Si una tienda tiene varias apps, devuelve un par (sitio, config) por cada token.

    Sirve cuando la misma tienda tiene, por ejemplo, la app vieja de catalogo y la app
    nueva de cupones, y no se sabe cual de las dos ve la Discount Function.

    Formato simple en Secrets:

        [shopify_sites.columbia.tokens]
        catalogo_digital = "shpat_..."
        app_cupones = "shpat_..."

    Formato con client_id por app:

        [shopify_sites.columbia.tokens.app_cupones]
        admin_access_token = "shpat_..."
        client_id = "..."
    """
    config = como_dict(config)
    tokens = como_dict(config.get(CLAVE_TOKENS))
    if not tokens:
        return [(sitio, config)]

    pares = []
    base = {clave: valor for clave, valor in config.items() if clave != CLAVE_TOKENS}
    for nombre, valor in tokens.items():
        detalle = como_dict(valor)
        if detalle:
            token = str(detalle.get("admin_access_token") or detalle.get("access_token") or detalle.get("token") or "").strip()
            extras = {clave: dato for clave, dato in detalle.items() if clave not in ("admin_access_token", "access_token", "token")}
        else:
            token = str(valor or "").strip()
            extras = {}
        if not token:
            continue
        config_token = {**base, **extras, "admin_access_token": token}
        config_token.pop("access_token", None)
        sitio_token = {
            **sitio,
            "name": (str(sitio.get("name", "")).strip() or str(sitio.get("id", ""))) + " [" + str(nombre) + "]",
            "token_nombre": str(nombre),
        }
        pares.append((sitio_token, config_token))
    return pares or [(sitio, config)]


def recomendar_tokens(resultados: Iterable[dict]) -> list[str]:
    """Con varios tokens por tienda, dice cual va en admin_access_token."""
    por_tienda: dict[str, list[dict]] = {}
    for fila in resultados or []:
        por_tienda.setdefault(fila.get("shop_key", ""), []).append(fila)

    mensajes = []
    for shop_key, filas in por_tienda.items():
        nombrados = [fila for fila in filas if fila.get("token_nombre")]
        if len(nombrados) < 2:
            continue
        ganadores = [fila for fila in nombrados if fila.get("funcion_id")]
        if ganadores:
            fila = ganadores[0]
            mensajes.append(
                shop_key
                + ": usa el token '"
                + fila["token_nombre"]
                + "' en admin_access_token (es el unico que ve la Function '"
                + fila["funcion_handle"]
                + "')."
            )
            continue
        con_permiso = [fila for fila in nombrados if fila.get("scopes") and not fila.get("scopes_faltantes")]
        if con_permiso:
            mensajes.append(
                shop_key
                + ": ningun token ve la Function. Con '"
                + con_permiso[0]["token_nombre"]
                + "' solo se pueden crear cupones de Price actual; falta instalar la app de la Function."
            )
        else:
            mensajes.append(shop_key + ": ningun token sirve todavia. Revisa el detalle de arriba.")
    return mensajes


def normalizar_dominio(valor) -> str:
    """Deja el dominio como `tienda.myshopify.com`, sin protocolo ni barras."""
    texto = str(valor or "").strip().lower()
    texto = texto.replace("https://", "").replace("http://", "")
    return texto.strip("/").split("/")[0].strip()


def token_enmascarado(valor) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    if len(texto) <= 10:
        return texto[0] + "*" * (len(texto) - 1)
    return texto[:6] + "..." + texto[-4:]


def scopes_faltantes(otorgados: Iterable[str], requeridos: Sequence[str] = SCOPES_MINIMOS) -> list[str]:
    disponibles = {str(scope).strip().lower() for scope in otorgados or []}
    return [scope for scope in requeridos if scope.lower() not in disponibles]


def elegir_funcion(
    nodos: Iterable[dict],
    handle_esperado: str = FUNCTION_HANDLE_POR_DEFECTO,
    client_id: str = "",
) -> tuple[dict | None, str]:
    """Devuelve (funcion, motivo).

    Si se pasa `client_id` (el mismo de Secrets), primero se filtra por `appKey`, que es
    justamente el client_id de la app dueña de la Function. Asi, aunque la tienda tenga
    varias Discount Functions de otras apps, se elige la nuestra sin depender del handle.

    motivo:
      - "handle_exacto": se encontro el handle esperado.
      - "por_client_id": una sola Function de nuestra app, con otro handle.
      - "unica_funcion": una sola Discount Function en la tienda, con otro handle.
      - "sin_funciones": la app no expone Discount Functions en esa tienda.
      - "varias_funciones": hay varias y ninguna coincide con el handle esperado.
    """
    funciones = [nodo for nodo in (nodos or []) if isinstance(nodo, dict)]
    descuentos = [
        nodo
        for nodo in funciones
        if str(nodo.get("apiType", API_TYPE_DESCUENTOS)).strip().lower() == API_TYPE_DESCUENTOS
    ]
    if not descuentos:
        descuentos = funciones
    if not descuentos:
        return None, "sin_funciones"

    clave = str(client_id or "").strip().lower()
    propias = [nodo for nodo in descuentos if str(nodo.get("appKey", "")).strip().lower() == clave] if clave else []
    candidatos = propias or descuentos

    esperado = str(handle_esperado or "").strip().lower()
    for nodo in candidatos:
        if str(nodo.get("handle", "")).strip().lower() == esperado:
            return nodo, "handle_exacto"
    if len(candidatos) == 1:
        return candidatos[0], "por_client_id" if propias else "unica_funcion"
    return None, "varias_funciones"


def bloque_secrets(
    shop_key: str,
    dominio: str,
    handle: str,
    api_version: str = "2026-04",
    client_id: str = "",
) -> str:
    """Arma el bloque TOML listo para pegar en Secrets."""
    lineas = [
        "[shopify_sites." + str(shop_key).strip() + "]",
        'shop_domain = "' + normalizar_dominio(dominio) + '"',
    ]
    if client_id:
        lineas.append('client_id = "' + str(client_id).strip() + '"')
    lineas.append('admin_access_token = "shpat_..."')
    lineas.append('api_version = "' + str(api_version).strip() + '"')
    if handle:
        lineas.append('compare_at_best_wins_function_handle = "' + str(handle).strip() + '"')
    else:
        lineas.append("# Falta el handle: corre el diagnostico con el token puesto y lo completa solo.")
    return "\n".join(lineas)


def _ejecutar(graphql: GraphQLCaller, query: str, variables: dict | None = None, respaldo: str | None = None) -> dict:
    """Ejecuta la query y, si falla por campos no disponibles, reintenta con una version reducida."""
    try:
        return graphql(query, variables) or {}
    except Exception:
        if not respaldo:
            raise
        return graphql(respaldo, variables) or {}


def diagnosticar_tienda(
    sitio: dict,
    config: dict,
    graphql: GraphQLCaller,
    handle_esperado: str = FUNCTION_HANDLE_POR_DEFECTO,
    scopes_requeridos: Sequence[str] = SCOPES_MINIMOS,
) -> dict:
    """Revisa una tienda y devuelve una fila de diagnostico lista para mostrar."""
    shop_key = str(sitio.get("shop_key") or sitio.get("id") or "").strip()
    client_id = str(config.get("client_id", "")).strip()
    resultado = {
        "id": str(sitio.get("id", "")).strip(),
        "sitio": str(sitio.get("name", "")).strip() or shop_key,
        "shop_key": shop_key,
        "token_nombre": str(sitio.get("token_nombre", "")).strip(),
        "client_id": client_id,
        "dominio": normalizar_dominio(config.get("shop_domain")),
        "token": token_enmascarado(config.get("access_token") or config.get("admin_access_token")),
        "api_version": str(config.get("api_version", "2026-04")).strip() or "2026-04",
        "tienda": "",
        "plan": "",
        "es_plus": False,
        "app": "",
        "scopes": [],
        "scopes_faltantes": [],
        "funcion_handle": "",
        "funcion_id": "",
        "funcion_titulo": "",
        "handle_en_secrets": str(config.get("compare_at_best_wins_function_handle", "")).strip(),
        "estado": ESTADO_ERROR,
        "detalles": [],
        "secrets_sugeridos": "",
    }

    token = str(config.get("access_token") or config.get("admin_access_token") or "").strip()
    if not resultado["dominio"] or not token:
        resultado["estado"] = ESTADO_SIN_CONFIG
        if not resultado["dominio"]:
            resultado["detalles"].append("Falta shop_domain en Secrets.")
        if not token:
            resultado["detalles"].append("Falta admin_access_token en Secrets.")
        resultado["secrets_sugeridos"] = bloque_secrets(
            shop_key,
            resultado["dominio"] or shop_key + ".myshopify.com",
            handle_esperado,
            resultado["api_version"],
            client_id,
        )
        return resultado

    try:
        datos_tienda = _ejecutar(graphql, QUERY_TIENDA)
    except Exception as exc:
        resultado["estado"] = ESTADO_ERROR
        resultado["detalles"].append("El token no respondio: " + str(exc))
        return resultado

    shop = (datos_tienda or {}).get("shop") or {}
    plan = shop.get("plan") or {}
    resultado["tienda"] = str(shop.get("name", "")).strip()
    resultado["plan"] = str(plan.get("displayName", "")).strip()
    resultado["es_plus"] = bool(plan.get("shopifyPlus"))
    dominio_real = normalizar_dominio(shop.get("myshopifyDomain"))
    if dominio_real and resultado["dominio"] and dominio_real != resultado["dominio"]:
        resultado["detalles"].append(
            "Ojo: el token pertenece a " + dominio_real + " y en Secrets pusiste " + resultado["dominio"] + "."
        )
        resultado["dominio"] = dominio_real

    try:
        datos_instalacion = _ejecutar(graphql, QUERY_INSTALACION, None, QUERY_INSTALACION_SIMPLE)
        instalacion = (datos_instalacion or {}).get("currentAppInstallation") or {}
        resultado["scopes"] = sorted(
            str(item.get("handle", "")).strip()
            for item in (instalacion.get("accessScopes") or [])
            if str(item.get("handle", "")).strip()
        )
        resultado["app"] = str((instalacion.get("app") or {}).get("title", "")).strip()
    except Exception as exc:
        resultado["detalles"].append("No pude leer los permisos de la app: " + str(exc))

    resultado["scopes_faltantes"] = scopes_faltantes(resultado["scopes"], scopes_requeridos)
    if resultado["scopes"] and resultado["scopes_faltantes"]:
        resultado["detalles"].append(
            "Al token le faltan permisos: " + ", ".join(resultado["scopes_faltantes"]) + "."
        )

    motivo = "sin_funciones"
    try:
        datos_funciones = _ejecutar(
            graphql,
            QUERY_FUNCIONES,
            {"apiType": API_TYPE_DESCUENTOS, "first": 50},
            QUERY_FUNCIONES_SIMPLE,
        )
        nodos = ((datos_funciones or {}).get("shopifyFunctions") or {}).get("nodes") or []
        funcion, motivo = elegir_funcion(nodos, handle_esperado, client_id)
        if funcion:
            resultado["funcion_handle"] = str(funcion.get("handle", "")).strip()
            resultado["funcion_id"] = str(funcion.get("id", "")).strip()
            resultado["funcion_titulo"] = str(funcion.get("title", "")).strip()
    except Exception as exc:
        motivo = "error"
        resultado["detalles"].append("No pude listar las Shopify Functions: " + str(exc))

    if motivo == "por_client_id":
        resultado["detalles"].append(
            "Encontre la Function de tu app (client_id "
            + client_id
            + ") con handle '"
            + resultado["funcion_handle"]
            + "'. Ese es el valor para compare_at_best_wins_function_handle."
        )
    elif motivo == "unica_funcion":
        resultado["detalles"].append(
            "La Function desplegada usa el handle '"
            + resultado["funcion_handle"]
            + "', no '"
            + handle_esperado
            + "'. Copia ese handle en Secrets."
        )
    elif motivo == "varias_funciones":
        resultado["detalles"].append(
            "Hay varias Discount Functions y ninguna con handle '" + handle_esperado + "'. Revisa el deploy."
        )
    elif motivo == "sin_funciones":
        resultado["detalles"].append(
            "Esta tienda no ve ninguna Discount Function de esta app: instala la app del CLI en la tienda y "
            "usa el token de esa app (un custom app creado desde el Admin nunca trae Functions)."
        )

    handle_final = resultado["funcion_handle"] or resultado["handle_en_secrets"]
    if resultado["handle_en_secrets"] and resultado["funcion_handle"] and (
        resultado["handle_en_secrets"].lower() != resultado["funcion_handle"].lower()
    ):
        resultado["detalles"].append(
            "Secrets dice '"
            + resultado["handle_en_secrets"]
            + "' pero la tienda expone '"
            + resultado["funcion_handle"]
            + "'."
        )

    if resultado["scopes"] and resultado["scopes_faltantes"]:
        resultado["estado"] = ESTADO_ERROR
    elif resultado["funcion_id"]:
        resultado["estado"] = ESTADO_LISTO
    else:
        resultado["estado"] = ESTADO_SOLO_BASICO

    resultado["secrets_sugeridos"] = bloque_secrets(
        shop_key, resultado["dominio"], handle_final, resultado["api_version"], client_id
    )
    return resultado


def diagnosticar_tiendas(
    sitios: Iterable[dict],
    obtener_config: Callable[[str], dict],
    crear_graphql: Callable[[str, dict], GraphQLCaller],
    handle_esperado: str = FUNCTION_HANDLE_POR_DEFECTO,
    scopes_requeridos: Sequence[str] = SCOPES_MINIMOS,
) -> list[dict]:
    """Corre el diagnostico para varias tiendas y devuelve una fila por tienda y token."""
    filas = []
    for sitio in sitios or []:
        shop_key = str(sitio.get("shop_key") or sitio.get("id") or "").strip()
        config = obtener_config(shop_key) or {}
        for sitio_token, config_token in expandir_tokens(sitio, config):
            filas.append(
                diagnosticar_tienda(
                    sitio_token,
                    config_token,
                    crear_graphql(shop_key, config_token),
                    handle_esperado=handle_esperado,
                    scopes_requeridos=scopes_requeridos,
                )
            )
    return filas


def resumen_por_estado(resultados: Iterable[dict]) -> dict[str, int]:
    resumen = {ESTADO_LISTO: 0, ESTADO_SOLO_BASICO: 0, ESTADO_SIN_CONFIG: 0, ESTADO_ERROR: 0}
    for fila in resultados or []:
        estado = fila.get("estado", ESTADO_ERROR)
        resumen[estado] = resumen.get(estado, 0) + 1
    return resumen


def filas_tabla(resultados: Iterable[dict]) -> list[dict]:
    """Version compacta para st.dataframe o para imprimir."""
    filas = []
    for fila in resultados or []:
        if not fila.get("scopes"):
            permiso = "-"
        elif fila.get("scopes_faltantes"):
            permiso = "No"
        else:
            permiso = "Si"
        filas.append(
            {
                "Sitio": fila.get("sitio", ""),
                "Dominio": fila.get("dominio", "") or "-",
                "Token": fila.get("token", "") or "-",
                "Plan": fila.get("plan", "") or "-",
                "App": fila.get("app", "") or "-",
                "write_discounts": permiso,
                "Function": fila.get("funcion_handle", "") or "-",
                "Estado": ETIQUETA_ESTADO.get(fila.get("estado", ESTADO_ERROR), fila.get("estado", "")),
            }
        )
    return filas


def texto_tabla(resultados: Iterable[dict]) -> str:
    """Tabla de ancho fijo para consola."""
    filas = filas_tabla(resultados)
    if not filas:
        return "No hay tiendas configuradas en COUPON_SHOPIFY_SITES."
    columnas = list(filas[0].keys())
    anchos = {col: len(col) for col in columnas}
    for fila in filas:
        for col in columnas:
            anchos[col] = max(anchos[col], len(str(fila[col])))
    lineas = [" | ".join(col.ljust(anchos[col]) for col in columnas)]
    lineas.append("-+-".join("-" * anchos[col] for col in columnas))
    for fila in filas:
        lineas.append(" | ".join(str(fila[col]).ljust(anchos[col]) for col in columnas))
    return "\n".join(lineas)
