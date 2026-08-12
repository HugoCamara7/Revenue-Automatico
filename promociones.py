"""Descuentos promocionales: cambiar el precio real del catalogo desde un archivo.

A diferencia de los cupones, esto **escribe precios en Shopify**: el cliente ve el
precio tachado en la ficha, en los listados y en Google Shopping.

La regla de oro que pidio Hugo:

    La base del calculo es SIEMPRE el Compare At Price. Si el producto no tiene,
    se usa el Variant Price.

Eso evita el error clasico de re-descontar sobre un precio ya rebajado: si un producto
esta a S/70 con lista de S/100, un 40% da S/60 (sobre 100), no S/42 (sobre 70).

Al aplicar queda:

    Compare At Price = precio de lista (la base)
    Variant Price    = precio promocional calculado

Nunca sube un precio: si el calculo da mas caro que el precio vigente, la fila se
marca como "sin cambio" y no se toca.

El modulo es puro: no habla con Shopify ni con Streamlit, solo calcula. Asi se puede
probar con pytest y reutilizar desde la pantalla y desde el ejecutor programado.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

# Estados posibles de cada fila del plan
APLICA = "Aplica"
SIN_CAMBIO_MEJOR = "Sin cambio: el precio actual ya es mejor"
SIN_CAMBIO_SIN_REGLA = "Sin cambio: la fila no tiene ninguna regla"
NO_ENCONTRADO = "No encontrado en la tienda"
ERROR_DATO = "Dato invalido"

COLUMNAS_ID = ("id", "sku", "variant sku", "codigo", "id producto", "product id", "variant id")
COLUMNAS_PORCENTAJE = ("descuento", "porcentaje", "%", "off", "dcto", "descuento %")
COLUMNAS_OBJETIVO = ("precio objetivo", "precio final", "precio", "todo a", "target")
COLUMNAS_TOPE = ("tope", "tope maximo", "precio maximo", "maximo")
COLUMNAS_PISO = ("piso", "piso minimo", "precio minimo", "minimo")


def dinero(valor) -> Decimal | None:
    """Convierte a Decimal con 2 decimales. Devuelve None si no es un numero util."""
    if valor is None:
        return None
    texto = str(valor).strip().replace("S/", "").replace(",", "").replace("%", "").strip()
    if not texto or texto.lower() in ("nan", "none", "-"):
        return None
    try:
        numero = Decimal(texto)
    except Exception:
        return None
    if numero < 0:
        return None
    return numero.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalizar_columna(nombre: str) -> str:
    return str(nombre or "").strip().lower().replace("_", " ")


def detectar_columna(columnas, candidatas) -> str | None:
    """Encuentra la columna del archivo que corresponde a un rol."""
    mapa = {normalizar_columna(col): col for col in columnas}
    for candidata in candidatas:
        if candidata in mapa:
            return mapa[candidata]
    for normalizada, original in mapa.items():
        if any(candidata in normalizada for candidata in candidatas):
            return original
    return None


def leer_reglas(tabla: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """Lee el archivo del comercial y devuelve (reglas, avisos).

    Formato esperado: una columna con el ID o SKU y al menos una columna de regla.
    Los nombres se detectan solos: "SKU", "Descuento", "% off", "Precio objetivo",
    "Tope maximo", "Piso minimo".
    """
    avisos = []
    columna_id = detectar_columna(tabla.columns, COLUMNAS_ID)
    if not columna_id:
        return [], ["El archivo no tiene una columna de ID o SKU."]

    columna_pct = detectar_columna(tabla.columns, COLUMNAS_PORCENTAJE)
    columna_objetivo = detectar_columna(tabla.columns, COLUMNAS_OBJETIVO)
    columna_tope = detectar_columna(tabla.columns, COLUMNAS_TOPE)
    columna_piso = detectar_columna(tabla.columns, COLUMNAS_PISO)

    if not any((columna_pct, columna_objetivo, columna_tope, columna_piso)):
        return [], ["El archivo no tiene ninguna columna de regla (descuento, precio objetivo, tope o piso)."]

    reglas = []
    vistos = set()
    for _, fila in tabla.iterrows():
        identificador = str(fila.get(columna_id, "")).strip()
        if not identificador or identificador.lower() == "nan":
            continue
        if identificador.upper() in vistos:
            avisos.append("Repetido en el archivo, se usa la primera aparicion: " + identificador)
            continue
        vistos.add(identificador.upper())
        reglas.append(
            {
                "identificador": identificador,
                "porcentaje": dinero(fila.get(columna_pct)) if columna_pct else None,
                "precio_objetivo": dinero(fila.get(columna_objetivo)) if columna_objetivo else None,
                "tope_maximo": dinero(fila.get(columna_tope)) if columna_tope else None,
                "piso_minimo": dinero(fila.get(columna_piso)) if columna_piso else None,
            }
        )

    if not reglas:
        avisos.append("El archivo no trae ninguna fila con ID.")
    return reglas, avisos


def calcular_precio(precio_actual, compare_at, regla: dict) -> dict:
    """Calcula como queda una variante. No habla con Shopify.

    Devuelve un dict con la base usada, el precio nuevo, el compare at nuevo y el estado.
    """
    actual = dinero(precio_actual)
    lista = dinero(compare_at)
    if actual is None:
        return {"estado": ERROR_DATO, "detalle": "El producto no tiene precio."}

    # La base es el Compare At Price; si no hay, el precio vigente.
    base = lista if (lista is not None and lista > actual) else actual

    porcentaje = regla.get("porcentaje")
    objetivo = regla.get("precio_objetivo")
    tope = regla.get("tope_maximo")
    piso = regla.get("piso_minimo")

    if porcentaje is None and objetivo is None and tope is None and piso is None:
        return {"estado": SIN_CAMBIO_SIN_REGLA, "base": base, "precio_actual": actual}

    if objetivo is not None:
        nuevo = objetivo
    elif porcentaje is not None:
        nuevo = (base * (Decimal("1") - porcentaje / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        nuevo = base

    if tope is not None and nuevo > tope:
        nuevo = tope
    if piso is not None and nuevo < piso:
        nuevo = piso

    nuevo = nuevo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if nuevo >= actual:
        return {
            "estado": SIN_CAMBIO_MEJOR,
            "base": base,
            "precio_actual": actual,
            "precio_calculado": nuevo,
        }

    return {
        "estado": APLICA,
        "base": base,
        "precio_actual": actual,
        "precio_nuevo": nuevo,
        "compare_at_nuevo": base,
        "ahorro": (actual - nuevo).quantize(Decimal("0.01")),
        "descuento_real": ((base - nuevo) / base * Decimal("100")).quantize(Decimal("0.1")),
    }


def armar_plan(reglas: list[dict], variantes_por_clave: dict[str, dict]) -> list[dict]:
    """Cruza las reglas del archivo con las variantes reales de la tienda."""
    plan = []
    for regla in reglas:
        clave = regla["identificador"].strip().upper()
        variante = variantes_por_clave.get(clave)
        if not variante:
            plan.append(
                {
                    "Identificador": regla["identificador"],
                    "Producto": "",
                    "Estado": NO_ENCONTRADO,
                }
            )
            continue

        resultado = calcular_precio(variante.get("price"), variante.get("compare_at"), regla)
        fila = {
            "Identificador": regla["identificador"],
            "Producto": variante.get("nombre", ""),
            "Precio actual": float(resultado.get("precio_actual") or 0),
            "Compare At actual": float(dinero(variante.get("compare_at")) or 0),
            "Estado": resultado["estado"],
        }
        if resultado["estado"] == APLICA:
            fila.update(
                {
                    "Precio nuevo": float(resultado["precio_nuevo"]),
                    "Compare At nuevo": float(resultado["compare_at_nuevo"]),
                    "Ahorro": float(resultado["ahorro"]),
                    "Descuento real %": float(resultado["descuento_real"]),
                    "_variant_id": variante.get("id", ""),
                }
            )
        plan.append(fila)
    return plan


def resumen_plan(plan: list[dict]) -> dict:
    aplican = [fila for fila in plan if fila.get("Estado") == APLICA]
    return {
        "total": len(plan),
        "aplican": len(aplican),
        "sin_cambio": len([f for f in plan if f.get("Estado", "").startswith("Sin cambio")]),
        "no_encontrados": len([f for f in plan if f.get("Estado") == NO_ENCONTRADO]),
        "ahorro_promedio": (
            round(sum(f.get("Descuento real %", 0) for f in aplican) / len(aplican), 1) if aplican else 0.0
        ),
    }


def payload_actualizacion(fila: dict) -> dict:
    """Arma la entrada de productVariantsBulkUpdate para una variante."""
    return {
        "id": fila["_variant_id"],
        "price": str(fila["Precio nuevo"]),
        "compareAtPrice": str(fila["Compare At nuevo"]),
    }


def payload_reversion(fila: dict) -> dict:
    """Vuelve el precio de lista y limpia el Compare At."""
    return {
        "id": fila["_variant_id"],
        "price": str(fila["Compare At nuevo"]),
        "compareAtPrice": None,
    }


def agrupar_por_producto(filas: list[dict]) -> dict[str, list[dict]]:
    """`productVariantsBulkUpdate` recibe las variantes agrupadas por producto."""
    grupos: dict[str, list[dict]] = {}
    for fila in filas:
        producto = fila.get("_product_id", "")
        grupos.setdefault(producto, []).append(fila)
    return grupos
