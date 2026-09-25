import unicodedata
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from base_datos import consultar, crear

def _dataframe_con_columnas(dataframe, columnas):
    """Devuelve siempre un DataFrame con las columnas minimas requeridas."""
    if dataframe is None:
        salida = pd.DataFrame()
    elif isinstance(dataframe, pd.DataFrame):
        salida = dataframe.copy()
    elif isinstance(dataframe, dict):
        salida = pd.DataFrame([dataframe])
    else:
        salida = pd.DataFrame(dataframe)
    for columna in columnas:
        if columna not in salida.columns:
            salida[columna] = pd.Series(index=salida.index, dtype='object')
    return salida

def now_iso():
    return datetime.now().isoformat(timespec='seconds')

def opt_blank(values):
    return [''] + [str(v) for v in values if str(v).strip()]

def idx_or_zero(options, value):
    value = '' if value is None else str(value)
    return options.index(value) if value in options else 0

def normalizar_catalogo(v):
    t = unicodedata.normalize('NFKD', str(v or '').strip().upper())
    return ' '.join(''.join((c for c in t if not unicodedata.combining(c))).split())

def normalizar_nave(valor):
    texto = normalizar_catalogo(valor)
    mapa = {'1': 'Nave 1', 'NAVE 1': 'Nave 1', '2': 'Nave 2', 'NAVE 2': 'Nave 2', '3': 'Nave 3', 'NAVE 3': 'Nave 3'}
    return mapa.get(texto, str(valor or '').strip())

def clave_periodo(fecha, tipo):
    if tipo == 'SEMANA':
        iso = fecha.isocalendar()
        return f'{iso.year}-S{iso.week:02d}'
    return fecha.strftime('%Y-%m')

def nave_por_catalogo(linea, grupo=''):
    d = consultar({'accion': 'consultar', 'tabla': 'catalogo_naves_lineas', 'columnas': 'nave,linea_norm,sector_norm', 'filtros_texto': 'activo=1', 'orden_texto': '', 'limite': None})
    for v in (normalizar_catalogo(linea), normalizar_catalogo(grupo)):
        if v and (not d.empty):
            x = d[(d.linea_norm == v) | (d.sector_norm == v)]
            if not x.empty:
                return str(x.iloc[0].nave)
    return ''

def clasificar_filas(filas):
    t = {'Nave 1': 0.0, 'Nave 2': 0.0, 'Nave 3': 0.0, 'Sin clasificar': 0.0}
    out = []
    for g, l, p, h, c, o, n in filas:
        nv = nave_por_catalogo(l, g) or 'Sin clasificar'
        t[nv] += float(h or 0)
        out.append((g, l, p, h, c, o, n, nv))
    return (t, out)

def formato_entrega(nave, tipo='PROCESO'):
    df = consultar({'accion': 'consultar', 'tabla': 'catalogo_formatos_entrega', 'columnas': 'linea,sector,tipo_analisis,orden_linea,orden_sector', 'filtros_texto': 'formato_nave=? AND tipo=? AND activo=1', 'orden_texto': 'orden_linea,orden_sector,id', 'limite': None}, (nave, tipo))
    if tipo == 'ANALISIS':
        return [(str(r.linea), str(r.sector), str(r.tipo_analisis or '')) for r in df.itertuples()]
    resultado = {}
    for r in df.itertuples():
        resultado.setdefault(str(r.linea), []).append(str(r.sector))
    return resultado

def formato_seguimientos():
    df = consultar({'accion': 'consultar', 'tabla': 'catalogo_seguimientos_entrega', 'columnas': 'nombre', 'filtros_texto': 'activo=1', 'orden_texto': 'orden,id', 'limite': None})
    return df['nombre'].dropna().astype(str).str.strip().loc[lambda x: x.ne('')].tolist() if not df.empty else []

