import streamlit as st
import pandas as pd
import sqlite3
import bcrypt
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

# =========================================================
# APP PRIVADA PARA SISTEMA DE CALIDAD
# Roles:
#   - usuario: visualizar, capturar datos, descargar informacion y adjuntar evidencia
#   - desarrollador: administrar usuarios, catalogos, permisos, registros y auditoria
#
# Funciones incluidas:
#   - Expiracion de sesion por inactividad
#   - Cambio obligatorio de contrasena temporal
#   - Restablecimiento de contrasena por administrador/desarrollador
#   - Permisos granulares por rol y modulo
#   - Folio automatico para cada registro
#   - Adjuntos de evidencia
#   - Auditoria con IP aproximada y agente de usuario cuando Streamlit lo permita
# =========================================================

APP_NAME = "Sistema de Calidad"
DB_PATH = "calidad_app.db"
UPLOAD_DIR = Path("evidencias_calidad")
SESSION_TIMEOUT_MINUTES = 30

# Usuario inicial de administracion/desarrollo.
# IMPORTANTE: cambia estos valores antes de usar en produccion.
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASSWORD = "Cambiar123!"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------
# Estilos visuales
# -----------------------------

def apply_styles():
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        div[data-testid="metric-container"] {
            background-color: #f8fafc;
            border: 1px solid #e5e7eb;
            padding: 14px;
            border-radius: 14px;
        }
        .stButton > button, .stDownloadButton > button {
            border-radius: 10px;
            font-weight: 600;
        }
        .app-card {
            padding: 16px;
            border-radius: 14px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# -----------------------------
# Seguridad y base de datos
# -----------------------------

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def check_password(password: str, password_hash: bytes) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash)
    except Exception:
        return False


def get_request_info():
    """
    Streamlit no siempre expone IP real, especialmente detras de proxy.
    Si st.context.headers esta disponible, se intenta leer X-Forwarded-For y User-Agent.
    Si no existe, se registra como no disponible.
    """
    ip = "No disponible"
    user_agent = "No disponible"
    try:
        context = getattr(st, "context", None)
        headers = getattr(context, "headers", None) if context else None
        if headers:
            ip = headers.get("X-Forwarded-For", headers.get("X-Real-Ip", "No disponible"))
            user_agent = headers.get("User-Agent", "No disponible")
    except Exception:
        pass
    return ip, user_agent


def column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(f"PRAGMA table_info({table_name})")
    return column_name in [row[1] for row in cur.fetchall()]


def ensure_column(cur, table_name: str, column_name: str, definition: str):
    if not column_exists(cur, table_name, column_name):
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def seed_default_permissions(cur):
    default_permissions = {
        "usuario": {
            "Inicio": 1,
            "Captura": 1,
            "Consulta y descarga": 1,
            "Mis adjuntos": 1,
            "Editar registros": 0,
            "Usuarios": 0,
            "Catalogos": 0,
            "Permisos": 0,
            "Auditoria": 0,
        },
        "desarrollador": {
            "Inicio": 1,
            "Captura": 1,
            "Consulta y descarga": 1,
            "Mis adjuntos": 1,
            "Editar registros": 1,
            "Usuarios": 1,
            "Catalogos": 1,
            "Permisos": 1,
            "Auditoria": 1,
        }
    }

    for rol, modules in default_permissions.items():
        for modulo, permitido in modules.items():
            cur.execute("""
                INSERT OR IGNORE INTO permisos (rol, modulo, permitido, actualizado_en)
                VALUES (?, ?, ?, ?)
            """, (rol, modulo, permitido, now_iso()))


