import streamlit as st

from configuracion import APP_NAME, FORCE_RESET_ADMIN, ADMIN_PASS
from base_datos import init_db
from seguridad import reset_admin, _instalar_filtro_entradas_streamlit
from interfaz import (
    init_state, login, cambiar_password_obligatoria, styles, left_menu, topbar,
    page_inicio, page_registro, page_consulta, page_muestras_retencion,
    page_entrega_turno, page_catalogos, page_usuarios, page_auditoria,
)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="collapsed",
)
_instalar_filtro_entradas_streamlit()

def main():
    init_state()
    init_db()

    if FORCE_RESET_ADMIN and ADMIN_PASS:
        reset_admin()

    user = login()
    cambiar_password_obligatoria()
    styles(False)

    left_col, right_col = st.columns([0.19, 0.81], gap="large")
    with left_col:
        left_menu()

    with right_col:
        topbar(user)
        page = st.session_state.page

        if page == "Inicio":
            page_inicio()
        elif page == "Nuevo registro":
            page_registro()
        elif page == "Consulta y descarga":
            page_consulta()
        elif page == "Muestras de retención":
            page_muestras_retencion()
        elif page == "Entrega de turno":
            page_entrega_turno()
        elif page == "Catálogos":
            page_catalogos()
        elif page == "Usuarios":
            page_usuarios()
        elif page == "Auditoría":
            page_auditoria()

if __name__ == "__main__":
    main()
