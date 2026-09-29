"""Contrato único de persistencia de Calidad MD.

El resto de la aplicación solo utiliza las funciones públicas de este módulo.
Para migrar de Supabase a otro motor se reemplaza únicamente esta implementación,
conservando las mismas firmas y tipos de retorno.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

import pandas as pd
import streamlit as st
from supabase import create_client


class ErrorBaseDatos(Exception):
    """Error general de persistencia que puedo mostrar de forma controlada."""


class ErrorIntegridad(ErrorBaseDatos):
    """La operación viola una regla de integridad o unicidad."""


class ErrorOperacion(ErrorBaseDatos):
    """La operación no pudo completarse en el proveedor configurado."""



# =============================================================================
# Configuración de conexión
# =============================================================================
def _secreto(nombre: str, alternativos: tuple[str, ...] = ()) -> str:
    """Obtiene una configuración sensible desde variables de entorno o secretos de Streamlit."""
    for clave in (nombre,) + alternativos:
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
def _cliente_proveedor():
    """Creo el cliente del proveedor actual. Ningún otro módulo conoce este cliente."""
    url = _secreto("SUPABASE_URL").rstrip("/")
    clave = _secreto("SUPABASE_SECRET_KEY", ("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"))
    if not url or not clave:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SECRET_KEY.")
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise RuntimeError("SUPABASE_URL no tiene un formato válido.")
    if clave.startswith("sb_publishable_"):
        raise RuntimeError("La aplicación requiere una credencial privada de servidor.")
    return create_client(url, clave)


@st.cache_data(ttl=120, show_spinner=False)
def _validar_conexion_cache() -> bool:
    """Comprueba la disponibilidad de la base de datos mediante una consulta mínima."""
    respuesta = _cliente_proveedor().table("app_config").select("clave").limit(1).execute()
    return respuesta.data is not None


def diagnostico_conexion() -> tuple[bool, str]:
    """Devuelve el estado y el mensaje de diagnóstico de la conexión."""
    try:
        _validar_conexion_cache()
        return True, "Conexión correcta."
    except Exception as exc:
        return False, "El proveedor de datos rechazó la validación: " + _detalle_error(exc)


def verificar_conexion() -> bool:
    """Indica si la conexión con la base de datos está disponible."""
    return diagnostico_conexion()[0]


def inicializar_base() -> bool:
    """Valida la conexión requerida antes de iniciar la aplicación."""
    correcto, mensaje = diagnostico_conexion()
    if not correcto:
        raise RuntimeError(mensaje)
    return True


@st.cache_resource(show_spinner=False)

# =============================================================================
# Control de caché
# =============================================================================
def _versiones_datos() -> dict[str, int]:
    """Mantiene versiones internas para invalidar la caché por tabla."""
    return {}


def _version(tabla: str) -> int:
    """Obtiene la versión de caché asociada con una tabla."""
    return int(_versiones_datos().get(str(tabla), 0))


def limpiar_cache_datos(tabla: str | None = None) -> None:
    """Invalida la caché global o la caché de una tabla específica."""
    clave = str(tabla or "__global__")
    _versiones_datos()[clave] = _version(clave) + 1


def _congelar(valor: Any) -> Any:
    """Convierte estructuras mutables en valores compatibles con la caché."""
    if isinstance(valor, dict):
        return tuple(sorted((str(k), _congelar(v)) for k, v in valor.items()))
    if isinstance(valor, (list, tuple, set)):
        return tuple(_congelar(v) for v in valor)
    return valor


def _descongelar_filtros(valor: Any) -> dict[str, Any]:
    """Restaura filtros almacenados en una representación inmutable."""
    def restaurar(dato: Any) -> Any:
        if isinstance(dato, tuple):
            if all(isinstance(x, tuple) and len(x) == 2 for x in dato):
                return {k: restaurar(v) for k, v in dato}
            return [restaurar(x) for x in dato]
        return dato
    return {campo: restaurar(dato) for campo, dato in (valor or ())}



# =============================================================================
# Normalización de consultas
# =============================================================================
def _columnas(columnas: str | Iterable[str] | None) -> str:
    """Normaliza la selección de columnas permitida por el contrato de datos."""
    if columnas is None or columnas == "*":
        return "*"
    if isinstance(columnas, str):
        columnas = [x.strip() for x in columnas.split(",") if x.strip()]
    limpias = []
    for columna in columnas:
        texto = str(columna).strip()
        if texto and texto.replace("_", "").isalnum() and texto not in limpias:
            limpias.append(texto)
    return ",".join(limpias) if limpias else "*"


def _orden(ordenar_por: Iterable[tuple[str, str]] | None) -> list[tuple[str, str]]:
    """Normaliza los criterios de ordenamiento de una consulta."""
    resultado = []
    for elemento in ordenar_por or []:
        columna, direccion = elemento
        columna = str(columna).strip()
        if columna.replace("_", "").isalnum():
            resultado.append((columna, "desc" if str(direccion).lower() == "desc" else "asc"))
    return resultado


def _aplicar_filtros(consulta, filtros: dict[str, Any] | None):
    """Aplica filtros neutrales sobre la consulta del proveedor."""
    for campo, valor in (filtros or {}).items():
        campo = str(campo).strip()
        if not campo.replace("_", "").isalnum():
            raise ValueError(f"Nombre de campo no válido: {campo}")
        if isinstance(valor, dict):
            for operador, dato in valor.items():
                metodo = {
                    "neq": "neq", "like": "like", "ilike": "ilike", "gt": "gt",
                    "gte": "gte", "lt": "lt", "lte": "lte", "is": "is_",
                }.get(str(operador).lower())
                if not metodo:
                    raise ValueError(f"Operador de filtro no soportado: {operador}")
                consulta = getattr(consulta, metodo)(campo, dato)
        elif isinstance(valor, (list, tuple, set)):
            consulta = consulta.in_(campo, list(valor))
        elif valor is None:
            consulta = consulta.is_(campo, "null")
        else:
            consulta = consulta.eq(campo, valor)
    return consulta


@st.cache_data(ttl=120, show_spinner=False, max_entries=512)
def _consultar_cache(tabla, columnas, filtros_congelados, orden_congelado, limite, version_tabla, version_global):
    """Ejecuta y almacena temporalmente una consulta normalizada."""
    consulta = _cliente_proveedor().table(tabla).select(columnas)
    consulta = _aplicar_filtros(consulta, _descongelar_filtros(filtros_congelados))
    for columna, direccion in orden_congelado:
        consulta = consulta.order(columna, desc=direccion == "desc")
    if limite is not None:
        consulta = consulta.limit(int(limite))
    return consulta.execute().data or []



# =============================================================================
# Operaciones públicas de consulta
# =============================================================================
def consultar(tabla: str, columnas: str | Iterable[str] = "*", filtros: dict[str, Any] | None = None,
              ordenar_por: Iterable[tuple[str, str]] | None = None, limite: int | None = None,
              uno: bool = False):
    """Consulto registros mediante un contrato independiente del proveedor."""
    columnas_finales = _columnas(columnas)
    orden_final = _orden(ordenar_por)
    limite_final = 1 if uno else limite
    try:
        datos = _consultar_cache(
            str(tabla), columnas_finales, _congelar(filtros or {}), tuple(orden_final),
            limite_final, _version(tabla), _version("__global__"),
        )
    except Exception as exc:
        raise ErrorOperacion(f"No pude consultar '{tabla}'. {_detalle_error(exc)}") from exc
    if uno:
        return datos[0] if datos else None
    if datos:
        return pd.DataFrame(datos)
    if columnas_finales == "*":
        return pd.DataFrame()
    return pd.DataFrame(columns=columnas_finales.split(","))


def consultar_uno(tabla: str, columnas="*", filtros=None, ordenar_por=None):
    """Consulta como máximo un registro y devuelve un diccionario o None."""
    return consultar(tabla, columnas, filtros, ordenar_por, limite=1, uno=True)


def consultar_vista(nombre: str, columnas="*", filtros=None, ordenar_por=None, limite=None):
    """Consulto una vista usando el mismo contrato empleado para una tabla."""
    return consultar(nombre, columnas, filtros, ordenar_por, limite)



# =============================================================================
# Normalización de datos
# =============================================================================
def _valor_serializable(valor: Any) -> Any:
    """Convierte fechas, decimales y valores de pandas a tipos serializables."""
    if valor is None:
        return None
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, dict):
        return {str(k): _valor_serializable(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [_valor_serializable(v) for v in valor]
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(valor, "item"):
        try:
            return _valor_serializable(valor.item())
        except Exception:
            pass
    return valor


CAMPOS_FECHA = {
    "fecha", "fecha_apertura", "fecha_cierre", "fecha_final_tratamiento",
    "creado_en", "actualizado_en", "ultimo_acceso", "fecha_hora",
}

CAMPOS_NUMERICOS = {
    "id", "dia", "mes", "anio", "semana", "orden", "orden_fila",
    "orden_linea", "orden_sector", "activo", "obligatorio",
    "intentos_fallidos", "requiere_cambio_pass", "particulas_halladas",
    "cantidad_observada", "cantidad_reproceso", "cantidad_decomiso",
    "cantidad_aprobado_segunda", "cantidad_total_pnc", "cantidad_afectada",
    "numero_muestras", "numero_corrugado", "total_carga_datos",
    "total_horas_trabajadas", "horas_trabajadas", "carga_spac",
    "horas_nave1", "horas_nave2", "horas_nave3", "valor", "meta",
}


def _datos(datos: dict[str, Any]) -> dict[str, Any]:
    """Normalizo el payload sin depender de metadatos ni funciones del proveedor.

    Una cadena vacía conserva su significado en columnas de texto, pero se convierte
    en None cuando el contrato funcional define una fecha o un número. Así evito
    enviar valores como fecha_final_tratamiento="" a motores SQL estrictos.
    """
    if not isinstance(datos, dict):
        raise TypeError("Los datos deben enviarse como diccionario.")
    salida = {}
    for campo, valor in datos.items():
        nombre = str(campo)
        limpio = _valor_serializable(valor)
        if isinstance(limpio, str) and not limpio.strip() and (
            nombre in CAMPOS_FECHA or nombre in CAMPOS_NUMERICOS
        ):
            limpio = None
        salida[nombre] = limpio
    return salida


def _detalle_error(exc: Exception) -> str:
    """Extrae un mensaje útil de una excepción del proveedor."""
    detalle = None
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], dict):
        detalle = args[0]
    elif isinstance(getattr(exc, "message", None), dict):
        detalle = exc.message
    if detalle:
        partes = [str(detalle.get(k)) for k in ("code", "message", "details", "hint") if detalle.get(k)]
        return " | ".join(partes)[:700]
    return str(getattr(exc, "message", None) or exc)[:700]


def _traducir_error(tabla: str, accion: str, exc: Exception):
    """Convierte errores técnicos en excepciones controladas de la aplicación."""
    texto = _detalle_error(exc)
    if any(x in texto.lower() for x in ("duplicate", "unique", "23505")):
        raise ErrorIntegridad(texto) from exc
    raise ErrorOperacion(f"No pude {accion} en '{tabla}'. {texto}") from exc



# =============================================================================
# Operaciones públicas de escritura
# =============================================================================
def crear(tabla: str, datos: dict[str, Any], **kwargs):
    """Creo un registro y devuelvo su identificador cuando el proveedor lo informa."""
    if kwargs:
        raise TypeError("crear() no admite opciones del proveedor. Usa guardar() para altas idempotentes.")
    try:
        respuesta = _cliente_proveedor().table(tabla).insert(_datos(datos)).execute().data or []
        limpiar_cache_datos(tabla)
        return respuesta[0].get("id") if respuesta and isinstance(respuesta[0], dict) else None
    except Exception as exc:
        _traducir_error(tabla, "crear el registro", exc)


def guardar(tabla: str, datos: dict[str, Any], claves_conflicto: str | Iterable[str] | None = None):
    """Creo o actualizo un registro por una clave funcional, sin exponer API del proveedor."""
    claves = ",".join(claves_conflicto) if isinstance(claves_conflicto, (list, tuple, set)) else claves_conflicto
    try:
        respuesta = _cliente_proveedor().table(tabla).upsert(_datos(datos), on_conflict=claves).execute().data or []
        limpiar_cache_datos(tabla)
        return respuesta[0].get("id") if respuesta and isinstance(respuesta[0], dict) else None
    except Exception as exc:
        _traducir_error(tabla, "guardar el registro", exc)


def editar(tabla: str, datos: dict[str, Any], filtros: dict[str, Any], invalidar_cache: bool = True) -> int:
    """Actualiza registros que coinciden con los filtros indicados."""
    if not filtros:
        raise ValueError("editar() requiere filtros.")
    if not datos:
        return 0
    try:
        consulta = _cliente_proveedor().table(tabla).update(_datos(datos))
        respuesta = _aplicar_filtros(consulta, filtros).execute().data or []
        if invalidar_cache:
            limpiar_cache_datos(tabla)
        return len(respuesta)
    except Exception as exc:
        _traducir_error(tabla, "actualizar el registro", exc)


def eliminar(tabla: str, filtros: dict[str, Any], logico: bool = False) -> int:
    """Elimina registros o aplica una baja lógica según la operación solicitada."""
    if not filtros:
        raise ValueError("eliminar() requiere filtros.")
    if logico:
        return editar(tabla, {"activo": 0}, filtros)
    try:
        consulta = _cliente_proveedor().table(tabla).delete()
        respuesta = _aplicar_filtros(consulta, filtros).execute().data or []
        limpiar_cache_datos(tabla)
        return len(respuesta)
    except Exception as exc:
        _traducir_error(tabla, "eliminar el registro", exc)


def contar(tabla: str, filtros: dict[str, Any] | None = None) -> int:
    """Cuenta los registros que cumplen los filtros indicados."""
    try:
        consulta = _cliente_proveedor().table(tabla).select("id", count="exact", head=True)
        return int(_aplicar_filtros(consulta, filtros).execute().count or 0)
    except Exception as exc:
        _traducir_error(tabla, "contar registros", exc)


def existe(tabla: str, filtros: dict[str, Any]) -> bool:
    """Comprueba la existencia de al menos un registro coincidente."""
    return contar(tabla, filtros) > 0


def crear_varios(tabla: str, filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Inserta varios registros en una sola operación del proveedor."""
    if not filas:
        return []
    try:
        respuesta = _cliente_proveedor().table(tabla).insert([_datos(fila) for fila in filas]).execute().data or []
        limpiar_cache_datos(tabla)
        return respuesta
    except Exception as exc:
        _traducir_error(tabla, "crear los registros", exc)


def guardar_varios(operaciones: Iterable[dict[str, Any]]) -> list[Any]:
    """Ejecuto operaciones neutrales declaradas con acción, tabla, datos y filtros."""
    resultados = []
    for operacion in operaciones:
        accion = operacion.get("accion")
        if accion == "crear":
            resultados.append(crear(operacion["tabla"], operacion.get("datos", {})))
        elif accion == "guardar":
            resultados.append(guardar(operacion["tabla"], operacion.get("datos", {}), operacion.get("claves_conflicto")))
        elif accion == "editar":
            resultados.append(editar(operacion["tabla"], operacion.get("datos", {}), operacion.get("filtros", {})))
        elif accion == "eliminar":
            resultados.append(eliminar(operacion["tabla"], operacion.get("filtros", {}), operacion.get("logico", False)))
        else:
            raise ValueError(f"Acción no soportada: {accion}")
    return resultados


def columnas_tabla(tabla: str) -> set[str]:
    """Obtengo columnas a partir de una fila; evita funciones especiales del proveedor."""
    fila = consultar_uno(tabla)
    return set(fila or {})


def reiniciar_consecutivo(tabla: str):
    """No modifico consecutivos automáticamente para preservar trazabilidad."""
    return None
