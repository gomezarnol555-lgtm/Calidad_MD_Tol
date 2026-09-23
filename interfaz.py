import streamlit as st
import pandas as pd
import altair as alt
import hashlib, os, base64, json, re
from io import BytesIO
from openpyxl.styles import Font, PatternFill
from datetime import datetime, date, timedelta
from pathlib import Path
from uuid import uuid4
from configuracion import *
from base_datos import consultar, crear, editar, eliminar, guardar_varios,  operacion_tabla, ErrorIntegridad, reiniciar_consecutivo, inicializar_base
from seguridad import *
from servicios import *
from reportes import *

def cambiar_password_obligatoria():
    auth = st.session_state.get('auth') or {}
    if not auth or not int(auth.get('requiere_cambio_pass', 0) or 0):
        return
    styles(False)
    st.markdown('<div class="login-card"><div class="login-title">Cambio de contraseña obligatorio</div></div>', unsafe_allow_html=True)
    st.warning('Debes actualizar la contraseña inicial antes de acceder al sistema.')
    with st.form('cambio_password_obligatorio'):
        nueva = st.text_input('Nueva contraseña', type='password')
        confirmar = st.text_input('Confirmar nueva contraseña', type='password')
        guardar = st.form_submit_button('Actualizar contraseña', type='primary')
    if guardar:
        errores = []
        if len(nueva) < 8:
            errores.append('mínimo 8 caracteres')
        if not re.search('[A-ZÁÉÍÓÚÑ]', nueva):
            errores.append('una mayúscula')
        if not re.search('[a-záéíóúñ]', nueva):
            errores.append('una minúscula')
        if not re.search('\\d', nueva):
            errores.append('un número')
        if nueva != confirmar:
            errores.append('las contraseñas deben coincidir')
        if errores:
            st.error('La contraseña requiere: ' + ', '.join(errores) + '.')
        else:
            crear(operacion_tabla('INTERFAZ_0028'), (hash_password(nueva), auth['usuario']))
            audit(auth['usuario'], 'CAMBIO_PASSWORD_OBLIGATORIO', 'Contraseña inicial actualizada')
            st.session_state.auth['requiere_cambio_pass'] = 0
            st.success('Contraseña actualizada correctamente.')
            st.rerun()
    st.stop()

def styles(compact=False):
    st.markdown(operacion_tabla('INTERFAZ_0029'), unsafe_allow_html=True)

def init_state():
    if 'auth' not in st.session_state:
        st.session_state.auth = None
    if 'page' not in st.session_state:
        st.session_state.page = 'Inicio'
    if 'inicio_indicador' not in st.session_state:
        st.session_state.inicio_indicador = 'PNC'

def login():
    if st.session_state.auth:
        return st.session_state.auth
    styles(False)
    c1, c2, c3 = st.columns([0.36, 0.28, 0.36])
    with c2:
        st.markdown('<div class="login-card"><div class="login-title">Sistema de Calidad</div></div>', unsafe_allow_html=True)
        with st.form('login_form'):
            u = st.text_input('Usuario')
            p = st.text_input('Contraseña', type='password')
            ok = st.form_submit_button('Ingresar')
    if ok:
        au = auth_user(u.strip(), p)
        estado = au.get('estado') if au else 'credenciales_invalidas'
        if estado == 'ok':
            st.session_state.auth = {k: au[k] for k in ('usuario', 'nombre', 'rol', 'requiere_cambio_pass')}
            audit(au['usuario'], 'LOGIN', 'Ingreso correcto')
            st.rerun()
        elif estado == 'bloqueado_por_intentos':
            audit(au.get('usuario') or u.strip(), 'BLOQUEO_LOGIN', 'Cuenta bloqueada al alcanzar 8 intentos fallidos')
            st.error('Cuenta bloqueada por alcanzar 8 intentos fallidos. Solicita la reactivación a un desarrollador.')
        elif estado == 'bloqueado':
            st.error('La cuenta está bloqueada o inhabilitada. Solicita la reactivación a un desarrollador.')
        elif estado == 'advertencia':
            st.warning(f"Advertencia final: intento {au['intentos']} de 8. Quedan {au['restantes']} intento(s) antes del bloqueo.")
        else:
            restantes = au.get('restantes')
            detalle = f' Quedan {restantes} intento(s).' if restantes is not None else ''
            st.error('Usuario o contraseña incorrectos.' + detalle)
    st.stop()

def topbar(user):
    initials = ''.join([x[0] for x in user['nombre'].split()[:2]]).upper() or 'AD'
    st.markdown(f"""<div class="topbar"><div class="topbar-title">Sistema de Calidad MD</div><div class="topbar-user"><span>🔔</span><span>{user['nombre'].upper()}</span><span class="avatar">{initials}</span></div></div>""", unsafe_allow_html=True)

def menu_button(page, full, icon):
    label = full
    if st.session_state.page == page:
        st.markdown(f'<div class="menu-active"><span>{label}</span></div>', unsafe_allow_html=True)
    elif st.button(label, key=f'menu_{page}'):
        st.session_state.page = page
        st.rerun()

def left_menu():
    st.markdown('<div class="left-menu-bg"></div><span class="left-menu-marker"></span>', unsafe_allow_html=True)
    st.markdown('<div class="menu-brand"><span>◆</span><span class="menu-brand-text">CALIDAD MD</span></div><div class="menu-section">MENÚ PRINCIPAL</div>', unsafe_allow_html=True)
    menu_button('Inicio', '🏠 Inicio', '🏠')
    menu_button('Nuevo registro', '📝 Nuevo registro', '📝')
    menu_button('Consulta y descarga', '📊 Consulta y descarga', '📊')
    menu_button('Muestras de retención', '🧪 Muestras de retención', '🧪')
    menu_button('Entrega de turno', '🔄 Entrega de turno', '🔄')
    menu_button('Catálogos', '🧩 Catálogos', '🧩')
    if is_dev():
        menu_button('Usuarios', '👤 Usuarios', '👤')
        menu_button('Auditoría', '🧾 Auditoría', '🧾')
    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    if st.button('Cerrar sesión', key='logout_left_menu'):
        audit(st.session_state.auth['usuario'], 'LOGOUT', 'Cierre de sesión')
        st.session_state.auth = None
        st.rerun()

def _selector_indicador_actual(indicador, key):
    opciones = ['PNC', 'Materia extraña', 'Producto segregado por detector de metales y RX', 'Reclamos', 'Devoluciones', 'SPAC']
    with st.popover('Indicador', use_container_width=True):
        nuevo = st.radio('Seleccionar indicador', opciones, index=opciones.index(indicador), key=key, label_visibility='collapsed')
        if nuevo != indicador:
            st.session_state.inicio_indicador = nuevo
            st.rerun()

def _grafica_conteo(data, campo, titulo, etiqueta, key, color='#00A884'):
    if data.empty or campo not in data.columns:
        st.info('No hay información disponible para generar esta gráfica.')
        return
    serie = data[campo].fillna('').astype(str).str.strip()
    serie = serie[serie.ne('')]
    if serie.empty:
        st.info('No hay información disponible para generar esta gráfica.')
        return
    g = serie.value_counts().head(15).rename_axis(etiqueta).reset_index(name='Registros')
    orden = g[etiqueta].tolist()
    base = alt.Chart(g).encode(x=alt.X('Registros:Q', title='Número de registros', axis=alt.Axis(tickMinStep=1, grid=True, gridColor='#E8EDF3', domain=False, labelColor='#526078', titleColor='#344054')), y=alt.Y(f'{etiqueta}:N', title=None, sort=orden, axis=alt.Axis(domain=False, ticks=False, labelColor='#344054', labelLimit=320)), tooltip=[alt.Tooltip(f'{etiqueta}:N', title=etiqueta), alt.Tooltip('Registros:Q', title='Registros', format=',d')])
    barras = base.mark_bar(cornerRadiusEnd=7, color=color, size=22)
    textos = base.mark_text(align='left', dx=7, fontWeight='bold', fontSize=11, color='#203047').encode(text=alt.Text('Registros:Q', format=',d'))
    grafica = (barras + textos).properties(title=alt.TitleParams(titulo, anchor='start', fontSize=17, fontWeight=700, color='#0B3440', offset=18), height=max(270, min(520, 38 * len(g)))).configure_view(stroke=None).configure_axis(labelFontSize=11, titleFontSize=12)
    st.altair_chart(grafica, use_container_width=True, key=key)

def _grafica_mes(data, campo, titulo, key):
    fechas = pd.to_datetime(data[campo], errors='coerce').dropna() if campo in data.columns else pd.Series(dtype='datetime64[ns]')
    if fechas.empty:
        st.info('No hay fechas válidas para generar esta gráfica.')
        return
    g = fechas.dt.to_period('M').astype(str).value_counts().sort_index().rename_axis('Mes').reset_index(name='Registros')
    base = alt.Chart(g).encode(x=alt.X('Mes:N', sort=None, title=None, axis=alt.Axis(labelAngle=-35, labelColor='#526078', domain=False, ticks=False)), y=alt.Y('Registros:Q', title='Número de registros', axis=alt.Axis(tickMinStep=1, grid=True, gridColor='#E8EDF3', domain=False, labelColor='#526078', titleColor='#344054')), tooltip=[alt.Tooltip('Mes:N', title='Mes'), alt.Tooltip('Registros:Q', title='Registros', format=',d')])
    area = base.mark_area(color='#5850EC', opacity=0.09)
    linea = base.mark_line(point=alt.OverlayMarkDef(filled=True, fill='#FFFFFF', stroke='#5850EC', strokeWidth=3, size=90), strokeWidth=3, color='#5850EC')
    textos = base.mark_text(dy=-14, fontWeight='bold', fontSize=11, color='#203047').encode(text=alt.Text('Registros:Q', format=',d'))
    grafica = (area + linea + textos).properties(title=alt.TitleParams(titulo, anchor='start', fontSize=17, fontWeight=700, color='#0B3440', offset=18), height=315).configure_view(stroke=None).configure_axis(labelFontSize=11, titleFontSize=12)
    st.altair_chart(grafica, use_container_width=True, key=key)

def grafica_lineas_con_valores(df, titulo, key):
    """Grafica lineal con puntos y etiquetas visibles sin seleccionar la grafica."""
    if df.empty or df['Cumplimiento %'].dropna().empty:
        st.info(f'No hay porcentajes disponibles para {titulo}.')
        return
    datos = df.dropna(subset=['Cumplimiento %']).copy()
    datos['Cumplimiento %'] = pd.to_numeric(datos['Cumplimiento %'], errors='coerce')
    base = alt.Chart(datos).encode(x=alt.X('Periodo:N', title='Periodo', sort=None), y=alt.Y('Cumplimiento %:Q', title='Cumplimiento (%)'), color=alt.Color('Entidad:N', title='Serie'), detail='Entidad:N', tooltip=['Periodo:N', 'Entidad:N', alt.Tooltip('Cumplimiento %:Q', format='.1f')])
    linea = base.mark_line(point=True, strokeWidth=3)
    etiquetas = base.mark_text(dy=-12, fontSize=11, fontWeight='bold').encode(text=alt.Text('Cumplimiento %:Q', format='.1f'))
    regla = alt.Chart(pd.DataFrame({'Cumplimiento %': [100]})).mark_rule(color='#16A34A', strokeDash=[6, 4]).encode(y='Cumplimiento %:Q')
    st.altair_chart((linea + etiquetas + regla).properties(title=titulo, height=330), use_container_width=True, key=key)

def panel_indicadores_spac_inicio(indicador='SPAC'):
    st.session_state.inicio_indicador = 'SPAC'
    registros = consultar(operacion_tabla('INTERFAZ_0030'))
    h, sel, fil = st.columns([7.1, 1.4, 1.5], vertical_alignment='center')
    with h:
        st.markdown('<div class="indicator-title">Indicadores SPAC</div>', unsafe_allow_html=True)
    with sel:
        st.markdown('<span class="toolbar-marker"></span>', unsafe_allow_html=True)
        _selector_indicador_actual(indicador, 'selector_spac')
    if registros.empty:
        with fil:
            st.markdown('<span class="toolbar-marker"></span>', unsafe_allow_html=True)
            st.button('Filtros', disabled=True, key='filtro_spac_vacio')
        st.info('Aún no hay información SPAC disponible.')
        return
    registros['fecha_dt'] = pd.to_datetime(registros['fecha'], errors='coerce').dt.date
    registros = registros.dropna(subset=['fecha_dt'])
    registros = registros[registros['fecha_dt'] <= date.today()]
    if registros.empty:
        st.info('La matriz no contiene información válida hasta la fecha actual.')
        return
    with fil:
        st.markdown('<span class="toolbar-marker"></span>', unsafe_allow_html=True)
        with st.popover('Filtros', use_container_width=True):
            tipo = st.radio('Visualización', ['SEMANA', 'MES'], horizontal=True, format_func=lambda x: 'Semana' if x == 'SEMANA' else 'Mes', key='inicio_spac_tipo')
            grafica_base = datos_grafica_cumplimiento('ANALISTA', tipo)
            nombres = sorted(grafica_base['Entidad'].dropna().astype(str).unique().tolist()) if not grafica_base.empty else []
            seleccionar_todos = st.checkbox('Seleccionar todos los analistas', value=True, key='inicio_spac_todos_analistas')
            if seleccionar_todos:
                analistas = nombres
                st.caption(f'{len(nombres)} analistas seleccionados.')
            else:
                analistas = st.multiselect('Selección de analistas', nombres, default=[], key='inicio_spac_analistas')
    ga = datos_grafica_cumplimiento('ANALISTA', tipo)
    gc = datos_grafica_cumplimiento('CALIDAD_NAVE', tipo)
    gp = datos_grafica_cumplimiento('NAVE', tipo)
    periodo_actual = clave_periodo(date.today(), tipo)
    if not ga.empty:
        ga = ga[ga['Periodo'].astype(str) <= periodo_actual]
        ga = ga[ga['Entidad'].astype(str).isin(analistas)] if analistas else ga.iloc[0:0]
    if not gc.empty:
        gc = gc[gc['Periodo'].astype(str) <= periodo_actual]
    if not gp.empty:
        gp = gp[gp['Periodo'].astype(str) <= periodo_actual]
    st.markdown('### Cumplimiento SPAC por analista')
    grafica_lineas_con_valores(ga, 'Cumplimiento SPAC por analista', 'inicio_chart_analistas')
    c1, c2 = st.columns(2)
    with c1:
        grafica_lineas_con_valores(gc, 'Indicador SPAC Calidad', 'inicio_chart_calidad')
    with c2:
        grafica_lineas_con_valores(gp, 'Indicador SPAC Producción', 'inicio_chart_produccion')