def _campos_seguimiento_predeterminados():
    return [
        {'id': 0, 'nombre': 'Registro #', 'tipo': 'Texto', 'opciones': [], 'obligatorio': False},
        {'id': 0, 'nombre': 'Hoja física', 'tipo': 'Sí / No / N/A', 'opciones': ['Sí', 'No', 'N/A'], 'obligatorio': False},
        {'id': 0, 'nombre': 'Carga electrónica', 'tipo': 'Sí / No / N/A', 'opciones': ['Sí', 'No', 'N/A'], 'obligatorio': False},
        {'id': 0, 'nombre': 'Correo', 'tipo': 'Sí / No / N/A', 'opciones': ['Sí', 'No', 'N/A'], 'obligatorio': False},
        {'id': 0, 'nombre': 'Descripción del seguimiento', 'tipo': 'Texto largo', 'opciones': [], 'obligatorio': False},
    ]


def configuracion_seguimientos():
    bloques = consultar({'accion': 'consultar', 'tabla': 'catalogo_seguimientos_entrega', 'columnas': 'id,nombre', 'filtros_texto': 'activo=1', 'orden_texto': 'orden,id', 'limite': None})
    bloques = _dataframe_con_columnas(bloques, ['id', 'nombre'])
    resultado = []
    for bloque in bloques.itertuples():
        nombre = str(getattr(bloque, 'nombre', '') or '').strip()
        if not nombre or pd.isna(getattr(bloque, 'id', None)):
            continue
        campos = consultar({'accion': 'consultar', 'tabla': 'catalogo_seguimientos_campos', 'columnas': 'id,nombre,tipo_campo,opciones,obligatorio,orden', 'filtros_texto': 'seguimiento_id=? AND activo=1', 'orden_texto': 'orden,id', 'limite': None}, (int(bloque.id),))
        campos = _dataframe_con_columnas(campos, ['id', 'nombre', 'tipo_campo', 'opciones', 'obligatorio', 'orden'])
        definiciones = []
        for campo in campos.itertuples():
            nombre_campo = str(getattr(campo, 'nombre', '') or '').strip()
            if not nombre_campo:
                continue
            opciones = [x.strip() for x in str(getattr(campo, 'opciones', '') or '').split('|') if x.strip()]
            definiciones.append({'id': int(campo.id), 'nombre': nombre_campo, 'tipo': str(getattr(campo, 'tipo_campo', '') or 'Texto'), 'opciones': opciones, 'obligatorio': bool(getattr(campo, 'obligatorio', False))})
        resultado.append({'id': int(bloque.id), 'nombre': nombre, 'campos': definiciones or _campos_seguimiento_predeterminados()})
    return resultado or [{'id': 0, 'nombre': 'Seguimientos generales', 'campos': _campos_seguimiento_predeterminados()}]

def catalog(cat):
    df = consultar(tabla='catalogos', columnas=['valor'], filtros={'categoria': cat, 'activo': 1}, ordenar_por=[('valor','asc')])
    valores = df['valor'].dropna().astype(str).str.strip().loc[lambda x: x.ne('')].tolist() if not df.empty else []
    if cat == 'nave':
        return list(dict.fromkeys(normalizar_nave(v) for v in valores if normalizar_nave(v)))
    if cat == 'disposicion' and not valores:
        return ['Reproceso','Retrabajo','Decomiso','Inspección','Aprobado en segunda instancia','Liberación','Devolución','Destrucción','Otro']
    return list(dict.fromkeys(valores))


def existe_valor_normalizado(tabla, columna, valor, excluir_id=None):
    """Comparo sin depender de funciones SQL ni del proveedor."""
    buscado = normalizar_catalogo(valor)
    if not buscado: return False
    df = consultar(tabla=tabla, columnas=['id', columna])
    if df.empty or columna not in df.columns: return False
    if excluir_id is not None:
        df = df[pd.to_numeric(df['id'], errors='coerce') != int(excluir_id)]
    return any(normalizar_catalogo(v) == buscado for v in df[columna].dropna())

