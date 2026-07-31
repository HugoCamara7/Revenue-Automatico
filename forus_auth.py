"""Acceso al portal: usuarios autorizados, contrasenas y permisos por modulo."""
import streamlit as st

from forus_ui import LOGO_PATH, image_to_base64


ALLOWED_AUTH_USERS = [
    "liliana.vitate@forus.pe",
    "danitza.cupe@forus.pe",
    "hugo.camara@forus.pe",
    "romulo.rasilla@forus.pe",
    "bi@forus.pe",
]


# Modulos del portal, en el orden en que aparecen en el menu lateral.
MODULOS = {
    "comex": "Comex",
    "contabilidad": "Contabilidad",
    "rrhh": "Recursos Humanos",
}

# Si un usuario autorizado no figura en la seccion [modulos] de los secrets,
# conserva el acceso que ya tenia antes de esta version: solo Comex.
DEFAULT_MODULES = ["comex"]


def get_module_config():
    try:
        return dict(st.secrets.get("modulos", {}))
    except Exception:
        return {}


def get_user_modules(email):
    """Modulos permitidos para un correo, segun la seccion [modulos] de los secrets.

    Acepta "comex,rrhh", ["comex", "rrhh"] o "todos". Devuelve siempre claves
    validas y en el orden de MODULOS.
    """
    configurados = get_module_config()
    crudo = configurados.get(email)

    if crudo is None:
        permitidos = set(DEFAULT_MODULES)
    elif isinstance(crudo, str):
        texto = crudo.strip().lower()
        if texto in ("todos", "*", "all"):
            permitidos = set(MODULOS)
        else:
            permitidos = {parte.strip().lower() for parte in texto.replace(";", ",").split(",")}
    else:
        permitidos = {str(parte).strip().lower() for parte in crudo}

    return [clave for clave in MODULOS if clave in permitidos]

def usuarios_autorizados():
    """Correos con acceso: los que figuren en la seccion [auth] de los secrets.

    ALLOWED_AUTH_USERS solo se usa si no hay secrets configurados, para no
    dejar la aplicacion sin acceso.
    """
    try:
        configurados = dict(st.secrets.get("auth", {}))
    except Exception:
        configurados = {}
    if configurados:
        return [str(correo).strip().lower() for correo in configurados]
    return list(ALLOWED_AUTH_USERS)


def get_auth_passwords():
    try:
        configured = dict(st.secrets.get("auth", {}))
    except Exception:
        configured = {}
    normalizado = {str(correo).strip().lower(): str(clave)
                   for correo, clave in configured.items()}
    return {email: normalizado.get(email, "") for email in usuarios_autorizados()}


def is_authenticated():
    return bool(st.session_state.get("auth_ok")) and st.session_state.get("auth_user") in usuarios_autorizados()


def current_user_modules():
    """Modulos permitidos para la sesion en curso."""
    if not is_authenticated():
        return []
    guardados = st.session_state.get("auth_modules")
    if guardados is None:
        guardados = get_user_modules(st.session_state["auth_user"])
        st.session_state["auth_modules"] = guardados
    return guardados


