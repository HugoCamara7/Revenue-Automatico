"""Descuentos promocionales: subir un archivo y cambiar precios reales del catalogo.

A diferencia de los cupones, esto escribe en el producto: el cliente ve el precio
tachado navegando la web. Por eso todo pasa por tres etapas separadas:

    1. Subis el archivo  ->  2. Revisas el plan  ->  3. Aplicas (con confirmacion)

El plan aplicado se descarga en Excel: ese archivo es el que permite revertir la
campana despues, porque guarda el precio de lista de cada variante.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coupon_config import COUPON_SHOPIFY_SITES  # noqa: E402
from promociones import (  # noqa: E402
    APLICA,
    armar_plan,
    leer_reglas,
    payload_actualizacion,
    payload_reversion,
    resumen_plan,
)
from ui_kit import (  # noqa: E402
    ancho,
    aviso,
    encabezado,
    imagen_data_uri,
    inject_css,
    seccion,
)

st.set_page_config(page_title="Promociones", layout="wide", initial_sidebar_state="expanded")
inject_css()

TAMANO_LOTE = 40

QUERY_VARIANTES = """
query VariantesPorSku($first: Int!, $query: String!) {
  productVariants(first: $first, query: $query) {
    nodes {
      id
      sku
      displayName
      price
      compareAtPrice
      product { id title }
    }
  }
}
"""

MUTACION_PRECIOS = """
mutation ActualizarPrecios($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id price compareAtPrice }
    userErrors { field message }
  }
}
"""


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
    except Exception:
        return {}
    return {}


def crear_graphql(config: dict, timeout: int = 60):
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


def tiendas_configuradas() -> list[dict]:
    listas = []
    for sitio in COUPON_SHOPIFY_SITES:
        if not sitio.get("enabled", True):
            continue
        config = obtener_config(sitio["shop_key"])
        token = str(config.get("access_token") or config.get("admin_access_token") or "").strip()
        if str(config.get("shop_domain", "")).strip() and token:
            listas.append(sitio)
    return listas


def buscar_variantes(graphql, identificadores: list[str]) -> dict[str, dict]:
    """Busca las variantes por SKU, en lotes para no armar una query gigante."""
    encontradas: dict[str, dict] = {}
    barra = st.progress(0.0, text="Buscando productos en la tienda...")
    lotes = [identificadores[i:i + TAMANO_LOTE] for i in range(0, len(identificadores), TAMANO_LOTE)]
    for indice, lote in enumerate(lotes):
        consulta = " OR ".join("sku:" + sku for sku in lote)
        barra.progress((indice + 1) / max(len(lotes), 1), text="Buscando productos... lote " + str(indice + 1))
        try:
            datos = graphql(QUERY_VARIANTES, {"first": 250, "query": consulta})
        except Exception as exc:
            barra.empty()
            raise exc
        for nodo in ((datos or {}).get("productVariants") or {}).get("nodes") or []:
            sku = str(nodo.get("sku") or "").strip().upper()
            if not sku:
                continue
            encontradas[sku] = {
                "id": nodo.get("id", ""),
                "nombre": nodo.get("displayName") or (nodo.get("product") or {}).get("title", ""),
                "price": nodo.get("price"),
                "compare_at": nodo.get("compareAtPrice"),
                "product_id": (nodo.get("product") or {}).get("id", ""),
            }
    barra.empty()
    return encontradas


def excel_bytes(tabla: pd.DataFrame, hoja: str = "Plan") -> bytes:
    memoria = io.BytesIO()
    with pd.ExcelWriter(memoria, engine="openpyxl") as escritor:
        tabla.to_excel(escritor, index=False, sheet_name=hoja)
    return memoria.getvalue()


def aplicar_cambios(graphql, filas: list[dict], revertir: bool = False) -> tuple[int, list[str]]:
    """Escribe los precios en Shopify, agrupando por producto. Devuelve (ok, errores)."""
    grupos: dict[str, list[dict]] = {}
    for fila in filas:
        grupos.setdefault(fila.get("_product_id", ""), []).append(fila)

    correctas = 0
    errores = []
    barra = st.progress(0.0, text="Actualizando precios...")
    for indice, (producto, variantes) in enumerate(grupos.items()):
        barra.progress((indice + 1) / max(len(grupos), 1), text="Actualizando " + str(indice + 1) + " de " + str(len(grupos)))
        if not producto:
            errores.append("Fila sin producto asociado, se omitio.")
            continue
        entradas = [
            payload_reversion(fila) if revertir else payload_actualizacion(fila) for fila in variantes
        ]
        try:
            datos = graphql(MUTACION_PRECIOS, {"productId": producto, "variants": entradas})
        except Exception as exc:
            errores.append(str(exc)[:160])
            continue
        resultado = (datos or {}).get("productVariantsBulkUpdate") or {}
        fallos = resultado.get("userErrors") or []
        if fallos:
            errores.append("; ".join(str(error.get("message", "")) for error in fallos)[:160])
            continue
        correctas += len(entradas)
    barra.empty()
    return correctas, errores


def render_sidebar() -> None:
    logo_src = imagen_data_uri("forus_logo.png")
    marca = (
        '<div class="brand-logo"><img src="' + logo_src + '" alt="FORUS"></div>'
        if logo_src
        else '<div class="brand-icon">R</div>'
    )
    st.sidebar.markdown(
        '<div class="brand-card">' + marca
        + '<div><div class="brand-nombre">Revenue Control Center</div>'
        '<div class="brand-sub">Cupones y descuentos Shopify</div></div></div>',
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown('<div class="sidebar-label">Navegacion</div>', unsafe_allow_html=True)
        if st.button("Volver a la app", icon=":material/arrow_back:", key="promo_volver", **ancho()):
            try:
                st.switch_page("app.py")
            except Exception:
                st.warning("Abre la app principal desde el menu.")
        st.button("Promociones", icon=":material/sell:", type="primary", disabled=True, **ancho())


def main() -> None:
    render_sidebar()

    if not st.session_state.get("authenticated"):
        encabezado("Promociones", "Descuentos que cambian el precio del catalogo.")
        aviso("Inicia sesion en la pantalla principal para entrar aqui.", "error")
        st.stop()

    encabezado(
        "Descuentos promocionales",
        "Subis un archivo con IDs y reglas, y la app cambia el precio real en la tienda. "
        "El cliente ve el precio tachado en la ficha.",
        chip="Precios",
        hero=True,
    )

    sitios = tiendas_configuradas()
    if not sitios:
        aviso("Ninguna tienda tiene shop_domain y admin_access_token en Secrets.", "error")
        st.stop()

    # ---------------------------------------------------------------- paso 1
    seccion("1", "Tienda y archivo", "Una columna con el SKU y al menos una columna de regla.")
    tienda_col, archivo_col = st.columns([1, 2])
    with tienda_col:
        nombres = {sitio["name"]: sitio["shop_key"] for sitio in sitios}
        nombre_tienda = st.selectbox("Tienda", list(nombres))
        shop_key = nombres[nombre_tienda]
    with archivo_col:
        archivo = st.file_uploader("Archivo de promocion", type=["xlsx", "xlsm", "csv"], key="promo_archivo")

    with st.expander("Que columnas puede tener el archivo"):
        st.dataframe(
            pd.DataFrame(
                [
                    {"Columna": "SKU o ID", "Obligatoria": "Si", "Ejemplo": "ABC123-001"},
                    {"Columna": "Descuento %", "Obligatoria": "No", "Ejemplo": "40"},
                    {"Columna": "Precio objetivo", "Obligatoria": "No", "Ejemplo": "199"},
                    {"Columna": "Tope maximo", "Obligatoria": "No", "Ejemplo": "299"},
                    {"Columna": "Piso minimo", "Obligatoria": "No", "Ejemplo": "99"},
                ]
            ),
            hide_index=True,
            **ancho(),
        )
        st.caption(
            "El porcentaje se calcula SIEMPRE sobre el Compare At Price. Si el producto no tiene, "
            "se usa el precio vigente. Si el resultado queda mas caro que el precio actual, esa fila no se toca."
        )

    if not archivo:
        aviso("Suba un archivo para ver el plan.")
        st.stop()

    try:
        tabla = pd.read_csv(archivo) if archivo.name.lower().endswith(".csv") else pd.read_excel(archivo)
    except Exception as exc:
        aviso("No pude leer el archivo: " + str(exc)[:200], "error")
        st.stop()

    reglas, avisos_lectura = leer_reglas(tabla)
    for mensaje in avisos_lectura[:5]:
        aviso(mensaje, "error" if not reglas else "info")
    if not reglas:
        st.stop()

    # ---------------------------------------------------------------- paso 2
    st.write("")
    seccion("2", "Plan de cambios", str(len(reglas)) + " fila(s) en el archivo. Nada se aplica todavia.")

    if st.button("Calcular plan", type="primary", icon=":material/calculate:"):
        try:
            variantes = buscar_variantes(crear_graphql(obtener_config(shop_key)), [r["identificador"] for r in reglas])
        except Exception as exc:
            mensaje = str(exc)
            if "read_products" in mensaje or "403" in mensaje:
                aviso("A la app le falta el permiso <code>read_products</code> en esta tienda.", "error")
            else:
                aviso("No pude leer el catalogo: " + mensaje[:200], "error")
            st.stop()
        plan = armar_plan(reglas, variantes)
        for fila in plan:
            clave = str(fila["Identificador"]).strip().upper()
            if clave in variantes:
                fila["_product_id"] = variantes[clave].get("product_id", "")
        st.session_state["promo_plan"] = plan
        st.session_state["promo_tienda"] = nombre_tienda

    plan = st.session_state.get("promo_plan")
    if not plan or st.session_state.get("promo_tienda") != nombre_tienda:
        aviso("Toca <b>Calcular plan</b> para cruzar el archivo con los precios reales de la tienda.")
        st.stop()

    resumen = resumen_plan(plan)
    columnas = st.columns(4)
    tarjetas = [
        ("Cambian de precio", str(resumen["aplican"]), "#0f9d58", "#e8f6ee"),
        ("Sin cambio", str(resumen["sin_cambio"]), "#b45309", "#fdf4e3"),
        ("No encontrados", str(resumen["no_encontrados"]), "#d93025", "#fdecea"),
        ("Descuento promedio", str(resumen["ahorro_promedio"]) + "%", "#1e5eff", "#eaf0ff"),
    ]
    for columna, (titulo, valor, color, fondo) in zip(columnas, tarjetas):
        columna.markdown(
            '<div style="background:' + fondo + ";border-left:5px solid " + color + ";"
            'border-radius:14px;padding:15px 18px;">'
            '<div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
            'font-weight:700;color:#64748b;">' + titulo + "</div>"
            '<div style="font-size:31px;font-weight:800;color:' + color + ';line-height:1.15;">' + valor + "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    visible = pd.DataFrame([{k: v for k, v in fila.items() if not k.startswith("_")} for fila in plan])
    st.dataframe(visible, hide_index=True, **ancho())
    st.download_button(
        "Descargar plan",
        data=excel_bytes(visible),
        file_name="plan_promocion.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
    )

    # ---------------------------------------------------------------- paso 3
    aplicables = [fila for fila in plan if fila.get("Estado") == APLICA and fila.get("_variant_id")]
    if not aplicables:
        aviso("Ninguna fila cambia de precio con este archivo.", "error")
        st.stop()

    st.write("")
    seccion(
        "3",
        "Aplicar en la tienda",
        "Esto escribe el precio en " + nombre_tienda + " y se ve en la web al instante.",
    )
    aviso(
        "Descarga el plan antes de aplicar: es el archivo que permite revertir la campana, "
        "porque guarda el precio de lista de cada variante."
    )
    confirmado = st.checkbox(
        "Confirmo cambiar el precio de " + str(len(aplicables)) + " variante(s) en " + nombre_tienda,
        key="promo_confirmar",
    )
    accion_col, revertir_col = st.columns(2)
    if accion_col.button("Aplicar precios", type="primary", disabled=not confirmado, **ancho()):
        correctas, errores = aplicar_cambios(crear_graphql(obtener_config(shop_key)), aplicables)
        if errores:
            aviso(str(len(errores)) + " error(es): " + " | ".join(errores[:3]), "error")
        if correctas:
            st.success(str(correctas) + " variante(s) actualizadas en " + nombre_tienda + ".")
            st.balloons()
    if revertir_col.button("Revertir a precio de lista", disabled=not confirmado, **ancho()):
        correctas, errores = aplicar_cambios(crear_graphql(obtener_config(shop_key)), aplicables, revertir=True)
        if errores:
            aviso(str(len(errores)) + " error(es): " + " | ".join(errores[:3]), "error")
        if correctas:
            st.success(str(correctas) + " variante(s) volvieron al precio de lista.")


main()
