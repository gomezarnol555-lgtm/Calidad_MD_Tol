import streamlit as st

from configuracion import ADMIN_PASS, APP_NAME, FORCE_RESET_ADMIN
from base_datos import diagnostico_conexion, inicializar_base
from estilos import ESTILOS_APP
from seguridad import _instalar_filtro_entradas_streamlit, reset_admin
from interfaz import *


st.set_page_config(
    page_title=APP_NAME,
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_instalar_filtro_entradas_streamlit()


def aplicar_estilos_corporativos():
    """Aplica el CSS directamente, sin pasar por la capa de datos."""
    if not isinstance(ESTILOS_APP, str) or not ESTILOS_APP.strip():
        st.error(
            "No fue posible cargar el diseño corporativo: "
            "ESTILOS_APP no contiene CSS válido."
        )
        return

    st.markdown(
        ESTILOS_APP,
        unsafe_allow_html=True,
    )


def main():
    init_state()

    # Cargar el diseño antes de mostrar el acceso o cualquier página.
    # No llamar styles(False), porque la versión heredada devuelve
    # {'accion': 'recurso', 'nombre': 'estilos'}.
    aplicar_estilos_corporativos()

    try:
        inicializar_base()
    except Exception:
        _, mensaje = diagnostico_conexion()
        st.error("No fue posible iniciar la conexión con Supabase.")
        st.info(mensaje)
        st.markdown(
            "**Revisa:** Settings → Secrets, la URL raíz del proyecto "
            "y las tablas esenciales."
        )
        st.stop()

    if FORCE_RESET_ADMIN and ADMIN_PASS:
        try:
            reset_admin()
        except Exception as exc:
            st.error("No fue posible crear o restablecer el administrador.")
            st.info(str(exc))
            st.stop()

    user = login()
    cambiar_password_obligatoria()

    columna_menu, columna_contenido = st.columns(
        [0.19, 0.81],
        gap="large",
    )

    with columna_menu:
        left_menu()

    with columna_contenido:
        topbar(user)
        pagina = st.session_state.page

        if pagina == "Inicio":
            page_inicio()
        elif pagina == "Nuevo registro":
            page_registro()
        elif pagina == "Consulta y descarga":
            page_consulta()
        elif pagina == "Muestras de retención":
            page_muestras_retencion()
        elif pagina == "Entrega de turno":
            page_entrega_turno()
        elif pagina == "Catálogos":
            page_catalogos()
        elif pagina == "Usuarios":
            page_usuarios()
        elif pagina == "Auditoría":
            page_auditoria()


if __name__ == "__main__":
    main()