def seed_default_catalogs(cur):
    defaults = [
        ("area", "Producción"),
        ("area", "Calidad"),
        ("area", "Almacén"),
        ("area", "Mantenimiento"),
        ("tipo_evento", "Evaluación sensorial"),
        ("tipo_evento", "Desviación"),
        ("tipo_evento", "No conformidad"),
        ("tipo_evento", "Liberación"),
        ("tipo_evento", "Retención"),
        ("disposicion", "Se detiene línea, se segrega e identifica el producto"),
        ("disposicion", "Se libera producto"),
        ("disposicion", "Se mantiene en retención"),
        ("disposicion", "Se solicita evaluación adicional"),
    ]
    for categoria, elemento in defaults:
        cur.execute("""
            SELECT id FROM catalogo_elementos
            WHERE categoria = ? AND elemento = ?
        """, (categoria, elemento))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO catalogo_elementos (categoria, elemento, activo, creado_en)
                VALUES (?, ?, ?, ?)
            """, (categoria, elemento, 1, now_iso()))


def init_db():
    UPLOAD_DIR.mkdir(exist_ok=True)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            password_hash BLOB NOT NULL,
            rol TEXT NOT NULL CHECK(rol IN ('usuario','desarrollador')),
            activo INTEGER NOT NULL DEFAULT 1,
            debe_cambiar_password INTEGER NOT NULL DEFAULT 0,
            ultimo_login TEXT,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS catalogo_elementos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            elemento TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registros_calidad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE,
            fecha TEXT NOT NULL,
            area TEXT NOT NULL,
            producto TEXT NOT NULL,
            lote TEXT NOT NULL,
            tipo_evento TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            disposicion TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'Abierto',
            creado_por TEXT NOT NULL,
            creado_en TEXT NOT NULL,
            actualizado_por TEXT,
            actualizado_en TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS adjuntos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registro_id INTEGER NOT NULL,
            folio TEXT NOT NULL,
            nombre_original TEXT NOT NULL,
            ruta_archivo TEXT NOT NULL,
            tipo_archivo TEXT,
            tamano_bytes INTEGER,
            subido_por TEXT NOT NULL,
            subido_en TEXT NOT NULL,
            FOREIGN KEY (registro_id) REFERENCES registros_calidad(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS permisos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rol TEXT NOT NULL,
            modulo TEXT NOT NULL,
            permitido INTEGER NOT NULL DEFAULT 1,
            actualizado_en TEXT,
            UNIQUE(rol, modulo)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            accion TEXT NOT NULL,
            detalle TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            fecha_hora TEXT NOT NULL
        )
    """)

    # Migraciones ligeras por si ya existia una version anterior de la base.
    ensure_column(cur, "usuarios", "debe_cambiar_password", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(cur, "usuarios", "ultimo_login", "TEXT")
    ensure_column(cur, "registros_calidad", "folio", "TEXT")
    ensure_column(cur, "auditoria", "ip", "TEXT")
    ensure_column(cur, "auditoria", "user_agent", "TEXT")

    conn.commit()

    # Crear usuario administrador inicial si no existe ningun usuario.
    cur.execute("SELECT COUNT(*) FROM usuarios")
    total = cur.fetchone()[0]
    if total == 0:
        cur.execute("""
            INSERT INTO usuarios
            (usuario, nombre, password_hash, rol, activo, debe_cambiar_password, creado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            DEFAULT_ADMIN_USER,
            "Administrador del sistema",
            hash_password(DEFAULT_ADMIN_PASSWORD),
            "desarrollador",
            1,
            1,
            now_iso()
        ))
        conn.commit()

    seed_default_permissions(cur)
    seed_default_catalogs(cur)
    conn.commit()
    conn.close()


def audit(usuario: str, accion: str, detalle: str):
    ip, user_agent = get_request_info()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO auditoria (usuario, accion, detalle, ip, user_agent, fecha_hora)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (usuario, accion, detalle, ip, user_agent, now_iso()))
    conn.commit()
    conn.close()


def authenticate(usuario: str, password: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT usuario, nombre, password_hash, rol, activo, debe_cambiar_password
        FROM usuarios
        WHERE usuario = ?
    """, (usuario,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return None

    user, nombre, password_hash, rol, activo, debe_cambiar_password = row
    if activo != 1:
        conn.close()
        return None

    if check_password(password, password_hash):
        cur.execute("UPDATE usuarios SET ultimo_login = ? WHERE usuario = ?", (now_iso(), user))
        conn.commit()
        conn.close()
        return {
            "usuario": user,
            "nombre": nombre,
            "rol": rol,
            "debe_cambiar_password": bool(debe_cambiar_password)
        }

    conn.close()
    return None


def require_login():
    if "auth" not in st.session_state:
        st.session_state.auth = None
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now()

    if st.session_state.auth:
        inactive_time = datetime.now() - st.session_state.last_activity
        if inactive_time > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            usuario = st.session_state.auth.get("usuario", "desconocido")
            audit(usuario, "SESSION_TIMEOUT", "Sesion cerrada por inactividad")
            st.session_state.auth = None
            st.warning("Tu sesión expiró por inactividad. Ingresa nuevamente.")
            st.stop()
        st.session_state.last_activity = datetime.now()
        return st.session_state.auth

    st.title(APP_NAME)
    st.subheader("Acceso privado")
    st.info("Ingresa tus credenciales para continuar.")

    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")

    if submit:
        auth = authenticate(usuario.strip(), password)
        if auth:
            st.session_state.auth = auth
            st.session_state.last_activity = datetime.now()
            audit(auth["usuario"], "LOGIN", "Ingreso correcto al sistema")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos, o usuario inactivo.")

    st.stop()


def require_password_change():
    auth = st.session_state.auth
    if not auth or not auth.get("debe_cambiar_password"):
        return

    st.title("Cambio obligatorio de contraseña")
    st.warning("Por seguridad, cambia tu contraseña temporal antes de continuar.")

    with st.form("forced_password_change"):
        nueva = st.text_input("Nueva contraseña", type="password")
        repetir = st.text_input("Confirmar nueva contraseña", type="password")
        cambiar = st.form_submit_button("Actualizar contraseña")

    if cambiar:
        if len(nueva) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
        elif nueva != repetir:
            st.error("Las contraseñas no coinciden.")
        else:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                UPDATE usuarios
                SET password_hash = ?, debe_cambiar_password = 0, actualizado_en = ?
                WHERE usuario = ?
            """, (hash_password(nueva), now_iso(), auth["usuario"]))
            conn.commit()
            conn.close()
            st.session_state.auth["debe_cambiar_password"] = False
            audit(auth["usuario"], "CAMBIO_PASSWORD", "Cambio obligatorio completado")
            st.success("Contraseña actualizada correctamente.")
            st.rerun()

    st.stop()


def has_permission(modulo: str) -> bool:
    auth = st.session_state.auth
    if not auth:
        return False

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT permitido FROM permisos
        WHERE rol = ? AND modulo = ?
    """, (auth["rol"], modulo))
    row = cur.fetchone()
    conn.close()

    return bool(row and row[0] == 1)


def require_permission(modulo: str):
    if not has_permission(modulo):
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()


# -----------------------------
# Consultas y utilidades
# -----------------------------

def read_df(query: str, params=()):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_active_elements(categoria: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT elemento FROM catalogo_elementos
        WHERE categoria = ? AND activo = 1
        ORDER BY elemento
    """, (categoria,))
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def generate_folio() -> str:
    year = datetime.now().year
    prefix = f"CAL-{year}-"

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT folio FROM registros_calidad
        WHERE folio LIKE ?
        ORDER BY folio DESC
        LIMIT 1
    """, (f"{prefix}%",))
    row = cur.fetchone()
    conn.close()

    if row and row[0]:
        try:
            last_number = int(row[0].split("-")[-1])
        except Exception:
            last_number = 0
    else:
        last_number = 0

    return f"{prefix}{last_number + 1:05d}"


def save_uploaded_files(files, registro_id: int, folio: str, usuario: str):
    saved = 0
    conn = get_conn()
    cur = conn.cursor()

    folio_dir = UPLOAD_DIR / folio
    folio_dir.mkdir(parents=True, exist_ok=True)

    for file in files or []:
        safe_suffix = Path(file.name).suffix.lower()
        unique_name = f"{uuid4().hex}{safe_suffix}"
        file_path = folio_dir / unique_name
        data = file.getbuffer()

        with open(file_path, "wb") as f:
            f.write(data)

        cur.execute("""
            INSERT INTO adjuntos
            (registro_id, folio, nombre_original, ruta_archivo, tipo_archivo, tamano_bytes, subido_por, subido_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            registro_id,
            folio,
            file.name,
            str(file_path),
            file.type,
            len(data),
            usuario,
            now_iso()
        ))
        saved += 1

    conn.commit()
    conn.close()
    return saved


def get_record_options():
    df = read_df("""
        SELECT id, folio, producto, lote, estado
        FROM registros_calidad
        ORDER BY id DESC
    """)
    if df.empty:
        return df, []
    options = [f"{row['id']} | {row['folio']} | {row['producto']} | Lote {row['lote']} | {row['estado']}" for _, row in df.iterrows()]
    return df, options


# -----------------------------
# Pantallas
# -----------------------------

def page_inicio():
    require_permission("Inicio")
    st.title("Panel principal")

    c1, c2, c3, c4 = st.columns(4)
    df = read_df("SELECT * FROM registros_calidad")

    total = len(df)
    abiertos = int((df["estado"] == "Abierto").sum()) if not df.empty else 0
    cerrados = int((df["estado"] == "Cerrado").sum()) if not df.empty else 0
    revision = int((df["estado"] == "En revision").sum()) if not df.empty else 0

    c1.metric("Registros", total)
    c2.metric("Abiertos", abiertos)
    c3.metric("En revisión", revision)
    c4.metric("Cerrados", cerrados)

    st.divider()
    st.subheader("Últimos registros")
    latest = read_df("""
        SELECT id, folio, fecha, area, producto, lote, tipo_evento, estado, creado_por
        FROM registros_calidad
        ORDER BY id DESC
        LIMIT 10
    """)
    st.dataframe(latest, use_container_width=True, hide_index=True)


def page_captura():
    require_permission("Captura")
    st.title("Captura de información de calidad")
    st.caption("Registra eventos, desviaciones, hallazgos, evaluaciones internas y evidencias.")

    areas = get_active_elements("area")
    eventos = get_active_elements("tipo_evento")
    disposiciones = get_active_elements("disposicion")

    with st.form("form_registro"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=datetime.now().date())
            area = st.selectbox("Área", areas)
            producto = st.text_input("Producto")
            lote = st.text_input("Lote")
        with col2:
            tipo_evento = st.selectbox("Tipo de evento", eventos)
            disposicion = st.selectbox("Disposición", disposiciones)
            estado = st.selectbox("Estado", ["Abierto", "En revision", "Cerrado"])

        descripcion = st.text_area(
            "Descripción",
            placeholder="Ejemplo: Durante la evaluación sensorial, se identificaron notas ácidas muy pronunciadas, fuera del perfil esperado del producto."
        )

        evidencias = st.file_uploader(
            "Adjuntar evidencia, opcional",
            type=["pdf", "png", "jpg", "jpeg", "xlsx", "csv", "txt", "docx"],
            accept_multiple_files=True
        )

        guardar = st.form_submit_button("Guardar registro")

    if guardar:
        if not producto.strip() or not lote.strip() or not descripcion.strip():
            st.warning("Completa producto, lote y descripción antes de guardar.")
            return

        folio = generate_folio()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO registros_calidad
            (folio, fecha, area, producto, lote, tipo_evento, descripcion, disposicion, estado, creado_por, creado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            folio,
            fecha.isoformat(),
            area,
            producto.strip(),
            lote.strip(),
            tipo_evento,
            descripcion.strip(),
            disposicion,
            estado,
            st.session_state.auth["usuario"],
            now_iso()
        ))
        registro_id = cur.lastrowid
        conn.commit()
        conn.close()

        total_adjuntos = save_uploaded_files(evidencias, registro_id, folio, st.session_state.auth["usuario"])
        audit(st.session_state.auth["usuario"], "CREAR_REGISTRO", f"Folio={folio}, Producto={producto}, Lote={lote}, Adjuntos={total_adjuntos}")
        st.success(f"Registro guardado correctamente con folio {folio}.")


def page_consulta():
    require_permission("Consulta y descarga")
    st.title("Consulta y descarga")

    df = read_df("""
        SELECT id, folio, fecha, area, producto, lote, tipo_evento, descripcion, disposicion,
               estado, creado_por, creado_en, actualizado_por, actualizado_en
        FROM registros_calidad
        ORDER BY id DESC
    """)

    if df.empty:
        st.info("No hay registros capturados.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_estado = st.multiselect("Estado", sorted(df["estado"].dropna().unique()))
    with col2:
        filtro_area = st.multiselect("Área", sorted(df["area"].dropna().unique()))
    with col3:
        buscar = st.text_input("Buscar por folio, producto, lote o descripción")

    filtered = df.copy()
    if filtro_estado:
        filtered = filtered[filtered["estado"].isin(filtro_estado)]
    if filtro_area:
        filtered = filtered[filtered["area"].isin(filtro_area)]
    if buscar.strip():
        q = buscar.lower().strip()
        filtered = filtered[
            filtered["folio"].fillna("").str.lower().str.contains(q, na=False) |
            filtered["producto"].str.lower().str.contains(q, na=False) |
            filtered["lote"].str.lower().str.contains(q, na=False) |
            filtered["descripcion"].str.lower().str.contains(q, na=False)
        ]

    st.dataframe(filtered, use_container_width=True, hide_index=True)

    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Descargar CSV",
        data=csv,
        file_name=f"registros_calidad_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


def page_mis_adjuntos():
    require_permission("Mis adjuntos")
    st.title("Adjuntos de evidencia")

    df = read_df("""
        SELECT a.id, a.folio, r.producto, r.lote, a.nombre_original, a.ruta_archivo,
               a.tipo_archivo, a.tamano_bytes, a.subido_por, a.subido_en
        FROM adjuntos a
        LEFT JOIN registros_calidad r ON a.registro_id = r.id
        ORDER BY a.id DESC
    """)

    if df.empty:
        st.info("No hay evidencias adjuntas.")
        return

    st.dataframe(
        df.drop(columns=["ruta_archivo"]),
        use_container_width=True,
        hide_index=True
    )

    selected = st.selectbox(
        "Selecciona evidencia para descargar",
        [f"{row['id']} | {row['folio']} | {row['nombre_original']}" for _, row in df.iterrows()]
    )
    selected_id = int(selected.split("|")[0].strip())
    row = df[df["id"] == selected_id].iloc[0]
    path = Path(row["ruta_archivo"])

    if path.exists():
        with open(path, "rb") as f:
            st.download_button(
                "Descargar evidencia seleccionada",
                data=f.read(),
                file_name=row["nombre_original"],
                mime=row["tipo_archivo"] or "application/octet-stream"
            )
    else:
        st.error("El archivo no se encuentra en el almacenamiento local.")


def page_edicion_registros():
    require_permission("Editar registros")
    st.title("Edición avanzada de registros")

    df, options = get_record_options()
    if df.empty:
        st.info("No hay registros disponibles.")
        return

    selected_option = st.selectbox("Selecciona registro", options)
    selected_id = int(selected_option.split("|")[0].strip())
    record = read_df("SELECT * FROM registros_calidad WHERE id = ?", (selected_id,)).iloc[0]

    with st.form("edit_record"):
        st.text_input("Folio", value=str(record["folio"]), disabled=True)
        fecha = st.text_input("Fecha", value=str(record["fecha"]))
        area = st.text_input("Área", value=str(record["area"]))
        producto = st.text_input("Producto", value=str(record["producto"]))
        lote = st.text_input("Lote", value=str(record["lote"]))
        tipo_evento = st.text_input("Tipo de evento", value=str(record["tipo_evento"]))
        descripcion = st.text_area("Descripción", value=str(record["descripcion"]))
        disposicion = st.text_area("Disposición", value=str(record["disposicion"]))
        estado = st.selectbox(
            "Estado",
            ["Abierto", "En revision", "Cerrado"],
            index=["Abierto", "En revision", "Cerrado"].index(record["estado"]) if record["estado"] in ["Abierto", "En revision", "Cerrado"] else 0
        )
        nuevos_adjuntos = st.file_uploader(
            "Agregar nuevas evidencias, opcional",
            type=["pdf", "png", "jpg", "jpeg", "xlsx", "csv", "txt", "docx"],
            accept_multiple_files=True
        )
        guardar = st.form_submit_button("Actualizar registro")

    if guardar:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE registros_calidad
            SET fecha=?, area=?, producto=?, lote=?, tipo_evento=?, descripcion=?, disposicion=?, estado=?,
                actualizado_por=?, actualizado_en=?
            WHERE id=?
        """, (
            fecha,
            area,
            producto,
            lote,
            tipo_evento,
            descripcion,
            disposicion,
            estado,
            st.session_state.auth["usuario"],
            now_iso(),
            int(selected_id)
        ))
        conn.commit()
        conn.close()

        total_adjuntos = save_uploaded_files(nuevos_adjuntos, int(selected_id), str(record["folio"]), st.session_state.auth["usuario"])
        audit(st.session_state.auth["usuario"], "EDITAR_REGISTRO", f"ID={selected_id}, Folio={record['folio']}, Adjuntos nuevos={total_adjuntos}")
        st.success("Registro actualizado correctamente.")


def page_usuarios():
    require_permission("Usuarios")
    st.title("Administración de usuarios")

    st.subheader("Crear usuario")
    with st.form("create_user"):
        col1, col2 = st.columns(2)
        with col1:
            usuario = st.text_input("Usuario nuevo")
            nombre = st.text_input("Nombre")
        with col2:
            password = st.text_input("Contraseña temporal", type="password")
            rol = st.selectbox("Rol", ["usuario", "desarrollador"])
        crear = st.form_submit_button("Crear usuario")

    if crear:
        if not usuario.strip() or not nombre.strip() or not password:
            st.warning("Completa usuario, nombre y contraseña.")
        elif len(password) < 8:
            st.warning("La contraseña debe tener al menos 8 caracteres.")
        else:
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO usuarios
                    (usuario, nombre, password_hash, rol, activo, debe_cambiar_password, creado_en)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    usuario.strip(),
                    nombre.strip(),
                    hash_password(password),
                    rol,
                    1,
                    1,
                    now_iso()
                ))
                conn.commit()
                conn.close()
                audit(st.session_state.auth["usuario"], "CREAR_USUARIO", f"Usuario={usuario}, Rol={rol}")
                st.success("Usuario creado correctamente. Deberá cambiar su contraseña al iniciar sesión.")
            except sqlite3.IntegrityError:
                st.error("Ese usuario ya existe.")

    st.divider()
    st.subheader("Usuarios existentes")
    users = read_df("""
        SELECT id, usuario, nombre, rol, activo, debe_cambiar_password, ultimo_login, creado_en, actualizado_en
        FROM usuarios
        ORDER BY id
    """)
    st.dataframe(users, use_container_width=True, hide_index=True)

    st.subheader("Actualizar usuario")
    if not users.empty:
        selected_user = st.selectbox("Selecciona usuario", users["usuario"].tolist())
        selected = users[users["usuario"] == selected_user].iloc[0]

        with st.form("update_user"):
            nuevo_nombre = st.text_input("Nombre", value=str(selected["nombre"]))
            nuevo_rol = st.selectbox(
                "Rol",
                ["usuario", "desarrollador"],
                index=0 if selected["rol"] == "usuario" else 1
            )
            activo = st.checkbox("Activo", value=bool(selected["activo"]))
            forzar_cambio = st.checkbox("Forzar cambio de contraseña", value=bool(selected["debe_cambiar_password"]))
            nueva_password = st.text_input("Restablecer contraseña, opcional", type="password")
            actualizar = st.form_submit_button("Actualizar usuario")

        if actualizar:
            if nueva_password and len(nueva_password) < 8:
                st.error("La nueva contraseña debe tener al menos 8 caracteres.")
                return

            conn = get_conn()
            cur = conn.cursor()
            if nueva_password:
                cur.execute("""
                    UPDATE usuarios
                    SET nombre=?, rol=?, activo=?, debe_cambiar_password=?, password_hash=?, actualizado_en=?
                    WHERE usuario=?
                """, (
                    nuevo_nombre,
                    nuevo_rol,
                    1 if activo else 0,
                    1,
                    hash_password(nueva_password),
                    now_iso(),
                    selected_user
                ))
            else:
                cur.execute("""
                    UPDATE usuarios
                    SET nombre=?, rol=?, activo=?, debe_cambiar_password=?, actualizado_en=?
                    WHERE usuario=?
                """, (
                    nuevo_nombre,
                    nuevo_rol,
                    1 if activo else 0,
                    1 if forzar_cambio else 0,
                    now_iso(),
                    selected_user
                ))
            conn.commit()
            conn.close()
            audit(st.session_state.auth["usuario"], "ACTUALIZAR_USUARIO", f"Usuario={selected_user}")
            st.success("Usuario actualizado correctamente.")


