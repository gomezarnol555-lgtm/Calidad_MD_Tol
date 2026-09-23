import streamlit as st
from configuracion import APP_NAME,FORCE_RESET_ADMIN,ADMIN_PASS
from base_datos import inicializar_base
from seguridad import reset_admin,_instalar_filtro_entradas_streamlit
from interfaz import *
st.set_page_config(page_title=APP_NAME,page_icon="✅",layout="wide",initial_sidebar_state="collapsed")
_instalar_filtro_entradas_streamlit()
def main():
 init_state();inicializar_base()
 if FORCE_RESET_ADMIN and ADMIN_PASS:reset_admin()
 user=login();cambiar_password_obligatoria();styles(False);a,b=st.columns([.19,.81],gap='large')
 with a:left_menu()
 with b:
  topbar(user);p=st.session_state.page
  if p=='Inicio':page_inicio()
  elif p=='Nuevo registro':page_registro()
  elif p=='Consulta y descarga':page_consulta()
  elif p=='Muestras de retención':page_muestras_retencion()
  elif p=='Entrega de turno':page_entrega_turno()
  elif p=='Catálogos':page_catalogos()
  elif p=='Usuarios':page_usuarios()
  elif p=='Auditoría':page_auditoria()
if __name__=='__main__':main()
