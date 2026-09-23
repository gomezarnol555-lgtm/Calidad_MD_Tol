from dataclasses import dataclass
from typing import Any
import os,re
import pandas as pd
import streamlit as st
from supabase import create_client

class ErrorIntegridad(Exception):
    pass









_CLIENTE = None
_ULTIMO_ERROR_CONEXION = ""


def _secreto(nombre, alternativos=()):
    nombres = (nombre,) + tuple(alternativos)
    for clave in nombres:
        valor = os.getenv(clave, "").strip()
        if valor:
            return valor
        try:
            valor = str(st.secrets.get(clave, "")).strip()
        except Exception:
            valor = ""
        if valor:
            return valor
    return ""


def diagnostico_conexion():
    url = _secreto("SUPABASE_URL")
    key = _secreto("SUPABASE_SECRET_KEY", ("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"))
    if not url:
        return False, "Falta SUPABASE_URL en Settings > Secrets de Streamlit."
    if not url.startswith("https://") or ".supabase.co" not in url:
        return False, "SUPABASE_URL no tiene el formato esperado: https://<proyecto>.supabase.co"
    if not key:
        return False, "Falta SUPABASE_SECRET_KEY en Settings > Secrets de Streamlit."
    if key.startswith("sb_publishable_"):
        return False, "Se configuró una clave publicable. Esta app de servidor requiere sb_secret_... o la clave service_role heredada."
    try:
        c = create_client(url, key)
        c.table("app_config").select("clave").limit(1).execute()
        return True, "Conexión correcta."
    except Exception as exc:
        texto = str(exc)
        bajo = texto.lower()
        if "invalid api key" in bajo or "unauthorized" in bajo or "401" in bajo:
            return False, "La clave de Supabase no es válida para este proyecto. Copia la clave sb_secret_... del mismo proyecto que SUPABASE_URL."
        if "does not exist" in bajo or "pgrst205" in bajo or "app_config" in bajo:
            return False, "La conexión llegó a Supabase, pero no existe public.app_config. Ejecuta completo supabase_esquema.sql en SQL Editor y después reinicia la app."
        if "permission denied" in bajo or "row-level security" in bajo or "42501" in bajo:
            return False, "La clave no tiene acceso administrativo. Usa SUPABASE_SECRET_KEY con sb_secret_... y no una clave publicable."
        if "timed out" in bajo or "connect" in bajo:
            return False, "No fue posible alcanzar la Data API. Verifica SUPABASE_URL y que el proyecto de Supabase esté activo."
        return False, "Supabase rechazó la validación: " + texto[:500]


def cliente():
    global _CLIENTE
    if _CLIENTE is None:
        url = _secreto("SUPABASE_URL")
        key = _secreto("SUPABASE_SECRET_KEY", ("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"))
        if not url or not key:
            ok, mensaje = diagnostico_conexion()
            raise RuntimeError(mensaje)
        _CLIENTE = create_client(url, key)
    return _CLIENTE


def verificar_conexion():
    return diagnostico_conexion()[0]


def inicializar_base():
    ok, mensaje = diagnostico_conexion()
    if not ok:
        raise RuntimeError(mensaje)
    return True


def _columnas_lista(columnas):
    if columnas in (None,'*'): return '*'
    if isinstance(columnas,(list,tuple)): return ','.join(columnas)
    # aliases and COALESCE are handled by views/RPC. Basic lists remain valid for PostgREST.
    return str(columnas)

def _aplicar_filtros(q,filtros):
    for campo,valor in (filtros or {}).items():
        if isinstance(valor,dict):
            for op,v in valor.items():
                q=getattr(q,op)(campo,v)
        elif isinstance(valor,(list,tuple,set)): q=q.in_(campo,list(valor))
        elif valor is None: q=q.is_(campo,'null')
        else: q=q.eq(campo,valor)
    return q

def consultar(tabla=None,columnas='*',filtros=None,ordenar_por=None,limite=None,uno=False,operacion=None,parametros=()):
    if isinstance(tabla,dict):
        if columnas != '*': parametros=columnas
        operacion=tabla; tabla=None
    if operacion is not None or isinstance(tabla,dict): return _ejecutar_descriptor(operacion or tabla,parametros,espera='consulta')
    q=cliente().table(tabla).select(_columnas_lista(columnas)); q=_aplicar_filtros(q,filtros)
    for campo,direccion in (ordenar_por or []): q=q.order(campo,desc=str(direccion).lower()=='desc')
    if limite: q=q.limit(int(limite))
    if uno: q=q.limit(1)
    data=q.execute().data or []
    return (data[0] if data else None) if uno else pd.DataFrame(data)

def consultar_uno(tabla,columnas='*',filtros=None,ordenar_por=None):
    return consultar(tabla,columnas,filtros,ordenar_por,1,True)

def crear(tabla=None,datos=None,upsert=False,on_conflict=None,operacion=None,parametros=()):
    if isinstance(tabla,dict): return _ejecutar_descriptor(tabla,datos or (),espera='cambio')
    try:
        q=cliente().table(tabla).upsert(datos,on_conflict=on_conflict) if upsert else cliente().table(tabla).insert(datos)
        data=q.execute().data or []; return data[0].get('id') if data and isinstance(data[0],dict) else None
    except Exception as exc:
        if 'duplicate' in str(exc).lower() or 'unique' in str(exc).lower(): raise ErrorIntegridad(str(exc)) from exc
        raise