def guardar_matriz(eid, fecha, analista, carga, tot):
    analista_limpio = str(analista or '').strip()
    crear({'accion': 'crear', 'tabla': 'matriz_entrega', 'columnas': ['fecha', 'analista', 'entrega_id', 'total_carga_datos', 'horas_nave1', 'horas_nave2', 'horas_nave3', 'actualizado_en'], 'upsert': False, 'ignorar': False}, (fecha, analista_limpio, eid, carga, tot.get('Nave 1', 0), tot.get('Nave 2', 0), tot.get('Nave 3', 0), now_iso()))

def audit(u, a, d):
    crear({'accion': 'crear', 'tabla': 'auditoria', 'columnas': ['usuario', 'accion', 'detalle', 'fecha_hora'], 'upsert': False, 'ignorar': False}, (u, a, d, now_iso()))

def new_folio():
    pref = f'PNC-{datetime.now().year}-'
    df = consultar({'accion': 'consultar', 'tabla': 'pnc_registros', 'columnas': 'folio', 'filtros_texto': 'folio LIKE ?', 'orden_texto': 'folio DESC', 'limite': 1}, (f'{pref}%',))
    n = 0
    if not df.empty:
        try:
            n = int(str(df.iloc[0]['folio']).split('-')[-1])
        except Exception:
            n = 0
    return f'{pref}{n + 1:05d}'

def is_dev():
    return st.session_state.get('auth', {}).get('rol') == 'desarrollador'

def aplicar_ajustes_diarios(tabla, tipo_entidad, columna_entidad):
    ajustes = consultar({'accion': 'consultar', 'tabla': 'ajustes_diarios_spac', 'columnas': 'entidad,fecha,valor', 'filtros_texto': 'tipo_entidad=?', 'orden_texto': '', 'limite': None}, (tipo_entidad,))
    ajustes = _dataframe_con_columnas(ajustes, ['entidad', 'fecha', 'valor'])
    for r in ajustes.itertuples():
        entidad = str(getattr(r, 'entidad', '') or '').strip()
        fecha = str(getattr(r, 'fecha', '') or '').strip()
        valor = getattr(r, 'valor', None)
        if entidad in tabla.index and fecha in tabla.columns:
            tabla.loc[entidad, fecha] = float(valor) if pd.notna(valor) else None
    return tabla


