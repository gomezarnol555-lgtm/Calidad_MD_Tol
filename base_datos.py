import os
import re
import pandas as pd
import streamlit as st
from supabase import create_client

class ErrorIntegridad(Exception):
    pass

_CLIENTE = None

def _secreto(nombre, alternativos=()):
    for clave in (nombre,) + tuple(alternativos):
        valor = os.getenv(clave, '').strip()
        if not valor:
            try: valor = str(st.secrets.get(clave, '')).strip()
            except Exception: valor = ''
        if valor: return valor
    return ''

def cliente():
    global _CLIENTE
    if _CLIENTE is None:
        url = _secreto('SUPABASE_URL').rstrip('/')
        key = _secreto('SUPABASE_SECRET_KEY', ('SUPABASE_KEY','SUPABASE_SERVICE_ROLE_KEY'))
        if not url or not key: raise RuntimeError('Faltan SUPABASE_URL o SUPABASE_SECRET_KEY.')
        _CLIENTE = create_client(url, key)
    return _CLIENTE

def diagnostico_conexion():
    try:
        cliente().table('app_config').select('clave').limit(1).execute()
        return True, 'Conexion correcta.'
    except Exception as exc:
        return False, 'Supabase rechazo la validacion: ' + str(exc)[:500]

def verificar_conexion(): return diagnostico_conexion()[0]
def inicializar_base():
    ok, mensaje = diagnostico_conexion()
    if not ok: raise RuntimeError(mensaje)
    return True

def _separar_expresiones(texto):
    partes, actual, nivel = [], [], 0
    for caracter in str(texto or ''):
        if caracter == '(': nivel += 1
        elif caracter == ')' and nivel: nivel -= 1
        if caracter == ',' and nivel == 0:
            partes.append(''.join(actual).strip()); actual = []
        else: actual.append(caracter)
    if actual: partes.append(''.join(actual).strip())
    return [x for x in partes if x]

def _normalizar_select(expresion):
    texto = str(expresion or '').strip()
    if texto == '*': return '*'
    # COALESCE(intentos_fallidos,0) AS intentos_fallidos
    m = re.fullmatch(r'COALESCE\s*\(\s*(?:\w+\.)?["\']?([A-Za-z_]\w*)["\']?\s*,.*\)\s*(?:AS\s+["\']?([A-Za-z_]\w*)["\']?)?', texto, re.I)
    if m: return m.group(1)
    # CAST(codigo AS INTEGER) AS codigo_num
    m = re.fullmatch(r'CAST\s*\(\s*(?:\w+\.)?["\']?([A-Za-z_]\w*)["\']?\s+AS\s+[^)]+\)\s*(?:AS\s+["\']?([A-Za-z_]\w*)["\']?)?', texto, re.I)
    if m: return m.group(1)
    # columna [AS alias]
    m = re.fullmatch(r'(?:\w+\.)?["\']?([A-Za-z_]\w*)["\']?\s*(?:AS\s+["\']?([A-Za-z_]\w*)["\']?)?', texto, re.I)
    if m:
        columna, alias = m.groups()
        return f'{alias}:{columna}' if alias and alias != columna else columna
    return None

def _columnas_lista(columnas):
    if columnas in (None, '*'): return '*'
    expresiones = list(columnas) if isinstance(columnas,(list,tuple)) else _separar_expresiones(columnas)
    salida = []
    for expresion in expresiones:
        valor = _normalizar_select(expresion)
        if valor and valor not in salida: salida.append(valor)
    return ','.join(salida) if salida else '*'

def _normalizar_orden(expresion):
    texto = str(expresion or '').strip()
    if not texto: return None
    direccion = 'desc' if re.search(r'\s+DESC\s*$', texto, re.I) else 'asc'
    texto = re.sub(r'\s+(ASC|DESC)\s*$', '', texto, flags=re.I).strip()
    m = re.fullmatch(r'(?:CAST|LOWER|UPPER|TRIM)\s*\(\s*(?:\w+\.)?["\']?([A-Za-z_]\w*)["\']?(?:\s+AS\s+[^)]+)?\)', texto, re.I)
    if m: return m.group(1), direccion
    columna = texto.split('.')[-1].strip('" \'')
    return (columna,direccion) if re.fullmatch(r'[A-Za-z_]\w*', columna) else None

