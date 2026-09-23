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
from base_datos import consultar, crear, editar, eliminar, guardar_varios, ErrorIntegridad, reiniciar_consecutivo, inicializar_base

def now_iso():
    return datetime.now().isoformat(timespec='seconds')

def opt_blank(values):
    return [''] + [str(v) for v in values if str(v).strip()]

def idx_or_zero(options, value):
    value = '' if value is None else str(value)
    return options.index(value) if value in options else 0

def normalizar_catalogo(v):
    import unicodedata
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

def configuracion_seguimientos():
    bloques = consultar({'accion': 'consultar', 'tabla': 'catalogo_seguimientos_entrega', 'columnas': 'id,nombre', 'filtros_texto': 'activo=1', 'orden_texto': 'orden,id', 'limite': None})
    resultado = []
    for bloque in bloques.itertuples():
        campos = consultar({'accion': 'consultar', 'tabla': 'catalogo_seguimientos_campos', 'columnas': 'id,nombre,tipo_campo,opciones,obligatorio,orden', 'filtros_texto': 'seguimiento_id=? AND activo=1', 'orden_texto': 'orden,id', 'limite': None}, (int(bloque.id),))
        definiciones = []
        for campo in campos.itertuples():
            opciones = [x.strip() for x in str(campo.opciones or '').split('|') if x.strip()]
            definiciones.append({'id': int(campo.id), 'nombre': str(campo.nombre), 'tipo': str(campo.tipo_campo or 'Texto'), 'opciones': opciones, 'obligatorio': bool(campo.obligatorio)})
        resultado.append({'id': int(bloque.id), 'nombre': str(bloque.nombre), 'campos': definiciones})
    return resultado

def catalog(cat):
    df = consultar({'accion': 'consultar', 'tabla': 'catalogos', 'columnas': 'valor', 'filtros_texto': 'categoria=? AND activo=1', 'orden_texto': 'valor', 'limite': None}, (cat,))
    valores = df['valor'].tolist() if not df.empty else []
    if cat == 'nave':
        return list(dict.fromkeys((normalizar_nave(v) for v in valores if normalizar_nave(v))))
    return valores

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
    for r in ajustes.itertuples():
        if str(r.entidad) in tabla.index and str(r.fecha) in tabla.columns:
            tabla.loc[str(r.entidad), str(r.fecha)] = float(r.valor) if pd.notna(r.valor) else None
    return tabla

def datos_grafica_cumplimiento(tipo_entidad, periodo_tipo):
    cargados = consultar({'accion': 'consultar', 'tabla': 'metas_carga_spac', 'columnas': 'entidad,periodo_clave,meta', 'filtros_texto': 'tipo_entidad=? AND periodo_tipo=?', 'orden_texto': 'periodo_clave,entidad', 'limite': None}, (tipo_entidad, periodo_tipo))
    if cargados.empty:
        return pd.DataFrame(columns=['Periodo', 'Entidad', 'Cumplimiento %'])
    registros = consultar({'accion': 'consultar', 'tabla': 'matriz_entrega', 'columnas': 'fecha,analista,total_carga_datos,horas_nave1,horas_nave2,horas_nave3', 'filtros_texto': '', 'orden_texto': '', 'limite': None})
    registros['fecha_dt'] = pd.to_datetime(registros['fecha'], errors='coerce').dt.date
    ajustes = consultar({'accion': 'consultar', 'tabla': 'ajustes_diarios_spac', 'columnas': 'entidad,fecha,valor', 'filtros_texto': 'tipo_entidad=?', 'orden_texto': '', 'limite': None}, (tipo_entidad,))
    resultado = []
    for fila in cargados.itertuples():
        periodo = str(fila.periodo_clave)
        datos_cargados = float(fila.meta or 0)
        if periodo_tipo == 'SEMANA':
            anio, semana = periodo.split('-S')
            inicio = date.fromisocalendar(int(anio), int(semana), 1)
            fin = date.fromisocalendar(int(anio), int(semana), 7)
        else:
            inicio = datetime.strptime(periodo + '-01', '%Y-%m-%d').date()
            fin = (pd.Timestamp(inicio) + pd.offsets.MonthBegin(1)).date() - timedelta(days=1)
        fechas = [x.date().isoformat() for x in pd.date_range(inicio, fin, freq='D')]
        entidad = str(fila.entidad)
        if tipo_entidad == 'ANALISTA':
            serie = registros[(registros['fecha_dt'] >= inicio) & (registros['fecha_dt'] <= fin) & (registros['analista'].astype(str) == entidad)].groupby('fecha')['total_carga_datos'].sum().reindex(fechas)
        elif tipo_entidad == 'CALIDAD_NAVE':
            calidad = consultar({'accion': 'vista', 'nombre': 'vista_calidad_nave_diaria'})
            calidad['fecha_dt'] = pd.to_datetime(calidad['fecha'], errors='coerce').dt.date
            serie = calidad[(calidad['fecha_dt'] >= inicio) & (calidad['fecha_dt'] <= fin) & (calidad['nave'].astype(str) == entidad)].groupby('fecha')['total_carga_datos'].sum().reindex(fechas)
        else:
            campo = {'Nave 1': 'horas_nave1', 'Nave 2': 'horas_nave2', 'Nave 3': 'horas_nave3'}.get(entidad)
            if not campo:
                continue
            serie = registros[(registros['fecha_dt'] >= inicio) & (registros['fecha_dt'] <= fin)].groupby('fecha')[campo].sum(min_count=1).reindex(fechas)
        for ajuste in ajustes[ajustes['entidad'].astype(str) == entidad].itertuples():
            if str(ajuste.fecha) in serie.index:
                serie.loc[str(ajuste.fecha)] = float(ajuste.valor)
        datos_teoricos = float(serie.fillna(0).sum())
        porcentaje = datos_cargados / datos_teoricos * 100 if datos_teoricos > 0 else None
        resultado.append({'Periodo': periodo, 'Entidad': entidad, 'Cumplimiento %': porcentaje})
    return pd.DataFrame(resultado)
