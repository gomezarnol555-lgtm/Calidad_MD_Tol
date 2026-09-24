import streamlit as st

from configuracion import ADMIN_PASS, APP_NAME, FORCE_RESET_ADMIN
from base_datos import inicializar_base
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


def aplicar_estilos():
    if isinstance(ESTILOS_APP, str) and ESTILOS_APP.strip():
        st.markdown(ESTILOS_APP, unsafe_allow_html=True)


def main():
    init_state()
    aplicar_estilos()

    try:
        inicializar_base()
    except Exception as exc:
        st.error("No fue posible iniciar la conexión con Supabase.")
        st.info(str(exc))
        st.stop()

    if (
        FORCE_RESET_ADMIN
        and ADMIN_PASS
        and not st.session_state.get("admin_restaurado_en_sesion", False)
    ):
        try:
            reset_admin()
            st.session_state["admin_restaurado_en_sesion"] = True
        except Exception as exc:
            st.error("No fue posible crear o restablecer el administrador.")
            st.info(str(exc))
            st.stop()

    user = login()
    cambiar_password_obligatoria()

    columna_menu, columna_contenido = st.columns([0.19, 0.81], gap="large")
    with columna_menu:
        left_menu()
    with columna_contenido:
        topbar(user)
        pagina = st.session_state.page
        paginas = {
            "Inicio": page_inicio,
            "Nuevo registro": page_registro,
            "Consulta y descarga": page_consulta,
            "Muestras de retención": page_muestras_retencion,
            "Entrega de turno": page_entrega_turno,
            "Catálogos": page_catalogos,
            "Usuarios": page_usuarios,
            "Auditoría": page_auditoria,
        }
        paginas.get(pagina, page_inicio)()


if __name__ == "__main__":
    main()