def editar(tabla,datos,filtros):
    if not filtros: raise ValueError('Editar requiere filtros')
    q=_aplicar_filtros(cliente().table(tabla).update(datos),filtros); data=q.execute().data or []; return len(data)

def eliminar(tabla,filtros,logico=False):
    if logico: return editar(tabla,{'activo':0},filtros)
    if not filtros: raise ValueError('Eliminar requiere filtros')
    data=_aplicar_filtros(cliente().table(tabla).delete(),filtros).execute().data or []; return len(data)

def contar(tabla,filtros=None):
    q=cliente().table(tabla).select('id',count='exact',head=True); q=_aplicar_filtros(q,filtros); r=q.execute(); return int(r.count or 0)

def existe(tabla,filtros): return contar(tabla,filtros)>0

def crear_varios(tabla,filas,upsert=False,on_conflict=None):
    if not filas:return []
    q=cliente().table(tabla).upsert(filas,on_conflict=on_conflict) if upsert else cliente().table(tabla).insert(filas)
    return q.execute().data or []

def guardar_varios(operaciones):
    resultados=[]
    for op in operaciones:
        a=op['accion']; t=op['tabla']
        if a=='crear': resultados.append(crear(t,op.get('datos',{}),op.get('upsert',False),op.get('on_conflict')))
        elif a=='editar': resultados.append(editar(t,op.get('datos',{}),op.get('filtros',{})))
        elif a=='eliminar': resultados.append(eliminar(t,op.get('filtros',{}),op.get('logico',False)))
    return resultados

def ejecutar_funcion(nombre,parametros=None):
    return cliente().rpc(nombre,parametros or {}).execute().data

def columnas_tabla(tabla):
    data=ejecutar_funcion('columnas_tabla',{'nombre_tabla':tabla}) or []
    return {str(x.get('nombre_columna')) for x in data}

def reiniciar_consecutivo(tabla): return None

def _parametros_where(texto,parametros,inicio=0):
    filtros={}; idx=inicio
    if not texto:return filtros,idx
    for parte in re.split(r'\s+AND\s+',texto,flags=re.I):
        m=re.match(r'(?:UPPER\(TRIM\()?([\w]+).*?(=|<>| LIKE )\s*\?',parte,re.I)
        if not m: continue
        campo,op=m.group(1),m.group(2).strip(); valor=parametros[idx];idx+=1
        filtros[campo]={'neq':valor} if op=='<>' else ({'like':valor} if op.upper()=='LIKE' else valor)
    return filtros,idx

def _ejecutar_descriptor(op,parametros,espera='consulta'):
    parametros=tuple(parametros or ())
    a=op['accion']
    if a=='vista': return consultar(op['nombre'])
    if a=='columnas': return [{'nombre_columna':x} for x in columnas_tabla(op['tabla'])]
    if a=='rpc':
        data=ejecutar_funcion(op['nombre'],{'argumentos':list(parametros)})
        return pd.DataFrame(data or []) if espera=='consulta' else data
    if a=='consultar':
        filtros,_=_parametros_where(op.get('filtros_texto',''),parametros)
        orden=[]
        for x in op.get('orden_texto','').split(','):
            x=x.strip()
            if x:
                p=x.split(); orden.append((p[0].split('.')[-1],p[1] if len(p)>1 else 'asc'))
        return consultar(op['tabla'],op.get('columnas','*'),filtros,orden,op.get('limite'))
    if a=='crear':
        datos=dict(zip(op['columnas'],parametros)); return crear(op['tabla'],datos,op.get('upsert',False))
    if a=='eliminar':
        filtros,_=_parametros_where(op.get('filtros_texto',''),parametros); return eliminar(op['tabla'],filtros)
    if a=='editar':
        cols=[m.group(1) for m in re.finditer(r'"?([\w]+)"?\s*=\s*\?',op.get('asignaciones_texto',''))]
        datos=dict(zip(cols,parametros[:len(cols)])); filtros,_=_parametros_where(op.get('filtros_texto',''),parametros,len(cols)); return editar(op['tabla'],datos,filtros)
    raise ValueError(f'Operación declarativa no soportada: {a}')

class _CursorDeclarativo:
    def __init__(self): self._resultado=None
    def execute(self,operacion,parametros=()):
        if not isinstance(operacion,dict): raise TypeError("Solo se permiten operaciones declarativas.")
        espera="consulta" if operacion.get("accion") in {"consultar","vista","columnas","rpc"} else "cambio"
        self._resultado=_ejecutar_descriptor(operacion,parametros,espera); return self
    def fetchone(self):
        if isinstance(self._resultado,pd.DataFrame): return tuple(self._resultado.iloc[0].tolist()) if not self._resultado.empty else None
        if isinstance(self._resultado,list):
            if not self._resultado:return None
            x=self._resultado[0]; return tuple(x.values()) if isinstance(x,dict) else x
        return self._resultado
    def fetchall(self):
        if isinstance(self._resultado,pd.DataFrame): return [tuple(x) for x in self._resultado.itertuples(index=False,name=None)]
        return self._resultado or []
    @property
    def rowcount(self): return len(self._resultado) if isinstance(self._resultado,(pd.DataFrame,list)) else int(self._resultado or 0)
class _TransaccionDeclarativa:
    def cursor(self): return _CursorDeclarativo()
    def execute(self,operacion,parametros=()): return _CursorDeclarativo().execute(operacion,parametros)
    def commit(self): return None
    def rollback(self): return None
    def close(self): return None
def transaccion(): return _TransaccionDeclarativa()
