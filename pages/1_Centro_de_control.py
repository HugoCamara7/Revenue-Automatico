"""Centro de Control multitienda.

Pagina de Streamlit dentro de `pages/`: la app la detecta sola y no toca `app.py`.

Tres pestanas:

1. Estado de tiendas: una tarjeta por tienda con token, permisos y Function.
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
    recomendar_tokens,
    resumen_por_estado,
)
from ui_kit import (  # noqa: E402
    ancho,
    aviso,
    encabezado,
    imagen_data_uri,
    inject_css,
    seccion,
)

st.set_page_config(
    page_title="Centro de Control",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

TONO_ESTADO = {
    ESTADO_LISTO: "green",
    ESTADO_SOLO_BASICO: "orange",
    ESTADO_SIN_CONFIG: "muted",
    ESTADO_ERROR: "red",
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


def falta_config(config: dict) -> str:
    """Devuelve que falta en Secrets, o cadena vacia si esta completo."""
    faltantes = []
    if not str(config.get("shop_domain", "")).strip():
        faltantes.append("shop_domain")
    if not str(config.get("access_token") or config.get("admin_access_token") or "").strip():
        faltantes.append("admin_access_token")
    return "Falta " + " y ".join(faltantes) + " en Secrets." if faltantes else ""


def obtener_config(shop_key: str) -> dict:
    def como_dict(valor) -> dict:
        if not valor:
            return {}
        try:
            return dict(valor)
        except Exception:
            return {}

    try:
        for seccion_secrets in ("shopify_sites", "shopify"):
            bloque = como_dict(st.secrets.get(seccion_secrets, {}))
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


def render_sidebar() -> None:
    logo_src = imagen_data_uri("forus_logo.png")
    marca = (
        '<div class="brand-logo"><img src="' + logo_src + '" alt="FORUS"></div>'
        if logo_src
        else '<div class="brand-icon">R</div>'
    )
    st.sidebar.markdown(
        '<div class="brand-card">'
        + marca
        + '<div><div class="brand-nombre">Revenue Control Center</div>'
        '<div class="brand-sub">Cupones y descuentos Shopify</div></div></div>',
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown('<div class="sidebar-label">Navegacion</div>', unsafe_allow_html=True)
        if st.button("Volver a la app", icon=":material/arrow_back:", key="volver_app", **ancho()):
            try:
                st.switch_page("app.py")
            except Exception:
                st.warning("Abre la app principal desde el menu.")
        st.button("Centro de Control", icon=":material/monitoring:", type="primary", disabled=True, **ancho())

        correo = str(st.session_state.get("user_email", "")).strip()
        if correo:
            nombre = correo.split("@")[0].replace(".", " ").replace("_", " ").title()
            partes = [parte for parte in nombre.split() if parte]
            iniciales = "".join(parte[0] for parte in partes[:2]).upper() or "US"
            st.markdown(
                '<div class="nav-card user-card">'
                '<div class="user-avatar">' + iniciales + "</div>"
                '<div><div class="user-rol">Administrador</div>'
                '<div class="user-nombre">' + nombre + "</div>"
                '<div class="user-mail">' + correo + "</div></div></div>",
                unsafe_allow_html=True,
            )


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
        '<div style="background:' + fondo + ";border-left:5px solid " + color + ";"
        'border-radius:14px;padding:15px 18px;">'
        '<div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
        'font-weight:700;color:#64748b;">' + titulo + "</div>"
        '<div style="font-size:31px;font-weight:800;color:' + color + ';line-height:1.15;">' + valor + "</div>"
        "</div>"
    )


def tarjeta_tienda(fila: dict) -> str:
    estado = fila.get("estado", ESTADO_ERROR)
    datos = [
        ("Dominio", fila.get("dominio") or "-"),
        ("App del token", fila.get("app") or "-"),
        ("Plan", fila.get("plan") or "-"),
        ("Function", fila.get("funcion_handle") or "-"),
        ("Token", fila.get("token") or "-"),
        ("write_discounts", "-" if not fila.get("scopes") else ("No" if fila.get("scopes_faltantes") else "Si")),
    ]
    lineas = "".join(
        '<div class="dato-linea"><span class="dato-tag">' + etiqueta + "</span>"
        '<span class="dato-valor">' + str(valor) + "</span></div>"
        for etiqueta, valor in datos
    )
    detalle = ""
    if fila.get("detalles"):
        detalle = '<div class="tienda-detalle">' + "<br>".join(fila["detalles"]) + "</div>"
    return (
        '<div class="tienda-card ' + estado + '">'
        '<div class="tienda-head">'
        '<div class="tienda-nombre">' + fila.get("sitio", "") + "</div>"
        '<span class="pill ' + TONO_ESTADO.get(estado, "muted") + '">'
        + ETIQUETA_ESTADO.get(estado, estado)
        + "</span>"
        "</div>"
        '<div class="tienda-datos">' + lineas + "</div>"
        + detalle
        + "</div>"
    )


def pestana_estado() -> None:
    izquierda, derecha = st.columns([3, 1])
    with izquierda:
        handle = st.text_input(
            "Handle esperado de la Function",
            value=FUNCTION_HANDLE_POR_DEFECTO,
            help="Si no lo sabes, dejalo vacio: se resuelve con el client_id de Secrets.",
        )
    with derecha:
        st.write("")
        st.write("")
        revisar = st.button("Revisar tiendas", type="primary", icon=":material/refresh:", **ancho())

    if revisar:
        st.session_state["panel_resultados"] = revisar_tiendas(handle.strip())

    resultados = st.session_state.get("panel_resultados")
    if not resultados:
        aviso("Toca <b>Revisar tiendas</b> para leer el estado real de cada tienda en Shopify.")
        return

    resumen = resumen_por_estado(resultados)
    columnas = st.columns(4)
    tarjetas = [
        ("Listas para Best Wins", resumen[ESTADO_LISTO], "#0f9d58", "#e8f6ee"),
        ("Solo precio actual", resumen[ESTADO_SOLO_BASICO], "#b45309", "#fdf4e3"),
        ("Sin configurar", resumen[ESTADO_SIN_CONFIG], "#64748b", "#f1f5f9"),
        ("Con error", resumen[ESTADO_ERROR], "#d93025", "#fdecea"),
    ]
    for columna, (titulo, valor, color, fondo) in zip(columnas, tarjetas):
        columna.markdown(tarjeta_metrica(titulo, str(valor), color, fondo), unsafe_allow_html=True)

    recomendaciones = recomendar_tokens(resultados)
    if recomendaciones:
        aviso("<b>Que token dejar en admin_access_token:</b><br>" + "<br>".join(recomendaciones))

    st.write("")
    tarjetas_html = "".join(tarjeta_tienda(fila) for fila in resultados)
    st.markdown('<div class="tienda-grid">' + tarjetas_html + "</div>", unsafe_allow_html=True)

    pendientes = [fila for fila in resultados if fila["estado"] != ESTADO_LISTO]
    if pendientes:
        with st.expander("Secrets sugeridos para las tiendas pendientes"):
            for fila in pendientes:
                st.caption(fila["sitio"])
                st.code(fila["secrets_sugeridos"], language="toml")


def pestana_simulador() -> None:
    seccion(
        "S",
        "Simulador Best Wins",
        "Trae productos reales de la tienda y calcula como quedaria el precio con el cupon. Necesita read_products.",
    )
    columnas = st.columns([2, 1, 1])
    sitios = sitios_activos()
    nombres = {sitio["name"]: sitio["shop_key"] for sitio in sitios}
    nombre = columnas[0].selectbox("Tienda", list(nombres.keys()))
    porcentaje = columnas[1].number_input("Descuento %", min_value=1.0, max_value=100.0, value=40.0, step=5.0)
    cantidad = columnas[2].number_input("Productos", min_value=1, max_value=50, value=10, step=5)

    if not st.button("Simular con productos reales", type="primary", icon=":material/play_arrow:"):
        return

    config = obtener_config(nombres[nombre])
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
            resultado = best_wins_line_result(variante.get("price"), variante.get("compareAtPrice"), porcentaje)
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
    st.dataframe(tabla, hide_index=True, **ancho())
    st.caption(
        "`Ahorro extra` es lo que descuenta la Function sobre el precio vigente. Cuando la promocion actual "
        "ya es mejor que el cupon, el ahorro extra es 0 y el precio no se toca."
    )


def pestana_codigos() -> None:
    seccion("V", "Verificar codigo", "Revisa en que tiendas ya existe un codigo, para no chocar al crearlo.")
    columna_codigo, columna_boton = st.columns([3, 1])
    codigo = columna_codigo.text_input("Codigo del cupon", placeholder="BCP30").strip().upper()
    columna_boton.write("")
    columna_boton.write("")
    buscar = columna_boton.button("Buscar", type="primary", icon=":material/search:", **ancho())
    if not buscar or not codigo:
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
            filas.append(
                {
                    "Sitio": sitio["name"],
                    "Existe": "Si",
                    "Detalle": (detalle + " " + str(descuento.get("status", ""))).strip(),
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
    st.dataframe(tabla, hide_index=True, **ancho())


def main() -> None:
    render_sidebar()

    if not st.session_state.get("authenticated"):
        encabezado("Centro de Control", "Estado real de las tiendas Shopify.")
        aviso("Inicia sesion en la pantalla principal para entrar aqui.", "error")
        st.stop()

    encabezado(
        "Centro de Control multitienda",
        "Estado real de las " + str(len(sitios_activos())) + " tiendas Shopify. Todo aqui es de solo lectura.",
        chip="Diagnostico",
        hero=True,
    )

    estado, simulador, codigos = st.tabs(["Estado de tiendas", "Simulador Best Wins", "Verificar codigo"])
    with estado:
        pestana_estado()
    with simulador:
        pestana_simulador()
    with codigos:
        pestana_codigos()


main()
