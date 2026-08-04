"""Revisa las 8 tiendas Shopify antes de lanzar cupones.

Solo lee: no crea, no modifica y no borra nada en Shopify.

Uso:

    python diagnostico_multitienda.py
    python diagnostico_multitienda.py --sitios vans,columbia
    python diagnostico_multitienda.py --secrets .streamlit/secrets.toml --json

Codigo de salida: 0 si todas las tiendas revisadas quedaron en LISTO, 1 si alguna
quedo en SOLO PRECIO ACTUAL, SIN CONFIGURAR o ERROR (util para dejarlo en CI).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

from coupon_config import COUPON_SHOPIFY_SITES
from shopify_multisite import (
    ESTADO_LISTO,
    ETIQUETA_ESTADO,
    FUNCTION_HANDLE_POR_DEFECTO,
    diagnosticar_tiendas,
    recomendar_tokens,
    resumen_por_estado,
    texto_tabla,
)

RUTA_SECRETS_POR_DEFECTO = Path(".streamlit") / "secrets.toml"


def cargar_secrets(ruta: Path) -> dict:
    if not ruta.exists():
        raise SystemExit(
            "No encontre " + str(ruta) + ".\n"
            "Crea el archivo local o pasa la ruta con --secrets. En Streamlit Cloud el mismo\n"
            "contenido va en Settings > Secrets."
        )
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10 o menor
        try:
            import tomli as tomllib  # type: ignore
        except ModuleNotFoundError:
            raise SystemExit("Necesito Python 3.11+ o instalar tomli: pip install tomli")
    with ruta.open("rb") as archivo:
        return tomllib.load(archivo)


def obtener_config_desde_secrets(secrets: dict, shop_key: str) -> dict:
    for seccion in ("shopify_sites", "shopify"):
        bloque = secrets.get(seccion) or {}
        if not isinstance(bloque, dict):
            continue
        config = bloque.get(shop_key)
        if isinstance(config, dict) and config:
            return config
        if bloque.get("shop_domain") or bloque.get("access_token") or bloque.get("admin_access_token"):
            return bloque
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnostico multitienda de cupones Shopify.")
    parser.add_argument("--secrets", default=str(RUTA_SECRETS_POR_DEFECTO), help="Ruta al secrets.toml")
    parser.add_argument("--sitios", default="", help="Lista separada por comas de ids a revisar")
    parser.add_argument("--handle", default=FUNCTION_HANDLE_POR_DEFECTO, help="Handle esperado de la Function")
    parser.add_argument("--json", action="store_true", help="Devuelve el resultado completo en JSON")
    args = parser.parse_args(argv)

    secrets = cargar_secrets(Path(args.secrets))
    pedidos = {texto.strip().lower() for texto in args.sitios.split(",") if texto.strip()}
    sitios = [
        sitio
        for sitio in COUPON_SHOPIFY_SITES
        if sitio.get("enabled", True) and (not pedidos or sitio["id"].lower() in pedidos)
    ]
    if not sitios:
        print("Ningun sitio coincide con --sitios.")
        return 1

    resultados = diagnosticar_tiendas(
        sitios,
        obtener_config=lambda shop_key: obtener_config_desde_secrets(secrets, shop_key),
        crear_graphql=lambda shop_key, config: crear_graphql(config),
        handle_esperado=args.handle,
    )

    if args.json:
        print(json.dumps(resultados, ensure_ascii=False, indent=2))
    else:
        print(texto_tabla(resultados))
        print("")
        for fila in resultados:
            if not fila["detalles"]:
                continue
            print("[" + ETIQUETA_ESTADO.get(fila["estado"], fila["estado"]) + "] " + fila["sitio"])
            for detalle in fila["detalles"]:
                print("   - " + detalle)
            print("")
        recomendaciones = recomendar_tokens(resultados)
        if recomendaciones:
            print("Que token dejar en admin_access_token:")
            for mensaje in recomendaciones:
                print("   - " + mensaje)
            print("")
        pendientes = [fila for fila in resultados if fila["estado"] != ESTADO_LISTO]
        if pendientes:
            print("Secrets sugeridos para las tiendas pendientes:")
            print("")
            for fila in pendientes:
                print(fila["secrets_sugeridos"])
                print("")
        resumen = resumen_por_estado(resultados)
        print(
            "Resumen: "
            + str(resumen[ESTADO_LISTO])
            + " listas | "
            + str(resumen["solo_precio_actual"])
            + " solo precio actual | "
            + str(resumen["sin_configurar"])
            + " sin configurar | "
            + str(resumen["error"])
            + " con error."
        )

    return 0 if all(fila["estado"] == ESTADO_LISTO for fila in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
