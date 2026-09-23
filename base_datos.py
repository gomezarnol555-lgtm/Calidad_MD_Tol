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
    url = _secreto("SUPABASE_URL").rstrip("/")
    key = _secreto(
        "SUPABASE_SECRET_KEY",
        ("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
    )

    if not url:
        return False, "Falta SUPABASE_URL en los secretos de Streamlit."
    if not url.startswith("https://") or ".supabase.co" not in url:
        return False, (
            "SUPABASE_URL debe usar únicamente la URL raíz: "
            "https://<proyecto>.supabase.co"
        )
    if not key:
        return False, "Falta SUPABASE_SECRET_KEY en los secretos de Streamlit."
    if key.startswith("sb_publishable_"):
        return False, "La aplicación requiere una clave sb_secret_ de servidor."

    try:
        create_client(url, key).table("app_config").select("clave").limit(1).execute()
        return True, "Conexión correcta."
    except Exception as exc:
        texto = str(exc)
        bajo = texto.lower()
        if "pgrst125" in bajo or "invalid path" in bajo:
            return False, (
                "SUPABASE_URL contiene una ruta inválida. Debe terminar en "
                ".supabase.co, sin /rest/v1 ni nombres de tablas."
            )
        if "pgrst205" in bajo or "does not exist" in bajo:
            return False, "No existe public.app_config. Ejecuta el esquema completo."
        if "401" in bajo or "unauthorized" in bajo or "invalid api key" in bajo:
            return False, "La clave secreta no corresponde al proyecto indicado."
        return False, "Supabase rechazó la validación: " + texto[:500]


def cliente():
    global _CLIENTE
    if _CLIENTE is None:
        ok, mensaje = diagnostico_conexion()
        if not ok:
            raise RuntimeError(mensaje)
        _CLIENTE = create_client(
            _secreto("SUPABASE_URL").rstrip("/"),
            _secreto(
                "SUPABASE_SECRET_KEY",
                ("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
            ),
        )
    return _CLIENTE


def verificar_conexion():
    return diagnostico_conexion()[0]


def inicializar_base():
    ok, mensaje = diagnostico_conexion()
    if not ok:
        raise RuntimeError(mensaje)
    return True


def _columnas_lista(columnas):
    if columnas in (None, "*"):
        return "*"
    if isinstance(columnas, (list, tuple)):
        return ",".join(str(x) for x in columnas)
    return str(columnas)


def _aplicar_filtros(query, filtros):
    for campo, valor in (filtros or {}).items():
        campo = str(campo).split(".")[-1].strip('" ')
        if isinstance(valor, dict):
            for operador, dato in valor.items():
                if operador == "neq":
                    query = query.neq(campo, dato)
                elif operador == "like":
                    query = query.like(campo, dato)
                elif operador == "ilike":
                    query = query.ilike(campo, dato)
                elif operador == "gt":
                    query = query.gt(campo, dato)
                elif operador == "gte":
                    query = query.gte(campo, dato)
                elif operador == "lt":
                    query = query.lt(campo, dato)
                elif operador == "lte":
                    query = query.lte(campo, dato)
                elif operador == "is":
                    query = query.is_(campo, dato)
        elif isinstance(valor, (list, tuple, set)):
            query = query.in_(campo, list(valor))
        elif valor is None:
            query = query.is_(campo, "null")
        else:
            query = query.eq(campo, valor)
    return query


def _normalizar_orden(expresion):
    """Convierte orden SQL heredado a columna válida de PostgREST."""
    texto = str(expresion or "").strip()
    if not texto:
        return None

    direccion = "asc"
    if re.search(r"\s+DESC\s*$", texto, re.IGNORECASE):
        direccion = "desc"
    texto = re.sub(r"\s+(ASC|DESC)\s*$", "", texto, flags=re.IGNORECASE).strip()

    # CAST(codigo AS INTEGER) no es válido como order de PostgREST.
    cast = re.fullmatch(
        r"CAST\s*\(\s*(?:\w+\.)?[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?\s+AS\s+[A-Za-z0-9_ ]+\s*\)",
        texto,
        flags=re.IGNORECASE,
    )
    if cast:
        return cast.group(1), direccion

    # LOWER(nombre), UPPER(nombre), TRIM(nombre): ordenar por la columna base.
    funcion = re.fullmatch(
        r"(?:LOWER|UPPER|TRIM)\s*\(\s*(?:\w+\.)?[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?\s*\)",
        texto,
        flags=re.IGNORECASE,
    )
    if funcion:
        return funcion.group(1), direccion

    columna = texto.split(".")[-1].strip('" ')
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", columna):
        return columna, direccion
    return None


def consultar(
    tabla=None,
    columnas="*",
    filtros=None,
    ordenar_por=None,
    limite=None,
    uno=False,
    operacion=None,
    parametros=(),
):
    if isinstance(tabla, dict):
        if columnas != "*":
            parametros = columnas
        operacion = tabla
        tabla = None

    if operacion is not None:
        return _ejecutar_descriptor(operacion, parametros, espera="consulta")

    query = cliente().table(tabla).select(_columnas_lista(columnas))
    query = _aplicar_filtros(query, filtros)

    for elemento in ordenar_por or []:
        if isinstance(elemento, (list, tuple)):
            columna = elemento[0]
            direccion = elemento[1] if len(elemento) > 1 else "asc"
            orden = _normalizar_orden(f"{columna} {direccion}")
        else:
            orden = _normalizar_orden(elemento)
        if orden:
            columna, direccion = orden
            query = query.order(columna, desc=direccion == "desc")

    if limite:
        query = query.limit(int(limite))
    if uno:
        query = query.limit(1)

    data = query.execute().data or []
    if uno:
        return data[0] if data else None
    return pd.DataFrame(data)


def consultar_uno(tabla, columnas="*", filtros=None, ordenar_por=None):
    return consultar(
        tabla=tabla,
        columnas=columnas,
        filtros=filtros,
        ordenar_por=ordenar_por,
        limite=1,
        uno=True,
    )


def crear(tabla=None, datos=None, upsert=False, on_conflict=None):
    if isinstance(tabla, dict):
        return _ejecutar_descriptor(tabla, datos or (), espera="cambio")
    try:
        if upsert:
            query = cliente().table(tabla).upsert(datos, on_conflict=on_conflict)
        else:
            query = cliente().table(tabla).insert(datos)
        data = query.execute().data or []
        if data and isinstance(data[0], dict):
            return data[0].get("id")
        return None
    except Exception as exc:
        bajo = str(exc).lower()
        if "duplicate" in bajo or "unique" in bajo or "23505" in bajo:
            raise ErrorIntegridad(str(exc)) from exc
        raise


def editar(tabla, datos=None, filtros=None):
    if isinstance(tabla, dict):
        return _ejecutar_descriptor(tabla, datos or (), espera="cambio")
    if not filtros:
        raise ValueError("Editar requiere filtros.")
    query = _aplicar_filtros(cliente().table(tabla).update(datos), filtros)
    return len(query.execute().data or [])


def eliminar(tabla, filtros=None, logico=False):
    if isinstance(tabla, dict):
        return _ejecutar_descriptor(tabla, filtros or (), espera="cambio")
    if not filtros:
        raise ValueError("Eliminar requiere filtros.")
    if logico:
        return editar(tabla, {"activo": 0}, filtros)
    query = _aplicar_filtros(cliente().table(tabla).delete(), filtros)
    return len(query.execute().data or [])


def contar(tabla, filtros=None):
    query = cliente().table(tabla).select("id", count="exact", head=True)
    query = _aplicar_filtros(query, filtros)
    respuesta = query.execute()
    return int(respuesta.count or 0)


def existe(tabla, filtros):
    return contar(tabla, filtros) > 0


def crear_varios(tabla, filas, upsert=False, on_conflict=None):
    if not filas:
        return []
    if upsert:
        query = cliente().table(tabla).upsert(filas, on_conflict=on_conflict)
    else:
        query = cliente().table(tabla).insert(filas)
    return query.execute().data or []


def guardar_varios(operaciones):
    resultados = []
    for op in operaciones:
        accion = op["accion"]
        if accion == "crear":
            resultados.append(
                crear(
                    op["tabla"],
                    op.get("datos", {}),
                    op.get("upsert", False),
                    op.get("on_conflict"),
                )
            )
        elif accion == "editar":
            resultados.append(editar(op["tabla"], op.get("datos", {}), op["filtros"]))
        elif accion == "eliminar":
            resultados.append(
                eliminar(op["tabla"], op["filtros"], op.get("logico", False))
            )
    return resultados


def ejecutar_funcion(nombre, parametros=None):
    return cliente().rpc(nombre, parametros or {}).execute().data


def columnas_tabla(tabla):
    data = ejecutar_funcion("columnas_tabla", {"nombre_tabla": tabla}) or []
    return {str(x.get("nombre_columna")) for x in data}


def reiniciar_consecutivo(tabla):
    return None


def _convertir_literal(valor):
    texto = str(valor).strip()
    if texto.upper() == "NULL":
        return None
    if texto.upper() == "TRUE":
        return True
    if texto.upper() == "FALSE":
        return False
    if (texto.startswith("'") and texto.endswith("'")) or (
        texto.startswith('"') and texto.endswith('"')
    ):
        return texto[1:-1]
    if re.fullmatch(r"-?\d+", texto):
        return int(texto)
    if re.fullmatch(r"-?\d+\.\d+", texto):
        return float(texto)
    return texto


def _filtros_descriptor(texto, parametros, inicio=0):
    filtros = {}
    indice = inicio
    if not texto:
        return filtros, indice

    partes = re.split(r"\s+AND\s+", str(texto), flags=re.IGNORECASE)
    for parte in partes:
        parte = parte.strip().strip("()")
        parte = re.sub(r"^(?:UPPER|LOWER|TRIM)\s*\(\s*", "", parte, flags=re.IGNORECASE)
        parte = re.sub(r"\s*\)\s*$", "", parte)
        coincidencia = re.match(
            r"(?:\w+\.)?[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?\s*(=|<>|!=|LIKE|ILIKE|>=|<=|>|<)\s*(.+)$",
            parte,
            flags=re.IGNORECASE,
        )
        if not coincidencia:
            continue

        campo, operador, valor_texto = coincidencia.groups()
        if valor_texto.strip() == "?":
            if indice >= len(parametros):
                continue
            valor = parametros[indice]
            indice += 1
        else:
            valor = _convertir_literal(valor_texto)

        operador = operador.upper()
        if operador == "=":
            filtros[campo] = valor
        elif operador in ("<>", "!="):
            filtros[campo] = {"neq": valor}
        elif operador == "LIKE":
            filtros[campo] = {"like": valor}
        elif operador == "ILIKE":
            filtros[campo] = {"ilike": valor}
        elif operador == ">":
            filtros[campo] = {"gt": valor}
        elif operador == ">=":
            filtros[campo] = {"gte": valor}
        elif operador == "<":
            filtros[campo] = {"lt": valor}
        elif operador == "<=":
            filtros[campo] = {"lte": valor}

    return filtros, indice


def _ejecutar_descriptor(op, parametros=(), espera="consulta"):
    parametros = tuple(parametros or ())
    accion = op.get("accion")

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
        texto_orden = str(op.get("orden_texto", "") or "")
        # No dividir comas internas de CAST(...), solo soportar listas simples.
        candidatos = [texto_orden] if "CAST(" in texto_orden.upper() else texto_orden.split(",")
        for candidato in candidatos:
            normalizado = _normalizar_orden(candidato)
            if normalizado:
                orden.append(normalizado)
        return consultar(
            tabla=op["tabla"],
            columnas=op.get("columnas", "*"),
            filtros=filtros,
            ordenar_por=orden,
            limite=op.get("limite"),
        )

    if accion == "crear":
        columnas = op.get("columnas", [])
        datos = dict(zip(columnas, parametros))
        return crear(
            tabla=op["tabla"],
            datos=datos,
            upsert=op.get("upsert", False),
        )

    if accion == "editar":
        asignaciones = op.get("asignaciones_texto", "")
        columnas = [
            m.group(1)
            for m in re.finditer(
                r"[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?\s*=\s*\?",
                asignaciones,
            )
        ]
        datos = dict(zip(columnas, parametros[: len(columnas)]))
        filtros, _ = _filtros_descriptor(
            op.get("filtros_texto", ""),
            parametros,
            len(columnas),
        )
        return editar(op["tabla"], datos, filtros)

    if accion == "eliminar":
        filtros, _ = _filtros_descriptor(op.get("filtros_texto", ""), parametros)
        return eliminar(op["tabla"], filtros)

    raise ValueError(f"Operación declarativa no soportada: {accion}")
