import base64
import hashlib
import hmac
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from configuracion import ADMIN_PASS, ADMIN_USER
from base_datos import ErrorIntegridad, consultar_uno, crear, editar


_PATRON_ENTRADA_PELIGROSA = re.compile(
    r"(?:https?://|www\.|<\s*script|<\s*/?\s*[a-z][^>]*>|javascript:|data:text/html)",
    re.IGNORECASE,
)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password):
    password = str(password or "")
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return base64.b64encode(salt + key).decode("ascii")


def check_password(password, stored):
    try:
        raw = base64.b64decode(str(stored or "").encode("ascii"))
        if len(raw) != 48:
            return False
        salt = raw[:16]
        expected = raw[16:]
        calculated = hashlib.pbkdf2_hmac(
            "sha256",
            str(password or "").encode("utf-8"),
            salt,
            120000,
        )
        return hmac.compare_digest(calculated, expected)
    except Exception:
        return False


def detectar_entrada_peligrosa(valor):
    if valor is None or not isinstance(valor, str):
        return None
    texto = valor.strip()
    if not texto:
        return None
    coincidencia = _PATRON_ENTRADA_PELIGROSA.search(texto)
    return coincidencia.group(0) if coincidencia else None


def entrada_segura(valor, campo="Campo"):
    texto = "" if valor is None else str(valor)
    return (False, texto) if detectar_entrada_peligrosa(texto) else (True, texto)


def _instalar_filtro_entradas_streamlit():
    if getattr(st, "_filtro_seguridad_instalado", False):
        return

    original_text_input = st.text_input
    original_text_area = st.text_area
    original_data_editor = st.data_editor

    def text_input_seguro(label, *args, **kwargs):
        valor = original_text_input(label, *args, **kwargs)
        if kwargs.get("type") == "password":
            return valor
        if detectar_entrada_peligrosa(valor):
            st.error(f"{label}: no se permiten enlaces, dominios ni etiquetas HTML/script.")
            return ""
        return valor

    def text_area_segura(label, *args, **kwargs):
        valor = original_text_area(label, *args, **kwargs)
        if detectar_entrada_peligrosa(valor):
            st.error(f"{label}: no se permiten enlaces, dominios ni etiquetas HTML/script.")
            return ""
        return valor

    def data_editor_seguro(data, *args, **kwargs):
        resultado = original_data_editor(data, *args, **kwargs)
        if isinstance(resultado, pd.DataFrame):
            peligros = []
            for columna in resultado.columns:
                for indice, valor in resultado[columna].items():
                    if isinstance(valor, str) and detectar_entrada_peligrosa(valor):
                        fila = indice + 1 if isinstance(indice, int) else indice
                        peligros.append(f"{columna}, fila {fila}")
                        resultado.at[indice, columna] = ""
            if peligros:
                st.error(
                    "Se bloquearon enlaces o etiquetas HTML/script en: "
                    + ", ".join(peligros[:8])
                    + "."
                )
        return resultado

    st.text_input = text_input_seguro
    st.text_area = text_area_seguro
    st.data_editor = data_editor_seguro
    st._filtro_seguridad_instalado = True


def reset_admin():
    """Crea o restablece el administrador usando operaciones por tabla."""
    usuario = str(ADMIN_USER or "admin").strip() or "admin"
    password = str(ADMIN_PASS or "").strip()
    if not password:
        raise RuntimeError(
            "CALIDAD_FORCE_RESET_ADMIN está activo, pero CALIDAD_ADMIN_PASS está vacío."
        )

    password_hash = hash_password(password)
    existente = consultar_uno(
        tabla="usuarios",
        columnas="id,usuario",
        filtros={"usuario": usuario},
    )

    datos = {
        "nombre": "Administrador del sistema",
        "password_hash": password_hash,
        "rol": "desarrollador",
        "activo": 1,
        "intentos_fallidos": 0,
        "requiere_cambio_pass": 1,
        "actualizado_por": "sistema",
        "actualizado_en": now_iso(),
    }

    if existente:
        editar(
            tabla="usuarios",
            datos=datos,
            filtros={"id": existente["id"]},
        )
        return existente["id"]

    datos.update(
        {
            "usuario": usuario,
            "creado_por": "sistema",
            "creado_en": now_iso(),
        }
    )
    try:
        return crear(tabla="usuarios", datos=datos)
    except ErrorIntegridad:
        # Protección frente a dos reinicios simultáneos de Streamlit.
        existente = consultar_uno(
            tabla="usuarios",
            columnas="id",
            filtros={"usuario": usuario},
        )
        if not existente:
            raise
        editar(tabla="usuarios", datos=datos, filtros={"id": existente["id"]})
        return existente["id"]


def auth_user(usuario, password):
    """Autentica, cuenta hasta ocho fallos y bloquea al alcanzar el límite."""
    usuario = str(usuario or "").strip()
    fila = consultar_uno(
        tabla="usuarios",
        columnas=(
            "id,usuario,nombre,password_hash,rol,activo,"
            "intentos_fallidos,requiere_cambio_pass"
        ),
        filtros={"usuario": usuario},
    )

    if not fila:
        return {
            "estado": "credenciales_invalidas",
            "intentos": None,
            "restantes": None,
        }

    activo = int(fila.get("activo") or 0)
    intentos = int(fila.get("intentos_fallidos") or 0)

    if activo != 1:
        return {"estado": "bloqueado", "usuario": fila.get("usuario", usuario)}

    if check_password(password, fila.get("password_hash")):
        editar(
            tabla="usuarios",
            datos={
                "intentos_fallidos": 0,
                "ultimo_acceso": now_iso(),
                "actualizado_en": now_iso(),
            },
            filtros={"id": fila["id"]},
        )
        return {
            "estado": "ok",
            "usuario": fila.get("usuario", usuario),
            "nombre": fila.get("nombre", ""),
            "rol": fila.get("rol", "consulta"),
            "requiere_cambio_pass": int(fila.get("requiere_cambio_pass") or 0),
        }

    nuevos_intentos = min(intentos + 1, 8)
    bloqueado = nuevos_intentos >= 8
    editar(
        tabla="usuarios",
        datos={
            "intentos_fallidos": nuevos_intentos,
            "activo": 0 if bloqueado else 1,
            "actualizado_en": now_iso(),
        },
        filtros={"id": fila["id"]},
    )

    if bloqueado:
        return {
            "estado": "bloqueado_por_intentos",
            "usuario": fila.get("usuario", usuario),
            "intentos": 8,
            "restantes": 0,
        }

    return {
        "estado": "advertencia" if nuevos_intentos >= 6 else "credenciales_invalidas",
        "usuario": fila.get("usuario", usuario),
        "intentos": nuevos_intentos,
        "restantes": 8 - nuevos_intentos,
    }