def _aplicar_filtros(query, filtros):
    for campo, valor in (filtros or {}).items():
        campo = str(campo).split('.')[-1].strip('" ')
        if isinstance(valor, dict):
            for op,dato in valor.items():
                metodo = {'neq':'neq','like':'like','ilike':'ilike','gt':'gt','gte':'gte','lt':'lt','lte':'lte','is':'is_'}.get(op)
                if metodo: query = getattr(query, metodo)(campo,dato)
        elif isinstance(valor,(list,tuple,set)): query = query.in_(campo,list(valor))
        elif valor is None: query = query.is_(campo,'null')
        else: query = query.eq(campo,valor)
    return query

def consultar(tabla=None,columnas='*',filtros=None,ordenar_por=None,limite=None,uno=False,operacion=None,parametros=()):
    if isinstance(tabla,dict):
        if columnas != '*': parametros = columnas
        operacion, tabla = tabla, None
    if operacion is not None: return _ejecutar_descriptor(operacion,parametros,'consulta')
    q = cliente().table(tabla).select(_columnas_lista(columnas))
    q = _aplicar_filtros(q,filtros)
    for item in ordenar_por or []:
        orden = _normalizar_orden(f'{item[0]} {item[1] if len(item)>1 else "asc"}') if isinstance(item,(list,tuple)) else _normalizar_orden(item)
        if orden: q = q.order(orden[0], desc=orden[1]=='desc')
    if limite: q = q.limit(int(limite))
    if uno: q = q.limit(1)
    data = q.execute().data or []
    return (data[0] if data else None) if uno else pd.DataFrame(data)

def consultar_uno(tabla,columnas='*',filtros=None,ordenar_por=None):
    return consultar(tabla,columnas,filtros,ordenar_por,1,True)

def crear(tabla=None,datos=None,upsert=False,on_conflict=None):
    if isinstance(tabla,dict): return _ejecutar_descriptor(tabla,datos or (),'cambio')
    try:
        q = cliente().table(tabla).upsert(datos,on_conflict=on_conflict) if upsert else cliente().table(tabla).insert(datos)
        data = q.execute().data or []
        return data[0].get('id') if data and isinstance(data[0],dict) else None
    except Exception as exc:
        if any(x in str(exc).lower() for x in ('duplicate','unique','23505')): raise ErrorIntegridad(str(exc)) from exc
        raise

def editar(tabla,datos=None,filtros=None):
    if isinstance(tabla,dict): return _ejecutar_descriptor(tabla,datos or (),'cambio')
    if not filtros: raise ValueError('Editar requiere filtros.')
    return len(_aplicar_filtros(cliente().table(tabla).update(datos),filtros).execute().data or [])

def eliminar(tabla,filtros=None,logico=False):
    if isinstance(tabla,dict): return _ejecutar_descriptor(tabla,filtros or (),'cambio')
    if not filtros: raise ValueError('Eliminar requiere filtros.')
    if logico: return editar(tabla,{'activo':0},filtros)
    return len(_aplicar_filtros(cliente().table(tabla).delete(),filtros).execute().data or [])

def contar(tabla,filtros=None):
    r = _aplicar_filtros(cliente().table(tabla).select('id',count='exact',head=True),filtros).execute()
    return int(r.count or 0)
def existe(tabla,filtros): return contar(tabla,filtros)>0

def crear_varios(tabla,filas,upsert=False,on_conflict=None):
    if not filas: return []
    q = cliente().table(tabla).upsert(filas,on_conflict=on_conflict) if upsert else cliente().table(tabla).insert(filas)
    return q.execute().data or []

