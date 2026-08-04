"""Centro de Control multitienda.

Pagina nueva de Streamlit: no toca app.py. Streamlit la detecta sola por estar en
`pages/` y la muestra en el menu lateral.

Tres pestanas:

1. Estado de tiendas: semaforo por tienda (token, permisos, Function) y que falta.
2. Simulador Best Wins: como queda el precio con productos reales de la tienda.
3. Verificar codigo: si un codigo de cupon ya existe antes de crearlo.

Todo es de solo lectura: no crea, no modifica y no borra nada en Shopify.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compare_at_best_wins import best_wins_line_result  # noqa: E402
from coupon_config import COUPON_SHOPIFY_SITES  # noqa: E402
from shopify_multisite import (  # noqa: E402
    ESTADO_ERROR,
    ESTADO_LISTO,
    ESTADO_SIN_CONFIG,
    ESTADO_SOLO_BASICO,
    ETIQUETA_ESTADO,
    FUNCTION_HANDLE_POR_DEFECTO,
    diagnosticar_tienda,
    expandir_tokens,
    filas_tabla,
    recomendar_tokens,
    resumen_por_estado,
)

st.set_page_config(page_title="Centro de Control", layout="wide")

COLOR_ESTADO = {
    ESTADO_LISTO: ("#0f9d58", "#e6f6ec"),
    ESTADO_SOLO_BASICO: ("#c77700", "#fdf3e2"),
    ESTADO_SIN_CONFIG: ("#5f6b7a", "#eef1f5"),
    ESTADO_ERROR: ("#d93025", "#fdecea"),
}

ICONO_ESTADO = {
    ESTADO_LISTO: "OK",
    ESTADO_SOLO_BASICO: "!",
    ESTADO_SIN_CONFIG: "-",
    ESTADO_ERROR: "X",
}

QUERY_PRODUCTOS = """
query ProductosConCompareAt($first: Int!) {
  products(first: $first, query: "status:active") {
    nodes {
      title
      variants(first: 5) {
        nodes {
          sku
          price
          compareAtPrice
        }
      }
    }
  }
}
"""

QUERY_CODIGO = """
query BuscarCodigo($code: String!) {
  codeDiscountNodeByCode(code: $code) {
    id
    codeDiscount {
      __typename
      ... on DiscountCodeBasic {
        title
        status
      }
      ... on DiscountCodeApp {
        title
        status
      }
    }
  }
}
"""

QUERY_CODIGO_SIMPLE = """
query BuscarCodigoSimple($code: String!) {
  codeDiscountNodeByCode(code: $code) {
    id
    codeDiscount {
      __typename
    }
  }
}
"""


def ancho_completo() -> dict:
    """`use_container_width` quedo deprecado y `width` no existe en Streamlit viejo."""
    try:
        mayor, menor = (int(parte) for parte in str(st.__version__).split(".")[:2])
    except Exception:
        return {"use_container_width": True}
    return {"width": "stretch"} if (mayor, menor) >= (1, 49) else {"use_container_width": True}


ANCHO = ancho_completo()


def falta_config(config: dict) -> str:
    """Devuelve el mensaje de lo que falta en Secrets, o cadena vacia si esta completo."""
    dominio = str(config.get("shop_domain", "")).strip()
    token = str(config.get("access_token") or config.get("admin_access_token") or "").strip()
    faltantes = []
    if not dominio:
        faltantes.append("shop_domain")
    if not token:
        faltantes.append("admin_access_token")
    if not faltantes:
        return ""
    return "Falta " + " y ".join(faltantes) + " en Secrets para esta tienda."


def obtener_config(shop_key: str) -> dict:
    def como_dict(valor) -> dict:
        if not valor:
            return {}
        try:
            return dict(valor)
        except Exception:
            return {}

    try:
        for seccion in ("shopify_sites", "shopify"):
            bloque = como_dict(st.secrets.get(seccion, {}))
            config = como_dict(bloque.get(shop_key, {}))
            if config:
                return config
            if bloque.get("shop_domain") or bloque.get("access_token") or bloque.get("admin_access_token"):
                return bloque
    except Exception:
        return {}
    return {}


def crear_graphql(config: dict, timeout: int = 45):
    dominio = str(config.get("shop_domain", "")).strip().replace("https://", "").replace("http://", "").strip("/")
    token = str(config.get("access_token") or config.get("admin_access_token") or "").strip()
    api_version = str(config.get("api_version", "2026-04")).strip() or "2026-04"
    url = "https://" + dominio + "/admin/api/" + api_version + "/graphql.json"

    def ejecutar(query: str, variables: dict | None = None) -> dict:
        cuerpo = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        peticion = request.Request(
            url,
            data=cuerpo,
            headers={"Content-Type": "application/json", "X-Shopify-Access-Token": token},
            method="POST",
        )
        try:
            with request.urlopen(peticion, timeout=timeout) as respuesta:
                datos = json.loads(respuesta.read().decode("utf-8"))
        except HTTPError as exc:
            detalle = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError("Shopify respondio " + str(exc.code) + ": " + detalle) from exc
        except URLError as exc:
            raise RuntimeError("No pude conectar con Shopify: " + str(exc.reason)) from exc
        if datos.get("errors"):
            raise RuntimeError(json.dumps(datos["errors"], ensure_ascii=False)[:300])
        return datos.get("data", {})

    return ejecutar


def sitios_activos() -> list[dict]:
    return [sitio for sitio in COUPON_SHOPIFY_SITES if sitio.get("enabled", True)]


def revisar_tiendas(handle_esperado: str) -> list[dict]:
    filas = []
    sitios = sitios_activos()
    barra = st.progress(0.0, text="Revisando tiendas...")
    for indice, sitio in enumerate(sitios):
        shop_key = sitio["shop_key"]
        config = obtener_config(shop_key)
        for sitio_token, config_token in expandir_tokens(sitio, config):
            barra.progress(
                (indice + 1) / max(len(sitios), 1),
                text="Revisando " + str(sitio_token.get("name", shop_key)) + "...",
            )
            filas.append(
                diagnosticar_tienda(
                    sitio_token,
                    config_token,
                    crear_graphql(config_token),
                    handle_esperado=handle_esperado,
                )
            )
    barra.empty()
    return filas


def tarjeta_metrica(titulo: str, valor: str, color: str, fondo: str) -> str:
    return (
        '<div style="background:' + fondo + ';border-left:5px solid ' + color + ';'
        'border-radius:12px;padding:14px 18px;">'
        '<div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#5f6b7a;">'
        + titulo
        + "</div>"
        '<div style="font-size:30px;font-weight:700;color:' + color + ';line-height:1.1;">' + valor + "</div>"
        "</div>"
    )


def pintar_estado(fila: dict) -> str:
    color, fondo = COLOR_ESTADO.get(fila["estado"], ("#5f6b7a", "#eef1f5"))
    return (
        '<span style="background:' + fondo + ";color:" + color + ';padding:3px 10px;'
        'border-radius:999px;font-size:12px;font-weight:700;">'
        + ICONO_ESTADO.get(fila["estado"], "?")
        + "  "
        + ETIQUETA_ESTADO.get(fila["estado"], fila["estado"])
        + "</span>"
    )


def pestana_estado() -> None:
    izquierda, derecha = st.columns([3, 1])
    with izquierda:
        handle = st.text_input(
            "Handle esperado de la Function",
            value=FUNCTION_HANDLE_POR_DEFECTO,
            help="Si no lo sabes, dejalo vacio: se resuelve solo con el client_id de Secrets.",
        )
    with derecha:
        st.write("")
        st.write("")
        revisar = st.button("Revisar tiendas", type="primary", **ANCHO)

    if revisar:
        st.session_state["panel_resultados"] = revisar_tiendas(handle.strip())

    resultados = st.session_state.get("panel_resultados")
    if not resultados:
        st.info("Toca **Revisar tiendas** para leer el estado real de cada tienda en Shopify.")
        return

    resumen = resumen_por_estado(resultados)
    columnas = st.columns(4)
    tarjetas = [
        ("Listas para Best Wins", resumen[ESTADO_LISTO], ESTADO_LISTO),
        ("Solo precio actual", resumen[ESTADO_SOLO_BASICO], ESTADO_SOLO_BASICO),
        ("Sin configurar", resumen[ESTADO_SIN_CONFIG], ESTADO_SIN_CONFIG),
        ("Con error", resumen[ESTADO_ERROR], ESTADO_ERROR),
    ]
    for columna, (titulo, valor, estado) in zip(columnas, tarjetas):
        color, fondo = COLOR_ESTADO[estado]
        columna.markdown(tarjeta_metrica(titulo, str(valor), color, fondo), unsafe_allow_html=True)

    st.write("")
    st.dataframe(pd.DataFrame(filas_tabla(resultados)), hide_index=True, **ANCHO)

    recomendaciones = recomendar_tokens(resultados)
    if recomendaciones:
        st.markdown("**Que token dejar en `admin_access_token`:**")
        for mensaje in recomendaciones:
            st.write("- " + mensaje)

    st.write("")
    st.markdown("### Detalle por tienda")
    for fila in resultados:
        etiqueta = fila["sitio"] + "  ·  " + ETIQUETA_ESTADO.get(fila["estado"], fila["estado"])
        with st.expander(etiqueta, expanded=fila["estado"] == ESTADO_ERROR):
            st.markdown(pintar_estado(fila), unsafe_allow_html=True)
            datos = {
                "Dominio": fila["dominio"] or "-",
                "Tienda": fila["tienda"] or "-",
                "Plan": fila["plan"] or "-",
                "App del token": fila["app"] or "-",
                "Function": fila["funcion_handle"] or "-",
                "Function ID": fila["funcion_id"] or "-",
                "Permisos": ", ".join(fila["scopes"]) or "-",
            }
            st.table(pd.DataFrame([datos]).T.rename(columns={0: "Valor"}))
            for detalle in fila["detalles"]:
                st.warning(detalle)
            if fila["estado"] != ESTADO_LISTO:
                st.caption("Secrets sugeridos para esta tienda:")
                st.code(fila["secrets_sugeridos"], language="toml")


def pestana_simulador() -> None:
    st.caption(
        "Trae productos reales de la tienda y muestra como quedaria el precio con el cupon. "
        "Necesita el permiso `read_products` en la app."
    )
    columnas = st.columns([2, 1, 1])
    sitios = sitios_activos()
    nombres = {sitio["name"]: sitio["shop_key"] for sitio in sitios}
    nombre = columnas[0].selectbox("Tienda", list(nombres.keys()))
    porcentaje = columnas[1].number_input("Descuento %", min_value=1.0, max_value=100.0, value=40.0, step=5.0)
    cantidad = columnas[2].number_input("Productos", min_value=1, max_value=50, value=10, step=5)

    if not st.button("Simular con productos reales", type="primary"):
        return

    shop_key = nombres[nombre]
    config = obtener_config(shop_key)
    problema = falta_config(config)
    if problema:
        st.error(problema)
        return

    try:
        datos = crear_graphql(config)(QUERY_PRODUCTOS, {"first": int(cantidad)})
    except Exception as exc:
        mensaje = str(exc)
        if "read_products" in mensaje or "403" in mensaje or "access denied" in mensaje.lower():
            st.error(
                "A la app le falta el permiso `read_products`. Pidelo a quien administra la app "
                "y vuelve a instalarla; sin eso no puedo leer precios reales."
            )
        else:
            st.error(mensaje)
        return

    filas = []
    for producto in (datos.get("products") or {}).get("nodes") or []:
        for variante in (producto.get("variants") or {}).get("nodes") or []:
            resultado = best_wins_line_result(
                variante.get("price"),
                variante.get("compareAtPrice"),
                porcentaje,
            )
            filas.append(
                {
                    "Producto": producto.get("title", ""),
                    "SKU": variante.get("sku", ""),
                    "Compare At": "" if resultado.compare_at_price is None else float(resultado.compare_at_price),
                    "Price actual": float(resultado.current_price),
                    "Precio con cupon": float(resultado.final_price),
                    "Ahorro extra": float(resultado.unit_discount),
                    "Estado": resultado.status,
                }
            )

    if not filas:
        st.warning("La tienda no devolvio productos activos.")
        return

    tabla = pd.DataFrame(filas)
    metricas = st.columns(3)
    metricas[0].metric("Variantes simuladas", len(tabla))
    metricas[1].metric("Gana el cupon", int((tabla["Estado"] == "Gana cupon").sum()))
    metricas[2].metric("Gana la promocion vigente", int((tabla["Estado"] == "Gana promocion actual").sum()))
    st.dataframe(tabla, hide_index=True, **ANCHO)
    st.caption(
        "`Ahorro extra` es lo que descuenta la Function sobre el precio vigente. "
        "Cuando la promocion actual ya es mejor que el cupon, el ahorro extra es 0 y el precio no se toca."
    )


def pestana_codigos() -> None:
    st.caption("Revisa en que tiendas ya existe un codigo, para no chocar al crearlo.")
    codigo = st.text_input("Codigo del cupon", placeholder="BCP30").strip().upper()
    if not st.button("Buscar en todas las tiendas", type="primary") or not codigo:
        return

    filas = []
    for sitio in sitios_activos():
        config = obtener_config(sitio["shop_key"])
        problema = falta_config(config)
        if problema:
            filas.append({"Sitio": sitio["name"], "Existe": "-", "Detalle": problema})
            continue
        graphql = crear_graphql(config)
        try:
            try:
                datos = graphql(QUERY_CODIGO, {"code": codigo})
            except Exception:
                datos = graphql(QUERY_CODIGO_SIMPLE, {"code": codigo})
            nodo = datos.get("codeDiscountNodeByCode")
            if not nodo:
                filas.append({"Sitio": sitio["name"], "Existe": "No", "Detalle": "Codigo libre"})
                continue
            descuento = nodo.get("codeDiscount") or {}
            detalle = str(descuento.get("title", "")) or str(descuento.get("__typename", ""))
            estado = str(descuento.get("status", ""))
            filas.append(
                {
                    "Sitio": sitio["name"],
                    "Existe": "Si",
                    "Detalle": (detalle + " " + estado).strip(),
                }
            )
        except Exception as exc:
            filas.append({"Sitio": sitio["name"], "Existe": "?", "Detalle": str(exc)[:120]})

    tabla = pd.DataFrame(filas)
    ocupados = int((tabla["Existe"] == "Si").sum())
    if ocupados:
        st.warning("El codigo " + codigo + " ya existe en " + str(ocupados) + " tienda(s).")
    else:
        st.success("El codigo " + codigo + " esta libre en todas las tiendas revisadas.")
    st.dataframe(tabla, hide_index=True, **ANCHO)


def main() -> None:
    if not st.session_state.get("authenticated"):
        st.title("Centro de Control")
        st.warning("Inicia sesion en la pantalla principal para entrar aqui.")
        st.stop()

    st.title("Centro de Control multitienda")
    st.caption(
        "Estado real de las "
        + str(len(sitios_activos()))
        + " tiendas Shopify. Todo lo de esta pagina es de solo lectura."
    )

    estado, simulador, codigos = st.tabs(["Estado de tiendas", "Simulador Best Wins", "Verificar codigo"])
    with estado:
        pestana_estado()
    with simulador:
        pestana_simulador()
    with codigos:
        pestana_codigos()


main()