def page_catalogos():
    require_permission("Catalogos")
    st.title("Administración de catálogos")
    st.caption("Aquí puedes agregar áreas, tipos de evento y disposiciones para estandarizar la captura.")

    with st.form("add_catalog"):
        categoria = st.selectbox("Categoría", ["area", "tipo_evento", "disposicion"])
        elemento = st.text_input("Elemento")
        agregar = st.form_submit_button("Agregar elemento")

    if agregar:
        if not elemento.strip():
            st.warning("Escribe un elemento antes de guardar.")
        else:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO catalogo_elementos (categoria, elemento, activo, creado_en)
                VALUES (?, ?, ?, ?)
            """, (categoria, elemento.strip(), 1, now_iso()))
            conn.commit()
            conn.close()
            audit(st.session_state.auth["usuario"], "AGREGAR_CATALOGO", f"{categoria}={elemento}")
            st.success("Elemento agregado correctamente.")

    df = read_df("SELECT * FROM catalogo_elementos ORDER BY categoria, elemento")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Activar o desactivar elemento")
    if not df.empty:
        option = st.selectbox(
            "Selecciona elemento",
            [f"{row['id']} | {row['categoria']} | {row['elemento']} | Activo={row['activo']}" for _, row in df.iterrows()]
        )
        catalog_id = int(option.split("|")[0].strip())
        nuevo_activo = st.checkbox("Activo", value=bool(df[df["id"] == catalog_id].iloc[0]["activo"]))
        if st.button("Actualizar estado del catálogo"):
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                UPDATE catalogo_elementos
                SET activo = ?, actualizado_en = ?
                WHERE id = ?
            """, (1 if nuevo_activo else 0, now_iso(), catalog_id))
            conn.commit()
            conn.close()
            audit(st.session_state.auth["usuario"], "ACTUALIZAR_CATALOGO", f"ID={catalog_id}, Activo={nuevo_activo}")
            st.success("Catálogo actualizado correctamente.")


