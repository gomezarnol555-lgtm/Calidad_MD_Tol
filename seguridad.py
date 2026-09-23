import base64
import hashlib
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from configuracion import ADMIN_PASS, ADMIN_USER
from base_datos import conn, exec_sql


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password):
    password = "" if password is None else str(password)
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120000)
    return base64.b64encode(salt + key).decode()


def check_password(password, stored):
    try:
        password = "" if password is None else str(password)
        raw = base64.b64decode(str(stored).encode())
        calculated = hashlib.pbkdf2_hmac("sha256", password.encode(), raw[:16], 120000)
        return calculated == raw[16:]
    except (ValueError, TypeError, base64.binascii.Error):
        return False


_PATRON_ENTRADA_PELIGROSA = re.compile(
    r"(?is)(?:https?\s*:\s*/\s*/|www\s*\.|<\s*/?\s*[a-z][^>]*>|"
    r"(?:javascript|data|vbscript)\s*:|"
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|net|org|mx|io|co|gov|edu|info|biz|app|dev|tech|online|site|xyz|me|tv|cloud)\b)"
)


def detectar_entrada_peligrosa(valor):
    """Detecta enlaces, dominios o etiquetas peligrosas sin fallar con None u otros tipos."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if not texto:
        return None
    coincidencia = _PATRON_ENTRADA_PELIGROSA.search(texto)
    return coincidencia.group(0) if coincidencia else None


def entrada_segura(valor, campo="Campo"):
    """Retorna (es_seguro, texto) sin transformar silenciosamente el contenido."""
    texto = "" if valor is None else str(valor)
    return (False, texto) if detectar_entrada_peligrosa(texto) else (True, texto)


def _instalar_filtro_entradas_streamlit():
    """Instala una sola vez el filtro en entradas libres de Streamlit."""
    if getattr(st, "_filtro_seguridad_instalado", False):
        return

    original_text_input = st.text_input
    original_text_area = st.text_area
    original_data_editor = st.data_editor

    def text_input_seguro(label, *args, **kwargs):
        valor = original_text_input(label, *args, **kwargs)
        if kwargs.get("type") == "password":
            return "" if valor is None else valor
        if detectar_entrada_peligrosa(valor):
            st.error(f"{label}: no se permiten enlaces, dominios ni etiquetas HTML/script.")
            return ""
        return "" if valor is None else valor

    def text_area_segura(label, *args, **kwargs):
        valor = original_text_area(label, *args, **kwargs)
        if detectar_entrada_peligrosa(valor):
            st.error(f"{label}: no se permiten enlaces, dominios ni etiquetas HTML/script.")
            return ""
        return "" if valor is None else valor

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
    st.text_area = text_area_segura
    st.data_editor = data_editor_seguro
    st._filtro_seguridad_instalado = True


def reset_admin():
    pw = hash_password(ADMIN_PASS)
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT id FROM usuarios WHERE usuario=?", (ADMIN_USER,))
    exists = cur.fetchone()
    if exists:
        cur.execute(
            "UPDATE usuarios SET nombre=?, password_hash=?, rol=?, activo=1, "
            "intentos_fallidos=0, requiere_cambio_pass=0 WHERE usuario=?",
            ("Administrador del sistema", pw, "desarrollador", ADMIN_USER),
        )
    else:
        cur.execute(
            "INSERT INTO usuarios(usuario,nombre,password_hash,rol,activo,"
            "intentos_fallidos,requiere_cambio_pass,creado_en) "
            "VALUES(?,?,?,?,1,0,0,?)",
            (ADMIN_USER, "Administrador del sistema", pw, "desarrollador", now_iso()),
        )
    c.commit()
    c.close()


def auth_user(usuario, password):
    """Autentica y controla 8 fallos: 5 base, 3 advertencias finales y bloqueo."""
    usuario = "" if usuario is None else str(usuario).strip()
    password = "" if password is None else str(password)
    c = conn()
    cur = c.cursor()
    cur.execute(
        "SELECT id,usuario,nombre,password_hash,rol,activo,"
        "COALESCE(intentos_fallidos,0),COALESCE(requiere_cambio_pass,0) "
        "FROM usuarios WHERE usuario=?",
        (usuario,),
    )
    row = cur.fetchone()
    if not row:
        c.close()
        return {"estado": "credenciales_invalidas", "intentos": None, "restantes": None}

    uid, user, nombre, pw, rol, activo, intentos, requiere = row
    intentos = int(intentos or 0)
    if int(activo or 0) != 1:
        c.close()
        return {"estado": "bloqueado", "usuario": user}

    if check_password(password, pw):
        cur.execute("UPDATE usuarios SET intentos_fallidos=0 WHERE id=?", (uid,))
        c.commit()
        c.close()
        return {
            "estado": "ok",
            "usuario": user,
            "nombre": nombre,
            "rol": rol,
            "requiere_cambio_pass": int(requiere or 0),
        }

    nuevos = intentos + 1
    bloqueado = nuevos >= 8
    cur.execute(
        "UPDATE usuarios SET intentos_fallidos=?, activo=? WHERE id=?",
        (min(nuevos, 8), 0 if bloqueado else 1, uid),
    )
    c.commit()
    c.close()
    if bloqueado:
        return {
            "estado": "bloqueado_por_intentos",
            "usuario": user,
            "intentos": 8,
            "restantes": 0,
        }
    return {
        "estado": "advertencia" if nuevos >= 6 else "credenciales_invalidas",
        "usuario": user,
        "intentos": nuevos,
        "restantes": 8 - nuevos,
    }