def datos_grafica_cumplimiento(tipo_entidad, periodo_tipo):
    columnas_salida = ['Periodo', 'Entidad', 'Cumplimiento %']
    cargados = consultar({'accion': 'consultar', 'tabla': 'metas_carga_spac', 'columnas': 'entidad,periodo_clave,meta', 'filtros_texto': 'tipo_entidad=? AND periodo_tipo=?', 'orden_texto': 'periodo_clave,entidad', 'limite': None}, (tipo_entidad, periodo_tipo))
    cargados = _dataframe_con_columnas(cargados, ['entidad', 'periodo_clave', 'meta'])
    if cargados.empty:
        return pd.DataFrame(columns=columnas_salida)

    registros = consultar({'accion': 'consultar', 'tabla': 'matriz_entrega', 'columnas': 'fecha,analista,total_carga_datos,horas_nave1,horas_nave2,horas_nave3', 'filtros_texto': '', 'orden_texto': '', 'limite': None})
    registros = _dataframe_con_columnas(registros, ['fecha', 'analista', 'total_carga_datos', 'horas_nave1', 'horas_nave2', 'horas_nave3'])
    registros['fecha_dt'] = pd.to_datetime(registros['fecha'], errors='coerce').dt.date
    for columna in ['total_carga_datos', 'horas_nave1', 'horas_nave2', 'horas_nave3']:
        registros[columna] = pd.to_numeric(registros[columna], errors='coerce')

    ajustes = consultar({'accion': 'consultar', 'tabla': 'ajustes_diarios_spac', 'columnas': 'entidad,fecha,valor', 'filtros_texto': 'tipo_entidad=?', 'orden_texto': '', 'limite': None}, (tipo_entidad,))
    ajustes = _dataframe_con_columnas(ajustes, ['entidad', 'fecha', 'valor'])
    ajustes['entidad'] = ajustes['entidad'].fillna('').astype(str).str.strip()
    ajustes['fecha'] = pd.to_datetime(ajustes['fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
    ajustes['valor'] = pd.to_numeric(ajustes['valor'], errors='coerce')

    calidad = pd.DataFrame(columns=['fecha', 'nave', 'total_carga_datos', 'fecha_dt'])
    if tipo_entidad == 'CALIDAD_NAVE':
        calidad = consultar({'accion': 'vista', 'nombre': 'vista_calidad_nave_diaria'})
        calidad = _dataframe_con_columnas(calidad, ['fecha', 'nave', 'total_carga_datos'])
        calidad['fecha_dt'] = pd.to_datetime(calidad['fecha'], errors='coerce').dt.date
        calidad['total_carga_datos'] = pd.to_numeric(calidad['total_carga_datos'], errors='coerce')

    resultado = []
    for fila in cargados.itertuples():
        periodo = str(getattr(fila, 'periodo_clave', '') or '').strip()
        entidad = str(getattr(fila, 'entidad', '') or '').strip()
        if not periodo or not entidad:
            continue
        try:
            datos_cargados = float(getattr(fila, 'meta', 0) or 0)
            if periodo_tipo == 'SEMANA':
                anio, semana = periodo.split('-S')
                inicio = date.fromisocalendar(int(anio), int(semana), 1)
                fin = date.fromisocalendar(int(anio), int(semana), 7)
            else:
                inicio = datetime.strptime(periodo + '-01', '%Y-%m-%d').date()
                fin = (pd.Timestamp(inicio) + pd.offsets.MonthBegin(1)).date() - timedelta(days=1)
        except (TypeError, ValueError):
            continue
        fechas = [x.date().isoformat() for x in pd.date_range(inicio, fin, freq='D')]
        if tipo_entidad == 'ANALISTA':
            base = registros[(registros['fecha_dt'] >= inicio) & (registros['fecha_dt'] <= fin) & (registros['analista'].fillna('').astype(str) == entidad)].copy()
            base['fecha_clave'] = pd.to_datetime(base['fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
            serie = base.groupby('fecha_clave')['total_carga_datos'].sum().reindex(fechas)
        elif tipo_entidad == 'CALIDAD_NAVE':
            base = calidad[(calidad['fecha_dt'] >= inicio) & (calidad['fecha_dt'] <= fin) & (calidad['nave'].fillna('').astype(str) == entidad)].copy()
            base['fecha_clave'] = pd.to_datetime(base['fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
            serie = base.groupby('fecha_clave')['total_carga_datos'].sum().reindex(fechas)
        else:
            campo = {'Nave 1': 'horas_nave1', 'Nave 2': 'horas_nave2', 'Nave 3': 'horas_nave3'}.get(entidad)
            if not campo:
                continue
            base = registros[(registros['fecha_dt'] >= inicio) & (registros['fecha_dt'] <= fin)].copy()
            base['fecha_clave'] = pd.to_datetime(base['fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
            serie = base.groupby('fecha_clave')[campo].sum(min_count=1).reindex(fechas)
        for ajuste in ajustes[ajustes['entidad'] == entidad].itertuples():
            fecha_ajuste = str(getattr(ajuste, 'fecha', '') or '')
            if fecha_ajuste in serie.index:
                valor = getattr(ajuste, 'valor', None)
                serie.loc[fecha_ajuste] = float(valor) if pd.notna(valor) else None
        teorico = float(pd.to_numeric(serie, errors='coerce').fillna(0).sum())
        resultado.append({'Periodo': periodo, 'Entidad': entidad, 'Cumplimiento %': datos_cargados / teorico * 100 if teorico > 0 else None})
    return pd.DataFrame(resultado, columns=columnas_salida)