def guardar_varios(operaciones):
    salida=[]
    for op in operaciones:
        if op['accion']=='crear': salida.append(crear(op['tabla'],op.get('datos',{}),op.get('upsert',False),op.get('on_conflict')))
        elif op['accion']=='editar': salida.append(editar(op['tabla'],op.get('datos',{}),op.get('filtros',{})))
        elif op['accion']=='eliminar': salida.append(eliminar(op['tabla'],op.get('filtros',{}),op.get('logico',False)))
    return salida

def ejecutar_funcion(nombre,parametros=None): return cliente().rpc(nombre,parametros or {}).execute().data
def columnas_tabla(tabla): return {str(x.get('nombre_columna')) for x in (ejecutar_funcion('columnas_tabla',{'nombre_tabla':tabla}) or [])}
def reiniciar_consecutivo(tabla): return None

def _literal(texto):
    texto=str(texto).strip()
    if texto.upper()=='NULL': return None
    if texto.upper()=='TRUE': return True
    if texto.upper()=='FALSE': return False
    if len(texto)>1 and texto[0] in "'\"" and texto[-1]==texto[0]: return texto[1:-1]
    if re.fullmatch(r'-?\d+',texto): return int(texto)
    if re.fullmatch(r'-?\d+\.\d+',texto): return float(texto)
    return texto

def _filtros_descriptor(texto,parametros,inicio=0):
    filtros={}; indice=inicio
    for parte in re.split(r'\s+AND\s+',str(texto or ''),flags=re.I):
        parte=parte.strip()
        m=re.match(r'(?:\w+\.)?["\']?([A-Za-z_]\w*)["\']?\s*(=|<>|!=|LIKE|ILIKE|>=|<=|>|<)\s*(.+)$',parte,re.I)
        if not m: continue
        campo,op,valor=m.groups()
        if valor.strip()=='?':
            if indice>=len(parametros): continue
            valor=parametros[indice]; indice+=1
        else: valor=_literal(valor)
        mapa={'<>':'neq','!=':'neq','LIKE':'like','ILIKE':'ilike','>':'gt','>=':'gte','<':'lt','<=':'lte'}
        filtros[campo]=valor if op=='=' else {mapa[op.upper()]:valor}
    return filtros,indice

def _ejecutar_descriptor(op,parametros=(),espera='consulta'):
    parametros=tuple(parametros or ()); accion=op.get('accion')
    if accion=='vista': return consultar(op['nombre'])
    if accion=='columnas': return [{'nombre_columna':x} for x in columnas_tabla(op['tabla'])]
    if accion=='rpc':
        data=ejecutar_funcion(op['nombre'],{'argumentos':list(parametros)})
        return pd.DataFrame(data or []) if espera=='consulta' else data
    if accion=='consultar':
        filtros,_=_filtros_descriptor(op.get('filtros_texto',''),parametros)
        orden=[]
        texto=str(op.get('orden_texto','') or '')
        candidatos=[texto] if 'CAST(' in texto.upper() else _separar_expresiones(texto)
        for x in candidatos:
            n=_normalizar_orden(x)
            if n: orden.append(n)
        return consultar(op['tabla'],op.get('columnas','*'),filtros,orden,op.get('limite'))
    if accion=='crear':
        return crear(op['tabla'],dict(zip(op.get('columnas',[]),parametros)),op.get('upsert',False))
    if accion=='editar':
        cols=[m.group(1) for m in re.finditer(r'["\']?([A-Za-z_]\w*)["\']?\s*=\s*\?',op.get('asignaciones_texto',''))]
        datos=dict(zip(cols,parametros[:len(cols)])); filtros,_=_filtros_descriptor(op.get('filtros_texto',''),parametros,len(cols))
        return editar(op['tabla'],datos,filtros)
    if accion=='eliminar':
        filtros,_=_filtros_descriptor(op.get('filtros_texto',''),parametros)
        return eliminar(op['tabla'],filtros)
    raise ValueError(f'Operacion declarativa no soportada: {accion}')

