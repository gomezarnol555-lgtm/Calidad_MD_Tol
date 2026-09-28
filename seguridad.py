import base64
import hashlib
import hmac
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from configuracion import ADMIN_PASS, ADMIN_REQUIRE_PASSWORD_CHANGE, ADMIN_USER
from base_datos import ErrorIntegridad, consultar_uno, crear, editar


# Solo bloquea URLs, dominios, HTML y JavaScript en campos de texto libre.
_PATRON_ENTRADA_PELIGROSA = re.compile(
    r"(?:https?://|www\.|javascript:|data:text/html|<\s*script|<\s*/?\s*[a-z][^>]*>)",
    flags=re.IGNORECASE,
)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password):
    texto = str(password or "")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        texto.encode("utf-8"),
        salt,
        120000,
    )
    return base64.b64encode(salt + digest).decode("ascii")


def check_password(password, stored):
    try:
        raw = base64.b64decode(str(stored or "").encode("ascii"), validate=True)
        if len(raw) != 48:
            return False
        salt = raw[:16]
        esperado = raw[16:]
        calculado = hashlib.pbkdf2_hmac(
            "sha256",
            str(password or "").encode("utf-8"),
            salt,
            120000,
        )
        return hmac.compare_digest(calculado, esperado)
    except (ValueError, TypeError, UnicodeError, base64.binascii.Error):
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
    return (detectar_entrada_peligrosa(texto) is None, texto)


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
            bloqueados = []
            for columna in resultado.columns:
                for indice, valor in resultado[columna].items():
                    if isinstance(valor, str) and detectar_entrada_peligrosa(valor):
                        resultado.at[indice, columna] = ""
                        fila = indice + 1 if isinstance(indice, int) else indice
                        bloqueados.append(f"{columna}, fila {fila}")
            if bloqueados:
                st.error(
                    "Se bloquearon enlaces o etiquetas HTML/script en: "
                    + ", ".join(bloqueados[:8])
                    + "."
                )
        return resultado

    st.text_input = text_input_seguro
    st.text_area = text_area_segura
    st.data_editor = data_editor_seguro
    st._filtro_seguridad_instalado = True


def asegurar_admin():
    usuario = str(ADMIN_USER or "admin").strip() or "admin"
    existente = consultar_uno("usuarios", ["id"], {"usuario": usuario})
    if existente:
        return existente["id"]
    if not ADMIN_PASS:
        return None
    return crear_usuario(usuario, "Administrador del sistema", ADMIN_PASS, "desarrollador", "sistema", ADMIN_REQUIRE_PASSWORD_CHANGE)

def reset_admin():
    usuario = str(ADMIN_USER or "admin").strip() or "admin"
    existente = consultar_uno("usuarios", ["id"], {"usuario": usuario})
    datos = {
        "nombre": "Administrador del sistema",
        "password_hash": hash_password(ADMIN_PASS),
        "rol": "desarrollador",
        "activo": 1,
        "intentos_fallidos": 0,
        "requiere_cambio_pass": int(ADMIN_REQUIRE_PASSWORD_CHANGE),
        "actualizado_por": "sistema",
        "actualizado_en": now_iso(),
    }
    if existente:
        editar("usuarios", datos, {"id": existente["id"]})
        return existente["id"]
    return crear_usuario(usuario, datos["nombre"], ADMIN_PASS, "desarrollador", "sistema", ADMIN_REQUIRE_PASSWORD_CHANGE)

def crear_usuario(usuario, nombre, password, rol="consulta", creado_por="sistema", requiere_cambio=True):
    rol = str(rol or "consulta").strip().lower()
    if rol not in {"consulta", "desarrollador"}:
        raise ValueError("El rol debe ser consulta o desarrollador.")
    return crear("usuarios", {
        "usuario": str(usuario).strip(),
        "nombre": str(nombre).strip(),
        "password_hash": hash_password(password),
        "rol": rol,
        "activo": 1,
        "intentos_fallidos": 0,
        "requiere_cambio_pass": int(bool(requiere_cambio)),
        "creado_en": now_iso(),
        "creado_por": str(creado_por).strip(),
    })

def auth_user(usuario, password):
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

    intentos = int(fila.get("intentos_fallidos") or 0)
    if int(fila.get("activo") or 0) != 1:
        return {"estado": "bloqueado", "usuario": fila.get("usuario", usuario)}

    if check_password(password, fila.get("password_hash")):
        editar(
            "usuarios",
            {
                "intentos_fallidos": 0,
                "ultimo_acceso": now_iso(),
                "actualizado_en": now_iso(),
            },
            {"id": fila["id"]},
            invalidar_cache=False,
        )
        return {
            "estado": "ok",
            "usuario": fila.get("usuario", usuario),
            "nombre": fila.get("nombre", ""),
            "rol": fila.get("rol", "consulta"),
            "requiere_cambio_pass": int(fila.get("requiere_cambio_pass") or 0),
        }

    nuevos = min(intentos + 1, 8)
    bloqueado = nuevos >= 8
    editar(
        "usuarios",
        {
            "intentos_fallidos": nuevos,
            "activo": 0 if bloqueado else 1,
            "actualizado_en": now_iso(),
        },
        {"id": fila["id"]},
    )

    if bloqueado:
        return {
            "estado": "bloqueado_por_intentos",
            "usuario": fila.get("usuario", usuario),
            "intentos": 8,
            "restantes": 0,
        }

    return {
        "estado": "advertencia" if nuevos >= 6 else "credenciales_invalidas",
        "usuario": fila.get("usuario", usuario),
        "intentos": nuevos,
        "restantes": 8 - nuevos,
    }
