"""Conecto mi aplicación con Supabase Data API y Storage API."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st
from supabase import Client, create_client


def secreto(nombre: str, predeterminado: str = "") -> str:
    """Leo mis secretos desde el entorno o desde Streamlit Secrets."""
    valor = os.getenv(nombre)
    if valor:
        return valor
    return str(st.secrets.get(nombre, predeterminado))


@st.cache_resource
def cliente() -> Client:
    """Creo un único cliente HTTPS y lo reutilizo durante la sesión."""
    url = secreto("SUPABASE_URL")
    clave = secreto("SUPABASE_SECRET_KEY")
    if not url or not clave:
        raise RuntimeError("Debo configurar SUPABASE_URL y SUPABASE_SECRET_KEY en Secrets.")
    return create_client(url, clave)


def dataframe(respuesta) -> pd.DataFrame:
    """Convierto una respuesta de Supabase en DataFrame."""
    return pd.DataFrame(respuesta.data or [])


def subir_evidencia(archivo, folio: str) -> str:
    """Guardo una evidencia en mi bucket privado y regreso su ruta."""
    bucket = secreto("SUPABASE_STORAGE_BUCKET", "evidencias-calidad")
    extension = Path(archivo.name).suffix.lower()
    ruta = f"{folio}/{uuid4().hex}{extension}"
    cliente().storage.from_(bucket).upload(
        ruta,
        archivo.getvalue(),
        {
            "content-type": archivo.type or "application/octet-stream",
            "upsert": "false",
        },
    )
    return f"{bucket}/{ruta}"


def comprobar_conexion() -> bool:
    """Compruebo la conexión leyendo una fila de app_config."""
    respuesta = cliente().table("app_config").select("clave").limit(1).execute()
    return respuesta.data is not None
