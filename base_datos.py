import os
import re

import pandas as pd
import streamlit as st
from supabase import create_client


class ErrorIntegridad(Exception):
    pass


def _secreto(nombre, alternativos=()):
    for clave in (nombre,) + tuple(alternativos):
        valor = os.getenv(clave, "").strip()
        if not valor:
            try:
                valor = str(st.secrets.get(clave, "")).strip()
            except Exception:
                valor = ""
        if valor:
            return valor
    return ""


@st.cache_resource(show_spinner=False)
def cliente():
    url = _secreto("SUPABASE_URL").rstrip("/")
    key = _secreto(
        "SUPABASE_SECRET_KEY",
        ("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
    )
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SECRET_KEY.")
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise RuntimeError("SUPABASE_URL debe ser https://<proyecto>.supabase.co")
    if key.startswith("sb_publishable_"):
        raise RuntimeError("La aplicación requiere una clave sb_secret_ de servidor.")
    return create_client(url, key)


@st.cache_data(ttl=300, show_spinner=False)
def _validar_conexion_cache():
    respuesta = cliente().table("app_config").select("clave").limit(1).execute()
    return respuesta.data is not None


def diagnostico_conexion():
    try:
        _validar_conexion_cache()
        return True, "Conexión correcta."
    except Exception as exc:
        return False, "Supabase rechazó la validación: " + str(exc)[:500]


def verificar_conexion():
    return diagnostico_conexion()[0]


def inicializar_base():
    ok, mensaje = diagnostico_conexion()
    if not ok:
        raise RuntimeError(mensaje)
    return True


def limpiar_cache_datos():
    st.cache_data.clear()


def _congelar(valor):
    if isinstance(valor, dict):
        return tuple(sorted((str(k), _congelar(v)) for k, v in valor.items()))
    if isinstance(valor, (list, tuple, set)):
        return tuple(_congelar(v) for v in valor)
    return valor


def _descongelar_valor(valor):
    """Restaura valores anidados sin confundir listas de orden con diccionarios."""
    if isinstance(valor, tuple):
        if all(isinstance(x, tuple) and len(x) == 2 for x in valor):
            return {k: _descongelar_valor(v) for k, v in valor}
        return [_descongelar_valor(v) for v in valor]
    return valor


def _descongelar_filtros(valor):
    """Los filtros congelados siempre son pares campo-valor."""
    if not valor:
        return {}
    return {campo: _descongelar_valor(dato) for campo, dato in valor}


def _descongelar_orden(valor):
    """El orden congelado siempre es una lista de pares columna-direccion."""
    if not valor:
        return []
    return [(str(columna), str(direccion)) for columna, direccion in valor]


def _separar_expresiones(texto):
    partes, actual, nivel = [], [], 0
    for caracter in str(texto or ""):
        if caracter == "(":
            nivel += 1
        elif caracter == ")" and nivel:
            nivel -= 1
        if caracter == "," and nivel == 0:
            partes.append("".join(actual).strip())
            actual = []
        else:
            actual.append(caracter)
    if actual:
        partes.append("".join(actual).strip())
    return [x for x in partes if x]


def _normalizar_select(expresion):
    texto = str(expresion or "").strip()
    if texto == "*":
        return "*"
    patron = r"COALESCE\s*\(\s*(?:\w+\.)?[\"']?([A-Za-z_]\w*)[\"']?\s*,.*\)\s*(?:AS\s+[\"']?([A-Za-z_]\w*)[\"']?)?"
    encontrado = re.fullmatch(patron, texto, re.I)
    if encontrado:
        return encontrado.group(1)
    patron = r"CAST\s*\(\s*(?:\w+\.)?[\"']?([A-Za-z_]\w*)[\"']?\s+AS\s+[^)]+\)\s*(?:AS\s+[\"']?([A-Za-z_]\w*)[\"']?)?"
    encontrado = re.fullmatch(patron, texto, re.I)
    if encontrado:
        return encontrado.group(1)
    patron = r"(?:\w+\.)?[\"']?([A-Za-z_]\w*)[\"']?\s*(?:AS\s+[\"']?([A-Za-z_]\w*)[\"']?)?"
    encontrado = re.fullmatch(patron, texto, re.I)
    if encontrado:
        columna, alias = encontrado.groups()
        return f"{alias}:{columna}" if alias and alias != columna else columna
    return None


def _columnas_lista(columnas):
    if columnas in (None, "*"):
        return "*"
    expresiones = list(columnas) if isinstance(columnas, (list, tuple)) else _separar_expresiones(columnas)
    salida = []
    for expresion in expresiones:
        valor = _normalizar_select(expresion)
        if valor and valor not in salida:
            salida.append(valor)
    return ",".join(salida) if salida else "*"


def _normalizar_orden(expresion):
    texto = str(expresion or "").strip()
    if not texto:
        return None
    direccion = "desc" if re.search(r"\s+DESC\s*$", texto, re.I) else "asc"
    texto = re.sub(r"\s+(ASC|DESC)\s*$", "", texto, flags=re.I).strip()
    patron = r"(?:CAST|LOWER|UPPER|TRIM)\s*\(\s*(?:\w+\.)?[\"']?([A-Za-z_]\w*)[\"']?(?:\s+AS\s+[^)]+)?\)"
    encontrado = re.fullmatch(patron, texto, re.I)
    if encontrado:
        return encontrado.group(1), direccion
    columna = texto.split(".")[-1].strip("\" '")
    return (columna, direccion) if re.fullmatch(r"[A-Za-z_]\w*", columna) else None


def _aplicar_filtros(query, filtros):
    for campo, valor in (filtros or {}).items():
        campo = str(campo).split(".")[-1].strip('" ')
        if isinstance(valor, dict):
            for operador, dato in valor.items():
                metodo = {
                    "neq": "neq", "like": "like", "ilike": "ilike",
                    "gt": "gt", "gte": "gte", "lt": "lt", "lte": "lte",
                    "is": "is_",
                }.get(operador)
                if metodo:
                    query = getattr(query, metodo)(campo, dato)
        elif isinstance(valor, (list, tuple, set)):
            query = query.in_(campo, list(valor))
        elif valor is None:
            query = query.is_(campo, "null")
        else:
            query = query.eq(campo, valor)
    return query


@st.cache_data(ttl=180, show_spinner=False, max_entries=256)
def _consultar_cache(tabla, columnas, filtros_congelados, orden_congelado, limite):
    filtros = _descongelar_filtros(filtros_congelados)
    orden = _descongelar_orden(orden_congelado)
    query = cliente().table(tabla).select(columnas)
    query = _aplicar_filtros(query, filtros)
    for columna, direccion in orden:
        query = query.order(columna, desc=direccion == "desc")
    if limite:
        query = query.limit(int(limite))
    return query.execute().data or []


def consultar(tabla=None, columnas="*", filtros=None, ordenar_por=None, limite=None, uno=False, operacion=None, parametros=()):
    if isinstance(tabla, dict):
        if columnas != "*":
            parametros = columnas
        operacion, tabla = tabla, None
    if operacion is not None:
        return _ejecutar_descriptor(operacion, parametros, "consulta")

    columnas_limpias = _columnas_lista(columnas)
    orden_limpio = []
    for elemento in ordenar_por or []:
        normalizado = _normalizar_orden(
            f"{elemento[0]} {elemento[1] if len(elemento) > 1 else 'asc'}"
        ) if isinstance(elemento, (list, tuple)) else _normalizar_orden(elemento)
        if normalizado:
            orden_limpio.append(normalizado)

    limite_real = 1 if uno else limite
    data = _consultar_cache(
        str(tabla), columnas_limpias, _congelar(filtros or {}),
        _congelar(orden_limpio), limite_real,
    )
    if uno:
        return data[0] if data else None
    return pd.DataFrame(data)


def consultar_uno(tabla, columnas="*", filtros=None, ordenar_por=None):
    return consultar(tabla, columnas, filtros, ordenar_por, 1, True)


def crear(tabla=None, datos=None, upsert=False, on_conflict=None):
    if isinstance(tabla, dict):
        return _ejecutar_descriptor(tabla, datos or (), "cambio")
    try:
        query = cliente().table(tabla).upsert(datos, on_conflict=on_conflict) if upsert else cliente().table(tabla).insert(datos)
        data = query.execute().data or []
        limpiar_cache_datos()
        return data[0].get("id") if data and isinstance(data[0], dict) else None
    except Exception as exc:
        if any(x in str(exc).lower() for x in ("duplicate", "unique", "23505")):
            raise ErrorIntegridad(str(exc)) from exc
        raise


def editar(tabla, datos=None, filtros=None):
    if isinstance(tabla, dict):
        return _ejecutar_descriptor(tabla, datos or (), "cambio")
    if not filtros:
        raise ValueError("Editar requiere filtros.")
    data = _aplicar_filtros(cliente().table(tabla).update(datos), filtros).execute().data or []
    limpiar_cache_datos()
    return len(data)


def eliminar(tabla, filtros=None, logico=False):
    if isinstance(tabla, dict):
        return _ejecutar_descriptor(tabla, filtros or (), "cambio")
    if not filtros:
        raise ValueError("Eliminar requiere filtros.")
    if logico:
        return editar(tabla, {"activo": 0}, filtros)
    data = _aplicar_filtros(cliente().table(tabla).delete(), filtros).execute().data or []
    limpiar_cache_datos()
    return len(data)


def contar(tabla, filtros=None):
    query = cliente().table(tabla).select("id", count="exact", head=True)
    respuesta = _aplicar_filtros(query, filtros).execute()
    return int(respuesta.count or 0)


def existe(tabla, filtros):
    return contar(tabla, filtros) > 0


def crear_varios(tabla, filas, upsert=False, on_conflict=None):
    if not filas:
        return []
    query = cliente().table(tabla).upsert(filas, on_conflict=on_conflict) if upsert else cliente().table(tabla).insert(filas)
    data = query.execute().data or []
    limpiar_cache_datos()
    return data


def guardar_varios(operaciones):
    resultados = []
    for op in operaciones:
        if op["accion"] == "crear":
            resultados.append(crear(op["tabla"], op.get("datos", {}), op.get("upsert", False), op.get("on_conflict")))
        elif op["accion"] == "editar":
            resultados.append(editar(op["tabla"], op.get("datos", {}), op.get("filtros", {})))
        elif op["accion"] == "eliminar":
            resultados.append(eliminar(op["tabla"], op.get("filtros", {}), op.get("logico", False)))
    return resultados


def ejecutar_funcion(nombre, parametros=None):
    return cliente().rpc(nombre, parametros or {}).execute().data


def columnas_tabla(tabla):
    respuesta = ejecutar_funcion("columnas_tabla", {"nombre_tabla": tabla}) or []
    return {str(x.get("nombre_columna")) for x in respuesta}




def _literal(texto):
    texto = str(texto).strip()
    if texto.upper() == "NULL":
        return None
    if texto.upper() == "TRUE":
        return True
    if texto.upper() == "FALSE":
        return False
    if len(texto) > 1 and texto[0] in "'\"" and texto[-1] == texto[0]:
        return texto[1:-1]
    if re.fullmatch(r"-?\d+", texto):
        return int(texto)
    if re.fullmatch(r"-?\d+\.\d+", texto):
        return float(texto)
    return texto


def _filtros_descriptor(texto, parametros, inicio=0):
    filtros, indice = {}, inicio
    for parte in re.split(r"\s+AND\s+", str(texto or ""), flags=re.I):
        encontrado = re.match(
            r"(?:\w+\.)?[\"']?([A-Za-z_]\w*)[\"']?\s*(=|<>|!=|LIKE|ILIKE|>=|<=|>|<)\s*(.+)$",
            parte.strip(), re.I,
        )
        if not encontrado:
            continue
        campo, operador, valor = encontrado.groups()
        if valor.strip() == "?":
            if indice >= len(parametros):
                continue
            valor = parametros[indice]
            indice += 1
        else:
            valor = _literal(valor)
        mapa = {"<>": "neq", "!=": "neq", "LIKE": "like", "ILIKE": "ilike", ">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}
        filtros[campo] = valor if operador == "=" else {mapa[operador.upper()]: valor}
    return filtros, indice


def _ejecutar_descriptor(op, parametros=(), espera="consulta"):
    parametros, accion = tuple(parametros or ()), op.get("accion")
    if accion == "vista":
        return consultar(op["nombre"])
    if accion == "columnas":
        return [{"nombre_columna": x} for x in columnas_tabla(op["tabla"])]
    if accion == "rpc":
        data = ejecutar_funcion(op["nombre"], {"argumentos": list(parametros)})
        return pd.DataFrame(data or []) if espera == "consulta" else data
    if accion == "consultar":
        filtros, _ = _filtros_descriptor(op.get("filtros_texto", ""), parametros)
        orden = []
        for valor in _separar_expresiones(op.get("orden_texto", "")):
            normalizado = _normalizar_orden(valor)
            if normalizado:
                orden.append(normalizado)
        return consultar(op["tabla"], op.get("columnas", "*"), filtros, orden, op.get("limite"))
    if accion == "crear":
        return crear(op["tabla"], dict(zip(op.get("columnas", []), parametros)), op.get("upsert", False))
    if accion == "editar":
        columnas = [m.group(1) for m in re.finditer(r"[\"']?([A-Za-z_]\w*)[\"']?\s*=\s*\?", op.get("asignaciones_texto", ""))]
        datos = dict(zip(columnas, parametros[:len(columnas)]))
        filtros, _ = _filtros_descriptor(op.get("filtros_texto", ""), parametros, len(columnas))
        return editar(op["tabla"], datos, filtros)
    if accion == "eliminar":
        filtros, _ = _filtros_descriptor(op.get("filtros_texto", ""), parametros)
        return eliminar(op["tabla"], filtros)
    raise ValueError(f"Operación declarativa no soportada: {accion}")
