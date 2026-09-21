"""Capa única de persistencia PostgreSQL/Supabase para Calidad MD."""
from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

import pandas as pd
import psycopg
from psycopg import errors
from supabase import Client, create_client

DatabaseIntegrityError = errors.IntegrityError
_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _secret(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def database_url() -> str:
    url = _secret("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("Falta SUPABASE_DB_URL en variables de entorno o .streamlit/secrets.toml")
    return url


def conn():
    return psycopg.connect(database_url(), autocommit=False)


def _sql(query: str) -> str:
    # La aplicación original usa placeholders SQLite (?). Se convierten sin tocar
    # signos de interrogación dentro de literales, que no existen en sus consultas.
    return query.replace("?", "%s")


def read_df(query: str, params=()) -> pd.DataFrame:
    with conn() as db:
        with db.cursor() as cur:
            cur.execute(_sql(query), tuple(params))
            rows = cur.fetchall()
            columns = [c.name for c in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=columns)


def exec_sql(query: str, params=()):
    statement = _sql(query.strip())
    upper = statement.upper()
    wants_id = upper.startswith("INSERT INTO") and " RETURNING " not in upper
    if wants_id:
        statement = statement.rstrip("; \n\t") + " RETURNING id"
    with conn() as db:
        try:
            with db.cursor() as cur:
                cur.execute(statement, tuple(params))
                result = cur.fetchone() if wants_id else None
            db.commit()
            return int(result[0]) if result and result[0] is not None else None
        except Exception:
            db.rollback()
            raise


def table_columns(table_name: str) -> set[str]:
    if not _SAFE_NAME.fullmatch(table_name):
        raise ValueError("Nombre de tabla no permitido")
    df = read_df("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=?", (table_name,))
    return set(df["column_name"].astype(str)) if not df.empty else set()


def reset_autoincrement(table_name: str):
    if not _SAFE_NAME.fullmatch(table_name):
        raise ValueError("Nombre de tabla no permitido")
    # PostgreSQL sequences do not need resetting after deletes. Kept as a no-op
    # to preserve the original interface and avoid reusing historical IDs.
    return None


def supabase_client() -> Client:
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def upload_evidence(uploaded_file, folio: str) -> str:
    bucket = _secret("SUPABASE_STORAGE_BUCKET", "evidencias-calidad")
    suffix = Path(uploaded_file.name).suffix.lower()
    object_path = f"{folio}/{uuid4().hex}{suffix}"
    payload = uploaded_file.getvalue()
    content_type = getattr(uploaded_file, "type", None) or "application/octet-stream"
    supabase_client().storage.from_(bucket).upload(
        object_path,
        payload,
        {"content-type": content_type, "upsert": "false"},
    )
    return f"{bucket}/{object_path}"