def page_permisos():
    require_permission("Permisos")
    st.title("Administración de permisos")
    st.caption("Configura qué módulos puede ver cada rol.")

    df = read_df("SELECT id, rol, modulo, permitido, actualizado_en FROM permisos ORDER BY rol, modulo")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Editar permiso")
    if not df.empty:
        option = st.selectbox(
            "Selecciona permiso",
            [f"{row['id']} | {row['rol']} | {row['modulo']} | Permitido={row['permitido']}" for _, row in df.iterrows()]
        )
        permiso_id = int(option.split("|")[0].strip())
        selected = df[df["id"] == permiso_id].iloc[0]
        permitido = st.checkbox("Permitido", value=bool(selected["permitido"]))

        if st.button("Actualizar permiso"):
            if selected["rol"] == "desarrollador" and selected["modulo"] == "Permisos" and not permitido:
                st.error("No se recomienda quitar el permiso de Permisos al rol desarrollador.")
                return

            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                UPDATE permisos
                SET permitido = ?, actualizado_en = ?
                WHERE id = ?
            """, (1 if permitido else 0, now_iso(), permiso_id))
            conn.commit()
            conn.close()
            audit(st.session_state.auth["usuario"], "ACTUALIZAR_PERMISO", f"ID={permiso_id}, Permitido={permitido}")
            st.success("Permiso actualizado correctamente.")


def page_auditoria():
    require_permission("Auditoria")
    st.title("Auditoría del sistema")
    df = read_df("SELECT * FROM auditoria ORDER BY id DESC LIMIT 1000")
    st.dataframe(df, use_container_width=True, hide_index=True)

    if not df.empty:
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Descargar auditoría",
            data=csv,
            file_name=f"auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )


# -----------------------------
# App principal
# -----------------------------

def main():
    apply_styles()
    init_db()
    auth = require_login()
    require_password_change()

    with st.sidebar:
        st.title("✅ Calidad")
        st.write(f"**Usuario:** {auth['nombre']}")
        st.write(f"**Rol:** {auth['rol']}")
        st.caption(f"Sesión expira tras {SESSION_TIMEOUT_MINUTES} min de inactividad")

        opciones_base = [
            "Inicio",
            "Captura",
            "Consulta y descarga",
            "Mis adjuntos",
            "Editar registros",
            "Usuarios",
            "Catalogos",
            "Permisos",
            "Auditoria"
        ]
        opciones = [op for op in opciones_base if has_permission(op)]

        if not opciones:
            st.error("Tu usuario no tiene módulos asignados.")
            st.stop()

        page = st.radio("Menú", opciones)

        st.divider()
        if st.button("Cerrar sesión"):
            audit(auth["usuario"], "LOGOUT", "Cierre de sesión")
            st.session_state.auth = None
            st.rerun()

    if page == "Inicio":
        page_inicio()
    elif page == "Captura":
        page_captura()
    elif page == "Consulta y descarga":
        page_consulta()
    elif page == "Mis adjuntos":
        page_mis_adjuntos()
    elif page == "Editar registros":
        page_edicion_registros()
    elif page == "Usuarios":
        page_usuarios()
    elif page == "Catalogos":
        page_catalogos()
    elif page == "Permisos":
        page_permisos()
    elif page == "Auditoria":
        page_auditoria()


if __name__ == "__main__":
    main()