# El CSS del login es una cadena normal, no un f-string: las llaves van simples
# y no hay forma de que una interpolacion mal escrita tire la pantalla.
LOGIN_CSS = """
<style>
.stApp {
    background:
        radial-gradient(circle at 20% 15%, rgba(37,99,235,0.18), transparent 42%),
        radial-gradient(circle at 82% 78%, rgba(20,168,232,0.14), transparent 46%),
        linear-gradient(160deg, #0a1628 0%, #0f1f38 55%, #142238 100%) !important;
}

header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
section[data-testid="stSidebar"],
#MainMenu,
footer {
    display: none !important;
    visibility: hidden !important;
}

.block-container {
    max-width: 470px !important;
    padding-top: 3.5rem !important;
    padding-bottom: 3rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* Streamlit envuelve cada widget en un contenedor que, dentro de un flex, se
   encoge al tamano de su contenido. Sin esto el boton de enviar se queda del
   ancho de su texto por mucho que se le ponga width al propio boton. */
div[data-testid="stForm"] [data-testid="stElementContainer"],
div[data-testid="stForm"] [data-testid="stElementContainer"] > div {
    width: 100% !important;
}

/* Cabecera de la tarjeta: se une con el formulario sin costura. */
.login-hero {
    background: linear-gradient(150deg, #1d4ed8 0%, #2563eb 55%, #1e40af 100%);
    border-radius: 16px 16px 0 0;
    padding: 2.4rem 2rem 2rem;
    text-align: center;
    box-shadow: 0 -1px 0 rgba(255,255,255,0.06) inset;
}

.login-logo {
    width: 176px;
    margin: 0 auto 1.5rem;
    background: #ffffff;
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
}

.login-logo img {
    display: block;
    width: 100%;
    height: auto;
}

.login-title {
    color: #ffffff;
    font-size: 1.55rem;
    font-weight: 800;
    letter-spacing: -0.01em;
    line-height: 1.2;
    margin: 0;
}

.login-subtitle {
    margin-top: 0.6rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: #bfdbfe;
    letter-spacing: 0.02em;
}

/* El formulario es la mitad inferior de la misma tarjeta. */
div[data-testid="stForm"] {
    background: #ffffff !important;
    border: 0 !important;
    border-radius: 0 0 16px 16px !important;
    padding: 1.9rem 2rem 2rem !important;
    margin: 0 0 1.5rem !important;
    box-shadow: 0 24px 60px rgba(2,10,25,0.45) !important;
}

div[data-testid="stForm"] label p {
    color: #0f213f !important;
    font-weight: 650 !important;
    font-size: 0.86rem !important;
}

div[data-testid="stForm"] input {
    min-height: 46px !important;
    background: #f8fafc !important;
    border: 1px solid #dbe3ee !important;
    border-radius: 10px !important;
    color: #0f213f !important;
    font-size: 0.95rem !important;
}

div[data-testid="stForm"] input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.15) !important;
}

div[data-testid="stForm"] [data-baseweb="input"] {
    background: transparent !important;
    border-radius: 10px !important;
}

/* El boton de enviar ocupa todo el ancho: hay que estirar tambien su
   contenedor, porque por si solo se ajusta al texto. */
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"],
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > div {
    width: 100% !important;
    display: block !important;
}

div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button,
div[data-testid="stForm"] button[data-testid="stBaseButton-secondaryFormSubmit"] {
    width: 100% !important;
    min-height: 48px !important;
    margin-top: 0.6rem !important;
    background: linear-gradient(90deg, #1d4ed8, #2563eb) !important;
    color: #ffffff !important;
    border: 0 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.01em;
    box-shadow: 0 10px 24px rgba(29,78,216,0.35) !important;
    transition: filter .15s ease, transform .15s ease;
}

div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover {
    filter: brightness(1.08);
}

div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:active {
    transform: translateY(1px);
}

/* El ojo de "mostrar contrasena" vive dentro del propio campo y heredaba el
   gradiente azul de los botones generales: por eso salia un recuadro oscuro
   ocupando medio campo. Aqui se devuelve a icono discreto. */
div[data-testid="stForm"] [data-testid="stTextInputRootElement"] button,
div[data-testid="stForm"] div[data-baseweb="input"] button {
    width: auto !important;
    min-width: 0 !important;
    min-height: auto !important;
    margin: 0 !important;
    padding: 0 0.55rem !important;
    background: transparent !important;
    background-image: none !important;
    border: 0 !important;
    border-radius: 0 10px 10px 0 !important;
    color: #64748b !important;
    box-shadow: none !important;
}

div[data-testid="stForm"] [data-testid="stTextInputRootElement"] button:hover {
    color: #1d4ed8 !important;
    background: transparent !important;
    background-image: none !important;
}

div[data-testid="stForm"] [data-testid="stTextInputRootElement"] {
    border-radius: 10px !important;
    background: #f8fafc !important;
}

.login-footer {
    text-align: center;
    color: #7f93b4;
    font-size: 0.78rem;
    line-height: 1.7;
    letter-spacing: 0.01em;
}

.login-footer strong {
    color: #a8bde0;
    font-weight: 650;
}

div[data-testid="stAlert"] {
    border-radius: 10px !important;
    margin-top: 0.9rem !important;
}
</style>
"""


def render_login_screen():
    """Pantalla de acceso: una sola tarjeta con la cabecera y el formulario."""
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    logo_base64 = image_to_base64(LOGO_PATH)
    logo_html = (
        f'<div class="login-logo"><img src="data:image/png;base64,{logo_base64}" alt="Forus"></div>'
        if logo_base64
        else '<div class="login-title" style="letter-spacing:.1em">FORUS</div>'
    )

    st.markdown(
        f"""
        <div class="login-hero">
            {logo_html}
            <div class="login-title">Lectura Documentos Forus</div>
            <div class="login-subtitle">Comex &nbsp;·&nbsp; Contabilidad &nbsp;·&nbsp; Recursos Humanos</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        email = st.text_input(
            "Correo electrónico",
            placeholder="nombre.apellido@forus.pe",
        ).strip().lower()
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")

    st.markdown(
        """
        <div class="login-footer">
            <strong>Sistema exclusivo para personal autorizado</strong><br>
            Si no puedes entrar, avisa al administrador del portal
        </div>
        """,
        unsafe_allow_html=True,
    )

    if submitted:
        auth_passwords = get_auth_passwords()
        if email not in usuarios_autorizados():
            st.error("Este correo no tiene acceso autorizado.")
            st.stop()
        expected_password = auth_passwords.get(email)
        if not expected_password:
            st.error("Falta configurar la contraseña de este usuario en Streamlit Secrets.")
            st.stop()
        if password == expected_password:
            modulos = get_user_modules(email)
            if not modulos:
                st.error("Este usuario no tiene ningun modulo asignado. Avisa al administrador.")
                st.stop()
            st.session_state["auth_ok"] = True
            st.session_state["auth_user"] = email
            st.session_state["auth_modules"] = modulos
            st.rerun()
        st.error("Correo o contraseña incorrectos.")

    st.stop()


def require_login():
    if not is_authenticated():
        render_login_screen()
