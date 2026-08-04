"""Auditoria de cupones.

Que cupones existen en cada tienda, en que estado, cuantas veces se usaron y quien
los creo desde esta app. Permite pausar (desactivar) o reactivar un cupon.

La lectura es directa de Shopify, asi que sirve aunque el cupon se haya creado a mano
desde el Admin. El registro local solo agrega el dato que Shopify no guarda: el usuario
interno que lo genero desde aqui.
"""

from __future__ import annotations

import io
import json
from datetime import date, time
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auditoria import (  # noqa: E402
    QUERY_CUPONES,
    QUERY_CUPONES_SIMPLE,
    actualizar_cupon,
    aplanar_cupones,
    cambiar_estado_cupon,
    filtrar_cupones,
    leer_detalle,
    leer_registro,
    resumen_cupones,
)
from coupon_config import COUPON_SHOPIFY_SITES  # noqa: E402
from ui_kit import (  # noqa: E402
    ancho,
    aviso,
    encabezado,
    imagen_data_uri,
    inject_css,
    seccion,
)

st.set_page_config(
    page_title="Auditoria de cupones",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()


QUERY_POR_CODIGO = """
query CuponPorCodigo($code: String!) {
  codeDiscountNodeByCode(code: $code) {
    id
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


def tiendas_configuradas() -> list[dict]:
    listas = []
    for sitio in COUPON_SHOPIFY_SITES:
        if not sitio.get("enabled", True):
            continue
        config = obtener_config(sitio["shop_key"])
        dominio = str(config.get("shop_domain", "")).strip()
        token = str(config.get("access_token") or config.get("admin_access_token") or "").strip()
        if dominio and token:
            listas.append(sitio)
    return listas


def excel_bytes(tabla: pd.DataFrame) -> bytes:
    memoria = io.BytesIO()
    with pd.ExcelWriter(memoria, engine="openpyxl") as escritor:
        tabla.to_excel(escritor, index=False, sheet_name="Auditoria")
    return memoria.getvalue()


def traer_cupones(sitios: list[dict], cantidad: int) -> tuple[list[dict], list[str]]:
    filas = []
    problemas = []
    barra = st.progress(0.0, text="Leyendo cupones...")
    for indice, sitio in enumerate(sitios):
        barra.progress((indice + 1) / max(len(sitios), 1), text="Leyendo " + sitio["name"] + "...")
        graphql = crear_graphql(obtener_config(sitio["shop_key"]))
        try:
            try:
                datos = graphql(QUERY_CUPONES, {"first": int(cantidad)})
            except Exception:
                datos = graphql(QUERY_CUPONES_SIMPLE, {"first": int(cantidad)})
            nodos = (datos.get("codeDiscountNodes") or {}).get("nodes") or []
            filas.extend(aplanar_cupones(nodos, sitio["name"]))
        except Exception as exc:
            problemas.append(sitio["name"] + ": " + str(exc)[:160])
    barra.empty()
    return filas, problemas


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
        if st.button("Volver a la app", icon=":material/arrow_back:", key="aud_volver", **ancho()):
            try:
                st.switch_page("app.py")
            except Exception:
                st.warning("Abre la app principal desde el menu.")
        if st.button("Centro de Control", icon=":material/monitoring:", key="aud_centro", **ancho()):
            try:
                st.switch_page("pages/1_Centro_de_control.py")
            except Exception:
                st.warning("Falta la pagina del Centro de Control.")
        st.button("Auditoria", icon=":material/fact_check:", type="primary", disabled=True, **ancho())


def pestana_shopify() -> None:
    sitios = tiendas_configuradas()
    if not sitios:
        aviso("Ninguna tienda tiene shop_domain y admin_access_token en Secrets.", "error")
        return

    filtros = st.columns([2, 1, 1])
    nombres = [sitio["name"] for sitio in sitios]
    elegidas = filtros[0].multiselect("Tiendas", nombres, default=nombres)
    cantidad = filtros[1].number_input("Cupones por tienda", min_value=10, max_value=250, value=50, step=10)
    filtros[2].write("")
    filtros[2].write("")
    consultar = filtros[2].button("Consultar", type="primary", icon=":material/refresh:", **ancho())

    if consultar:
        seleccion = [sitio for sitio in sitios if sitio["name"] in elegidas]
        filas, problemas = traer_cupones(seleccion, cantidad)
        st.session_state["auditoria_filas"] = filas
        st.session_state["auditoria_problemas"] = problemas

    filas = st.session_state.get("auditoria_filas")
    if not filas:
        aviso("Toca <b>Consultar</b> para traer los cupones que existen hoy en Shopify.")
        return

    for problema in st.session_state.get("auditoria_problemas", []):
        aviso(problema, "error")

    resumen = resumen_cupones(filas)
    columnas = st.columns(4)
    tarjetas = [
        ("Cupones", str(resumen["total"]), "#1e5eff", "#eaf0ff"),
        ("Activos", str(resumen["activos"]), "#0f9d58", "#e8f6ee"),
        ("Programados", str(resumen["programados"]), "#b45309", "#fdf4e3"),
        ("Usos acumulados", str(resumen["usos"]), "#16243d", "#f1f5f9"),
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
    busqueda_col, estado_col = st.columns([2, 1])
    texto = busqueda_col.text_input("Buscar por codigo o titulo", placeholder="BCP30")
    estado = estado_col.selectbox("Estado", ["Todos", "Activo", "Programado", "Expirado"])
    visibles = filtrar_cupones(filas, estado, texto)

    tabla = pd.DataFrame(visibles)
    st.caption(str(len(visibles)) + " de " + str(len(filas)) + " cupones")
    st.dataframe(tabla.drop(columns=["ID"]) if "ID" in tabla else tabla, hide_index=True, **ancho())

    st.download_button(
        "Descargar auditoria",
        data=excel_bytes(tabla),
        file_name="auditoria_cupones.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
    )

    st.write("")
    seccion(
        "A",
        "Editar, pausar o reactivar",
        "Los cambios se aplican en Shopify sobre el cupon ya creado. Nada se borra y todo es reversible.",
    )
    if not visibles:
        return

    opciones = {
        fila["Sitio"] + "  ·  " + fila["Codigo"] + "  ·  " + fila["Estado"]: fila
        for fila in visibles
        if fila.get("ID")
    }
    if not opciones:
        aviso("Los cupones listados no traen ID; no puedo modificarlos.")
        return

    elegido_col, cargar_col = st.columns([3, 1])
    etiqueta = elegido_col.selectbox("Cupon", list(opciones))
    fila = opciones[etiqueta]
    cargar_col.write("")
    cargar_col.write("")
    if cargar_col.button("Cargar datos", icon=":material/edit:", **ancho()):
        sitio = next((s for s in sitios if s["name"] == fila["Sitio"]), None)
        if sitio:
            graphql = crear_graphql(obtener_config(sitio["shop_key"]))
            st.session_state["auditoria_detalle"] = leer_detalle(graphql, fila["ID"])
            st.session_state["auditoria_detalle_sitio"] = fila["Sitio"]

    detalle = st.session_state.get("auditoria_detalle")
    if not detalle or st.session_state.get("auditoria_detalle_sitio") != fila["Sitio"] or detalle.get("id") != fila["ID"]:
        aviso("Elige un cupon y toca <b>Cargar datos</b> para editarlo.")
        render_pausa(fila, sitios)
        return

    es_function = detalle.get("tipo") == "DiscountCodeApp"
    st.caption(
        "Editando "
        + ", ".join(detalle.get("codigos") or ["-"])
        + " en "
        + fila["Sitio"]
        + ("  ·  Function Best Wins" if es_function else "  ·  Cupon nativo")
    )

    campo_izq, campo_der = st.columns(2)
    with campo_izq:
        titulo = st.text_input("Titulo interno", value=detalle.get("titulo", ""), key="edit_titulo")
        porcentaje = st.number_input(
            "Descuento %",
            min_value=0.0,
            max_value=100.0,
            value=float(detalle.get("porcentaje") or 0),
            step=1.0,
            key="edit_porcentaje",
        )
        compra_minima = st.number_input(
            "Compra minima (S/)",
            min_value=0.0,
            value=float(detalle.get("compra_minima") or 0),
            step=10.0,
            key="edit_minimo",
        )
    with campo_der:
        limite = st.number_input(
            "Limite total de usos",
            min_value=0,
            value=int(detalle.get("limite_usos") or 0),
            step=1,
            help="0 = sin limite.",
            key="edit_limite",
        )
        una_vez = st.checkbox(
            "Un solo uso por cliente",
            value=bool(detalle.get("una_vez_por_cliente")),
            key="edit_una_vez",
        )

    st.markdown('<div class="rango-tag">Vigencia</div>', unsafe_allow_html=True)
    inicio_dia, inicio_hora, fin_dia, fin_hora = st.columns(4)
    fecha_i, hora_i = partir_iso(detalle.get("inicio"), time(0, 0))
    fecha_f, hora_f = partir_iso(detalle.get("fin"), time(23, 59))
    nueva_fecha_i = inicio_dia.date_input("Dia inicio", value=fecha_i, format="DD/MM/YYYY", key="edit_fecha_i")
    nueva_hora_i = inicio_hora.time_input("Hora inicio", value=hora_i, step=300, key="edit_hora_i")
    nueva_fecha_f = fin_dia.date_input("Dia fin", value=fecha_f, format="DD/MM/YYYY", min_value=nueva_fecha_i, key="edit_fecha_f")
    nueva_hora_f = fin_hora.time_input("Hora fin", value=hora_f, step=300, key="edit_hora_f")

    if es_function and compra_minima > 0:
        aviso(
            "En un cupon Best Wins la compra minima la evalua la Function desde el metafield "
            "(<code>minimum_subtotal</code>), no Shopify. Confirma que la Function la implementa.",
            "error",
        )

    cambios = {
        "titulo": titulo,
        "inicio": armar_iso(nueva_fecha_i, nueva_hora_i),
        "fin": armar_iso(nueva_fecha_f, nueva_hora_f),
        "limite_usos": limite,
        "una_vez_por_cliente": una_vez,
        "porcentaje": porcentaje,
        "compra_minima": compra_minima,
    }

    todas = st.checkbox(
        "Aplicar el mismo cambio en todas las tiendas donde exista el codigo "
        + ", ".join(detalle.get("codigos") or []),
        key="edit_todas",
    )
    confirmar = st.checkbox("Confirmo que quiero guardar estos cambios en Shopify", key="edit_confirmar")
    if st.button("Guardar cambios", type="primary", disabled=not confirmar, icon=":material/save:"):
        guardar_cambios(fila, sitios, detalle, cambios, todas)

    st.write("")
    render_pausa(fila, sitios)


def partir_iso(valor, hora_defecto):
    """Separa '2026-08-10T00:00:00-05:00' en (date, time)."""
    texto_valor = str(valor or "")
    try:
        fecha = date.fromisoformat(texto_valor[:10])
    except Exception:
        fecha = date.today()
    try:
        hora = time(int(texto_valor[11:13]), int(texto_valor[14:16]))
    except Exception:
        hora = hora_defecto
    return fecha, hora


def armar_iso(fecha, hora) -> str:
    return fecha.isoformat() + "T" + hora.strftime("%H:%M") + ":00-05:00"


def guardar_cambios(fila: dict, sitios: list[dict], detalle: dict, cambios: dict, todas: bool) -> None:
    objetivos = []
    if todas:
        codigos = [codigo for codigo in (detalle.get("codigos") or []) if codigo]
        for sitio in sitios:
            objetivos.append((sitio, codigos[0] if codigos else fila["Codigo"]))
    else:
        sitio = next((s for s in sitios if s["name"] == fila["Sitio"]), None)
        if sitio:
            objetivos.append((sitio, None))

    resultados = []
    for sitio, codigo in objetivos:
        graphql = crear_graphql(obtener_config(sitio["shop_key"]))
        if codigo is None:
            detalle_sitio = detalle
        else:
            try:
                datos = graphql(QUERY_POR_CODIGO, {"code": codigo})
                nodo = (datos or {}).get("codeDiscountNodeByCode")
                if not nodo:
                    resultados.append({"Sitio": sitio["name"], "Resultado": "El codigo no existe en esta tienda"})
                    continue
                detalle_sitio = leer_detalle(graphql, nodo.get("id", ""))
            except Exception as exc:
                resultados.append({"Sitio": sitio["name"], "Resultado": str(exc)[:120]})
                continue
        if not detalle_sitio.get("id"):
            resultados.append({"Sitio": sitio["name"], "Resultado": "No pude leer el cupon"})
            continue
        error = actualizar_cupon(graphql, detalle_sitio, cambios)
        resultados.append({"Sitio": sitio["name"], "Resultado": error or "Actualizado"})

    tabla = pd.DataFrame(resultados)
    fallidos = int((tabla["Resultado"] != "Actualizado").sum()) if not tabla.empty else 0
    if fallidos:
        st.warning("Termino con " + str(fallidos) + " tienda(s) con problema.")
    else:
        st.success("Cambios guardados. Vuelve a consultar para ver los datos actualizados.")
    st.dataframe(tabla, hide_index=True, **ancho())
    st.session_state.pop("auditoria_filas", None)
    st.session_state.pop("auditoria_detalle", None)


def render_pausa(fila: dict, sitios: list[dict]) -> None:
    activar = str(fila.get("Estado", "")).lower() != "activo"
    accion = "Reactivar" if activar else "Pausar"
    confirmado = st.checkbox(
        "Confirmo que quiero " + accion.lower() + " " + str(fila.get("Codigo", "")) + " en " + str(fila.get("Sitio", "")),
        key="auditoria_confirmar",
    )
    if st.button(accion, disabled=not confirmado, icon=":material/pause:"):
        sitio = next((s for s in sitios if s["name"] == fila["Sitio"]), None)
        if not sitio:
            st.error("No encontre la configuracion de esa tienda.")
            return
        graphql = crear_graphql(obtener_config(sitio["shop_key"]))
        error = cambiar_estado_cupon(graphql, fila["ID"], activar)
        if error:
            st.error("No se pudo cambiar el estado: " + error)
        else:
            st.success("Listo. Vuelve a consultar para ver el estado actualizado.")
            st.session_state.pop("auditoria_filas", None)


def pestana_registro() -> None:
    seccion(
        "R",
        "Creados desde esta app",
        "Quien creo cada cupon y cuando. Shopify no guarda el usuario interno, por eso se registra aqui.",
    )
    registro = leer_registro()
    if registro.empty:
        aviso(
            "Todavia no hay registros. Se van escribiendo cada vez que creas cupones desde la app. "
            "En Streamlit Cloud el archivo se pierde al reiniciar el contenedor: descarga el Excel "
            "si necesitas conservarlo."
        )
        return

    columnas = st.columns(3)
    columnas[0].metric("Registros", len(registro))
    columnas[1].metric("Creados OK", int((registro["estado"] == "success").sum()))
    columnas[2].metric("Con problema", int((registro["estado"] != "success").sum()))

    usuarios = ["Todos"] + sorted({usuario for usuario in registro["usuario"].tolist() if usuario})
    usuario = st.selectbox("Usuario", usuarios)
    visible = registro if usuario == "Todos" else registro[registro["usuario"] == usuario]

    st.dataframe(visible.sort_values("fecha_hora", ascending=False), hide_index=True, **ancho())
    st.download_button(
        "Descargar registro",
        data=excel_bytes(visible),
        file_name="registro_creacion_cupones.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
    )


def main() -> None:
    render_sidebar()

    if not st.session_state.get("authenticated"):
        encabezado("Auditoria de cupones", "Historial y estado de los cupones.")
        aviso("Inicia sesion en la pantalla principal para entrar aqui.", "error")
        st.stop()

    encabezado(
        "Auditoria de cupones",
        "Que cupones existen en cada tienda, en que estado y cuantas veces se usaron.",
        chip="Control",
        hero=True,
    )

    shopify_tab, registro_tab = st.tabs(["Cupones en Shopify", "Creados desde la app"])
    with shopify_tab:
        pestana_shopify()
    with registro_tab:
        pestana_registro()


main()
