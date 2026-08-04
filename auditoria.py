"""Auditoria de cupones: registro local de lo creado y lectura de lo que vive en Shopify.

Dos fuentes que se complementan:

1. **Shopify** es la fuente de verdad: que cupones existen hoy, su estado y sus usos.
   Se consulta con `codeDiscountNodes` y no necesita que la app haya guardado nada.
2. **Registro local** (`data/auditoria_cupones.csv`): que se creo desde esta app, cuando
   y quien lo hizo. Shopify no guarda el usuario interno, por eso vale la pena.

Ojo con el registro local: en Streamlit Cloud el disco es efimero y se pierde al
reiniciar el contenedor. Por eso el modulo expone `exportar_registro` para bajarlo
a Excel, y la pantalla de auditoria siempre puede reconstruirse desde Shopify.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

RUTA_REGISTRO = Path("data") / "auditoria_cupones.csv"

COLUMNAS_REGISTRO = [
    "fecha_hora",
    "usuario",
    "sitio",
    "shop_key",
    "codigo",
    "estado",
    "mensaje",
    "discount_id",
    "base_calculo",
    "tipo_descuento",
    "valor",
    "inicio",
    "fin",
]

QUERY_CUPONES = """
query CuponesDeLaTienda($first: Int!) {
  codeDiscountNodes(first: $first, sortKey: CREATED_AT, reverse: true) {
    nodes {
      id
      codeDiscount {
        __typename
        ... on DiscountCodeBasic {
          title
          status
          startsAt
          endsAt
          createdAt
          usageLimit
          asyncUsageCount
          codes(first: 5) { nodes { code } }
        }
        ... on DiscountCodeApp {
          title
          status
          startsAt
          endsAt
          createdAt
          usageLimit
          asyncUsageCount
          codes(first: 5) { nodes { code } }
        }
      }
    }
  }
}
"""

QUERY_CUPONES_SIMPLE = """
query CuponesDeLaTiendaSimple($first: Int!) {
  codeDiscountNodes(first: $first) {
    nodes {
      id
      codeDiscount {
        __typename
        ... on DiscountCodeBasic {
          title
          status
          startsAt
          endsAt
          codes(first: 5) { nodes { code } }
        }
        ... on DiscountCodeApp {
          title
          status
          startsAt
          endsAt
          codes(first: 5) { nodes { code } }
        }
      }
    }
  }
}
"""

MUTACION_DESACTIVAR = """
mutation DesactivarCupon($id: ID!) {
  discountCodeDeactivate(id: $id) {
    codeDiscountNode { id }
    userErrors { field message }
  }
}
"""

MUTACION_ACTIVAR = """
mutation ActivarCupon($id: ID!) {
  discountCodeActivate(id: $id) {
    codeDiscountNode { id }
    userErrors { field message }
  }
}
"""

ETIQUETA_ESTADO_SHOPIFY = {
    "ACTIVE": "Activo",
    "SCHEDULED": "Programado",
    "EXPIRED": "Expirado",
}


def ahora_texto() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def filas_registro(resultados: list[dict], data: dict, usuario: str, momento: str | None = None) -> list[dict]:
    """Convierte el resultado de la creacion en filas de auditoria."""
    momento = momento or ahora_texto()
    filas = []
    for resultado in resultados or []:
        filas.append(
            {
                "fecha_hora": momento,
                "usuario": str(usuario or "").strip(),
                "sitio": resultado.get("siteName", ""),
                "shop_key": resultado.get("siteId", ""),
                "codigo": resultado.get("couponCode", ""),
                "estado": resultado.get("status", ""),
                "mensaje": str(resultado.get("message", ""))[:300],
                "discount_id": resultado.get("shopifyDiscountId", ""),
                "base_calculo": data.get("priceBasis", ""),
                "tipo_descuento": data.get("tipoDescuento", ""),
                "valor": data.get("valorDescuento", ""),
                "inicio": str(data.get("fechaInicio", "")) + " " + str(data.get("horaInicio", "")),
                "fin": str(data.get("fechaFin", "")) + " " + str(data.get("horaFin", "")),
            }
        )
    return filas


def registrar_creacion(
    resultados: list[dict],
    data: dict,
    usuario: str,
    ruta: Path | None = None,
) -> int:
    """Agrega al CSV lo que se acaba de crear. Devuelve cuantas filas se guardaron."""
    filas = filas_registro(resultados, data, usuario)
    if not filas:
        return 0
    destino = Path(ruta) if ruta else RUTA_REGISTRO
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        tabla = pd.DataFrame(filas, columns=COLUMNAS_REGISTRO)
        tabla.to_csv(destino, mode="a", header=not destino.exists(), index=False, encoding="utf-8")
        return len(filas)
    except Exception:
        # La auditoria nunca debe tumbar la creacion de cupones.
        return 0


def leer_registro(ruta: Path | None = None) -> pd.DataFrame:
    destino = Path(ruta) if ruta else RUTA_REGISTRO
    if not destino.exists():
        return pd.DataFrame(columns=COLUMNAS_REGISTRO)
    try:
        return pd.read_csv(destino, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame(columns=COLUMNAS_REGISTRO)


def aplanar_cupones(nodos: list[dict], sitio: str) -> list[dict]:
    """Convierte la respuesta de codeDiscountNodes en filas planas."""
    filas = []
    for nodo in nodos or []:
        if not isinstance(nodo, dict):
            continue
        descuento = nodo.get("codeDiscount") or {}
        codigos = [
            str(item.get("code", "")).strip()
            for item in ((descuento.get("codes") or {}).get("nodes") or [])
            if str(item.get("code", "")).strip()
        ]
        estado = str(descuento.get("status", "")).upper()
        usos = descuento.get("asyncUsageCount")
        limite = descuento.get("usageLimit")
        filas.append(
            {
                "Sitio": sitio,
                "Codigo": ", ".join(codigos) or "-",
                "Titulo": descuento.get("title", "") or "-",
                "Estado": ETIQUETA_ESTADO_SHOPIFY.get(estado, estado or "-"),
                "Tipo": "Function (Best Wins)" if descuento.get("__typename") == "DiscountCodeApp" else "Nativo",
                "Inicio": str(descuento.get("startsAt", "") or "")[:16].replace("T", " "),
                "Fin": str(descuento.get("endsAt", "") or "")[:16].replace("T", " ") or "Sin fin",
                "Usos": 0 if usos is None else int(usos),
                "Limite": "Sin limite" if not limite else int(limite),
                "ID": nodo.get("id", ""),
            }
        )
    return filas


def resumen_cupones(filas: list[dict]) -> dict:
    resumen = {"total": len(filas or []), "activos": 0, "programados": 0, "expirados": 0, "usos": 0}
    for fila in filas or []:
        estado = str(fila.get("Estado", "")).lower()
        if estado == "activo":
            resumen["activos"] += 1
        elif estado == "programado":
            resumen["programados"] += 1
        elif estado == "expirado":
            resumen["expirados"] += 1
        resumen["usos"] += int(fila.get("Usos", 0) or 0)
    return resumen


def filtrar_cupones(filas: list[dict], estado: str = "Todos", texto: str = "") -> list[dict]:
    busqueda = str(texto or "").strip().lower()
    resultado = []
    for fila in filas or []:
        if estado != "Todos" and str(fila.get("Estado", "")) != estado:
            continue
        if busqueda:
            en_codigo = busqueda in str(fila.get("Codigo", "")).lower()
            en_titulo = busqueda in str(fila.get("Titulo", "")).lower()
            if not en_codigo and not en_titulo:
                continue
        resultado.append(fila)
    return resultado


def cambiar_estado_cupon(graphql, discount_id: str, activar: bool) -> str:
    """Activa o desactiva un cupon. Devuelve mensaje de error, o cadena vacia si salio bien."""
    if not str(discount_id or "").strip():
        return "Falta el ID del cupon."
    mutacion = MUTACION_ACTIVAR if activar else MUTACION_DESACTIVAR
    clave = "discountCodeActivate" if activar else "discountCodeDeactivate"
    try:
        datos = graphql(mutacion, {"id": discount_id})
    except Exception as exc:
        return str(exc)[:300]
    errores = ((datos or {}).get(clave) or {}).get("userErrors") or []
    if errores:
        return "; ".join(str(error.get("message", "")) for error in errores)
    return ""
