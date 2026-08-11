"""Quien puede entrar a la app.

Los usuarios viven en los Secrets de Streamlit. Este modulo los normaliza (hay cuatro
formatos historicos dando vueltas), verifica el ingreso y arma el bloque que hay que
pegar para dar de alta a alguien nuevo.

Todos los usuarios tienen los mismos permisos: quien entra puede crear, editar y pausar
cupones. Lo que si queda registrado es **quien** hizo cada cosa, en la auditoria.

Sobre las contrasenas: se aceptan en texto plano (formato viejo) o como hash SHA-256,
que es lo recomendado para no dejarlas legibles en Secrets. No es un hash de contrasenas
robusto como bcrypt, pero evita que cualquiera que abra el archivo se lleve las claves.
"""

from __future__ import annotations

import hashlib
import unicodedata


def limpiar(valor) -> str:
    """Normaliza un texto de Secrets: sin acentos raros, sin comillas sobrantes."""
    texto = str(valor if valor is not None else "").strip()
    texto = unicodedata.normalize("NFKC", texto)
    if len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in ("'", '"'):
        texto = texto[1:-1].strip()
    return texto


def hash_clave(clave: str) -> str:
    """SHA-256 en minusculas, el formato que se guarda en `password_sha256`."""
    return hashlib.sha256(limpiar(clave).encode("utf-8")).hexdigest().lower()


def listar_usuarios(config: dict) -> list[dict]:
    """Devuelve [{'email', 'password', 'password_sha256'}] desde cualquiera de los formatos.

    Formatos soportados en Secrets:

        [[auth.users_list]]        email = "..."  password = "..."
        [auth.users]               "correo" = "clave"
        [auth]                     allowed_emails = [...]  password = "compartida"
    """
    usuarios: list[dict] = []
    if not isinstance(config, dict):
        return usuarios

    for clave_lista in ("users_list", "users"):
        entradas = config.get(clave_lista)
        if isinstance(entradas, list):
            for entrada in entradas:
                if not isinstance(entrada, dict):
                    continue
                correo = limpiar(entrada.get("email", "")).lower()
                if correo:
                    usuarios.append(
                        {
                            "email": correo,
                            "password": limpiar(entrada.get("password", "")),
                            "password_sha256": limpiar(entrada.get("password_sha256", "")).lower(),
                        }
                    )
        elif hasattr(entradas, "items"):
            for correo, clave in dict(entradas).items():
                correo_limpio = limpiar(correo).lower()
                if correo_limpio:
                    usuarios.append(
                        {"email": correo_limpio, "password": limpiar(clave), "password_sha256": ""}
                    )

    compartida = limpiar(config.get("password", ""))
    for correo in config.get("allowed_emails", []) or []:
        correo_limpio = limpiar(correo).lower()
        if correo_limpio:
            usuarios.append({"email": correo_limpio, "password": compartida, "password_sha256": ""})

    unicos: dict[str, dict] = {}
    for usuario in usuarios:
        unicos.setdefault(usuario["email"], usuario)
    return list(unicos.values())


def verificar(email: str, clave: str, config: dict) -> bool:
    """True si el correo y la clave coinciden con alguien de la lista."""
    correo = limpiar(email).lower()
    entrada = limpiar(clave)
    if not correo or not entrada:
        return False

    for usuario in listar_usuarios(config):
        if usuario["email"] != correo:
            continue
        if usuario["password_sha256"]:
            if hash_clave(entrada) == usuario["password_sha256"]:
                return True
            continue
        if usuario["password"] and usuario["password"] == entrada:
            return True
    return False


def correos_habilitados(config: dict) -> list[str]:
    return sorted(usuario["email"] for usuario in listar_usuarios(config))


def bloque_alta(email: str, clave: str = "", usar_hash: bool = True) -> str:
    """Bloque TOML para agregar a alguien en Secrets."""
    correo = limpiar(email).lower() or "nombre@forus.pe"
    if usar_hash and limpiar(clave):
        return (
            "[[auth.users_list]]\n"
            'email = "' + correo + '"\n'
            'password_sha256 = "' + hash_clave(clave) + '"'
        )
    return (
        "[[auth.users_list]]\n"
        'email = "' + correo + '"\n'
        'password = "' + (limpiar(clave) or "CLAVE_SEGURA") + '"'
    )