def _panel_registros_inicio(tipo):
    cfg = {'PNC': ('pnc_registros', 'fecha_apertura', 'defecto', 'Producto No Conforme', 'analista', 'linea_sector', 'status', 'cantidad_total_pnc'), 'Materia extraña': ('me_registros', '_fecha', '_codigo_defecto_panel', 'Materia extraña', 'analista_detecta', 'linea_sector', None, None), 'Producto segregado por detector de metales y RX': ('ddm_rx_registros', '_fecha', '_codigo_defecto_panel', 'Producto segregado por detector de metales y RX', 'analista_detecta', 'linea_sector', None, None), 'Reclamos': ('reclamos_registros', 'fecha', 'descripcion_defecto', 'Reclamos', 'creado_por', 'sector', 'estado_reclamo', 'cantidad_afectada'), 'Devoluciones': ('devoluciones_registros', 'fecha', 'defecto', 'Devoluciones', 'creado_por', 'sector', 'status', 'cantidad_afectada')}
    if tipo not in cfg:
        st.session_state.inicio_indicador = 'PNC'
        st.rerun()
    tabla, fecha, defecto, titulo, c_analista, c_linea, c_estado, c_cantidad = cfg[tipo]
    d = consultar(operacion_tabla('INTERFAZ_0031', tabla))
    if not d.empty and 'nave' in d.columns:
        d['nave'] = d['nave'].map(normalizar_nave)
    if fecha == '_fecha':
        d[fecha] = pd.to_datetime(dict(year=pd.to_numeric(d.get('anio'), errors='coerce'), month=pd.to_numeric(d.get('mes'), errors='coerce'), day=pd.to_numeric(d.get('dia'), errors='coerce')), errors='coerce') if not d.empty else pd.Series(dtype='datetime64[ns]')
    else:
        d[fecha] = pd.to_datetime(d[fecha], errors='coerce') if fecha in d.columns else pd.NaT
    if defecto == '_codigo_defecto_panel':
        cat = consultar(operacion_tabla('INTERFAZ_0032'))
        mapa = {str(r.codigo).strip(): str(r.defecto).strip() for r in cat.itertuples()}
        cod = d.get('codigo_defecto', pd.Series('', index=d.index)).fillna('').astype(str).str.strip()
        d[defecto] = cod.map(lambda x: f"{x} | {mapa.get(x, 'Defecto no catalogado')}" if x else '')
    fechas = d[fecha].dropna()
    limpio = lambda campo: sorted(d.get(campo, pd.Series(dtype=str)).dropna().astype(str).loc[lambda z: z.str.strip().ne('')].unique())
    lineas, naves, analistas = (limpio(c_linea), limpio('nave'), limpio(c_analista))
    h, sel, fil = st.columns([7.1, 1.4, 1.5], vertical_alignment='center')
    with h:
        st.markdown(f'<div class="indicator-title">Indicadores de {titulo}</div>', unsafe_allow_html=True)
    with sel:
        st.markdown('<span class="toolbar-marker"></span>', unsafe_allow_html=True)
        _selector_indicador_actual(tipo, f'selector_{tabla}')
    with fil:
        st.markdown('<span class="toolbar-marker"></span>', unsafe_allow_html=True)
        with st.popover('Filtros', use_container_width=True):
            if not fechas.empty:
                mn, mx = (fechas.min().date(), fechas.max().date())
                a, b = st.columns(2)
                desde = a.date_input('Fecha inicial', mn, min_value=mn, max_value=mx, key=f'desde_{tabla}')
                hasta = b.date_input('Fecha final', mx, min_value=mn, max_value=mx, key=f'hasta_{tabla}')
            else:
                desde = hasta = None
            sl = st.multiselect('Línea/Sector', lineas, key=f'lineas_{tabla}')
            sn = st.multiselect('Nave', naves, key=f'naves_{tabla}')
            sa = st.multiselect('Analista / usuario', analistas, key=f'analistas_{tabla}')
    x = d.copy()
    if desde and hasta:
        if desde > hasta:
            st.error('La fecha inicial no puede ser posterior a la fecha final.')
            return
        x = x[(x[fecha].dt.date >= desde) & (x[fecha].dt.date <= hasta)]
    if sl:
        x = x[x[c_linea].isin(sl)]
    if sn:
        x = x[x.nave.isin(sn)]
    if sa:
        x = x[x[c_analista].isin(sa)]
    total = len(x)
    ln = x.get(c_linea, pd.Series(dtype=str)).replace('', pd.NA).nunique()
    dn = x.get(defecto, pd.Series(dtype=str)).replace('', pd.NA).nunique()
    meses = x[fecha].dropna().dt.to_period('M').nunique()
    if tipo == 'PNC':
        e = x.get(c_estado, pd.Series('', index=x.index)).fillna('').astype(str).str.strip().str.upper()
        ce = int(e.eq('CERRADO').sum())
        ab = int(e.eq('ABIERTO').sum())
        cantidad = pd.to_numeric(x.get(c_cantidad, pd.Series(0, index=x.index)), errors='coerce').fillna(0).sum()
        cards = [('Total de PNC', f'{total:,}', 'Número de registros totales', '#00A884'), ('% de cierre', f'{(ce / total * 100 if total else 0):.1f}%', 'PNC cerrados respecto al total', '#5850EC'), ('Kg totales de PNC', f'{cantidad:,.2f} kg', 'Cantidad total registrada', '#3F7BFF'), ('PNC abiertos', f'{ab:,}', 'Registros pendientes de cierre', '#F59E0B')]
    elif tipo in {'Reclamos', 'Devoluciones'}:
        e = x.get(c_estado, pd.Series('', index=x.index)).fillna('').astype(str).str.strip().str.upper()
        ce = int(e.eq('CERRADO').sum())
        ab = int(e.eq('ABIERTO').sum())
        cantidad = pd.to_numeric(x.get(c_cantidad, pd.Series(0, index=x.index)), errors='coerce').fillna(0).sum()
        singular = 'Reclamos' if tipo == 'Reclamos' else 'Devoluciones'
        cards = [(f'Total de {tipo.lower()}', f'{total:,}', 'Número de registros totales', '#00A884'), ('% de cierre', f'{(ce / total * 100 if total else 0):.1f}%', f'{singular} cerrados respecto al total', '#5850EC'), ('Cantidad afectada', f'{cantidad:,.2f}', 'Suma de la cantidad registrada', '#3F7BFF'), ('Registros abiertos', f'{ab:,}', 'Pendientes de cierre', '#F59E0B')]
    else:
        cards = [('Registros', total, 'Total filtrado', '#00A884'), ('Códigos / defectos', dn, 'Tipos identificados', '#5850EC'), ('Líneas / sectores', ln, 'Con registros', '#3F7BFF'), ('Meses', meses, 'Periodos con actividad', '#F59E0B')]
    cols = st.columns(4, gap='large')
    for c, (la, va, pi, co) in zip(cols, cards):
        with c:
            st.markdown(f'<div class="kpi" style="--c:{co}"><div class="kpi-label">{la}</div><div class="kpi-value">{va}</div><div class="kpi-foot">{pi}</div></div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        st.markdown('<span class="chart-marker"></span>', unsafe_allow_html=True)
        especial = tipo in {'Materia extraña', 'Producto segregado por detector de metales y RX'}
        _grafica_conteo(x, defecto, 'Distribución por código y defecto' if especial else 'Distribución de defectos', 'Código / Defecto' if especial else 'Defecto', f'def_{tabla}', '#00A884')
    with b:
        _grafica_conteo(x, c_linea, 'Registros por línea o sector', 'Línea/Sector', f'lin_{tabla}', '#3F7BFF')
    _grafica_mes(x, fecha, 'Evolución mensual de registros', f'mes_{tabla}')

def page_inicio():
    st.markdown('<div class="home-hero"><div class="home-hero-title">Panel Calidad Mundo Dulce</div></div>', unsafe_allow_html=True)
    indicador = st.session_state.get('inicio_indicador', 'PNC')
    panel_indicadores_spac_inicio(indicador) if indicador == 'SPAC' else _panel_registros_inicio(indicador)

def estilo_faltantes_matriz(df, primeras_columnas=1):

    def pintar(valor):
        return 'background-color:#FECACA;color:#991B1B;font-weight:800;border:1px solid #EF4444' if pd.isna(valor) or str(valor).strip() == '' else ''
    return df.style.map(pintar, subset=list(df.columns[primeras_columnas:])).format(na_rep='')

def editor_metas_cumplimiento(tipo_entidad, entidades, teoricos, periodo_tipo, periodo_clave, key):
    """Datos teóricos vienen de registros; datos cargados se capturan manualmente."""
    guardados = consultar(operacion_tabla('INTERFAZ_0033'), (tipo_entidad, periodo_tipo, periodo_clave))
    mapa = {str(r.entidad): float(r.meta or 0) for r in guardados.itertuples()}
    filas = []
    for entidad in entidades:
        teorico = float(teoricos.get(entidad, 0) or 0)
        cargado = float(mapa.get(entidad, 0) or 0)
        porcentaje = cargado / teorico * 100 if teorico > 0 else None
        filas.append({'Entidad': entidad, 'Datos teóricos': teorico, 'Datos cargados': cargado, 'Cumplimiento %': porcentaje})
    base = pd.DataFrame(filas)
    if is_dev():
        editado = st.data_editor(base, use_container_width=True, hide_index=True, key=key, disabled=['Entidad', 'Datos teóricos', 'Cumplimiento %'], column_config={'Datos teóricos': st.column_config.NumberColumn(format='%.2f'), 'Datos cargados': st.column_config.NumberColumn(min_value=0.0, step=1.0, format='%.2f'), 'Cumplimiento %': st.column_config.NumberColumn(format='%.1f%%')})
        if st.button('Guardar datos cargados y calcular cumplimiento', key=key + '_guardar', type='primary'):
            c = transaccion()
            cur = c.cursor()
            try:
                for _, r in editado.iterrows():
                    cur.execute(operacion_tabla('INTERFAZ_0034'), (tipo_entidad, str(r['Entidad']), periodo_tipo, periodo_clave, float(r['Datos cargados'] or 0), st.session_state.auth['usuario'], now_iso()))
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()
            audit(st.session_state.auth['usuario'], 'ACTUALIZAR_DATOS_CARGADOS_SPAC', f'{tipo_entidad} | {periodo_tipo} | {periodo_clave}')
            st.success('Datos cargados guardados. Cumplimiento recalculado.')
            st.rerun()
    else:
        vista = base.copy()
        vista['Cumplimiento %'] = vista['Cumplimiento %'].map(lambda x: '' if pd.isna(x) else f'{x:.1f}%')
        st.dataframe(vista, use_container_width=True, hide_index=True)

def tabla_diaria_editable(tabla, tipo_entidad, columna_entidad, key):
    """Tabla unica: vacios rojos y edicion directa para desarrolladores."""
    vista = tabla.reset_index().rename(columns={tabla.index.name or 'index': columna_entidad})
    if not is_dev():
        st.dataframe(estilo_faltantes_matriz(vista), use_container_width=True, hide_index=True)
        return
    editable = vista.copy()
    columnas_valor = [c for c in editable.columns if c != columna_entidad]
    for c in columnas_valor:
        editable[c] = editable[c].map(lambda v: '🟥' if pd.isna(v) or str(v).strip() == '' else str(float(v)))
    st.caption('Edicion directa habilitada. La casilla 🟥 indica que falta el registro. Sustituye la casilla por 0 para justificar un dia sin carga o por el valor correspondiente.')
    editado = st.data_editor(editable, use_container_width=True, hide_index=True, key=key, disabled=[columna_entidad], num_rows='fixed', column_config={columna_entidad: st.column_config.TextColumn(columna_entidad, disabled=True), **{c: st.column_config.TextColumn(c) for c in columnas_valor}})
    if st.button('Guardar ajustes diarios', key=key + '_guardar', type='primary'):
        errores = []
        cambios = []
        for _, r in editado.iterrows():
            entidad = str(r[columna_entidad])
            for fecha_columna in columnas_valor:
                texto = str(r[fecha_columna] or '').strip()
                if texto in ('', '🟥'):
                    valor = None
                else:
                    try:
                        valor = float(texto.replace(',', '.'))
                    except ValueError:
                        errores.append(f'{entidad} / {fecha_columna}')
                        continue
                    if valor < 0:
                        errores.append(f'{entidad} / {fecha_columna}')
                        continue
                original = tabla.loc[entidad, fecha_columna] if entidad in tabla.index and fecha_columna in tabla.columns else None
                igual = valor is None and pd.isna(original) or (valor is not None and pd.notna(original) and (float(valor) == float(original)))
                if not igual:
                    cambios.append((entidad, fecha_columna, valor))
        if errores:
            st.error('Corrige los valores no numericos o negativos en: ' + ', '.join(errores) + '.')
        else:
            c = transaccion()
            cur = c.cursor()
            try:
                for entidad, fecha_columna, valor in cambios:
                    if valor is None:
                        cur.execute(operacion_tabla('INTERFAZ_0035'), (tipo_entidad, entidad, fecha_columna))
                    else:
                        cur.execute(operacion_tabla('INTERFAZ_0036'), (tipo_entidad, entidad, fecha_columna, float(valor), 'Ajuste administrativo', st.session_state.auth['usuario'], now_iso()))
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()
            audit(st.session_state.auth['usuario'], 'AJUSTAR_MATRIZ_DIARIA_SPAC', tipo_entidad)
            st.success('Ajustes diarios guardados correctamente.')
            st.rerun()

def editor_seguimiento_dinamico(bloque, key):
    campos = bloque.get('campos', [])
    if not campos:
        st.info('Este seguimiento no tiene campos activos. Un administrador puede configurarlos desde Catálogos.')
        return (pd.DataFrame(), {})
    base = pd.DataFrame([{c['nombre']: '' for c in campos} for _ in range(3)])
    config = {}
    for c in campos:
        nombre = c['nombre']
        tipo = c['tipo']
        opciones = c.get('opciones', [])
        if tipo == 'Lista desplegable':
            config[nombre] = st.column_config.SelectboxColumn(nombre, options=[''] + opciones, required=c['obligatorio'])
        elif tipo == 'Número':
            config[nombre] = st.column_config.NumberColumn(nombre, min_value=0.0, step=1.0, required=c['obligatorio'])
        elif tipo == 'Sí / No / N/A':
            config[nombre] = st.column_config.SelectboxColumn(nombre, options=['', 'Sí', 'No', 'N/A'], required=c['obligatorio'])
        elif tipo == 'Fecha':
            config[nombre] = st.column_config.DateColumn(nombre, required=c['obligatorio'])
        else:
            config[nombre] = st.column_config.TextColumn(nombre, required=c['obligatorio'])
    return (st.data_editor(base, num_rows='dynamic', use_container_width=True, hide_index=True, key=key, column_config=config), {c['nombre']: c for c in campos})

def matriz_entregas():
    st.markdown('## Entregas de turno y matriz histórica')
    st.caption('Consulta los registros de las tres naves. Selecciona un registro para descargar su reporte en PDF.')
    df = consultar(operacion_tabla('INTERFAZ_0037'))
    if df.empty:
        st.info('Todavía no hay entregas de turno registradas.')
        return
    df['fecha_dt'] = pd.to_datetime(df['fecha'], errors='coerce').dt.date
    validas = df['fecha_dt'].dropna()
    if validas.empty:
        st.warning('Los registros existentes no contienen fechas válidas.')
        return
    mn, mx = (min(validas), max(validas))
    a, b, c = st.columns(3)
    desde = a.date_input('Fecha inicial', mn, min_value=mn, max_value=mx, key='mx_desde')
    hasta = b.date_input('Fecha final', mx, min_value=mn, max_value=mx, key='mx_hasta')
    naves = c.multiselect('Nave', ['Nave 1', 'Nave 2', 'Nave 3'], key='mx_naves')
    if desde > hasta:
        st.error('La fecha inicial no puede ser posterior a la fecha final.')
        return
    nombres = sorted(df['analista'].dropna().astype(str).unique())
    analistas = st.multiselect('Analista', nombres, key='mx_names')
    f = df[(df['fecha_dt'] >= desde) & (df['fecha_dt'] <= hasta)].copy()
    if naves:
        f = f[f['nave'].isin(naves)]
    if analistas:
        f = f[f['analista'].isin(analistas)]
    if f.empty:
        st.info('No existen registros para los filtros seleccionados.')
        return
    vista = f[['id', 'entrega_id', 'fecha', 'nave', 'turno', 'analista', 'total_carga_datos', 'horas_nave1', 'horas_nave2', 'horas_nave3']].copy()
    vista['PDF'] = 'Disponible'
    vista = vista.rename(columns={'id': 'ID matriz', 'entrega_id': 'Registro', 'fecha': 'Fecha', 'nave': 'Nave', 'turno': 'Turno', 'analista': 'Analista', 'total_carga_datos': 'Total carga', 'horas_nave1': 'Horas Nave 1', 'horas_nave2': 'Horas Nave 2', 'horas_nave3': 'Horas Nave 3'})
    nonce = st.session_state.get('mx_table_nonce', 0)
    evento = st.dataframe(vista, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'mx_table_{nonce}', column_config={'PDF': st.column_config.TextColumn('PDF del registro', help='Selecciona la fila para descargar el PDF.')})
    excel_df = f[['fecha', 'nave', 'turno', 'analista', 'total_carga_datos', 'horas_nave1', 'horas_nave2', 'horas_nave3']].copy()
    st.download_button('Descargar matriz en Excel', excel_matriz(excel_df), f'matriz_entregas_{desde}_{hasta}.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key='mx_excel')
    rows = getattr(evento, 'selection', {}).get('rows', []) if evento is not None else []
    valida = bool(rows) and isinstance(rows[0], int) and (0 <= rows[0] < len(vista))
    if valida:
        seleccion = vista.iloc[rows[0]]
        rid = int(seleccion['ID matriz'])
        coincidencia = f[f['id'] == rid]
        if not coincidencia.empty:
            row = coincidencia.iloc[0]
            eid = int(row['entrega_id']) if pd.notna(row['entrega_id']) else None
            st.markdown(f"### Registro seleccionado: {eid or 'Sin número'} | {row['fecha']} | {row['nave']} | {row['analista']}")
            if eid:
                contenido_pdf = pdf_entrega(eid)
                if contenido_pdf:
                    st.download_button('Descargar PDF de este registro', contenido_pdf, f"entrega_turno_{eid}_{row['fecha']}.pdf", 'application/pdf', key=f'mx_pdf_{rid}_{eid}')
                else:
                    st.warning('No fue posible generar el PDF. Verifica que reportlab esté incluido en requirements.txt.')
            else:
                st.warning('Este indicador no tiene una entrega de turno relacionada.')
            if is_dev() and st.button('Eliminar registro seleccionado', key=f'mx_del_{rid}'):
                st.session_state.mx_confirm = rid
            if is_dev() and st.session_state.get('mx_confirm') == rid:
                st.warning('Se eliminarán de forma permanente la matriz y la entrega de turno relacionadas. Esta acción no se puede deshacer.')
                x, y = st.columns(2)
                if x.button('Confirmar eliminación', key=f'mx_ok_{rid}'):
                    cdb = transaccion()
                    cur = cdb.cursor()
                    try:
                        if eid:
                            cur.execute(operacion_tabla('INTERFAZ_0038'), (eid,))
                            cur.execute(operacion_tabla('INTERFAZ_0039'), (eid,))
                            cur.execute(operacion_tabla('INTERFAZ_0040'), (eid,))
                        cur.execute(operacion_tabla('INTERFAZ_0041'), (rid,))
                        cdb.commit()
                    except Exception:
                        cdb.rollback()
                        raise
                    finally:
                        cdb.close()
                    audit(st.session_state.auth['usuario'], 'ELIMINAR_DIA_MATRIZ', f'Matriz {rid} | Entrega {eid}')
                    st.session_state.pop('mx_confirm', None)
                    st.session_state.mx_table_nonce = nonce + 1
                    st.rerun()
                if y.button('Cancelar', key=f'mx_cancel_{rid}'):
                    st.session_state.pop('mx_confirm', None)
                    st.session_state.mx_table_nonce = nonce + 1
                    st.rerun()
    elif rows:
        st.session_state.mx_table_nonce = nonce + 1
        st.rerun()
    st.markdown('### Matrices por fecha y analista')
    for campo, titulo in [('total_carga_datos', 'Total de carga de datos'), ('horas_nave1', 'Horas trabajadas Nave 1'), ('horas_nave2', 'Horas trabajadas Nave 2'), ('horas_nave3', 'Horas trabajadas Nave 3')]:
        st.markdown(f'**{titulo}**')
        st.dataframe(f.pivot_table(index='analista', columns='fecha', values=campo, aggfunc='sum', fill_value=0), use_container_width=True)
    st.markdown('## Control diario de datos SPAC')
    st.caption('Analistas: TOTAL DE CARGA DE DATOS. Naves: suma diaria de Horas Nave 1, Horas Nave 2 y Horas Nave 3. Las celdas rojas vacías indican ausencia de registro.')
    columnas_fecha = [x.date().isoformat() for x in pd.date_range(desde, hasta, freq='D')]
    analistas_catalogo = catalog('analista')
    datos_rango = df[(df['fecha_dt'] >= desde) & (df['fecha_dt'] <= hasta)].copy()
    pa = datos_rango.pivot_table(index='analista', columns='fecha', values='total_carga_datos', aggfunc='sum').reindex(index=analistas_catalogo, columns=columnas_fecha)
    pa.index.name = 'Analista'
    pa = aplicar_ajustes_diarios(pa, 'ANALISTA', 'Analista')
    st.markdown('### TOTAL DE CARGA DE DATOS diario por analista')
    tabla_diaria_editable(pa, 'ANALISTA', 'Analista', 'tabla_diaria_analistas')
    calidad_diaria = datos_rango.pivot_table(index='nave', columns='fecha', values='total_carga_datos', aggfunc='sum').reindex(index=['Nave 1', 'Nave 2', 'Nave 3'], columns=columnas_fecha)
    calidad_diaria.index.name = 'Nave'
    calidad_diaria = aplicar_ajustes_diarios(calidad_diaria, 'CALIDAD_NAVE', 'Nave')
    st.markdown('### TOTAL DE CARGA DE DATOS diario por plantilla')
    st.caption('Suma el TOTAL DE CARGA DE DATOS segun la plantilla utilizada: Nave 1, Nave 2 o Nave 3.')
    tabla_diaria_editable(calidad_diaria, 'CALIDAD_NAVE', 'Nave', 'tabla_diaria_calidad_naves')
    filas_nave = []
    for nv, campo in [('Nave 1', 'horas_nave1'), ('Nave 2', 'horas_nave2'), ('Nave 3', 'horas_nave3')]:
        serie = datos_rango.groupby('fecha')[campo].sum(min_count=1).reindex(columnas_fecha)
        fila = {'Nave': nv}
        fila.update({f: float(serie.get(f)) if pd.notna(serie.get(f)) and float(serie.get(f)) > 0 else None for f in columnas_fecha})
        filas_nave.append(fila)
    pn = pd.DataFrame(filas_nave, columns=['Nave'] + columnas_fecha).set_index('Nave')
    pn = aplicar_ajustes_diarios(pn, 'NAVE', 'Nave')
    st.markdown('### Horas diarias consolidadas por nave')
    tabla_diaria_editable(pn, 'NAVE', 'Nave', 'tabla_diaria_naves')
    st.markdown('## Datos teóricos, datos cargados y cumplimiento SPAC')
    st.info('Fórmula: Cumplimiento (%) = Datos cargados ÷ Datos teóricos × 100. Los datos teóricos provienen de los registros y ajustes diarios. Los datos cargados se capturan manualmente.')
    pt = st.radio('Periodo de evaluación', ['SEMANA', 'MES'], horizontal=True, format_func=lambda x: 'Semana' if x == 'SEMANA' else 'Mes', key='meta_periodo_tipo')
    opciones = []
    for x in pd.date_range(desde, hasta, freq='D').date:
        k = clave_periodo(x, pt)
        if k not in opciones:
            opciones.append(k)
    pc = st.selectbox('Semana o mes', opciones, key='meta_periodo_clave')
    if pt == 'SEMANA':
        anio, semana = pc.split('-S')
        inicio = date.fromisocalendar(int(anio), int(semana), 1)
        fin = date.fromisocalendar(int(anio), int(semana), 7)
    else:
        inicio = datetime.strptime(pc + '-01', '%Y-%m-%d').date()
        fin = (pd.Timestamp(inicio) + pd.offsets.MonthBegin(1)).date() - timedelta(days=1)
    dp = df[(df['fecha_dt'] >= inicio) & (df['fecha_dt'] <= fin)].copy()
    fechas_meta = [x.date().isoformat() for x in pd.date_range(inicio, fin, freq='D')]
    pa_meta = dp.pivot_table(index='analista', columns='fecha', values='total_carga_datos', aggfunc='sum').reindex(index=analistas_catalogo, columns=fechas_meta)
    pa_meta.index.name = 'Analista'
    pa_meta = aplicar_ajustes_diarios(pa_meta, 'ANALISTA', 'Analista')
    teoricos_a = pa_meta.fillna(0).sum(axis=1).to_dict()
    filas_meta = []
    for nv, campo in [('Nave 1', 'horas_nave1'), ('Nave 2', 'horas_nave2'), ('Nave 3', 'horas_nave3')]:
        serie = dp.groupby('fecha')[campo].sum(min_count=1).reindex(fechas_meta)
        filas_meta.append([float(v) if pd.notna(v) and float(v) > 0 else None for v in serie])
    pn_meta = pd.DataFrame(filas_meta, index=['Nave 1', 'Nave 2', 'Nave 3'], columns=fechas_meta)
    pn_meta.index.name = 'Nave'
    pn_meta = aplicar_ajustes_diarios(pn_meta, 'NAVE', 'Nave')
    teoricos_n = pn_meta.fillna(0).sum(axis=1).to_dict()
    calidad_meta = dp.pivot_table(index='nave', columns='fecha', values='total_carga_datos', aggfunc='sum').reindex(index=['Nave 1', 'Nave 2', 'Nave 3'], columns=fechas_meta)
    calidad_meta.index.name = 'Nave'
    calidad_meta = aplicar_ajustes_diarios(calidad_meta, 'CALIDAD_NAVE', 'Nave')
    teoricos_calidad = calidad_meta.fillna(0).sum(axis=1).to_dict()
    ca, cn = st.columns(2)
    with ca:
        st.markdown('### Cumplimiento por analista')
        editor_metas_cumplimiento('ANALISTA', analistas_catalogo, teoricos_a, pt, pc, f'meta_a_{pt}_{pc}')
    with cn:
        st.markdown('### Indicador SPAC Produccion')
        editor_metas_cumplimiento('NAVE', ['Nave 1', 'Nave 2', 'Nave 3'], teoricos_n, pt, pc, f'meta_n_{pt}_{pc}')
    st.markdown('### Indicador SPAC Calidad')
    editor_metas_cumplimiento('CALIDAD_NAVE', ['Nave 1', 'Nave 2', 'Nave 3'], teoricos_calidad, pt, pc, f'meta_calidad_{pt}_{pc}')

def page_registro():
    if 'registro_tipo' not in st.session_state:
        st.session_state.registro_tipo = None
    if 'form_nonce' not in st.session_state:
        st.session_state.form_nonce = 0
    flash = st.session_state.pop('flash_registro_guardado', None)
    if flash:
        st.success(flash)

    def limpiar_form():
        st.session_state.form_nonce += 1

    def volver_selector():
        st.session_state.registro_tipo = None
        st.rerun()

    def selector():
        st.markdown('<div class="registro-landing-hero"><div class="registro-landing-title">Nuevo registro</div><div class="registro-landing-subtitle">Selecciona el tipo de registro que deseas capturar.</div></div>', unsafe_allow_html=True)
        tarjetas = [('PNC', '📝  **PNC´s**\n\nCaptura y seguimiento de producto no conforme.\n\n*Abrir registro*', 'card_pnc'), ('ME', '🧲  **Materia Extraña**\n\nRegistro de hallazgos y acciones de contención.\n\n*Abrir registro*', 'card_me'), ('DDM_RX', '📦  **Detector de metales y RX**\n\nControl de producto segregado por detección.\n\n*Abrir registro*', 'card_ddm'), ('RECLAMOS', '📣  **Reclamos**\n\nRegistro, investigación y seguimiento de reclamos.\n\n*Abrir registro*', 'card_reclamos'), ('DEVOLUCIONES', '↩️  **Devoluciones**\n\nRegistro y seguimiento de producto devuelto.\n\n*Abrir registro*', 'card_devoluciones')]
        for inicio in range(0, len(tarjetas), 3):
            lote = tarjetas[inicio:inicio + 3]
            if len(lote) == 2:
                columnas = st.columns([0.5, 1, 1, 0.5], gap='large')[1:3]
            else:
                columnas = st.columns(3, gap='large')
            for columna, (valor, texto, clave) in zip(columnas, lote):
                with columna:
                    st.markdown('<span class="registro-card-slot"></span>', unsafe_allow_html=True)
                    if st.button(texto, key=clave):
                        st.session_state.registro_tipo = valor
                        st.rerun()

    def form_hallazgo(tabla, titulo, audit_action):
        nonce = st.session_state.form_nonce
        st.markdown(f'<div class="registro-full-panel"><div class="registro-pill">Nuevo registro</div><div class="registro-full-title">{titulo}</div><div class="registro-full-subtitle">Los campos marcados con * son obligatorios.</div>', unsafe_allow_html=True)
        if st.button('← Cambiar tipo de registro', key=f'volver_{tabla}'):
            volver_selector()
        st.markdown('<div class="registro-form-shell">', unsafe_allow_html=True)
        prod = consultar(operacion_tabla('INTERFAZ_0042'))
        defs = consultar(operacion_tabla('INTERFAZ_0043'))
        opt_prod = [''] + [f'{r.item} | {r.descripcion}' for r in prod.itertuples()]
        opt_defs = [''] + [f'{r.codigo} | {r.defecto}' for r in defs.itertuples()]
        with st.container():
            a, b, c = st.columns(3)
            fecha = a.date_input('Fecha *', value=date.today(), key=f'fecha_{tabla}_{nonce}')
            semana = b.number_input('Semana *', min_value=1, max_value=53, value=int(date.today().isocalendar().week), step=1, key=f'semana_{tabla}_{nonce}')
            nave = c.selectbox('Nave *', opt_blank(catalog('nave')), key=f'nave_{tabla}_{nonce}')
            a, b, c = st.columns(3)
            opt = a.selectbox('ITEM *', opt_prod, key=f'item_{tabla}_{nonce}')
            item = opt.split('|')[0].strip() if opt else ''
            row = prod[prod['item'] == item].iloc[0] if item and item in prod['item'].values else None
            producto = str(row['descripcion']) if row is not None else ''
            cliente = str(row['cliente']) if row is not None else ''
            familia = str(row['familia']) if row is not None else ''
            lote = b.text_input('Lote *', key=f'lote_{tabla}_{nonce}')
            c.empty()
            a, b, c = st.columns(3)
            a.text_input('Descripción', value=producto, disabled=True)
            b.text_input('Cliente', value=cliente, disabled=True)
            c.text_input('Familia', value=familia, disabled=True)
            linea_sector = st.selectbox('Línea/Sector *', opt_blank(catalog('linea_sector')), key=f'linea_{tabla}_{nonce}')
            a, b, c = st.columns(3)
            optd = a.selectbox('Código / Defecto *', opt_defs, key=f'codigo_{tabla}_{nonce}')
            codigo = optd.split('|')[0].strip() if optd else ''
            dr = defs[defs['codigo'] == codigo].iloc[0] if codigo and codigo in defs['codigo'].values else None
            defecto = str(dr['defecto']) if dr is not None else ''
            tipo_defecto = str(dr['tipo_defecto']) if dr is not None else ''
            categoria = str(dr['clasificacion']) if dr is not None else ''
            b.text_input('Defecto', value=defecto, disabled=True)
            c.text_input('Tipo de defecto', value=tipo_defecto, disabled=True)
            x1, x2 = st.columns(2)
            x1.text_input('Clasificación *', value=categoria, disabled=True)
            turno = x2.selectbox('Turno *', opt_blank(catalog('turno')), key=f'turno_{tabla}_{nonce}')
            a, b, c = st.columns(3)
            supervisor = a.selectbox('Supervisor (Responsable) *', opt_blank(catalog('supervisor')), key=f'sup_{tabla}_{nonce}')
            analista = b.selectbox('Analista (Persona que detecta) *', opt_blank(catalog('analista')), key=f'ana_{tabla}_{nonce}')
            c.empty()
            descripcion = st.text_area('Descripción del defecto *', key=f'desc_{tabla}_{nonce}')
            acciones = st.text_area('Acciones inmediatas *', key=f'accion_{tabla}_{nonce}')
            a, b, c = st.columns(3)
            a.empty()
            b.empty()
            c.empty()
            a, b, c = st.columns(3)
            equipo = a.text_input('Equipo en donde se tiene el hallazgo', key=f'equipo_{tabla}_{nonce}')
            tipo = b.selectbox('Tipo', opt_blank(['Metal', 'Plástico duro', 'Plástico blando', 'Vidrio', 'Madera', 'Papel/Cartón', 'Cabello', 'Insecto', 'Otro']), key=f'tipo_{tabla}_{nonce}')
            particulas = c.number_input('# de partículas halladas', min_value=0, step=1, key=f'part_{tabla}_{nonce}')
            sector_hallazgo = ''
            ubicacion_material = ''
            if tabla == 'ddm_rx_registros':
                d1, d2 = st.columns(2)
                sector_hallazgo = d1.selectbox('Sector del hallazgo', ['', 'CONFORMADO', 'ENVOLTURA', 'EMPAQUE'], key=f'sector_hallazgo_{tabla}_{nonce}')
                ubicacion_material = d2.selectbox('Ubicación del material', ['', 'MASA', 'RELLENO', 'RECUBIERTO'], key=f'ubicacion_material_{tabla}_{nonce}')
            investigacion = st.text_area('Investigación del origen', key=f'inv_{tabla}_{nonce}')
            evitar = st.text_area('Acciones a realizar para evitar la incidencia', key=f'evitar_{tabla}_{nonce}')
            ok = st.button('Guardar registro', key=f'guardar_{tabla}_{nonce}', type='primary')
        if ok:
            obligatorios = {'Línea/Sector': linea_sector, 'Nave': nave, 'ITEM': item, 'Descripción': producto, 'Cliente': cliente, 'Familia': familia, 'Lote': lote, 'Código': codigo, 'Defecto': defecto, 'Tipo de defecto': tipo_defecto, 'Semana': semana, 'Turno': turno, 'Fecha': fecha, 'Supervisor': supervisor, 'Analista': analista, 'Descripción del hallazgo': descripcion, 'Acciones inmediatas': acciones, 'Categoría inicial': categoria}
            faltantes = [k for k, v in obligatorios.items() if v is None or (isinstance(v, str) and (not v.strip()))]
            if faltantes:
                st.error('Completa los siguientes campos obligatorios: ' + ', '.join(faltantes) + '.')
            else:
                rid = crear(operacion_tabla('INTERFAZ_0044', tabla), (fecha.day, fecha.month, fecha.year, nave, linea_sector, familia, equipo, item, producto, lote, descripcion, tipo, int(particulas), acciones, investigacion, analista, supervisor, evitar, st.session_state.auth['usuario'], now_iso(), '', codigo, int(semana), turno, '', acciones, '', 0.0, '', categoria, sector_hallazgo, ubicacion_material))
                audit(st.session_state.auth['usuario'], audit_action, f'ID {rid}')
                limpiar_form()
                st.session_state.flash_registro_guardado = f'Registro guardado correctamente: Número {rid}'
                st.rerun()
        st.markdown('</div></div>', unsafe_allow_html=True)

    def form_devoluciones():
        nonce = st.session_state.form_nonce
        st.markdown('<div class="registro-full-panel"><div class="registro-pill">Nuevo registro</div><div class="registro-full-title">↩️ Devoluciones</div><div class="registro-full-subtitle">Los campos marcados con * son obligatorios. Producto y cliente se completan desde el catálogo vigente.</div>', unsafe_allow_html=True)
        if st.button('← Cambiar tipo de registro', key='volver_devoluciones'):
            volver_selector()
        st.markdown('<div class="registro-form-shell">', unsafe_allow_html=True)
        prod = consultar(operacion_tabla('INTERFAZ_0045'))
        defs = consultar(operacion_tabla('INTERFAZ_0046'))
        opt_prod = [''] + [f'{r.item} | {r.descripcion}' for r in prod.itertuples()]
        opt_defs = [''] + [f'{r.codigo} | {r.defecto}' for r in defs.itertuples()]
        a, b, c = st.columns(3)
        fecha = a.date_input('Fecha *', date.today(), key=f'dev_fecha_{nonce}')
        od = b.selectbox('Código / Defecto *', opt_defs, key=f'dev_def_{nonce}')
        cedis = c.text_input('Cedis *', key=f'dev_cedis_{nonce}')
        codigo = od.split('|')[0].strip() if od else ''
        dr = defs[defs.codigo.astype(str) == codigo].iloc[0] if codigo and codigo in defs.codigo.astype(str).values else None
        defecto = '' if dr is None else str(dr.defecto)
        a, b, c = st.columns(3)
        pais_estado = a.text_input('País / Estado *', key=f'dev_pais_{nonce}')
        op = b.selectbox('ITEM *', opt_prod, key=f'dev_item_{nonce}')
        item = op.split('|')[0].strip() if op else ''
        pr = prod[prod.item.astype(str) == item].iloc[0] if item and item in prod.item.astype(str).values else None
        producto = '' if pr is None or pd.isna(pr.descripcion) else str(pr.descripcion).strip()
        cliente = '' if pr is None or pd.isna(pr.cliente) else str(pr.cliente).strip()
        familia = '' if pr is None or pd.isna(pr.familia) else str(pr.familia).strip()
        c.text_input('Producto', producto, disabled=True, key=f"dev_producto_{nonce}_{item or 'sin_item'}")
        a, b, c = st.columns(3)
        a.text_input('Cliente', cliente, disabled=True, key=f"dev_cliente_{nonce}_{item or 'sin_item'}")
        b.text_input('Familia', value=familia, disabled=True, key=f"dev_familia_{nonce}_{item or 'sin_item'}")
        lote = c.text_input('Lote *', key=f'dev_lote_{nonce}')
        a, b, c = st.columns(3)
        caducidad = a.text_input('Caducidad *', key=f'dev_cad_{nonce}')
        comprobado = b.selectbox('Comprobado *', ['', 'Sí', 'No'], key=f'dev_comp_{nonce}')
        cantidad = c.number_input('Cant. afectada *', min_value=0.0, step=1.0, format='%.2f', key=f'dev_cant_{nonce}')
        descripcion = st.text_area('Descripción de la devolución *', key=f'dev_desc_{nonce}')
        a, b, c = st.columns(3)
        unidad = a.selectbox('Unidad *', ['', 'Bulto', 'Bolsa', 'Pieza', 'Tarima'], key=f'dev_unidad_{nonce}')
        sector = b.text_input('Sector *', key=f'dev_sector_{nonce}')
        disposicion = c.selectbox('Disposición *', opt_blank(catalog('disposicion')), key=f'dev_disp_{nonce}')
        a, b, c = st.columns(3)
        tsp = a.text_input('TSP N°', key=f'dev_tsp_{nonce}')
        status = b.selectbox('Status *', ['', 'Cerrado', 'Abierto'], key=f'dev_status_{nonce}')
        nave = c.selectbox('Nave *', opt_blank(catalog('nave')), key=f'dev_nave_{nonce}')
        if st.button('Guardar registro', key=f'guardar_dev_{nonce}', type='primary'):
            req = {'Fecha': fecha, 'Código / Defecto': codigo, 'Cedis': cedis, 'País / Estado': pais_estado, 'ITEM': item, 'Producto': producto, 'Cliente': cliente, 'Familia': familia, 'Lote': lote, 'Caducidad': caducidad, 'Descripción del defecto': descripcion, 'Comprobado': comprobado, 'Cant. afectada': cantidad, 'Unidad': unidad, 'Sector': sector, 'Disposición': disposicion, 'Status': status, 'Nave': nave}
            faltan = [k for k, v in req.items() if v is None or (isinstance(v, str) and (not v.strip())) or (k == 'Cant. afectada' and float(v) <= 0)]
            if faltan:
                st.error('Completa los siguientes campos obligatorios: ' + ', '.join(faltan) + '.')
            else:
                rid = crear(operacion_tabla('INTERFAZ_0047'), (fecha.isoformat(), codigo, defecto, cedis.strip(), pais_estado.strip(), item, producto, cliente, '', familia, lote.strip(), caducidad.strip(), descripcion.strip(), comprobado, float(cantidad), unidad, sector.strip(), disposicion, tsp.strip(), status, nave, st.session_state.auth['usuario'], now_iso()))
                audit(st.session_state.auth['usuario'], 'CREAR_DEVOLUCION', f'ID {rid}')
                limpiar_form()
                st.session_state.flash_registro_guardado = f'Devolución guardada correctamente: Número {rid}'
                st.rerun()
        st.markdown('</div></div>', unsafe_allow_html=True)

    def form_reclamos():
        nonce = st.session_state.form_nonce
        st.markdown('<div class="registro-full-panel"><div class="registro-pill">Nuevo registro</div><div class="registro-full-title">📣 Reclamos</div><div class="registro-full-subtitle">Los campos marcados con * son obligatorios. Producto, cliente, familia y datos del defecto se completan desde los catálogos vigentes.</div>', unsafe_allow_html=True)
        if st.button('← Cambiar tipo de registro', key='volver_reclamos'):
            volver_selector()
        st.markdown('<div class="registro-form-shell">', unsafe_allow_html=True)
        prod = consultar(operacion_tabla('INTERFAZ_0048'))
        defs = consultar(operacion_tabla('INTERFAZ_0049'))
        opt_prod = [''] + [f'{r.item} | {r.descripcion}' for r in prod.itertuples()]
        opt_defs = [''] + [f'{r.codigo} | {r.defecto}' for r in defs.itertuples()]
        a, b, c = st.columns(3)
        fecha = a.date_input('Fecha *', date.today(), key=f'recl_fecha_{nonce}')
        od = b.selectbox('Código / Defecto *', opt_defs, key=f'recl_def_{nonce}')
        codigo = od.split('|')[0].strip() if od else ''
        dr = defs[defs.codigo.astype(str) == codigo].iloc[0] if codigo and codigo in defs.codigo.astype(str).values else None
        defecto = str(dr.defecto) if dr is not None else ''
        tipo_defecto = str(dr.tipo_defecto) if dr is not None else ''
        clasificacion = str(dr.clasificacion) if dr is not None else ''
        fuente = c.text_input('Fuente *', key=f'recl_fuente_{nonce}')
        a, b, c = st.columns(3)
        a.text_input('Descripción del defecto', defecto, disabled=True)
        b.text_input('Tipo de defecto', tipo_defecto, disabled=True)
        c.text_input('Clasificación del defecto', clasificacion, disabled=True)
        a, b, c = st.columns(3)
        mercado = a.selectbox('Mercado *', ['', 'Interno', 'Externo'], key=f'recl_mercado_{nonce}')
        pais_estado = b.text_input('País / Estado *', key=f'recl_pais_{nonce}')
        numero_caso = c.text_input('No. Caso Right Now / MDLZ *', key=f'recl_caso_{nonce}')
        a, b, c = st.columns(3)
        op = a.selectbox('ITEM *', opt_prod, key=f'recl_item_{nonce}')
        item = op.split('|')[0].strip() if op else ''
        pr = prod[prod.item.astype(str) == item].iloc[0] if item and item in prod.item.astype(str).values else None
        producto = str(pr.descripcion) if pr is not None else ''
        cliente = str(pr.cliente) if pr is not None else ''
        familia = '' if pr is None or pd.isna(pr.familia) else str(pr.familia).strip()
        b.text_input('Producto', producto, disabled=True)
        c.text_input('Cliente', cliente, disabled=True)
        st.text_input('Familia', value=familia, disabled=True, key=f"recl_familia_{nonce}_{item or 'sin_item'}")
        descripcion_reclamo = st.text_area('Descripción del reclamo *', key=f'recl_desc_{nonce}')
        causa_raiz = st.text_area('Causa raíz del defecto *', key=f'recl_causa_{nonce}')
        acciones = st.text_area('Acciones correctivas y contingentes *', key=f'recl_acciones_{nonce}')
        a, b, c = st.columns(3)
        comprobado = a.selectbox('Comprobado *', ['', 'Sí', 'No'], key=f'recl_comp_{nonce}')
        cantidad = b.number_input('Cantidad afectada *', 0.0, step=1.0, format='%.2f', key=f'recl_cant_{nonce}')
        unidad = c.selectbox('Unidad *', ['', 'Bulto', 'Bolsa', 'Pieza', 'Lámina'], key=f'recl_unidad_{nonce}')
        a, b, c = st.columns(3)
        sector = a.text_input('Sector *', key=f'recl_sector_{nonce}')
        estado = b.selectbox('Estado del reclamo *', ['', 'Abierto', 'Cerrado'], key=f'recl_estado_{nonce}')
        fecha_cierre = c.date_input('Fecha de cierre', value=None, key=f'recl_cierre_{nonce}')
        a, b, c = st.columns(3)
        tsp = a.text_input('TSP N°', key=f'recl_tsp_{nonce}')
        caducidad = b.text_input('Caducidad', key=f'recl_cad_{nonce}', placeholder='Llenado libre')
        lote = c.text_input('Lote *', key=f'recl_lote_{nonce}')
        a, b, c = st.columns(3)
        nave = a.selectbox('Nave *', opt_blank(catalog('nave')), key=f'recl_nave_{nonce}')
        pmd = b.selectbox('P / M / D *', ['', '1 - Manipulación', '2 - Producción', '3 - Diseño'], key=f'recl_pmd_{nonce}')
        red_social = c.selectbox('Red social *', ['', 'Mail', 'Web', 'Instagram', 'No indica', 'Facebook'], key=f'recl_red_{nonce}')
        if st.button('Guardar registro', key=f'guardar_reclamos_{nonce}', type='primary'):
            req = {'Código / Defecto': codigo, 'Descripción del defecto': defecto, 'Fuente': fuente, 'Mercado': mercado, 'País / Estado': pais_estado, 'No. Caso Right Now / MDLZ': numero_caso, 'ITEM': item, 'Producto': producto, 'Cliente': cliente, 'Familia': familia, 'Descripción del reclamo': descripcion_reclamo, 'Causa raíz': causa_raiz, 'Acciones correctivas y contingentes': acciones, 'Comprobado': comprobado, 'Cantidad afectada': cantidad, 'Unidad': unidad, 'Sector': sector, 'Estado': estado, 'Lote': lote, 'Nave': nave, 'P / M / D': pmd, 'Tipo de defecto': tipo_defecto, 'Clasificación': clasificacion, 'Red social': red_social}
            faltan = [k for k, v in req.items() if v is None or (isinstance(v, str) and (not v.strip())) or (k == 'Cantidad afectada' and float(v) <= 0)]
            duplicado = not consultar(operacion_tabla('INTERFAZ_0050'), (numero_caso,)).empty if numero_caso.strip() else False
            if duplicado:
                st.error('Registro repetido. Ya existe un reclamo con el mismo No. Caso Right Now / MDLZ. Corrige el número de caso o edita el registro existente.')
            elif faltan:
                st.error('Completa los siguientes campos obligatorios: ' + ', '.join(dict.fromkeys(faltan)) + '.')
            elif estado == 'Cerrado' and (not fecha_cierre):
                st.error('Captura la fecha de cierre para el reclamo cerrado.')
            elif fecha_cierre and fecha_cierre < fecha:
                st.error('La fecha de cierre no puede ser anterior a la fecha del reclamo.')
            else:
                try:
                    rid = crear(operacion_tabla('INTERFAZ_0051'), (fecha.isoformat(), codigo, defecto, fuente.strip(), mercado.strip(), pais_estado.strip(), numero_caso.strip(), item, producto, cliente, familia, descripcion_reclamo.strip(), causa_raiz.strip(), acciones.strip(), comprobado, float(cantidad), unidad, sector.strip(), estado, fecha_cierre.isoformat() if fecha_cierre else None, tsp.strip(), caducidad.strip(), lote.strip(), nave, pmd, tipo_defecto, clasificacion, red_social, st.session_state.auth['usuario'], now_iso()))
                    audit(st.session_state.auth['usuario'], 'CREAR_RECLAMO', f'ID {rid} | Caso {numero_caso.strip()}')
                    limpiar_form()
                    st.session_state.flash_registro_guardado = f'Reclamo guardado correctamente: Número {rid}'
                    st.rerun()
                except ErrorIntegridad:
                    st.error('No fue posible guardar el reclamo porque existe un registro incompatible o repetido. Actualiza la página y verifica el número de caso.')
        st.markdown('</div></div>', unsafe_allow_html=True)

    def form_pnc():
        nonce = st.session_state.form_nonce
        st.markdown('<div class="registro-full-panel"><div class="registro-pill">Nuevo registro</div><div class="registro-full-title">📝 PNC´s</div><div class="registro-full-subtitle">Los campos marcados con * son obligatorios.</div>', unsafe_allow_html=True)
        if st.button('← Cambiar tipo de registro', key='volver_pnc'):
            volver_selector()
        st.markdown('<div class="registro-form-shell">', unsafe_allow_html=True)
        prod = consultar(operacion_tabla('INTERFAZ_0052'))
        defs = consultar(operacion_tabla('INTERFAZ_0053'))
        opt_prod = [''] + [f'{r.item} | {r.descripcion}' for r in prod.itertuples()]
        opt_defs = [''] + [f'{r.codigo} | {r.defecto}' for r in defs.itertuples()]
        with st.container():
            a, b, c = st.columns(3)
            fecha = a.date_input('Fecha *', value=date.today(), key=f'pnc_fecha_{nonce}')
            semana = b.number_input('Semana *', min_value=1, max_value=53, value=int(date.today().isocalendar().week), step=1, key=f'pnc_semana_{nonce}')
            nave = c.selectbox('Nave *', opt_blank(catalog('nave')), key=f'pnc_nave_{nonce}')
            a, b, c = st.columns(3)
            opt = a.selectbox('ITEM / Producto *', opt_prod, key=f'pnc_item_{nonce}')
            item = opt.split('|')[0].strip() if opt else ''
            row = prod[prod['item'] == item].iloc[0] if item and item in prod['item'].values else None
            descp = str(row['descripcion']) if row is not None else ''
            cliente = str(row['cliente']) if row is not None else ''
            familia = str(row['familia']) if row is not None else ''
            lote = b.text_area('Lote *', key=f'pnc_lote_{nonce}')
            etapa = c.selectbox('Etapa *', opt_blank(catalog('etapa')), key=f'pnc_etapa_{nonce}')
            a, b, c = st.columns(3)
            a.text_input('Descripción', value=descp, disabled=True)
            b.text_input('Cliente', value=cliente, disabled=True)
            c.text_input('Familia', value=familia, disabled=True)
            linea = st.selectbox('Línea/Sector *', opt_blank(catalog('linea_sector')), key=f'pnc_linea_{nonce}')
            a, b, c = st.columns(3)
            turno = a.selectbox('Turno *', opt_blank(catalog('turno')), key=f'pnc_turno_{nonce}')
            status = b.selectbox('Status *', opt_blank(catalog('status')), key=f'pnc_status_{nonce}')
            optd = c.selectbox('Código / Defecto *', opt_defs, key=f'pnc_def_{nonce}')
            cod = optd.split('|')[0].strip() if optd else ''
            dr = defs[defs['codigo'] == cod].iloc[0] if cod and cod in defs['codigo'].values else None
            defecto = str(dr['defecto']) if dr is not None else ''
            tipo = str(dr['tipo_defecto']) if dr is not None else ''
            clas = str(dr['clasificacion']) if dr is not None else ''
            d1, d2, d3 = st.columns(3)
            d1.text_input('Defecto', value=defecto, disabled=True)
            d2.text_input('Tipo de defecto', value=tipo, disabled=True)
            d3.text_input('Clasificación *', value=clas, disabled=True)
            cat1, cat2 = st.columns(2)
            categoria_inicial_pnc = cat1.selectbox('Categoría inicial *', ['', '1', '2', '3'], key=f'pnc_cat_inicial_{nonce}')
            categoria_final_pnc = cat2.selectbox('Categoría final', ['', '1', '2', '3'], key=f'pnc_cat_final_{nonce}')
            descripcion = st.text_area('Descripción del defecto *', key=f'pnc_desc_{nonce}')
            acciones = st.text_area('Acciones inmediatas *', key=f'pnc_accion_{nonce}')
            a, b, c = st.columns(3)
            sup = a.selectbox('Supervisor (Responsable) *', opt_blank(catalog('supervisor')), key=f'pnc_sup_{nonce}')
            ana = b.selectbox('Analista (Persona que detecta) *', opt_blank(catalog('analista')), key=f'pnc_ana_{nonce}')
            resp = c.selectbox('Responsable de detectar el PNC *', opt_blank(catalog('responsable_detecta')), key=f'pnc_resp_{nonce}')
            a, b, c = st.columns(3)
            disp = a.selectbox('Disposición *', opt_blank(catalog('disposicion')), key=f'pnc_disp_{nonce}')
            obs = b.number_input('Cantidad observada (kg) *', min_value=0.0, step=1.0, format='%.2f', key=f'pnc_obs_{nonce}')
            fecha_final = c.date_input('Fecha final', value=date.today(), key=f'pnc_final_{nonce}') if status == 'CERRADO' else None
            q1, q2, q3 = st.columns(3)
            rep = q1.number_input('Reproceso kg', min_value=0.0, step=1.0, format='%.2f', key=f'pnc_rep_{nonce}')
            dec = q2.number_input('Decomiso kg', min_value=0.0, step=1.0, format='%.2f', key=f'pnc_dec_{nonce}')
            apr = q3.number_input('Aprobado 2da kg', min_value=0.0, step=1.0, format='%.2f', key=f'pnc_apr_{nonce}')
            total = float(obs)
            mat = st.text_area('Material hallado / ME', key=f'pnc_mat_{nonce}')
            notas = st.text_area('Observaciones', key=f'pnc_notas_{nonce}')
            ok = st.button('Guardar registro', key=f'guardar_pnc_{nonce}', type='primary')
        if ok:
            obligatorios = {'Línea/Sector': linea, 'Nave': nave, 'ITEM': item, 'Descripción': descp, 'Cliente': cliente, 'Familia': familia, 'Lote': lote, 'Etapa': etapa, 'Código': cod, 'Defecto': defecto, 'Tipo de defecto': tipo, 'Semana': semana, 'Turno': turno, 'Fecha': fecha, 'Supervisor': sup, 'Analista': ana, 'Responsable de detectar el PNC': resp, 'Descripción del defecto': descripcion, 'Acciones inmediatas': acciones, 'Disposición': disp, 'Cantidad observada': obs, 'Status': status, 'Clasificación': clas, 'Categoría inicial': categoria_inicial_pnc}
            faltantes = [k for k, v in obligatorios.items() if v is None or (isinstance(v, str) and (not v.strip())) or (k == 'Cantidad observada' and float(v) <= 0)]
            if faltantes:
                st.error('Completa los siguientes campos obligatorios: ' + ', '.join(faltantes) + '.')
            else:
                folio = new_folio()
                rid = crear(operacion_tabla('INTERFAZ_0054'), (folio, fecha.isoformat(), linea, nave, item, descp, cliente, familia, lote, etapa, cod, defecto, tipo, clas, turno, sup, ana, resp, descripcion, acciones, disp, float(obs), rep, dec, apr, total, status, fecha_final.isoformat() if fecha_final else None, notas, mat, st.session_state.auth['usuario'], now_iso(), int(semana), categoria_inicial_pnc, categoria_final_pnc))
                audit(st.session_state.auth['usuario'], 'CREAR_PNC', f'ID {rid}')
                limpiar_form()
                st.session_state.flash_registro_guardado = f'Registro guardado correctamente: Número {rid}'
                st.rerun()
        st.markdown('</div></div>', unsafe_allow_html=True)
    if st.session_state.registro_tipo is None:
        selector()
    elif st.session_state.registro_tipo == 'PNC':
        form_pnc()
    elif st.session_state.registro_tipo == 'ME':
        form_hallazgo('me_registros', '🧲 Materia Extraña', 'CREAR_ME')
    elif st.session_state.registro_tipo == 'DDM_RX':
        form_hallazgo('ddm_rx_registros', '📦 Producto segregado por detector de metales y RX', 'CREAR_DDM_RX')
    elif st.session_state.registro_tipo == 'RECLAMOS':
        form_reclamos()
    elif st.session_state.registro_tipo == 'DEVOLUCIONES':
        form_devoluciones()

def page_consulta():
    if 'consulta_tipo' not in st.session_state:
        st.session_state.consulta_tipo = None
    if st.session_state.consulta_tipo is None:
        st.markdown('<div class="registro-landing-hero"><div class="registro-landing-title">Consulta y descarga</div><div class="registro-landing-subtitle">Selecciona la sección que deseas consultar para acceder a su información.</div></div>', unsafe_allow_html=True)
        tarjetas = [('NO_CONFORMIDADES', '📋  **Consulta y seguimiento de No Conformes**\n\nPNC, Materia Extraña, Detector de metales/RX, Reclamos y Devoluciones.\n\n*Abrir sección*'), ('MUESTRAS', '🧪  **Muestras de retención**\n\nConsulta, edición, eliminación y descarga de muestras.\n\n*Abrir sección*'), ('MATRIZ', '📊  **Matriz de entrega de turno**\n\nRegistros de las tres naves, indicadores y reportes por registro.\n\n*Abrir sección*')]
        for columna, (valor, texto) in zip(st.columns(3, gap='large'), tarjetas):
            with columna:
                st.markdown('<span class="registro-card-slot"></span>', unsafe_allow_html=True)
                if st.button(texto, key=f'consulta_tarjeta_{valor}'):
                    st.session_state.consulta_tipo = valor
                    st.rerun()
        return
    if st.button('← Volver a Consulta y descarga', key='consulta_volver_tarjetas'):
        st.session_state.consulta_tipo = None
        st.rerun()
    tipo_consulta = st.session_state.consulta_tipo
    titulos = {'NO_CONFORMIDADES': 'Consulta y seguimiento de No Conformes', 'MUESTRAS': 'Muestras de retención', 'MATRIZ': 'Matriz de entrega de turno'}
    st.markdown(f"""<div class="registro-full-panel"><div class="registro-pill">Consulta y descarga</div><div class="registro-full-title">{titulos.get(tipo_consulta, 'Consulta')}</div></div>""", unsafe_allow_html=True)

    def prep(df):
        v = df.copy()
        if all((c in v.columns for c in ['dia', 'mes', 'anio'])):
            v['Fecha'] = pd.to_datetime(dict(year=v['anio'].fillna(1900).astype(int), month=v['mes'].fillna(1).astype(int), day=v['dia'].fillna(1).astype(int)), errors='coerce').dt.date
            v = v.drop(columns=['dia', 'mes', 'anio'])
        for c in ['folio', 'numero']:
            if c in v.columns:
                v = v.drop(columns=[c])
        v = v.rename(columns={'id': 'Número', 'fecha_apertura': 'Fecha', 'descripcion_producto': 'Producto', 'linea_sector': 'Línea/Sector', 'descripcion_hallazgo': 'Descripción del hallazgo', 'particulas_halladas': '# partículas', 'equipo_hallazgo': 'Equipo', 'analista_detecta': 'Analista', 'supervisor_responsable': 'Supervisor'})
        cols = list(v.columns)
        if 'Número' in cols and 'Fecha' in cols:
            v = v[['Número', 'Fecha'] + [c for c in cols if c not in ['Número', 'Fecha']]]
        return v

    def filtered(df, key):
        q = st.text_input('Buscar registro', placeholder='Buscar por número, fecha, producto, lote, línea, familia, analista...', key=f'buscar_{key}')
        if q and (not df.empty):
            mask = df.astype(str).apply(lambda c: c.str.contains(q, case=False, na=False)).any(axis=1)
            df = df[mask]
        return df

    def table(df, key):
        df = filtered(df, key)
        if df.empty:
            st.info('No se encontraron registros para mostrar.')
            return (None, df)
        v = prep(df)
        try:
            nonce_key = f'table_nonce_{key}'
            nonce = st.session_state.get(nonce_key, 0)
            ev = st.dataframe(v, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'table_{key}_{nonce}')
            rows = getattr(ev, 'selection', {}).get('rows', []) if ev is not None else []
            posicion_valida = bool(rows) and isinstance(rows[0], int) and (0 <= rows[0] < len(v))
            if posicion_valida:
                numero = v.iloc[rows[0]].get('Número')
                if pd.notna(numero):
                    return (int(numero), df)
            elif rows:
                st.session_state[nonce_key] = nonce + 1
                st.rerun()
        except Exception:
            st.dataframe(v, use_container_width=True, hide_index=True)
        return (None, df)

    def delete_confirm(table_name, key, audit_name, selected):
        if st.button('Eliminar registro', key=f'del_{key}_{selected}'):
            st.session_state[f'confirm_del_{key}'] = selected
        if st.session_state.get(f'confirm_del_{key}') == selected:
            st.warning(f'Confirma la eliminación del registro Número {selected}. Esta acción no se puede deshacer.')
            c1, c2 = st.columns(2)
            with c1:
                if st.button('Confirmar eliminación', key=f'ok_del_{key}_{selected}'):
                    crear(operacion_tabla('INTERFAZ_0055', table_name), (selected,))
                    reset_autoincrement(table_name)
                    audit(st.session_state.auth['usuario'], audit_name, f'ID {selected}')
                    st.session_state.pop(f'confirm_del_{key}', None)
                    st.session_state[f'table_nonce_{key}'] = st.session_state.get(f'table_nonce_{key}', 0) + 1
                    st.success(f'Registro eliminado correctamente: Número {selected}')
                    st.rerun()
            with c2:
                if st.button('Cancelar', key=f'cancel_del_{key}_{selected}'):
                    st.session_state.pop(f'confirm_del_{key}', None)
                    st.rerun()

    def edit_record(table_name, key, selected):
        row_df = consultar(operacion_tabla('INTERFAZ_0056', table_name), (selected,))
        if row_df.empty:
            st.warning('El registro seleccionado ya no está disponible.')
            return
        row = row_df.iloc[0].to_dict()
        prod = consultar(operacion_tabla('INTERFAZ_0057'))
        defs = consultar(operacion_tabla('INTERFAZ_0058'))
        opt_prod = [''] + [f'{r.item} | {r.descripcion}' for r in prod.itertuples()]
        opt_defs = [''] + [f'{r.codigo} | {r.defecto}' for r in defs.itertuples()]
        original_item = str(row.get('item') or '')
        original_codigo = str(row.get('codigo_defecto') or '')
        producto_actual = next((x for x in opt_prod if x.split('|')[0].strip() == original_item), '')
        defecto_actual = next((x for x in opt_defs if x.split('|')[0].strip() == original_codigo), '')
        labels = {'fecha_apertura': 'Fecha', 'dia': 'Día', 'mes': 'Mes', 'anio': 'Año', 'linea_sector': 'Línea/Sector *', 'nave': 'Nave *', 'lote': 'Lote *', 'etapa': 'Etapa *', 'semana': 'Semana *', 'turno': 'Turno *', 'supervisor': 'Supervisor *', 'supervisor_responsable': 'Supervisor *', 'analista': 'Analista *', 'analista_detecta': 'Analista *', 'responsable_detecta': 'Responsable de detectar el PNC *', 'descripcion_defecto': 'Descripción del defecto *', 'descripcion_hallazgo': 'Descripción del defecto *', 'acciones_inmediatas': 'Acciones inmediatas *', 'accion_contingente': 'Acciones inmediatas', 'disposicion': 'Disposición *', 'cantidad_observada': 'Cantidad observada (kg) *', 'status': 'Status *', 'equipo_hallazgo': 'Equipo del hallazgo', 'tipo': 'Tipo de hallazgo', 'particulas_halladas': 'Partículas halladas', 'investigacion_origen': 'Investigación del origen', 'acciones_evitar_incidencia': 'Acciones para evitar incidencia', 'observaciones': 'Observaciones', 'material_hallado': 'Material hallado / ME', 'fecha_final_tratamiento': 'Fecha final', 'cantidad_reproceso': 'Reproceso kg', 'cantidad_decomiso': 'Decomiso kg', 'cantidad_aprobado_segunda': 'Aprobado segunda instancia kg', 'categoria_inicial_pnc': 'Categoría inicial *', 'categoria_final_pnc': 'Categoría final'}
        protected = {'folio', 'creado_por', 'creado_en', 'actualizado_por', 'actualizado_en', 'cantidad_total_pnc', 'item', 'descripcion_producto', 'producto', 'cliente', 'familia', 'codigo_defecto', 'defecto', 'tipo_defecto', 'clasificacion', 'categoria_inicial'}
        numeric = {'dia', 'mes', 'anio', 'semana', 'particulas_halladas', 'cantidad_observada', 'cantidad_reproceso', 'cantidad_decomiso', 'cantidad_aprobado_segunda'}
        select_catalog = {'linea_sector': 'linea_sector', 'nave': 'nave', 'etapa': 'etapa', 'turno': 'turno', 'supervisor': 'supervisor', 'supervisor_responsable': 'supervisor', 'analista': 'analista', 'analista_detecta': 'analista', 'responsable_detecta': 'responsable_detecta', 'disposicion': 'disposicion', 'status': 'status', 'categoria_inicial_pnc': 'categoria_pnc', 'categoria_final_pnc': 'categoria_pnc'}
        with st.expander('✏️ Editar o completar registro', expanded=True):
            titulo = {'pnc': 'PNC', 'me': 'Materia Extraña', 'ddm': 'Detector de metales y RX'}.get(key, key)
            st.markdown(f'#### Editar registro de {titulo}: Número {selected}')
            st.caption('El registro original se carga completo. Al cambiar ITEM o Código, los campos relacionados se actualizan automáticamente.')
            a1, a2 = st.columns(2)
            opt_item = a1.selectbox('ITEM *', opt_prod, index=idx_or_zero(opt_prod, producto_actual), key=f'edit_live_item_{key}_{selected}')
            opt_codigo = a2.selectbox('Código / Defecto *', opt_defs, index=idx_or_zero(opt_defs, defecto_actual), key=f'edit_live_codigo_{key}_{selected}')
            item = opt_item.split('|')[0].strip() if opt_item else ''
            pr = prod[prod['item'] == item].iloc[0] if item and item in prod['item'].values else None
            descripcion = str(pr['descripcion']) if pr is not None else ''
            cliente = str(pr['cliente']) if pr is not None else ''
            familia = str(pr['familia']) if pr is not None else ''
            codigo = opt_codigo.split('|')[0].strip() if opt_codigo else ''
            dr = defs[defs['codigo'] == codigo].iloc[0] if codigo and codigo in defs['codigo'].values else None
            defecto = str(dr['defecto']) if dr is not None else ''
            tipo_defecto = str(dr['tipo_defecto']) if dr is not None else ''
            clasificacion = str(dr['clasificacion']) if dr is not None else ''
            p1, p2, p3 = st.columns(3)
            p1.text_input('Descripción', value=descripcion, disabled=True, key=f'edit_auto_descripcion_{key}_{selected}')
            p2.text_input('Cliente', value=cliente, disabled=True, key=f'edit_auto_cliente_{key}_{selected}')
            p3.text_input('Familia', value=familia, disabled=True, key=f'edit_auto_familia_{key}_{selected}')
            d1, d2, d3 = st.columns(3)
            d1.text_input('Defecto', value=defecto, disabled=True, key=f'edit_auto_defecto_{key}_{selected}')
            d2.text_input('Tipo de defecto', value=tipo_defecto, disabled=True, key=f'edit_auto_tipo_defecto_{key}_{selected}')
            d3.text_input('Clasificación', value=clasificacion, disabled=True, key=f'edit_auto_clasificacion_{key}_{selected}')
            values = {}
            columns = [c for c in row_df.columns if c != 'id' and c not in protected]
            if table_name in {'me_registros', 'ddm_rx_registros'}:
                campos_retirados = {'etapa', 'responsable_detecta', 'disposicion', 'status', 'cantidad_observada'}
                columns = [c for c in columns if c not in campos_retirados]
            with st.form(f'editar_form_{key}_{selected}'):
                for pos in range(0, len(columns), 3):
                    cols_ui = st.columns(3)
                    for ui, col in zip(cols_ui, columns[pos:pos + 3]):
                        raw = row.get(col)
                        value = '' if raw is None or pd.isna(raw) else raw
                        label = labels.get(col, col.replace('_', ' ').title())
                        if col in select_catalog:
                            options = ['', '1', '2', '3'] if select_catalog[col] == 'categoria_pnc' else opt_blank(catalog(select_catalog[col]))
                            current = str(value)
                            if current and current not in options:
                                options.append(current)
                            values[col] = ui.selectbox(label, options, index=idx_or_zero(options, current), key=f'edit_{key}_{selected}_{col}')
                        elif col in numeric:
                            if col in {'dia', 'mes', 'anio', 'semana', 'particulas_halladas'}:
                                values[col] = ui.number_input(label, min_value=0, step=1, value=int(float(value or 0)), key=f'edit_{key}_{selected}_{col}')
                            else:
                                values[col] = ui.number_input(label, min_value=0.0, step=1.0, format='%.2f', value=float(value or 0), key=f'edit_{key}_{selected}_{col}')
                        elif col in {'descripcion_defecto', 'descripcion_hallazgo', 'acciones_inmediatas', 'accion_contingente', 'investigacion_origen', 'acciones_evitar_incidencia', 'observaciones', 'material_hallado', 'lote'}:
                            values[col] = ui.text_area(label, value=str(value), key=f'edit_{key}_{selected}_{col}')
                        else:
                            values[col] = ui.text_input(label, value=str(value), key=f'edit_{key}_{selected}_{col}')
                guardar = st.form_submit_button('Guardar cambios', type='primary')
            if guardar:
                auto = {'item': item, 'cliente': cliente, 'familia': familia, 'codigo_defecto': codigo, 'defecto': defecto, 'tipo_defecto': tipo_defecto}
                if table_name == 'pnc_registros':
                    auto.update({'descripcion_producto': descripcion, 'clasificacion': clasificacion, 'cantidad_total_pnc': float(values.get('cantidad_observada') or 0)})
                else:
                    auto.update({'producto': descripcion, 'categoria_inicial': clasificacion})
                if table_name == 'pnc_registros':
                    required = ['linea_sector', 'nave', 'lote', 'etapa', 'semana', 'turno', 'responsable_detecta', 'acciones_inmediatas', 'disposicion', 'cantidad_observada', 'status', 'supervisor', 'analista', 'descripcion_defecto', 'categoria_inicial_pnc']
                else:
                    required = ['linea_sector', 'nave', 'lote', 'semana', 'turno', 'acciones_inmediatas', 'supervisor_responsable', 'analista_detecta', 'descripcion_hallazgo']
                missing = []
                for name, val in {'ITEM': item, 'Descripción': descripcion, 'Cliente': cliente, 'Familia': familia, 'Código': codigo, 'Defecto': defecto, 'Tipo de defecto': tipo_defecto, 'Clasificación': clasificacion}.items():
                    if not str(val).strip():
                        missing.append(name)
                for col in required:
                    val = values.get(col)
                    if val is None or (isinstance(val, str) and (not val.strip())) or (col == 'cantidad_observada' and float(val) <= 0):
                        missing.append(labels.get(col, col))
                if missing:
                    st.error('Completa los siguientes campos obligatorios: ' + ', '.join(dict.fromkeys(missing)) + '.')
                else:
                    updates = {**values, **auto}
                    c_esquema = transaccion()
                    try:
                        columnas_tabla = {r[1] for r in c_esquema.execute(operacion_tabla('INTERFAZ_0059', table_name)).fetchall()}
                    finally:
                        c_esquema.close()
                    if {'actualizado_por', 'actualizado_en'}.issubset(columnas_tabla):
                        updates['actualizado_por'] = st.session_state.auth['usuario']
                        updates['actualizado_en'] = now_iso()
                    update_cols = list(updates.keys())
                    assignments = ', '.join([f'"{c}"=?' for c in update_cols])
                    crear(operacion_tabla('INTERFAZ_0060', table_name, assignments), tuple((updates[c] for c in update_cols)) + (selected,))
                    audit(st.session_state.auth['usuario'], 'EDITAR_REGISTRO', f'Tabla {table_name} | ID {selected}')
                    st.success(f'Registro actualizado correctamente: Número {selected}')
                    st.rerun()
    if tipo_consulta == 'MUESTRAS':
        consulta_muestras_retencion()
        return
    if tipo_consulta == 'MATRIZ':
        matriz_entregas()
        return
    t1, t2, t3, t4, t5 = st.tabs(['PNC´s', 'Materia Extraña', 'Detector de metales y RX', 'Reclamos', 'Devoluciones'])
    with t1:
        df = consultar(operacion_tabla('INTERFAZ_0061'))
        auditoria = ['creado_por', 'creado_en', 'actualizado_por', 'actualizado_en']
        base = [c for c in df.columns if c not in auditoria]
        df_tabla = df[base + [c for c in auditoria if c in df.columns]]
        selected, shown = table(df_tabla, 'pnc')
        if not shown.empty:
            st.download_button('Descargar PNC CSV', prep(shown).to_csv(index=False).encode('utf-8-sig'), f"pnc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv')
        if selected:
            st.markdown(f'### Registro seleccionado: Número {selected}')
            contenido_pdf = pdf_pnc(selected)
            if contenido_pdf:
                st.download_button('Descargar informe PNC en PDF', contenido_pdf, f'informe_pnc_{selected}.pdf', 'application/pdf', key=f'pnc_pdf_{selected}')
            else:
                st.warning('No fue posible generar el informe PDF. Verifica que reportlab esté incluido en requirements.txt.')
            contenido_fisico = pdf_pnc_fisico(selected)
            if contenido_fisico:
                st.download_button('Descargar Registro Físico en PDF', contenido_fisico, f'registro_fisico_pnc_{selected}.pdf', 'application/pdf', key=f'pnc_fisico_pdf_{selected}')
            else:
                st.warning('No fue posible generar el Registro Físico. Verifica que reportlab esté incluido en requirements.txt.')
            edit_record('pnc_registros', 'pnc', selected)
            if is_dev():
                delete_confirm('pnc_registros', 'pnc', 'ELIMINAR_PNC', selected)
    with t2:
        df = consultar(operacion_tabla('INTERFAZ_0062'))
        campos_actuales = ['id', 'dia', 'mes', 'anio', 'semana', 'nave', 'item', 'producto', 'familia', 'lote', 'linea_sector', 'codigo_defecto', 'turno', 'supervisor_responsable', 'analista_detecta', 'descripcion_hallazgo', 'acciones_inmediatas', 'equipo_hallazgo', 'tipo', 'particulas_halladas', 'investigacion_origen', 'acciones_evitar_incidencia', 'creado_por', 'creado_en', 'actualizado_por', 'actualizado_en']
        disponibles = [c for c in campos_actuales if c in df.columns]
        df_tabla = df[disponibles].copy()
        if all((c in df_tabla.columns for c in ['dia', 'mes', 'anio'])):
            df_tabla.insert(1, 'Fecha', pd.to_datetime(dict(year=df_tabla.pop('anio'), month=df_tabla.pop('mes'), day=df_tabla.pop('dia')), errors='coerce').dt.strftime('%Y-%m-%d'))
        selected, shown = table(df_tabla, 'me')
        if not shown.empty:
            st.download_button('Descargar Materia Extraña CSV', prep(shown).to_csv(index=False).encode('utf-8-sig'), f"materia_extrana_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv')
        if selected:
            st.markdown(f'### Registro seleccionado: Número {selected}')
            contenido_pdf = pdf_materia_extrana(selected)
            if contenido_pdf:
                st.download_button('Descargar reporte de Materia Extraña en PDF', contenido_pdf, f'materia_extrana_{selected}.pdf', 'application/pdf', key=f'me_pdf_{selected}')
            else:
                st.warning('No fue posible generar el PDF. Verifica que reportlab esté incluido en requirements.txt.')
            edit_record('me_registros', 'me', selected)
            if is_dev():
                delete_confirm('me_registros', 'me', 'ELIMINAR_ME', selected)
    with t3:
        df = consultar(operacion_tabla('INTERFAZ_0063'))
        campos_actuales = ['id', 'dia', 'mes', 'anio', 'semana', 'nave', 'item', 'producto', 'familia', 'lote', 'linea_sector', 'codigo_defecto', 'turno', 'supervisor_responsable', 'analista_detecta', 'descripcion_hallazgo', 'acciones_inmediatas', 'equipo_hallazgo', 'tipo', 'particulas_halladas', 'investigacion_origen', 'acciones_evitar_incidencia', 'creado_por', 'creado_en', 'actualizado_por', 'actualizado_en']
        disponibles = [c for c in campos_actuales if c in df.columns]
        df_tabla = df[disponibles].copy()
        if all((c in df_tabla.columns for c in ['dia', 'mes', 'anio'])):
            df_tabla.insert(1, 'Fecha', pd.to_datetime(dict(year=df_tabla.pop('anio'), month=df_tabla.pop('mes'), day=df_tabla.pop('dia')), errors='coerce').dt.strftime('%Y-%m-%d'))
        selected, shown = table(df_tabla, 'ddm')
        if not shown.empty:
            st.download_button('Descargar Detector de metales y RX CSV', prep(shown).to_csv(index=False).encode('utf-8-sig'), f"ddm_rx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv')
        if selected:
            st.markdown(f'### Registro seleccionado: Número {selected}')
            contenido_pdf = pdf_detector_metales_rx(selected)
            if contenido_pdf:
                st.download_button('Descargar registro de Detector de metales y RX en PDF', contenido_pdf, f'detector_metales_rx_{selected}.pdf', 'application/pdf', key=f'ddm_pdf_{selected}')
            else:
                st.warning('No fue posible generar el PDF. Verifica que reportlab esté incluido en requirements.txt.')
            edit_record('ddm_rx_registros', 'ddm', selected)
            if is_dev():
                delete_confirm('ddm_rx_registros', 'ddm', 'ELIMINAR_DDM_RX', selected)
    with t4:
        df = consultar(operacion_tabla('INTERFAZ_0064'))
        selected, shown = table(df, 'reclamos')
        if not shown.empty:
            st.download_button('Descargar Reclamos CSV', prep(shown).to_csv(index=False).encode('utf-8-sig'), f"reclamos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv')
        if selected:
            st.markdown(f'### Reclamo seleccionado: Número {selected}')
            row_df = consultar(operacion_tabla('INTERFAZ_0065'), (selected,))
            if row_df.empty:
                st.warning('El registro seleccionado ya no está disponible.')
            else:
                row = row_df.iloc[0].to_dict()
                prod = consultar(operacion_tabla('INTERFAZ_0066'))
                defs = consultar(operacion_tabla('INTERFAZ_0067'))
                opt_prod = [''] + [f'{r.item} | {r.descripcion}' for r in prod.itertuples()]
                opt_defs = [''] + [f'{r.codigo} | {r.defecto}' for r in defs.itertuples()]
                item_actual = str(row.get('item') or '')
                codigo_actual = str(row.get('codigo_defecto') or '')
                producto_actual = next((x for x in opt_prod if x.split('|')[0].strip() == item_actual), '')
                defecto_actual = next((x for x in opt_defs if x.split('|')[0].strip() == codigo_actual), '')
                fecha_actual = pd.to_datetime(row.get('fecha'), errors='coerce')
                cierre_actual = pd.to_datetime(row.get('fecha_cierre'), errors='coerce')
                with st.expander('✏️ Editar registro de Reclamo', expanded=True):
                    with st.form(f'editar_reclamo_{selected}'):
                        a, b, c = st.columns(3)
                        fecha = a.date_input('Fecha *', value=fecha_actual.date() if pd.notna(fecha_actual) else date.today())
                        od = b.selectbox('Código / Defecto *', opt_defs, index=idx_or_zero(opt_defs, defecto_actual))
                        fuente = c.text_input('Fuente *', value=str(row.get('fuente') or ''))
                        codigo = od.split('|')[0].strip() if od else ''
                        dr = defs[defs['codigo'].astype(str) == codigo].iloc[0] if codigo and codigo in defs['codigo'].astype(str).values else None
                        defecto = str(dr['defecto']) if dr is not None else ''
                        tipo_defecto = str(dr['tipo_defecto']) if dr is not None else ''
                        clasificacion = str(dr['clasificacion']) if dr is not None else ''
                        a, b, c = st.columns(3)
                        a.text_input('Descripción del defecto', value=defecto, disabled=True)
                        b.text_input('Tipo de defecto', value=tipo_defecto, disabled=True)
                        c.text_input('Clasificación del defecto', value=clasificacion, disabled=True)
                        a, b, c = st.columns(3)
                        mercado_ops = ['', 'Interno', 'Externo']
                        mercado_actual = str(row.get('mercado') or '')
                        if mercado_actual and mercado_actual not in mercado_ops:
                            mercado_ops.append(mercado_actual)
                        mercado = a.selectbox('Mercado *', mercado_ops, index=idx_or_zero(mercado_ops, mercado_actual))
                        pais_estado = b.text_input('País / Estado *', value=str(row.get('pais_estado') or ''))
                        numero_caso = c.text_input('No. Caso Right Now / MDLZ *', value=str(row.get('numero_caso') or ''))
                        a, b, c = st.columns(3)
                        op = a.selectbox('ITEM *', opt_prod, index=idx_or_zero(opt_prod, producto_actual))
                        item = op.split('|')[0].strip() if op else ''
                        pr = prod[prod['item'].astype(str) == item].iloc[0] if item and item in prod['item'].astype(str).values else None
                        producto = '' if pr is None or pd.isna(pr['descripcion']) else str(pr['descripcion']).strip()
                        cliente = '' if pr is None or pd.isna(pr['cliente']) else str(pr['cliente']).strip()
                        familia = '' if pr is None or pd.isna(pr['familia']) else str(pr['familia']).strip()
                        b.text_input('Producto', value=producto, disabled=True)
                        c.text_input('Cliente', value=cliente, disabled=True)
                        st.text_input('Familia', value=familia, disabled=True)
                        descripcion_reclamo = st.text_area('Descripción del reclamo *', value=str(row.get('descripcion_reclamo') or ''))
                        causa_raiz = st.text_area('Causa raíz del defecto *', value=str(row.get('causa_raiz') or ''))
                        acciones = st.text_area('Acciones correctivas y contingentes *', value=str(row.get('acciones_correctivas_contingentes') or ''))
                        a, b, c = st.columns(3)
                        comp_ops = ['', 'Sí', 'No']
                        comprobado = a.selectbox('Comprobado *', comp_ops, index=idx_or_zero(comp_ops, str(row.get('comprobado') or '')))
                        cantidad = b.number_input('Cantidad afectada *', min_value=0.0, step=1.0, format='%.2f', value=float(row.get('cantidad_afectada') or 0))
                        unidad_ops = ['', 'Bulto', 'Bolsa', 'Pieza', 'Lámina']
                        unidad_actual = str(row.get('unidad') or '')
                        if unidad_actual and unidad_actual not in unidad_ops:
                            unidad_ops.append(unidad_actual)
                        unidad = c.selectbox('Unidad *', unidad_ops, index=idx_or_zero(unidad_ops, unidad_actual))
                        a, b, c = st.columns(3)
                        sector = a.text_input('Sector *', value=str(row.get('sector') or ''))
                        estado_ops = ['', 'Abierto', 'Cerrado']
                        estado_actual = str(row.get('estado_reclamo') or '')
                        estado = b.selectbox('Estado del reclamo *', estado_ops, index=idx_or_zero(estado_ops, estado_actual))
                        fecha_cierre = c.date_input('Fecha de cierre', value=cierre_actual.date() if pd.notna(cierre_actual) else None)
                        a, b, c = st.columns(3)
                        tsp = a.text_input('TSP N°', value=str(row.get('tsp_numero') or ''))
                        caducidad = b.text_input('Caducidad', value=str(row.get('caducidad') or ''))
                        lote = c.text_input('Lote *', value=str(row.get('lote') or ''))
                        a, b, c = st.columns(3)
                        nave_ops = opt_blank(catalog('nave'))
                        nave_actual = str(row.get('nave') or '')
                        if nave_actual and nave_actual not in nave_ops:
                            nave_ops.append(nave_actual)
                        nave = a.selectbox('Nave *', nave_ops, index=idx_or_zero(nave_ops, nave_actual))
                        pmd_ops = ['', '1 - Manipulación', '2 - Producción', '3 - Diseño']
                        pmd_actual = str(row.get('pmd') or '')
                        if pmd_actual and pmd_actual not in pmd_ops:
                            pmd_ops.append(pmd_actual)
                        pmd = b.selectbox('P / M / D *', pmd_ops, index=idx_or_zero(pmd_ops, pmd_actual))
                        red_ops = ['', 'Mail', 'Web', 'Instagram', 'No indica', 'Facebook']
                        red_actual = str(row.get('red_social') or '')
                        if red_actual and red_actual not in red_ops:
                            red_ops.append(red_actual)
                        red_social = c.selectbox('Red social *', red_ops, index=idx_or_zero(red_ops, red_actual))
                        guardar = st.form_submit_button('Guardar cambios', type='primary')
                    if guardar:
                        req = {'Código / Defecto': codigo, 'Descripción del defecto': defecto, 'Fuente': fuente, 'Mercado': mercado, 'País / Estado': pais_estado, 'No. Caso': numero_caso, 'ITEM': item, 'Producto': producto, 'Cliente': cliente, 'Familia': familia, 'Descripción del reclamo': descripcion_reclamo, 'Causa raíz': causa_raiz, 'Acciones': acciones, 'Comprobado': comprobado, 'Cantidad afectada': cantidad, 'Unidad': unidad, 'Sector': sector, 'Estado': estado, 'Lote': lote, 'Nave': nave, 'P / M / D': pmd, 'Tipo de defecto': tipo_defecto, 'Clasificación': clasificacion, 'Red social': red_social}
                        faltan = [k for k, v in req.items() if v is None or (isinstance(v, str) and (not v.strip())) or (k == 'Cantidad afectada' and float(v) <= 0)]
                        duplicado = not consultar(operacion_tabla('INTERFAZ_0068'), (numero_caso, selected)).empty if numero_caso.strip() else False
                        if duplicado:
                            st.error('Ya existe otro reclamo con el mismo No. Caso Right Now / MDLZ.')
                        elif faltan:
                            st.error('Completa los siguientes campos obligatorios: ' + ', '.join(faltan) + '.')
                        elif estado == 'Cerrado' and (not fecha_cierre):
                            st.error('Captura la fecha de cierre para el reclamo cerrado.')
                        elif fecha_cierre and fecha_cierre < fecha:
                            st.error('La fecha de cierre no puede ser anterior a la fecha del reclamo.')
                        else:
                            crear(operacion_tabla('INTERFAZ_0069'), (fecha.isoformat(), codigo, defecto, fuente.strip(), mercado, pais_estado.strip(), numero_caso.strip(), item, producto, cliente, familia, descripcion_reclamo.strip(), causa_raiz.strip(), acciones.strip(), comprobado, float(cantidad), unidad, sector.strip(), estado, fecha_cierre.isoformat() if fecha_cierre else None, tsp.strip(), caducidad.strip(), lote.strip(), nave, pmd, tipo_defecto, clasificacion, red_social, st.session_state.auth['usuario'], now_iso(), selected))
                            audit(st.session_state.auth['usuario'], 'EDITAR_RECLAMO', f'ID {selected} | Caso {numero_caso.strip()}')
                            st.success(f'Reclamo actualizado correctamente: Número {selected}')
                            st.rerun()
            if is_dev():
                delete_confirm('reclamos_registros', 'reclamos', 'ELIMINAR_RECLAMO', selected)
    with t5:
        df = consultar(operacion_tabla('INTERFAZ_0070'))
        df_tabla = df.drop(columns=['linea'], errors='ignore')
        selected, shown = table(df_tabla, 'devoluciones')
        if not shown.empty:
            st.download_button('Descargar Devoluciones CSV', prep(shown).to_csv(index=False).encode('utf-8-sig'), f"devoluciones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv')
        if selected:
            st.markdown(f'### Devolución seleccionada: Número {selected}')
            row_df = consultar(operacion_tabla('INTERFAZ_0071'), (selected,))
            if row_df.empty:
                st.warning('El registro seleccionado ya no está disponible.')
            else:
                r = row_df.iloc[0].to_dict()
                prod = consultar(operacion_tabla('INTERFAZ_0072'))
                defs = consultar(operacion_tabla('INTERFAZ_0073'))
                opt_prod = [''] + [f'{x.item} | {x.descripcion}' for x in prod.itertuples()]
                opt_defs = [''] + [f'{x.codigo} | {x.defecto}' for x in defs.itertuples()]
                item0 = str(r.get('item') or '')
                cod0 = str(r.get('codigo_defecto') or '')
                op0 = next((x for x in opt_prod if x.split('|')[0].strip() == item0), '')
                od0 = next((x for x in opt_defs if x.split('|')[0].strip() == cod0), '')
                fv = pd.to_datetime(r.get('fecha'), errors='coerce')
                with st.expander('✏️ Editar registro de Devolución', expanded=True):
                    with st.form(f'editar_devolucion_{selected}'):
                        a, b, c = st.columns(3)
                        fecha = a.date_input('Fecha *', fv.date() if pd.notna(fv) else date.today())
                        od = b.selectbox('Código / Defecto *', opt_defs, index=idx_or_zero(opt_defs, od0))
                        cedis = c.text_input('Cedis *', str(r.get('cedis') or ''))
                        codigo = od.split('|')[0].strip() if od else ''
                        dr = defs[defs.codigo.astype(str) == codigo].iloc[0] if codigo and codigo in defs.codigo.astype(str).values else None
                        defecto = '' if dr is None else str(dr.defecto)
                        a, b, c = st.columns(3)
                        pais = a.text_input('País / Estado *', str(r.get('pais_estado') or ''))
                        op = b.selectbox('ITEM *', opt_prod, index=idx_or_zero(opt_prod, op0))
                        item = op.split('|')[0].strip() if op else ''
                        pr = prod[prod.item.astype(str) == item].iloc[0] if item and item in prod.item.astype(str).values else None
                        producto = '' if pr is None or pd.isna(pr.descripcion) else str(pr.descripcion).strip()
                        cliente = '' if pr is None or pd.isna(pr.cliente) else str(pr.cliente).strip()
                        familia = '' if pr is None or pd.isna(pr.familia) else str(pr.familia).strip()
                        c.text_input('Producto', producto, disabled=True)
                        a, b, c = st.columns(3)
                        a.text_input('Cliente', cliente, disabled=True)
                        b.text_input('Familia', familia, disabled=True)
                        lote = c.text_input('Lote *', str(r.get('lote') or ''))
                        a, b, c = st.columns(3)
                        cad = a.text_input('Caducidad *', str(r.get('caducidad') or ''))
                        comp = b.selectbox('Comprobado *', ['', 'Sí', 'No'], index=idx_or_zero(['', 'Sí', 'No'], str(r.get('comprobado') or '')))
                        cant = c.number_input('Cant. afectada *', 0.0, step=1.0, value=float(r.get('cantidad_afectada') or 0))
                        desc = st.text_area('Descripción de la devolución *', str(r.get('descripcion_defecto') or ''))
                        a, b, c = st.columns(3)
                        uops = ['', 'Bulto', 'Bolsa', 'Pieza', 'Tarima']
                        unidad = a.selectbox('Unidad *', uops, index=idx_or_zero(uops, str(r.get('unidad') or '')))
                        sector = b.text_input('Sector *', str(r.get('sector') or ''))
                        dops = opt_blank(catalog('disposicion'))
                        da = str(r.get('disposicion') or '')
                        dops = dops + ([da] if da and da not in dops else [])
                        disp = c.selectbox('Disposición *', dops, index=idx_or_zero(dops, da))
                        a, b, c = st.columns(3)
                        tsp = a.text_input('TSP N°', str(r.get('tsp_numero') or ''))
                        status = b.selectbox('Status *', ['', 'Cerrado', 'Abierto'], index=idx_or_zero(['', 'Cerrado', 'Abierto'], str(r.get('status') or '')))
                        nops = opt_blank(catalog('nave'))
                        na = str(r.get('nave') or '')
                        nops = nops + ([na] if na and na not in nops else [])
                        nave = c.selectbox('Nave *', nops, index=idx_or_zero(nops, na))
                        guardar = st.form_submit_button('Guardar cambios', type='primary')
                    if guardar:
                        req = {'Código': codigo, 'Cedis': cedis, 'País/Estado': pais, 'ITEM': item, 'Producto': producto, 'Cliente': cliente, 'Familia': familia, 'Lote': lote, 'Caducidad': cad, 'Descripción': desc, 'Comprobado': comp, 'Cantidad': cant, 'Unidad': unidad, 'Sector': sector, 'Disposición': disp, 'Status': status, 'Nave': nave}
                        faltan = [k for k, v in req.items() if v is None or (isinstance(v, str) and (not v.strip())) or (k == 'Cantidad' and float(v) <= 0)]
                        if faltan:
                            st.error('Completa los siguientes campos obligatorios: ' + ', '.join(faltan) + '.')
                        else:
                            crear(operacion_tabla('INTERFAZ_0074'), (fecha.isoformat(), codigo, defecto, cedis.strip(), pais.strip(), item, producto, cliente, familia, lote.strip(), cad.strip(), desc.strip(), comp, float(cant), unidad, sector.strip(), disp, tsp.strip(), status, nave, st.session_state.auth['usuario'], now_iso(), selected))
                            audit(st.session_state.auth['usuario'], 'EDITAR_DEVOLUCION', f'ID {selected}')
                            st.success(f'Devolución actualizada correctamente: Número {selected}')
                            st.rerun()
            if is_dev():
                delete_confirm('devoluciones_registros', 'devoluciones', 'ELIMINAR_DEVOLUCION', selected)

def page_muestras_retencion():
    periodos = [('muestras_10_meses', '10 Meses', '🗓️'), ('muestras_12_meses_alergeno', '12 Meses Alérgeno', '⚠️'), ('muestras_12_meses_duvalin', '12 Meses Duvalin', '🍫'), ('muestras_12_meses_nave2', '12 Meses Nave 2', '🏭'), ('muestras_15_meses', '15 Meses', '📦'), ('muestras_18_meses', '18 Meses', '🧪'), ('muestras_24_meses', '24 Meses', '✅')]
    if 'muestra_tipo' not in st.session_state:
        st.session_state.muestra_tipo = None
    if 'muestra_nonce' not in st.session_state:
        st.session_state.muestra_nonce = 0
    seleccionado = st.session_state.muestra_tipo
    if seleccionado is None:
        st.markdown('<div class="registro-landing-hero"><div class="registro-landing-title">Muestras de retención</div><div class="registro-landing-subtitle">Selecciona el periodo de retención que deseas registrar.</div></div>', unsafe_allow_html=True)
        for inicio in range(0, len(periodos), 3):
            columnas = st.columns(3, gap='large')
            for col, (tabla, nombre, icono) in zip(columnas, periodos[inicio:inicio + 3]):
                with col:
                    st.markdown('<span class="registro-card-slot"></span>', unsafe_allow_html=True)
                    if st.button(f'{icono}  **{nombre}**\n\nCaptura y seguimiento de muestras de retención.\n\n*Abrir registro*', key=f'card_{tabla}'):
                        st.session_state.muestra_tipo = tabla
                        st.rerun()
        return
    info = next((x for x in periodos if x[0] == seleccionado), None)
    if not info:
        st.session_state.muestra_tipo = None
        st.rerun()
    tabla, nombre, icono = info
    if st.button('← Cambiar periodo de retención', key='volver_muestras'):
        st.session_state.muestra_tipo = None
        st.rerun()
    st.markdown(f'<div class="registro-full-panel"><div class="registro-pill">Nuevo registro</div><div class="registro-full-title">{icono} {nombre}</div><div class="registro-full-subtitle">Los campos marcados con * son obligatorios.</div>', unsafe_allow_html=True)
    productos = consultar(operacion_tabla('INTERFAZ_0075'))
    opciones = [''] + [f'{r.item} | {r.descripcion}' for r in productos.itertuples()]
    nonce = st.session_state.muestra_nonce
    elegido = st.selectbox('ITEM *', opciones, key=f'mr_item_{tabla}_{nonce}')
    item = elegido.split('|')[0].strip() if elegido else ''
    fila = productos[productos['item'].astype(str) == item]
    descripcion = str(fila.iloc[0]['descripcion']) if not fila.empty else ''
    st.text_input('Descripción', value=descripcion, disabled=True)
    with st.form(f'mr_form_{tabla}_{nonce}'):
        c1, c2 = st.columns(2)
        lote = c1.text_input('Lote *')
        destino = c2.selectbox('Destino *', ['', 'Nacional', 'Exportación'])
        c3, c4 = st.columns(2)
        muestras = c3.number_input('# De muestras *', min_value=0.0, step=1.0, format='%.2f')
        corrugado = c4.number_input('# Corrugado *', min_value=0.0, step=1.0, format='%.2f')
        responsable = st.selectbox('Responsable *', opt_blank(catalog('analista')))
        observaciones = st.text_area('Observaciones')
        guardar = st.form_submit_button('Guardar registro', type='primary')
    if guardar:
        req = {'ITEM': item, 'Descripción': descripcion, 'Lote': lote, 'Destino': destino, '# De muestras': muestras, '# Corrugado': corrugado, 'Responsable': responsable}
        faltan = [k for k, v in req.items() if v is None or (isinstance(v, str) and (not v.strip())) or (k in ['# De muestras', '# Corrugado'] and float(v) <= 0)]
        if faltan:
            st.error('Completa los siguientes campos obligatorios: ' + ', '.join(faltan) + '.')
        else:
            rid = crear(operacion_tabla('INTERFAZ_0076', tabla), (item, descripcion, lote.strip(), destino, float(muestras), float(corrugado), responsable, observaciones.strip(), st.session_state.auth['usuario'], now_iso()))
            audit(st.session_state.auth['usuario'], 'CREAR_MUESTRA_RETENCION', f'{nombre} | ID {rid}')
            st.session_state.muestra_nonce += 1
            st.success(f'Registro guardado correctamente. Número {rid}')
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def consulta_muestras_retencion():
    configuracion = [('muestras_10_meses', '10 Meses'), ('muestras_12_meses_alergeno', '12 Meses Alérgeno'), ('muestras_12_meses_duvalin', '12 Meses Duvalin'), ('muestras_12_meses_nave2', '12 Meses Nave 2'), ('muestras_15_meses', '15 Meses'), ('muestras_18_meses', '18 Meses'), ('muestras_24_meses', '24 Meses')]
    st.markdown('## Muestras de retención')
    tabs = st.tabs([n for _, n in configuracion])
    productos = consultar(operacion_tabla('INTERFAZ_0077'))
    opciones_item = [''] + [f'{r.item} | {r.descripcion}' for r in productos.itertuples()]
    for tab, (tabla, nombre) in zip(tabs, configuracion):
        with tab:
            df = consultar(operacion_tabla('INTERFAZ_0078', tabla))
            buscar = st.text_input('Buscar registro', placeholder='Buscar por número, ITEM, descripción, lote, destino o responsable...', key=f'buscar_{tabla}')
            mostrado = df.copy()
            if buscar and (not mostrado.empty):
                mask = mostrado.astype(str).apply(lambda col: col.str.contains(buscar, case=False, na=False)).any(axis=1)
                mostrado = mostrado[mask]
            if mostrado.empty:
                st.info('No se encontraron registros para mostrar.')
                continue
            vista = mostrado[['id', 'item', 'descripcion', 'lote', 'destino', 'numero_muestras', 'numero_corrugado', 'responsable', 'observaciones']].rename(columns={'id': 'N°', 'item': 'ITEM', 'descripcion': 'Descripción', 'lote': 'Lote', 'destino': 'Destino', 'numero_muestras': '# De muestras', 'numero_corrugado': '# Corrugado', 'responsable': 'Responsable', 'observaciones': 'Observaciones'})
            nonce_key = f'table_nonce_{tabla}'
            nonce = st.session_state.get(nonce_key, 0)
            evento = st.dataframe(vista, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'table_{tabla}_{nonce}')
            st.download_button('Descargar CSV', vista.to_csv(index=False).encode('utf-8-sig'), f"{tabla}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv', key=f'download_{tabla}')
            filas = getattr(evento, 'selection', {}).get('rows', []) if evento is not None else []
            posicion_valida = bool(filas) and isinstance(filas[0], int) and (0 <= filas[0] < len(vista))
            if not posicion_valida:
                if filas:
                    st.session_state[nonce_key] = nonce + 1
                    st.rerun()
                continue
            rid = int(vista.iloc[filas[0]]['N°'])
            coincidencia = mostrado[mostrado['id'] == rid]
            if coincidencia.empty:
                st.session_state[nonce_key] = nonce + 1
                st.rerun()
            st.markdown(f'### Registro seleccionado: Número {rid}')
            original_df = consultar(operacion_tabla('INTERFAZ_0079', tabla), (rid,))
            if original_df.empty:
                st.session_state[nonce_key] = nonce + 1
                st.rerun()
            original = original_df.iloc[0].to_dict()
            with st.expander(f'✏️ Editar registro N° {rid}', expanded=True):
                actual = next((x for x in opciones_item if x and x.split('|')[0].strip() == str(original['item'])), '')
                elegido = st.selectbox('ITEM *', opciones_item, index=idx_or_zero(opciones_item, actual), key=f'edit_item_{tabla}_{rid}')
                item = elegido.split('|')[0].strip() if elegido else ''
                fila = productos[productos['item'].astype(str) == item]
                descripcion = str(fila.iloc[0]['descripcion']) if not fila.empty else ''
                st.text_input('Descripción', value=descripcion, disabled=True, key=f'edit_desc_{tabla}_{rid}_{item}')
                with st.form(f'edit_form_{tabla}_{rid}'):
                    c1, c2 = st.columns(2)
                    lote = c1.text_input('Lote *', value=str(original['lote'] or ''))
                    destinos = ['', 'Nacional', 'Exportación']
                    dest = str(original['destino'] or '')
                    destino = c2.selectbox('Destino *', destinos, index=idx_or_zero(destinos, dest))
                    c3, c4 = st.columns(2)
                    muestras = c3.number_input('# De muestras *', min_value=0.0, step=1.0, format='%.2f', value=float(original['numero_muestras'] or 0))
                    corrugado = c4.number_input('# Corrugado *', min_value=0.0, step=1.0, format='%.2f', value=float(original['numero_corrugado'] or 0))
                    analistas = opt_blank(catalog('analista'))
                    resp = str(original['responsable'] or '')
                    if resp and resp not in analistas:
                        analistas.append(resp)
                    responsable = st.selectbox('Responsable *', analistas, index=idx_or_zero(analistas, resp))
                    observaciones = st.text_area('Observaciones', value=str(original['observaciones'] or ''))
                    actualizar = st.form_submit_button('Guardar cambios', type='primary')
                if actualizar:
                    req = {'ITEM': item, 'Descripción': descripcion, 'Lote': lote, 'Destino': destino, '# De muestras': muestras, '# Corrugado': corrugado, 'Responsable': responsable}
                    faltan = [k for k, v in req.items() if v is None or (isinstance(v, str) and (not v.strip())) or (k in ['# De muestras', '# Corrugado'] and float(v) <= 0)]
                    if faltan:
                        st.error('Completa los siguientes campos obligatorios: ' + ', '.join(faltan) + '.')
                    else:
                        crear(operacion_tabla('INTERFAZ_0080', tabla), (item, descripcion, lote.strip(), destino, float(muestras), float(corrugado), responsable, observaciones.strip(), st.session_state.auth['usuario'], now_iso(), rid))
                        audit(st.session_state.auth['usuario'], 'EDITAR_MUESTRA_RETENCION', f'{nombre} | ID {rid}')
                        st.success(f'Registro actualizado correctamente. Número {rid}')
                        st.rerun()
            if is_dev():
                if st.button('Eliminar registro', key=f'del_{tabla}_{rid}'):
                    st.session_state[f'confirm_{tabla}'] = rid
                if st.session_state.get(f'confirm_{tabla}') == rid:
                    st.warning(f'El registro número {rid} se eliminará de forma permanente. Esta acción no se puede deshacer.')
                    d1, d2 = st.columns(2)
                    if d1.button('Confirmar eliminación', key=f'ok_{tabla}_{rid}'):
                        crear(operacion_tabla('INTERFAZ_0081', tabla), (rid,))
                        reset_autoincrement(tabla)
                        audit(st.session_state.auth['usuario'], 'ELIMINAR_MUESTRA_RETENCION', f'{nombre} | ID {rid}')
                        st.session_state.pop(f'confirm_{tabla}', None)
                        st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1
                        st.rerun()
                    if d2.button('Cancelar', key=f'cancel_{tabla}_{rid}'):
                        st.session_state.pop(f'confirm_{tabla}', None)
                        st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1
                        st.rerun()

def page_entrega_turno():
    referencia = 'RE-CAL01-2301-00002-2013 Rev. 1'
    grupos = formato_entrega('Nave 1', 'PROCESO')
    if 'entrega_nave' not in st.session_state:
        st.session_state.entrega_nave = None
    if 'entrega_nonce' not in st.session_state:
        st.session_state.entrega_nonce = 0
    if st.session_state.entrega_nave is None:
        st.markdown('<div class="registro-landing-hero"><div class="registro-landing-title">Entrega de turno</div><div class="registro-landing-subtitle">Selecciona la nave correspondiente para iniciar el registro.</div></div>', unsafe_allow_html=True)
        cols = st.columns(3, gap='large')
        for col, nave in zip(cols, ['Nave 1', 'Nave 2', 'Nave 3']):
            with col:
                st.markdown('<span class="registro-card-slot"></span>', unsafe_allow_html=True)
                if st.button(f'🏭  **{nave}**\n\nEntrega y continuidad de actividades.\n\n*Abrir registro*', key=f'entrega_{nave}'):
                    st.session_state.entrega_nave = nave
                    st.rerun()
        return
    nave = st.session_state.entrega_nave
    if st.button('← Cambiar nave', key='entrega_volver'):
        st.session_state.entrega_nave = None
        st.rerun()
    if nave in ['Nave 2', 'Nave 3']:
        n = st.session_state.entrega_nonce
        st.markdown(f'<div class="registro-full-panel"><div class="registro-pill">{referencia}</div><div class="registro-full-title">ENTREGA DE TURNO CALIDAD PROCESOS</div><div class="registro-full-subtitle">NAVE 2 Y 3 · Captura correspondiente a {nave}</div>', unsafe_allow_html=True)
        a, b, c = st.columns([2, 1, 1])
        analista = a.selectbox('ANALISTA *', opt_blank(catalog('analista')), key=f'et23_a_{nave}_{n}')
        fecha = b.date_input('Fecha *', date.today(), key=f'et23_f_{nave}_{n}')
        turno = c.selectbox('Turno *', opt_blank(catalog('turno')), key=f'et23_t_{nave}_{n}')
        catalogo_procesos = {}
        orden_nave2 = []
        orden_nave3 = []
        procesos = formato_entrega(nave, 'PROCESO')
        color_lineas = '#0070C0' if nave == 'Nave 2' else '#00A651'
        filas = []
        st.markdown('### Líneas y procesos')
        st.caption('Producto es un solo campo libre dentro de cada proceso. Los controles − y + avanzan de uno en uno y permiten escribir decimales.')
        for gi, (grupo, lineas) in enumerate(procesos.items()):
            st.markdown(f'<div style="background:{color_lineas};color:white;padding:.55rem .8rem;border-radius:12px 12px 0 0;font-weight:900">{grupo}</div>', unsafe_allow_html=True)
            producto = st.text_input(f'Productos / Item / descripcion de la linea {grupo}', key=f'et23_prod_{nave}_{gi}_{n}', placeholder='Escritura libre')
            h = st.columns([2.2, 1, 1, 2.2])
            h[0].markdown('**Sector**')
            h[1].markdown('**Horas / cargas liberadas**')
            h[2].markdown('**Carga al SPAC**')
            h[3].markdown('**Observaciones**')
            for li, linea in enumerate(lineas):
                cols = st.columns([2.2, 1, 1, 2.2])
                cols[0].text_input('Sector', linea, disabled=True, key=f'et23_l_{nave}_{gi}_{li}_{n}', label_visibility='collapsed')
                horas = cols[1].number_input('Horas', 0.0, step=1.0, format='%.2f', key=f'et23_h_{nave}_{gi}_{li}_{n}', label_visibility='collapsed')
                carga = cols[2].number_input('Carga', 0.0, step=1.0, format='%.2f', key=f'et23_c_{nave}_{gi}_{li}_{n}', label_visibility='collapsed')
                obs = cols[3].text_input('Observaciones', key=f'et23_o_{nave}_{gi}_{li}_{n}', label_visibility='collapsed')
                filas.append((grupo, linea, producto, float(horas), float(carga), obs, len(filas)))
            st.markdown('<div style="height:.7rem"></div>', unsafe_allow_html=True)
        st.markdown('### Análisis de laboratorio')
        analisis = formato_entrega(nave, 'ANALISIS')
        resultados = []
        for ai, (grupo, linea, tipo_analisis) in enumerate(analisis):
            cc = st.columns([1.2, 2, 1.5, 1, 2])
            cc[0].text_input('Grupo', grupo, disabled=True, key=f'et23_ag_{nave}_{ai}_{n}', label_visibility='collapsed')
            cc[1].text_input('Línea', linea, disabled=True, key=f'et23_al_{nave}_{ai}_{n}', label_visibility='collapsed')
            cc[2].text_input('Análisis', tipo_analisis, disabled=True, key=f'et23_at_{nave}_{ai}_{n}', label_visibility='collapsed')
            resultado = cc[3].text_input('Resultado', key=f'et23_ar_{nave}_{ai}_{n}', label_visibility='collapsed')
            obs = cc[4].text_input('Observaciones', key=f'et23_ao_{nave}_{ai}_{n}', label_visibility='collapsed')
            contador = st.number_input(f'Cantidad de análisis - {linea} - {tipo_analisis}', min_value=0.0, step=1.0, format='%.2f', key=f'et23_cnt_{nave}_{ai}_{n}')
            resultados.append((grupo, linea, tipo_analisis, resultado, obs, float(contador)))
        seguimientos = []
        st.markdown('### Seguimientos')
        for bi, bloque_cfg in enumerate(configuracion_seguimientos()):
            bloque = bloque_cfg['nombre']
            with st.expander(bloque, expanded=bi < 2):
                ed, meta = editor_seguimiento_dinamico(bloque_cfg, f'et23_s_{nave}_{bi}_{n}')
                seguimientos.append((bloque, ed, meta))
        totales_nave, filas_clasificadas = clasificar_filas(filas)
        total_h = sum(totales_nave.values())
        total_c = sum((x[4] for x in filas)) + sum((x[5] for x in resultados))
        m1, m2 = st.columns(2)
        m1.metric('TOTAL DE CARGA DE DATOS', f'{total_c:.2f}')
        m2.metric('TOTAL GENERAL DE HORAS', f'{total_h:.2f}')
        q1, q2, q3 = st.columns(3)
        q1.metric('HORAS NAVE 1', f"{totales_nave['Nave 1']:.2f}")
        q2.metric('HORAS NAVE 2', f"{totales_nave['Nave 2']:.2f}")
        q3.metric('HORAS NAVE 3', f"{totales_nave['Nave 3']:.2f}")
        if st.button('Guardar entrega de turno', type='primary', key=f'et23_g_{nave}_{n}'):
            errores_seguimiento = []
            for bloque, df_seg, meta in seguimientos:
                for _, row_seg in df_seg.iterrows():
                    datos_seg = {str(col): '' if pd.isna(val) else str(val).strip() for col, val in row_seg.to_dict().items()}
                    if any(datos_seg.values()):
                        faltan_seg = [nombre for nombre, cfg in meta.items() if cfg.get('obligatorio') and (not datos_seg.get(nombre, ''))]
                        if faltan_seg:
                            errores_seguimiento.append(f'{bloque}: ' + ', '.join(faltan_seg))
            repetida = not consultar(operacion_tabla('INTERFAZ_0082'), (fecha.isoformat(), analista)).empty
            faltan = []
            if not analista:
                faltan.append('Analista')
            if not turno:
                faltan.append('Turno')
            if errores_seguimiento:
                st.error('No se guardó la entrega. Completa los campos obligatorios de seguimiento: ' + '; '.join(errores_seguimiento) + '.')
            elif repetida:
                st.error('Registro repetido. Ya existe una entrega de turno para el mismo analista y la misma fecha. Corrige la fecha, selecciona otro analista o elimina previamente ese registro desde la matriz.')
            elif faltan:
                st.error('Completa los campos obligatorios: ' + ', '.join(faltan) + '.')
            else:
                eid = crear(operacion_tabla('INTERFAZ_0083'), (nave, fecha.isoformat(), analista, turno, referencia, total_c, total_h, st.session_state.auth['usuario'], now_iso()))
                for grupo, linea, producto, horas, carga, obs, orden, nvcat in filas_clasificadas:
                    if producto.strip() or horas or carga or obs.strip():
                        crear(operacion_tabla('INTERFAZ_0084'), (eid, grupo, linea, producto.strip(), horas, carga, obs.strip(), orden, nvcat))
                base_orden = len(filas)
                for j, (grupo, linea, tipo_analisis, resultado, obs, contador) in enumerate(resultados):
                    if resultado.strip() or obs.strip():
                        crear(operacion_tabla('INTERFAZ_0085'), (eid, 'ANÁLISIS ' + grupo, linea, tipo_analisis, 0, contador, (resultado + ' | ' + obs).strip(' |'), base_orden + j))
                for bloque, df, meta in seguimientos:
                    for orden, row in df.iterrows():
                        datos = {str(col): '' if pd.isna(val) else str(val) for col, val in row.to_dict().items()}
                        if any((v.strip() for v in datos.values())):
                            obligatorios = [nombre for nombre, cfg in meta.items() if cfg.get('obligatorio') and (not datos.get(nombre, '').strip())]
                            if obligatorios:
                                st.warning(f'Seguimiento {bloque}: faltan campos obligatorios: ' + ', '.join(obligatorios))
                                continue
                            legado = [datos.get(c, '') for c in ['Registro #', 'Hoja física', 'Carga electrónica', 'Correo', 'Descripción del seguimiento']]
                            crear(operacion_tabla('INTERFAZ_0086'), (eid, bloque, *legado, json.dumps(datos, ensure_ascii=False), int(orden)))
                guardar_matriz(eid, fecha.isoformat(), analista, total_c, totales_nave)
                audit(st.session_state.auth['usuario'], 'CREAR_ENTREGA_TURNO', f'{nave} | ID {eid}')
                st.session_state.entrega_nonce += 1
                st.success(f'Entrega de turno guardada correctamente. Número {eid}')
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return
    n = st.session_state.entrega_nonce
    st.markdown(f'<div class="registro-full-panel"><div class="registro-pill">{referencia}</div><div class="registro-full-title">ENTREGA DE TURNO CALIDAD PROCESOS</div><div class="registro-full-subtitle">NAVE 1</div>', unsafe_allow_html=True)
    a, b, c = st.columns([2, 1, 1])
    analista = a.selectbox('ANALISTA *', opt_blank(catalog('analista')), key=f'et_a_{n}')
    fecha = b.date_input('Fecha *', date.today(), key=f'et_f_{n}')
    turno = c.selectbox('Turno *', opt_blank(catalog('turno')), key=f'et_t_{n}')
    st.markdown('### Líneas y procesos')
    st.caption('Producto es un único campo libre por proceso. Los botones − y + cambian horas y carga de uno en uno; también puedes escribir decimales directamente.')
    filas = []
    for gi, (grupo, lineas) in enumerate(grupos.items()):
        st.markdown(f'<div style="background:#062C36;color:white;padding:.55rem .8rem;border-radius:12px 12px 0 0;font-weight:900">{grupo}</div>', unsafe_allow_html=True)
        producto = st.text_input(f'Producto / Item / descripcion de la linea {grupo}', key=f'et_prod_{gi}_{n}', placeholder='Escritura libre, no ligado a catálogos')
        h = st.columns([2.2, 1, 1, 2.2])
        h[0].markdown('**Sector**')
        h[1].markdown('**Horas trabajadas**')
        h[2].markdown('**Carga al SPAC**')
        h[3].markdown('**Observaciones**')
        for li, linea in enumerate(lineas):
            cols = st.columns([2.2, 1, 1, 2.2])
            cols[0].text_input('Sector', linea, disabled=True, key=f'et_l_{gi}_{li}_{n}', label_visibility='collapsed')
            horas = cols[1].number_input('Horas', min_value=0.0, step=1.0, format='%.2f', key=f'et_h_{gi}_{li}_{n}', label_visibility='collapsed')
            carga = cols[2].number_input('Carga', min_value=0.0, step=1.0, format='%.2f', key=f'et_c_{gi}_{li}_{n}', label_visibility='collapsed')
            obs = cols[3].text_input('Observaciones', key=f'et_o_{gi}_{li}_{n}', label_visibility='collapsed')
            filas.append((grupo, linea, producto, float(horas), float(carga), obs, len(filas)))
        st.markdown('<div style="height:.7rem"></div>', unsafe_allow_html=True)
    seguimientos = []
    st.markdown('### Seguimientos')
    for bi, bloque_cfg in enumerate(configuracion_seguimientos()):
        bloque = bloque_cfg['nombre']
        with st.expander(bloque, expanded=bi < 2):
            ed, meta = editor_seguimiento_dinamico(bloque_cfg, f'et_s_{bi}_{n}')
            seguimientos.append((bloque, ed, meta))
    totales_nave, filas_clasificadas = clasificar_filas(filas)
    total_h = sum(totales_nave.values())
    total_c = sum((x[4] for x in filas))
    m1, m2 = st.columns(2)
    m1.metric('TOTAL DE CARGA DE DATOS', f'{total_c:.2f}')
    m2.metric('TOTAL GENERAL DE HORAS', f'{total_h:.2f}')
    q1, q2, q3 = st.columns(3)
    q1.metric('HORAS NAVE 1', f"{totales_nave['Nave 1']:.2f}")
    q2.metric('HORAS NAVE 2', f"{totales_nave['Nave 2']:.2f}")
    q3.metric('HORAS NAVE 3', f"{totales_nave['Nave 3']:.2f}")
    if st.button('Guardar entrega de turno', type='primary', key=f'et_g_{n}'):
        errores_seguimiento = []
        for bloque, df_seg, meta in seguimientos:
            for _, row_seg in df_seg.iterrows():
                datos_seg = {str(col): '' if pd.isna(val) else str(val).strip() for col, val in row_seg.to_dict().items()}
                if any(datos_seg.values()):
                    faltan_seg = [nombre for nombre, cfg in meta.items() if cfg.get('obligatorio') and (not datos_seg.get(nombre, ''))]
                    if faltan_seg:
                        errores_seguimiento.append(f'{bloque}: ' + ', '.join(faltan_seg))
        repetida = not consultar(operacion_tabla('INTERFAZ_0087'), (fecha.isoformat(), analista)).empty
        faltan = []
        if not analista:
            faltan.append('Analista')
        if not turno:
            faltan.append('Turno')
        if errores_seguimiento:
            st.error('No se guardó la entrega. Completa los campos obligatorios de seguimiento: ' + '; '.join(errores_seguimiento) + '.')
        elif repetida:
            st.error('Registro repetido. Ya existe una entrega de turno para el mismo analista y la misma fecha. Corrige la fecha, selecciona otro analista o elimina previamente ese registro desde la matriz.')
        elif faltan:
            st.error('Completa los campos obligatorios: ' + ', '.join(faltan) + '.')
        else:
            eid = crear(operacion_tabla('INTERFAZ_0088'), (nave, fecha.isoformat(), analista, turno, referencia, total_c, total_h, st.session_state.auth['usuario'], now_iso()))
            for grupo, linea, producto, horas, carga, obs, orden, nvcat in filas_clasificadas:
                if producto.strip() or horas or carga or obs.strip():
                    crear(operacion_tabla('INTERFAZ_0089'), (eid, grupo, linea, producto.strip(), horas, carga, obs.strip(), orden, nvcat))
            for bloque, df, meta in seguimientos:
                for orden, row in df.iterrows():
                    datos = {str(col): '' if pd.isna(val) else str(val) for col, val in row.to_dict().items()}
                    if any((v.strip() for v in datos.values())):
                        obligatorios = [nombre for nombre, cfg in meta.items() if cfg.get('obligatorio') and (not datos.get(nombre, '').strip())]
                        if obligatorios:
                            st.warning(f'Seguimiento {bloque}: faltan campos obligatorios: ' + ', '.join(obligatorios))
                            continue
                        legado = [datos.get(c, '') for c in ['Registro #', 'Hoja física', 'Carga electrónica', 'Correo', 'Descripción del seguimiento']]
                        crear(operacion_tabla('INTERFAZ_0090'), (eid, bloque, *legado, json.dumps(datos, ensure_ascii=False), int(orden)))
            guardar_matriz(eid, fecha.isoformat(), analista, total_c, totales_nave)
            audit(st.session_state.auth['usuario'], 'CREAR_ENTREGA_TURNO', f'Nave 1 | ID {eid}')
            st.session_state.entrega_nonce += 1
            st.success(f'Entrega de turno guardada correctamente. Número {eid}')
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def admin_required():
    if not is_dev():
        st.warning('Solo el usuario administrador puede modificar catálogos.')
        return False
    return True

def page_catalogos():
    if not is_dev():
        st.title('Catálogo de Productos')
        st.caption('Consulta los productos disponibles y agrega nuevos elementos al catálogo.')
        productos = consultar(operacion_tabla('INTERFAZ_0091'))
        vista = productos.rename(columns={'id': 'ID', 'item': 'ITEM', 'descripcion': 'Descripción', 'cliente': 'Cliente', 'familia': 'Familia'})
        if vista.empty:
            st.info('Todavía no hay productos activos en el catálogo.')
        else:
            st.dataframe(vista, use_container_width=True, hide_index=True)
        with st.expander('Agregar producto', expanded=True):
            with st.form('usuario_agregar_producto', clear_on_submit=True):
                a, b = st.columns(2)
                item = a.text_input('ITEM *')
                descripcion = b.text_input('Descripción *')
                c, d = st.columns(2)
                cliente = c.text_input('Cliente *')
                familia = d.text_input('Familia *')
                agregar = st.form_submit_button('Agregar producto', type='primary')
            if agregar:
                valores = [item.strip(), descripcion.strip(), cliente.strip(), familia.strip()]
                etiquetas = ['ITEM', 'Descripción', 'Cliente', 'Familia']
                faltantes = [etiquetas[i] for i, v in enumerate(valores) if not v]
                existente = consultar(operacion_tabla('INTERFAZ_0092'), (valores[0],)) if valores[0] else pd.DataFrame()
                if faltantes:
                    st.error('Completa los campos obligatorios: ' + ', '.join(faltantes) + '.')
                elif not existente.empty and int(existente.iloc[0].get('activo', 1) or 0) == 1:
                    st.error('No fue posible agregar el producto porque el ITEM ya existe.')
                elif not existente.empty:
                    crear(operacion_tabla('INTERFAZ_0093'), (valores[1], valores[2], valores[3], int(existente.iloc[0].id)))
                    audit(st.session_state.auth['usuario'], 'REACTIVAR_PRODUCTO', f'ITEM {valores[0]}')
                    st.success('Producto agregado correctamente.')
                    st.rerun()
                else:
                    crear(operacion_tabla('INTERFAZ_0094'), tuple(valores))
                    audit(st.session_state.auth['usuario'], 'AGREGAR_PRODUCTO', f'ITEM {valores[0]}')
                    st.success('Producto agregado correctamente.')
                    st.rerun()
        return
    st.title('Catálogos')
    st.caption('Datos precargados en el catálogo inicial. El administrador puede agregar o eliminar elementos.')
    tab1, tab2, tab3, tab4, tab5 = st.tabs(['Productos', 'Defectos', 'Datos generales', 'Naves, líneas y sectores', 'Formatos entrega de turno'])

    def catalogo_seleccionable(tabla, consulta, columnas_vista, clave, titulo_singular, campos, insertar_sql, actualizar_sql, duplicado_sql, valores_opciones=None):
        df = consultar(consulta)
        vista = df.rename(columns=columnas_vista)
        nonce_key = f'cat_{clave}_nonce'
        nonce = st.session_state.get(nonce_key, 0)
        evento = st.dataframe(vista, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'cat_{clave}_tabla_{nonce}') if not vista.empty else None
        st.download_button(f'Descargar tabla de {titulo_singular.lower()}s', vista.to_csv(index=False).encode('utf-8-sig'), f"catalogo_{clave}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv', key=f'cat_{clave}_csv')
        filas = getattr(evento, 'selection', {}).get('rows', []) if evento is not None else []
        valido = bool(filas) and isinstance(filas[0], int) and (0 <= filas[0] < len(vista))
        rid = int(vista.iloc[filas[0]]['ID']) if valido else None
        with st.expander(f'Agregar {titulo_singular.lower()}', expanded=False):
            with st.form(f'cat_{clave}_agregar', clear_on_submit=True):
                valores = {}
                cols = st.columns(min(4, len(campos)))
                for i, (campo, etiqueta) in enumerate(campos):
                    opciones = (valores_opciones or {}).get(campo)
                    valores[campo] = cols[i % len(cols)].selectbox(etiqueta, opciones) if opciones else cols[i % len(cols)].text_input(etiqueta)
                agregar = st.form_submit_button(f'Agregar {titulo_singular.lower()}', type='primary')
            if agregar:
                limpios = {k: v.strip() if isinstance(v, str) else v for k, v in valores.items()}
                obligatorios = [etiqueta.replace(' *', '') for campo, etiqueta in campos if etiqueta.endswith('*') and (not str(limpios.get(campo, '')).strip())]
                if obligatorios:
                    st.error('Completa los campos obligatorios: ' + ', '.join(obligatorios) + '.')
                elif not consultar(duplicado_sql, tuple((limpios[k] for k, _ in campos))).empty:
                    st.error(f'No fue posible agregar el {titulo_singular.lower()} porque ya existe un registro con los mismos datos.')
                else:
                    crear(insertar_sql, tuple((limpios[k] for k, _ in campos)))
                    audit(st.session_state.auth['usuario'], f'AGREGAR_{clave.upper()}', str(limpios))
                    st.session_state[nonce_key] = nonce + 1
                    st.success(f'{titulo_singular} agregado correctamente.')
                    st.rerun()
        if rid:
            actual = consultar(operacion_tabla('INTERFAZ_0095', tabla), (rid,))
            if not actual.empty:
                r = actual.iloc[0]
                with st.expander(f'Editar {titulo_singular.lower()} seleccionado', expanded=True):
                    with st.form(f'cat_{clave}_editar_{rid}'):
                        editados = {}
                        cols = st.columns(min(4, len(campos)))
                        for i, (campo, etiqueta) in enumerate(campos):
                            valor = str(r[campo] or '')
                            opciones = (valores_opciones or {}).get(campo)
                            if opciones:
                                opciones = list(opciones)
                                if valor not in opciones:
                                    opciones.append(valor)
                                editados[campo] = cols[i % len(cols)].selectbox(etiqueta, opciones, index=idx_or_zero(opciones, valor))
                            else:
                                editados[campo] = cols[i % len(cols)].text_input(etiqueta, valor)
                        guardar = st.form_submit_button('Guardar cambios', type='primary')
                    if guardar:
                        limpios = {k: v.strip() if isinstance(v, str) else v for k, v in editados.items()}
                        obligatorios = [etiqueta.replace(' *', '') for campo, etiqueta in campos if etiqueta.endswith('*') and (not str(limpios.get(campo, '')).strip())]
                        params = tuple((limpios[k] for k, _ in campos))
                        if obligatorios:
                            st.error('Completa los campos obligatorios: ' + ', '.join(obligatorios) + '.')
                        elif not consultar(duplicado_sql + ' AND id<>?', params + (rid,)).empty:
                            st.error(f'Ya existe otro {titulo_singular.lower()} activo con los mismos datos.')
                        else:
                            crear(actualizar_sql, params + (rid,))
                            audit(st.session_state.auth['usuario'], f'EDITAR_{clave.upper()}', f'ID {rid}')
                            st.session_state[nonce_key] = nonce + 1
                            st.success(f'{titulo_singular} actualizado correctamente.')
                            st.rerun()
                if st.button(f'Eliminar {titulo_singular.lower()}', key=f'cat_{clave}_eliminar_{rid}'):
                    st.session_state[f'cat_{clave}_confirmar'] = rid
                if st.session_state.get(f'cat_{clave}_confirmar') == rid:
                    st.warning(f'El {titulo_singular.lower()} dejará de estar disponible para nuevos registros. Los datos históricos se conservarán.')
                    x, y = st.columns(2)
                    if x.button('Confirmar eliminación', key=f'cat_{clave}_ok_{rid}'):
                        crear(operacion_tabla('INTERFAZ_0096', tabla), (rid,))
                        audit(st.session_state.auth['usuario'], f'ELIMINAR_{clave.upper()}', f'ID {rid}')
                        st.session_state.pop(f'cat_{clave}_confirmar', None)
                        st.session_state[nonce_key] = nonce + 1
                        st.rerun()
                    if y.button('Cancelar', key=f'cat_{clave}_cancelar_{rid}'):
                        st.session_state.pop(f'cat_{clave}_confirmar', None)
                        st.session_state[nonce_key] = nonce + 1
                        st.rerun()
    with tab1:
        st.subheader('Productos')
        st.caption('Selecciona una fila para editarla o eliminarla. Los cambios se aplican automáticamente en los formularios relacionados.')
        catalogo_seleccionable('productos', operacion_tabla('INTERFAZ_0097'), {'id': 'ID', 'item': 'ITEM', 'descripcion': 'Descripción', 'cliente': 'Cliente', 'familia': 'Familia'}, 'productos', 'Producto', [('item', 'ITEM *'), ('descripcion', 'Descripción *'), ('cliente', 'Cliente *'), ('familia', 'Familia *')], operacion_tabla('INTERFAZ_0098'), operacion_tabla('INTERFAZ_0099'), operacion_tabla('INTERFAZ_0100'))
    with tab2:
        st.subheader('Defectos')
        st.caption('Selecciona una fila para editarla o eliminarla. Los cambios se aplican automáticamente en los formularios relacionados.')
        catalogo_seleccionable('defectos', operacion_tabla('INTERFAZ_0101'), {'id': 'ID', 'codigo': 'Código', 'defecto': 'Defecto', 'tipo_defecto': 'Tipo de defecto', 'clasificacion': 'Clasificación'}, 'defectos', 'Defecto', [('codigo', 'Código *'), ('defecto', 'Defecto *'), ('tipo_defecto', 'Tipo de defecto *'), ('clasificacion', 'Clasificación *')], operacion_tabla('INTERFAZ_0102'), operacion_tabla('INTERFAZ_0103'), operacion_tabla('INTERFAZ_0104'), {'tipo_defecto': catalog('tipo_defecto') or ['Funcional', 'Contaminación'], 'clasificacion': ['Inocuidad', 'Calidad', 'Salubridad', 'Legalidad']})
    with tab3:
        st.subheader('Datos generales')
        st.caption('Selecciona una fila para editarla o eliminarla. Los cambios se aplican automáticamente en los formularios relacionados.')
        etiquetas = {'Supervisores': 'supervisor', 'Analistas': 'analista', 'Nave': 'nave', 'Status': 'status', 'Responsable de detectar PNC': 'responsable_detecta', 'Etapa': 'etapa', 'Línea': 'linea_sector', 'Turno': 'turno', 'Defecto': 'tipo_defecto', 'Disposición': 'disposicion'}
        inv = {v: k for k, v in etiquetas.items()}
        raw = consultar(operacion_tabla('INTERFAZ_0105'))
        raw['lista'] = raw['categoria'].map(inv)
        raw = raw.dropna(subset=['lista'])
        vista = raw[['id', 'lista', 'valor']].rename(columns={'id': 'ID', 'lista': 'Lista', 'valor': 'Valor'})
        nonce = st.session_state.get('cat_datos_nonce', 0)
        evento = st.dataframe(vista, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'cat_datos_tabla_{nonce}') if not vista.empty else None
        st.download_button('Descargar tabla de datos generales', vista.to_csv(index=False).encode('utf-8-sig'), f"datos_generales_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv', key='cat_datos_csv')
        filas = getattr(evento, 'selection', {}).get('rows', []) if evento is not None else []
        rid = int(vista.iloc[filas[0]]['ID']) if filas and isinstance(filas[0], int) and (0 <= filas[0] < len(vista)) else None
        with st.expander('Agregar valor', expanded=False):
            with st.form('cat_datos_agregar', clear_on_submit=True):
                a, b = st.columns(2)
                lista = a.selectbox('Lista *', list(etiquetas))
                valor = b.text_input('Valor *')
                agregar = st.form_submit_button('Agregar valor', type='primary')
            if agregar:
                if not valor.strip():
                    st.error('Ingresa el valor que deseas agregar.')
                elif not consultar(operacion_tabla('INTERFAZ_0106'), (etiquetas[lista], valor.strip())).empty:
                    st.error('El valor ya existe en la lista seleccionada.')
                else:
                    crear(operacion_tabla('INTERFAZ_0107'), (etiquetas[lista], valor.strip()))
                    audit(st.session_state.auth['usuario'], 'AGREGAR_DATO_GENERAL', f'{lista} | {valor.strip()}')
                    st.session_state.cat_datos_nonce = nonce + 1
                    st.rerun()
        if rid:
            r = raw[raw['id'] == rid].iloc[0]
            with st.expander('Editar valor seleccionado', expanded=True):
                with st.form(f'cat_datos_editar_{rid}'):
                    a, b = st.columns(2)
                    lista = a.selectbox('Lista *', list(etiquetas), index=idx_or_zero(list(etiquetas), str(r.lista)))
                    valor = b.text_input('Valor *', str(r.valor))
                    guardar = st.form_submit_button('Guardar cambios', type='primary')
                if guardar:
                    cat = etiquetas[lista]
                    val = valor.strip()
                    dup = consultar(operacion_tabla('INTERFAZ_0108'), (cat, val, rid))
                    if not val:
                        st.error('Ingresa un valor válido.')
                    elif not dup.empty:
                        st.error('Ya existe otro valor igual en la lista seleccionada.')
                    else:
                        crear(operacion_tabla('INTERFAZ_0109'), (cat, val, rid))
                        audit(st.session_state.auth['usuario'], 'EDITAR_DATO_GENERAL', f'ID {rid}')
                        st.session_state.cat_datos_nonce = nonce + 1
                        st.rerun()
            if st.button('Eliminar valor', key=f'cat_datos_eliminar_{rid}'):
                st.session_state.cat_datos_confirmar = rid
            if st.session_state.get('cat_datos_confirmar') == rid:
                st.warning('El valor dejará de estar disponible para nuevos registros. Los datos históricos se conservarán.')
                x, y = st.columns(2)
                if x.button('Confirmar eliminación', key=f'cat_datos_ok_{rid}'):
                    crear(operacion_tabla('INTERFAZ_0110'), (rid,))
                    audit(st.session_state.auth['usuario'], 'ELIMINAR_DATO_GENERAL', f'ID {rid}')
                    st.session_state.pop('cat_datos_confirmar', None)
                    st.session_state.cat_datos_nonce = nonce + 1
                    st.rerun()
                if y.button('Cancelar', key=f'cat_datos_cancelar_{rid}'):
                    st.session_state.pop('cat_datos_confirmar', None)
                    st.session_state.cat_datos_nonce = nonce + 1
                    st.rerun()
    with tab4:
        st.subheader('Naves, líneas y sectores')
        st.caption('Este catálogo clasifica cada Línea y Sector para calcular por separado las horas generales de Nave 1, Nave 2 y Nave 3. No modifica la estructura visible del formato.')
        f1, f2 = st.columns([1, 2])
        filtro_nave = f1.multiselect('Filtrar por nave', ['Nave 1', 'Nave 2', 'Nave 3'], key='cat_general_naves')
        buscar = f2.text_input('Buscar línea o sector', key='cat_general_buscar')
        df_general = consultar(operacion_tabla('INTERFAZ_0111'))
        if filtro_nave:
            df_general = df_general[df_general['nave'].isin(filtro_nave)]
        if buscar.strip() and (not df_general.empty):
            q = buscar.strip()
            df_general = df_general[df_general['linea'].fillna('').astype(str).str.contains(q, case=False, na=False) | df_general['sector'].fillna('').astype(str).str.contains(q, case=False, na=False)]
        vista_general = df_general.rename(columns={'id': 'ID', 'nave': 'Nave', 'linea': 'Línea', 'sector': 'Sector', 'orden': 'Orden'})
        st.download_button('Descargar tabla de naves, líneas y sectores', vista_general.to_csv(index=False).encode('utf-8-sig'), f"catalogo_naves_lineas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv', key='cat_general_csv')
        nonce_general = st.session_state.get('cat_general_nonce', 0)
        evento_general = st.dataframe(vista_general, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'cat_general_tabla_{nonce_general}') if not vista_general.empty else None
        filas_general = getattr(evento_general, 'selection', {}).get('rows', []) if evento_general is not None else []
        posicion_general = bool(filas_general) and isinstance(filas_general[0], int) and (0 <= filas_general[0] < len(vista_general))
        id_general = int(vista_general.iloc[filas_general[0]]['ID']) if posicion_general else None
        if admin_required():
            with st.expander('Agregar relación general', expanded=False):
                with st.form('cat_general_agregar', clear_on_submit=True):
                    a, bx, c = st.columns(3)
                    nueva_nave = a.selectbox('Nave *', ['Nave 1', 'Nave 2', 'Nave 3'])
                    nueva_linea = bx.text_input('Línea *', placeholder='Ejemplo: BOB, BUTTER, CARAMELO')
                    nuevo_sector = c.text_input('Sector *', placeholder='Ejemplo: MD - BOB - CENTRO DE MASA')
                    agregar_general = st.form_submit_button('Agregar relación', type='primary')
                if agregar_general:
                    li = nueva_linea.strip()
                    se = nuevo_sector.strip()
                    if not li or not se:
                        st.error('Completa Línea y Sector.')
                    else:
                        duplicado = consultar(operacion_tabla('INTERFAZ_0112'), (nueva_nave, normalizar_catalogo(li), normalizar_catalogo(se)))
                        if not duplicado.empty:
                            st.error('La relación ya existe en el catálogo general.')
                        else:
                            orden = int(consultar(operacion_tabla('INTERFAZ_0113'), (nueva_nave,)).iloc[0]['n'])
                            crear(operacion_tabla('INTERFAZ_0114'), (nueva_nave, li, se, normalizar_catalogo(li), normalizar_catalogo(se), orden))
                            audit(st.session_state.auth['usuario'], 'AGREGAR_RELACION_NAVE', f'{nueva_nave} | {li} | {se}')
                            st.session_state.cat_general_nonce = nonce_general + 1
                            st.rerun()
            if id_general:
                actual = consultar(operacion_tabla('INTERFAZ_0115'), (id_general,))
                if not actual.empty:
                    r = actual.iloc[0]
                    with st.expander('Editar relación general seleccionada', expanded=True):
                        with st.form(f'cat_general_editar_{id_general}'):
                            naves = ['Nave 1', 'Nave 2', 'Nave 3']
                            a, bx, c, d = st.columns([1, 2, 2, 1])
                            nave_e = a.selectbox('Nave *', naves, index=idx_or_zero(naves, str(r.nave)))
                            linea_e = bx.text_input('Línea *', str(r.linea or ''))
                            sector_e = c.text_input('Sector *', str(r.sector or ''))
                            orden_e = d.number_input('Orden', 0, value=int(r.orden or 0), step=1)
                            guardar_general = st.form_submit_button('Guardar cambios', type='primary')
                        if guardar_general:
                            li = linea_e.strip()
                            se = sector_e.strip()
                            duplicado = consultar(operacion_tabla('INTERFAZ_0116'), (nave_e, normalizar_catalogo(li), normalizar_catalogo(se), id_general))
                            if not li or not se:
                                st.error('Completa Línea y Sector.')
                            elif not duplicado.empty:
                                st.error('Ya existe otra relación activa con esos datos.')
                            else:
                                crear(operacion_tabla('INTERFAZ_0117'), (nave_e, li, se, normalizar_catalogo(li), normalizar_catalogo(se), int(orden_e), id_general))
                                audit(st.session_state.auth['usuario'], 'EDITAR_RELACION_NAVE', f'ID {id_general} | {nave_e} | {li} | {se}')
                                st.session_state.cat_general_nonce = nonce_general + 1
                                st.rerun()
                    if st.button('Eliminar relación general', key=f'cat_general_eliminar_{id_general}'):
                        st.session_state.cat_general_confirmar = id_general
                    if st.session_state.get('cat_general_confirmar') == id_general:
                        st.warning('Esta relación dejará de utilizarse en las nuevas sumatorias generales por nave.')
                        x, y = st.columns(2)
                        if x.button('Sí, eliminar', key=f'cat_general_ok_{id_general}'):
                            crear(operacion_tabla('INTERFAZ_0118'), (id_general,))
                            audit(st.session_state.auth['usuario'], 'ELIMINAR_RELACION_NAVE', f'ID {id_general}')
                            st.session_state.pop('cat_general_confirmar', None)
                            st.session_state.cat_general_nonce = nonce_general + 1
                            st.rerun()
                        if y.button('Cancelar', key=f'cat_general_cancelar_{id_general}'):
                            st.session_state.pop('cat_general_confirmar', None)
                            st.session_state.cat_general_nonce = nonce_general + 1
                            st.rerun()
    with tab5:
        st.subheader('Formatos de entrega de turno')
        st.caption('Este catálogo define la estructura visible de cada formato y el TOTAL DE CARGA DE DATOS individual del analista. Cada Línea se muestra como encabezado y sus Sectores como filas.')
        nave_fmt = st.radio('Formato', ['Nave 1', 'Nave 2', 'Nave 3'], horizontal=True, key='fmt_nave')
        tipo_fmt = st.radio('Sección', ['PROCESO', 'ANALISIS'], format_func=lambda x: 'Líneas y sectores' if x == 'PROCESO' else 'Análisis fisicoquímicos', horizontal=True, key='fmt_tipo')
        df = consultar(operacion_tabla('INTERFAZ_0119'), (nave_fmt, tipo_fmt))
        vista = df.rename(columns={'id': 'ID', 'linea': 'Línea', 'sector': 'Sector', 'tipo_analisis': 'Tipo de análisis', 'orden_linea': 'Orden línea', 'orden_sector': 'Orden sector'})
        st.download_button('Descargar tabla del formato seleccionado', vista.to_csv(index=False).encode('utf-8-sig'), f"formato_entrega_{nave_fmt}_{tipo_fmt}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 'text/csv', key=f'fmt_csv_{nave_fmt}_{tipo_fmt}')
        nonce = st.session_state.get('fmt_nonce', 0)
        evento = st.dataframe(vista, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'fmt_table_{nave_fmt}_{tipo_fmt}_{nonce}') if not vista.empty else None
        rows = getattr(evento, 'selection', {}).get('rows', []) if evento is not None else []
        valido = bool(rows) and isinstance(rows[0], int) and (0 <= rows[0] < len(vista))
        rid = int(vista.iloc[rows[0]]['ID']) if valido else None
        if admin_required():
            with st.expander('Agregar elemento al formato', expanded=False):
                with st.form(f'fmt_add_{nave_fmt}_{tipo_fmt}', clear_on_submit=True):
                    a, b = st.columns(2)
                    linea = a.text_input('Línea *', placeholder='Ejemplo: BOB, BUTTER, CARAMELO')
                    sector = b.text_input('Sector *', placeholder='Ejemplo: MD - BOB - CENTRO DE MASA')
                    c, d, e = st.columns(3)
                    analisis = c.text_input('Tipo de análisis *' if tipo_fmt == 'ANALISIS' else 'Tipo de análisis', disabled=tipo_fmt != 'ANALISIS')
                    ol = d.number_input('Orden línea', 0, step=1)
                    os = e.number_input('Orden sector', 0, step=1)
                    agregar = st.form_submit_button('Agregar', type='primary')
                if agregar:
                    faltan = not linea.strip() or not sector.strip() or (tipo_fmt == 'ANALISIS' and (not analisis.strip()))
                    if faltan:
                        st.error('Completa Línea, Sector y Tipo de análisis cuando corresponda.')
                    else:
                        existente = consultar(operacion_tabla('INTERFAZ_0120'), (nave_fmt, tipo_fmt, linea.strip(), sector.strip(), analisis.strip() if tipo_fmt == 'ANALISIS' else ''))
                        if existente.empty:
                            crear(operacion_tabla('INTERFAZ_0121'), (nave_fmt, tipo_fmt, linea.strip(), sector.strip(), analisis.strip() if tipo_fmt == 'ANALISIS' else '', int(ol), int(os)))
                        else:
                            crear(operacion_tabla('INTERFAZ_0122'), (int(ol), int(os), int(existente.iloc[0].id)))
                        audit(st.session_state.auth['usuario'], 'AGREGAR_FORMATO_ENTREGA', f'{nave_fmt} | {tipo_fmt} | {linea} | {sector}')
                        st.session_state.fmt_nonce = nonce + 1
                        st.success('Elemento agregado. Ya aparecerá en el formato correspondiente.')
                        st.rerun()
            if rid:
                r = consultar(operacion_tabla('INTERFAZ_0123'), (rid,))
                if not r.empty:
                    r = r.iloc[0]
                    with st.expander('Editar elemento seleccionado', expanded=True):
                        with st.form(f'fmt_edit_{rid}'):
                            a, b = st.columns(2)
                            linea = a.text_input('Línea *', str(r.linea))
                            sector = b.text_input('Sector *', str(r.sector))
                            c, d, e = st.columns(3)
                            analisis = c.text_input('Tipo de análisis', str(r.tipo_analisis or ''), disabled=tipo_fmt != 'ANALISIS')
                            ol = d.number_input('Orden línea', 0, value=int(r.orden_linea))
                            os = e.number_input('Orden sector', 0, value=int(r.orden_sector))
                            guardar = st.form_submit_button('Guardar cambios', type='primary')
                        if guardar:
                            linea_editada = linea.strip()
                            sector_editado = sector.strip()
                            analisis_editado = analisis.strip() if tipo_fmt == 'ANALISIS' else ''
                            if not linea_editada or not sector_editado or (tipo_fmt == 'ANALISIS' and (not analisis_editado)):
                                st.error('Completa Línea, Sector y Tipo de análisis cuando corresponda.')
                            else:
                                duplicado = consultar(operacion_tabla('INTERFAZ_0124'), (nave_fmt, tipo_fmt, linea_editada, sector_editado, analisis_editado, rid))
                                if not duplicado.empty:
                                    st.error('No se puede guardar porque ya existe otro elemento activo con la misma Nave, Línea, Sector y Tipo de análisis.')
                                else:
                                    try:
                                        crear(operacion_tabla('INTERFAZ_0125'), (linea_editada, sector_editado, analisis_editado, int(ol), int(os), rid))
                                    except ErrorIntegridad:
                                        st.error('No se pudo guardar porque esa combinación ya existe en el catálogo. Modifica la Línea, el Sector o el Tipo de análisis.')
                                    else:
                                        audit(st.session_state.auth['usuario'], 'EDITAR_FORMATO_ENTREGA', f'ID {rid} | {nave_fmt} | {tipo_fmt} | {linea_editada} | {sector_editado} | {analisis_editado}')
                                        st.session_state.fmt_nonce = nonce + 1
                                        st.success('Elemento actualizado correctamente.')
                                        st.rerun()
                    if st.button('Eliminar del formato', key=f'fmt_del_{rid}'):
                        st.session_state.fmt_confirm = rid
                    if st.session_state.get('fmt_confirm') == rid:
                        st.warning('El elemento dejará de aparecer en el formato correspondiente.')
                        x, y = st.columns(2)
                        if x.button('Sí, eliminar', key=f'fmt_ok_{rid}'):
                            crear(operacion_tabla('INTERFAZ_0126'), (rid,))
                            audit(st.session_state.auth['usuario'], 'ELIMINAR_FORMATO_ENTREGA', f'ID {rid}')
                            st.session_state.pop('fmt_confirm', None)
                            st.session_state.fmt_nonce = nonce + 1
                            st.rerun()
                        if y.button('Cancelar', key=f'fmt_cancel_{rid}'):
                            st.session_state.pop('fmt_confirm', None)
                            st.session_state.fmt_nonce = nonce + 1
                            st.rerun()
        st.markdown('---')
        st.subheader('Seguimientos generales de entrega de turno')
        st.caption('Catálogo general para Nave 1, Nave 2 y Nave 3. Los cambios se reflejan automáticamente en los formatos nuevos.')
        seg = consultar(operacion_tabla('INTERFAZ_0127'))
        vista_seg = seg.rename(columns={'id': 'ID', 'nombre': 'Seguimiento', 'orden': 'Orden'})
        ns = st.session_state.get('seg_nonce', 0)
        ev = st.dataframe(vista_seg, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'seg_tabla_{ns}') if not vista_seg.empty else None
        rs = getattr(ev, 'selection', {}).get('rows', []) if ev is not None else []
        sid = int(vista_seg.iloc[rs[0]].ID) if rs and isinstance(rs[0], int) and (0 <= rs[0] < len(vista_seg)) else None
        with st.expander('Agregar seguimiento'):
            with st.form('seg_agregar', clear_on_submit=True):
                a, b = st.columns([3, 1])
                nom = a.text_input('Seguimiento *')
                orden = b.number_input('Orden', 0, step=1)
                alta = st.form_submit_button('Agregar', type='primary')
            if alta:
                nombre = nom.strip()
                ex = consultar(operacion_tabla('INTERFAZ_0128'), (nombre,)) if nombre else pd.DataFrame()
                if not nombre:
                    st.error('Ingresa el seguimiento.')
                elif not ex.empty:
                    crear(operacion_tabla('INTERFAZ_0129'), (nombre, int(orden), int(ex.iloc[0].id)))
                    audit(st.session_state.auth['usuario'], 'REACTIVAR_SEGUIMIENTO_ENTREGA', nombre)
                    st.session_state.seg_nonce = ns + 1
                    st.rerun()
                else:
                    crear(operacion_tabla('INTERFAZ_0130'), (nombre, int(orden)))
                    audit(st.session_state.auth['usuario'], 'AGREGAR_SEGUIMIENTO_ENTREGA', nombre)
                    st.session_state.seg_nonce = ns + 1
                    st.rerun()
        if sid:
            rr = consultar(operacion_tabla('INTERFAZ_0131'), (sid,)).iloc[0]
            st.markdown('#### Campos configurables del seguimiento')
            st.caption('Define el nombre del campo, el tipo de captura y sus opciones. Solo administradores pueden modificar esta configuración.')
            campos_seg = consultar(operacion_tabla('INTERFAZ_0132'), (sid,))
            vista_campos = campos_seg.rename(columns={'id': 'ID', 'nombre': 'Nombre del campo', 'tipo_campo': 'Tipo', 'opciones': 'Opciones', 'obligatorio': 'Obligatorio', 'orden': 'Orden'})
            nc = st.session_state.get('seg_campos_nonce', 0)
            ec = st.dataframe(vista_campos, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'seg_campos_{sid}_{nc}') if not vista_campos.empty else None
            rc = getattr(ec, 'selection', {}).get('rows', []) if ec is not None else []
            cid = int(vista_campos.iloc[rc[0]].ID) if rc and isinstance(rc[0], int) and (0 <= rc[0] < len(vista_campos)) else None
            tipos_campo = ['Texto', 'Texto largo', 'Número', 'Fecha', 'Lista desplegable', 'Sí / No / N/A']
            with st.expander('Agregar campo al seguimiento'):
                with st.form(f'seg_campo_add_{sid}', clear_on_submit=True):
                    a, b, c, d = st.columns([2, 1.4, 2, 1])
                    cn = a.text_input('Nombre del campo *')
                    ct = b.selectbox('Tipo de campo *', tipos_campo)
                    co = c.text_input('Opciones', help='Para lista desplegable, separa las opciones con |')
                    cob = d.checkbox('Obligatorio')
                    cord = st.number_input('Orden del campo', 0, step=1)
                    ca = st.form_submit_button('Agregar campo', type='primary')
                if ca:
                    nombre_campo = cn.strip()
                    opciones_campo = co.strip() if ct == 'Lista desplegable' else 'Sí|No|N/A' if ct == 'Sí / No / N/A' else ''
                    if not nombre_campo:
                        st.error('Ingresa el nombre del campo.')
                    elif ct == 'Lista desplegable' and (not opciones_campo):
                        st.error('Captura al menos una opción para la lista desplegable.')
                    else:
                        crear(operacion_tabla('INTERFAZ_0133'), (sid, nombre_campo, ct, opciones_campo, int(cob), int(cord)))
                        audit(st.session_state.auth['usuario'], 'AGREGAR_CAMPO_SEGUIMIENTO', f'Seguimiento {sid} | {nombre_campo}')
                        st.session_state.seg_campos_nonce = nc + 1
                        st.rerun()
            if cid:
                cr = campos_seg[campos_seg.id == cid].iloc[0]
                with st.expander('Editar campo seleccionado', expanded=True):
                    with st.form(f'seg_campo_edit_{cid}'):
                        a, b, c, d = st.columns([2, 1.4, 2, 1])
                        cen = a.text_input('Nombre del campo *', str(cr.nombre))
                        cet = b.selectbox('Tipo de campo *', tipos_campo, index=idx_or_zero(tipos_campo, str(cr.tipo_campo)))
                        ceo = c.text_input('Opciones', str(cr.opciones or ''), help='Separa las opciones con |')
                        ceob = d.checkbox('Obligatorio', value=bool(cr.obligatorio))
                        ceord = st.number_input('Orden del campo', 0, value=int(cr.orden or 0), step=1)
                        ceg = st.form_submit_button('Guardar campo', type='primary')
                    if ceg:
                        opciones_edit = ceo.strip() if cet == 'Lista desplegable' else 'Sí|No|N/A' if cet == 'Sí / No / N/A' else ''
                        if not cen.strip():
                            st.error('Ingresa el nombre del campo.')
                        elif cet == 'Lista desplegable' and (not opciones_edit):
                            st.error('Captura las opciones de la lista desplegable.')
                        else:
                            crear(operacion_tabla('INTERFAZ_0134'), (cen.strip(), cet, opciones_edit, int(ceob), int(ceord), cid))
                            audit(st.session_state.auth['usuario'], 'EDITAR_CAMPO_SEGUIMIENTO', f'ID {cid}')
                            st.session_state.seg_campos_nonce = nc + 1
                            st.rerun()
                if st.button('Eliminar campo seleccionado', key=f'seg_campo_del_{cid}'):
                    crear(operacion_tabla('INTERFAZ_0135'), (cid,))
                    audit(st.session_state.auth['usuario'], 'ELIMINAR_CAMPO_SEGUIMIENTO', f'ID {cid}')
                    st.session_state.seg_campos_nonce = nc + 1
                    st.rerun()
            with st.expander('Editar seguimiento seleccionado', expanded=True):
                with st.form(f'seg_editar_{sid}'):
                    a, b = st.columns([3, 1])
                    ne = a.text_input('Seguimiento *', str(rr.nombre))
                    oe = b.number_input('Orden', 0, value=int(rr.orden or 0), step=1)
                    guardar = st.form_submit_button('Guardar cambios', type='primary')
                if guardar and ne.strip():
                    crear(operacion_tabla('INTERFAZ_0136'), (ne.strip(), int(oe), sid))
                    audit(st.session_state.auth['usuario'], 'EDITAR_SEGUIMIENTO_ENTREGA', f'ID {sid}')
                    st.session_state.seg_nonce = ns + 1
                    st.rerun()
            if st.button('Eliminar seguimiento', key=f'seg_del_{sid}'):
                st.session_state.seg_confirm = sid
            if st.session_state.get('seg_confirm') == sid:
                st.warning('Dejará de aparecer en entregas nuevas. Los registros históricos se conservarán.')
                a, b = st.columns(2)
                if a.button('Confirmar eliminación', key=f'seg_ok_{sid}'):
                    crear(operacion_tabla('INTERFAZ_0137'), (sid,))
                    audit(st.session_state.auth['usuario'], 'ELIMINAR_SEGUIMIENTO_ENTREGA', f'ID {sid}')
                    st.session_state.pop('seg_confirm', None)
                    st.session_state.seg_nonce = ns + 1
                    st.rerun()
                if b.button('Cancelar', key=f'seg_no_{sid}'):
                    st.session_state.pop('seg_confirm', None)
                    st.rerun()

def page_usuarios():
    if not is_dev():
        st.warning('Esta sección está disponible únicamente para administradores.')
        return
    st.title('Administración de usuarios')
    st.caption('Selecciona directamente un registro de la tabla para editar, habilitar, inhabilitar o eliminar la cuenta.')
    if 'usuarios_nonce' not in st.session_state:
        st.session_state.usuarios_nonce = 0
    bloqueados = consultar(operacion_tabla('INTERFAZ_0138'))
    with st.expander(f'🔓 Habilitación de cuentas bloqueadas ({len(bloqueados)})', expanded=not bloqueados.empty):
        if bloqueados.empty:
            st.info('No hay usuarios bloqueados.')
        else:
            st.dataframe(bloqueados.rename(columns={'id': 'ID', 'usuario': 'Usuario', 'nombre': 'Nombre', 'rol': 'Rol', 'intentos_fallidos': 'Intentos fallidos'}), use_container_width=True, hide_index=True)
            opciones_bloqueados = {f'{r.usuario} | {r.nombre}': int(r.id) for r in bloqueados.itertuples()}
            seleccion_bloqueado = st.selectbox('Cuenta bloqueada', list(opciones_bloqueados), key='usuario_bloqueado_reactivar')
            if st.button('Reactivar cuenta y reiniciar intentos', type='primary', key='reactivar_usuario_bloqueado'):
                bid = opciones_bloqueados[seleccion_bloqueado]
                usuario_bloqueado = str(bloqueados[bloqueados.id == bid].iloc[0].usuario)
                crear(operacion_tabla('INTERFAZ_0139'), (bid,))
                audit(st.session_state.auth['usuario'], 'REACTIVAR_USUARIO_BLOQUEADO', f'ID {bid} | {usuario_bloqueado}')
                st.session_state.usuarios_nonce += 1
                st.success('Cuenta reactivada correctamente. Los intentos fallidos se reiniciaron.')
                st.rerun()
    st.subheader('Crear usuario')
    with st.expander('Agregar nuevo usuario', expanded=False):
        with st.form('crear_usuario_form', clear_on_submit=True):
            c1, c2 = st.columns(2)
            nuevo_usuario = c1.text_input('Usuario *', placeholder='Ejemplo: jperez')
            nuevo_nombre = c2.text_input('Nombre completo *', placeholder='Ejemplo: Juan Pérez')
            c3, c4 = st.columns(2)
            nueva_password = c3.text_input('Contraseña inicial *', type='password')
            nuevo_rol = c4.selectbox('Rol *', ['usuario', 'desarrollador'], format_func=lambda x: 'Usuario' if x == 'usuario' else 'Administrador / desarrollador')
            crear = st.form_submit_button('Crear usuario', type='primary')
        if crear:
            usuario = nuevo_usuario.strip()
            nombre = nuevo_nombre.strip()
            password = nueva_password.strip()
            faltan = []
            if not usuario:
                faltan.append('Usuario')
            if not nombre:
                faltan.append('Nombre completo')
            if not password:
                faltan.append('Contraseña inicial')
            if faltan:
                st.error('Completa los campos obligatorios: ' + ', '.join(faltan) + '.')
            elif not consultar(operacion_tabla('INTERFAZ_0140'), (usuario,)).empty:
                st.error('No fue posible crear la cuenta porque el nombre de usuario ya está registrado.')
            else:
                crear(operacion_tabla('INTERFAZ_0141'), (usuario, nombre, hash_password(password), nuevo_rol, now_iso()))
                audit(st.session_state.auth['usuario'], 'CREAR_USUARIO', f'Usuario {usuario} | Rol {nuevo_rol}')
                st.session_state.usuarios_nonce += 1
                st.success('Usuario creado correctamente.')
                st.rerun()
    st.subheader('Usuarios registrados')
    usuarios = consultar(operacion_tabla('INTERFAZ_0142'))
    if usuarios.empty:
        st.info('No se encontraron usuarios registrados.')
        return
    vista = usuarios.rename(columns={'id': 'ID', 'usuario': 'Usuario', 'nombre': 'Nombre completo', 'rol': 'Rol', 'intentos_fallidos': 'Intentos fallidos', 'requiere_cambio_pass': 'Cambio de contraseña pendiente', 'estado': 'Estado', 'creado_en': 'Fecha de creación'})
    evento = st.dataframe(vista, use_container_width=True, hide_index=True, on_select='rerun', selection_mode='single-row', key=f'usuarios_tabla_{st.session_state.usuarios_nonce}')
    filas = getattr(evento, 'selection', {}).get('rows', []) if evento is not None else []
    valido = bool(filas) and isinstance(filas[0], int) and (0 <= filas[0] < len(vista))
    if not valido:
        st.info('Selecciona un usuario en la tabla para administrar la cuenta.')
        return
    rid = int(vista.iloc[filas[0]]['ID'])
    actual_df = consultar(operacion_tabla('INTERFAZ_0143'), (rid,))
    if actual_df.empty:
        st.session_state.usuarios_nonce += 1
        st.rerun()
    r = actual_df.iloc[0]
    st.markdown(f"### Usuario seleccionado: {r['usuario']}")
    with st.expander('Editar información y rol', expanded=True):
        with st.form(f'editar_usuario_{rid}'):
            a, b = st.columns(2)
            usuario_editado = a.text_input('Usuario *', value=str(r['usuario'] or ''))
            nombre_editado = b.text_input('Nombre completo *', value=str(r['nombre'] or ''))
            c, d = st.columns(2)
            roles = ['usuario', 'desarrollador']
            rol_editado = c.selectbox('Rol *', roles, index=idx_or_zero(roles, str(r['rol'] or 'usuario')), format_func=lambda x: 'Usuario' if x == 'usuario' else 'Administrador / desarrollador')
            password_nueva = d.text_input('Nueva contraseña', type='password', help='Déjala vacía para conservar la contraseña actual.')
            guardar = st.form_submit_button('Guardar cambios', type='primary')
        if guardar:
            usuario = usuario_editado.strip()
            nombre = nombre_editado.strip()
            nueva = password_nueva.strip()
            if not usuario or not nombre:
                st.error('Completa el usuario y el nombre completo.')
            elif not consultar(operacion_tabla('INTERFAZ_0144'), (usuario, rid)).empty:
                st.error('No fue posible guardar porque el nombre de usuario ya está asignado a otra cuenta.')
            elif str(r['usuario']) == ADMIN_USER and rol_editado != 'desarrollador':
                st.error('La cuenta administradora principal debe conservar el rol de administrador/desarrollador.')
            else:
                if nueva:
                    crear(operacion_tabla('INTERFAZ_0145'), (usuario, nombre, rol_editado, hash_password(nueva), rid))
                else:
                    crear(operacion_tabla('INTERFAZ_0146'), (usuario, nombre, rol_editado, rid))
                audit(st.session_state.auth['usuario'], 'EDITAR_USUARIO', f'ID {rid} | Usuario {usuario} | Rol {rol_editado}')
                if rid == int(consultar(operacion_tabla('INTERFAZ_0147'), (st.session_state.auth['usuario'],)).iloc[0].id):
                    st.session_state.auth.update({'usuario': usuario, 'nombre': nombre, 'rol': rol_editado})
                st.session_state.usuarios_nonce += 1
                st.success('La información del usuario se actualizó correctamente.')
                st.rerun()
    activo = int(r['activo'] or 0) == 1
    c1, c2 = st.columns(2)
    if activo:
        inhabilitar = c1.button('Inhabilitar usuario', key=f'inhabilitar_usuario_{rid}', use_container_width=True)
        habilitar = False
    else:
        habilitar = c1.button('Habilitar usuario', key=f'habilitar_usuario_{rid}', use_container_width=True)
        inhabilitar = False
    eliminar = c2.button('Eliminar usuario', key=f'eliminar_usuario_{rid}', use_container_width=True)
    if inhabilitar:
        if str(r['usuario']) == st.session_state.auth['usuario']:
            st.error('No puedes inhabilitar la cuenta utilizada en la sesión actual.')
        elif str(r['usuario']) == ADMIN_USER:
            st.error('La cuenta administradora principal no puede inhabilitarse.')
        else:
            crear(operacion_tabla('INTERFAZ_0148'), (rid,))
            audit(st.session_state.auth['usuario'], 'INHABILITAR_USUARIO', f"ID {rid} | {r['usuario']}")
            st.session_state.usuarios_nonce += 1
            st.success('Usuario inhabilitado correctamente.')
            st.rerun()
    if habilitar:
        crear(operacion_tabla('INTERFAZ_0149'), (rid,))
        audit(st.session_state.auth['usuario'], 'HABILITAR_USUARIO', f"ID {rid} | {r['usuario']}")
        st.session_state.usuarios_nonce += 1
        st.success('Usuario habilitado correctamente.')
        st.rerun()
    if eliminar:
        st.session_state.usuario_confirmar_eliminacion = rid
    if st.session_state.get('usuario_confirmar_eliminacion') == rid:
        st.warning('La cuenta se eliminará de forma permanente. Los registros históricos y de auditoría asociados conservarán el nombre de usuario.')
        x, y = st.columns(2)
        if x.button('Confirmar eliminación', key=f'confirmar_usuario_{rid}', use_container_width=True):
            if str(r['usuario']) == st.session_state.auth['usuario']:
                st.error('No puedes eliminar la cuenta utilizada en la sesión actual.')
            elif str(r['usuario']) == ADMIN_USER:
                st.error('La cuenta administradora principal no puede eliminarse.')
            else:
                audit(st.session_state.auth['usuario'], 'ELIMINAR_USUARIO', f"ID {rid} | {r['usuario']}")
                crear(operacion_tabla('INTERFAZ_0150'), (rid,))
                reset_autoincrement('usuarios')
                st.session_state.pop('usuario_confirmar_eliminacion', None)
                st.session_state.usuarios_nonce += 1
                st.success('Usuario eliminado correctamente.')
                st.rerun()
        if y.button('Cancelar', key=f'cancelar_usuario_{rid}', use_container_width=True):
            st.session_state.pop('usuario_confirmar_eliminacion', None)
            st.session_state.usuarios_nonce += 1
            st.rerun()

def page_auditoria():
    st.title('Auditoría')
    st.dataframe(consultar(operacion_tabla('INTERFAZ_0151')), use_container_width=True, hide_index=True)
