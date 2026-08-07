import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import os
import base64
from datetime import datetime, timedelta, date
from pathlib import Path
from uuid import uuid4

# =========================================================
# APP CALIDAD PNC / ME
# Usuario inicial:
#   Usuario: admin
#   Contraseña: Cambiar123!
# =========================================================

APP_NAME = "Calidad | PNC y ME"
DB_PATH = "calidad.db"
UPLOAD_DIR = Path("evidencias_calidad")
SESSION_TIMEOUT_MINUTES = 30

# Déjalo en True solo para recuperar acceso.
# Cuando ya puedas entrar, cambia a False.
FORCE_RESET_ADMIN = True

DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASSWORD = "Cambiar123!"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)


def apply_styles():
    st.markdown(
        """
        <style>
        .stApp {
            background: #f6f8fb;
        }

        .main .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }

        [data-testid="stSidebar"] {
            background: #0f172a;
        }

        [data-testid="stSidebar"] * {
            color: #f8fafc !important;
        }

        div[data-testid="metric-container"] {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, .05);
        }

        .hero {
            background: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%);
            border: 1px solid #e2e8f0;
            border-radius: 26px;
            padding: 28px 30px;
            box-shadow: 0 18px 40px rgba(15, 23, 42, .07);
            margin-bottom: 18px;
        }

        .hero-title {
            font-size: 2.1rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 4px;
        }

        .hero-subtitle {
            color: #475569;
            font-size: 1rem;
            margin-bottom: 16px;
        }

        .chip {
            display: inline-block;
            padding: 7px 12px;
            background: #ffffff;
            border: 1px solid #dbeafe;
            border-radius: 999px;
            color: #1d4ed8;
            font-size: .82rem;
            font-weight: 700;
            margin-right: 8px;
            margin-bottom: 6px;
        }

        .login-card {
            max-width: 490px;
            margin: 5vh auto 0 auto;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 28px;
            padding: 34px;
            box-shadow: 0 24px 70px rgba(15, 23, 42, .12);
        }

        .login-title {
            font-size: 2rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 4px;
        }

        .login-subtitle {
            color: #64748b;
            margin-bottom: 18px;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 12px !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000
    )
    return base64.b64encode(salt + key).decode("utf-8")


def check_password(password: str, stored_hash: str) -> bool:
    try:
        data = base64.b64decode(stored_hash.encode("utf-8"))
        salt = data[:16]
        original_key = data[16:]
        new_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            120000
        )
        return original_key == new_key
    except Exception:
        return False


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def read_df(query: str, params=()):
    conn = get_conn()
    try:
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()
    return df


def exec_sql(query: str, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def init_db():
    UPLOAD_DIR.mkdir(exist_ok=True)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL CHECK(rol IN ('usuario','desarrollador')),
            activo INTEGER NOT NULL DEFAULT 1,
            debe_cambiar_password INTEGER NOT NULL DEFAULT 0,
            ultimo_login TEXT,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS catalogos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            valor TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1,
            UNIQUE(categoria, valor)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT UNIQUE NOT NULL,
            descripcion TEXT NOT NULL,
            cliente TEXT,
            familia TEXT,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS defectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            defecto TEXT NOT NULL,
            tipo_defecto TEXT,
            clasificacion TEXT,
            observaciones TEXT,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pnc_registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE NOT NULL,
            fecha_apertura TEXT NOT NULL,
            linea_sector TEXT,
            nave TEXT,
            item TEXT,
            descripcion_producto TEXT,
            cliente TEXT,
            familia TEXT,
            lote TEXT,
            etapa TEXT,
            codigo_defecto TEXT,
            defecto TEXT,
            tipo_defecto TEXT,
            clasificacion TEXT,
            turno TEXT,
            supervisor TEXT,
            analista TEXT,
            responsable_detecta TEXT,
            descripcion_defecto TEXT,
            acciones_inmediatas TEXT,
            disposicion TEXT,
            cantidad_observada REAL DEFAULT 0,
            cantidad_reproceso REAL DEFAULT 0,
            cantidad_decomiso REAL DEFAULT 0,
            cantidad_aprobado_segunda REAL DEFAULT 0,
            cantidad_total_pnc REAL DEFAULT 0,
            status TEXT DEFAULT 'ABIERTO',
            fecha_final_tratamiento TEXT,
            dias REAL DEFAULT 0,
            horas REAL DEFAULT 0,
            personas INTEGER DEFAULT 0,
            observaciones TEXT,
            sector_me TEXT,
            equipo_me TEXT,
            material_hallado TEXT,
            numero_particulas TEXT,
            investigacion_origen TEXT,
            creado_por TEXT NOT NULL,
            creado_en TEXT NOT NULL
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
            subido_en TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            accion TEXT NOT NULL,
            detalle TEXT NOT NULL,
            fecha_hora TEXT NOT NULL
        )
    """)

    conn.commit()
    seed_catalogs(cur)
    seed_productos_basicos(cur)
    seed_defectos_basicos(cur)
    conn.commit()
    conn.close()


def seed_catalogs(cur):
    defaults = {
        "etapa": ["PT", "SE", "MP"],
        "status": ["ABIERTO", "CERRADO"],
        "turno": ["A", "B", "C", "MIXTO"],
        "responsable_detecta": ["AUTONOMO", "CALIDAD"],
        "tipo_defecto": ["Funcional", "Contaminación"],
        "clasificacion": ["Inocuidad", "Calidad", "Salubridad", "Legalidad"],
        "disposicion": [
            "Reproceso",
            "Retrabajo",
            "Decomiso",
            "Inspección",
            "Aprobado en segunda instancia",
            "Otro"
        ],
        "linea_sector": [
            "BON O BON",
            "OBLEAS",
            "MOLDEO",
            "CARAMELO",
            "BUTTER",
            "DUVALIN",
            "POOSH",
            "TETRA",
            "STICK",
            "CONFORMADO HUEVITO",
            "CONFITADO"
        ],
        "nave": [
            "1",
            "2",
            "3",
            "FABRIMA",
            "DELTA",
            "J&R",
            "CIMIS",
            "MOLINOS",
            "CONCAS",
            "EUROMEC",
            "ENVAFLEX",
            "MBP",
            "GD´S",
            "PFM",
            "MULTIFORMATO",
            "HD",
            "C2",
            "C1"
        ],
        "supervisor": [
            "AGUSTIN ABEL",
            "JAVIER PACHECO",
            "MARTIN TRUJILLO",
            "SANDRA GAMBOA",
            "JUAN CARLOS DOMINGUEZ",
            "DANIEL JIMENEZ",
            "VICTOR AYALA",
            "ARNOL GOMEZ"
        ],
        "analista": [
            "ELIZABETH ALMAZAN",
            "ALEJANDRO BECERRIL",
            "ALFREDO CHAVEZ",
            "JENNIFER CARRILLO",
            "MARISOL GARCIA",
            "VERONICA GÓMEZ",
            "ARNOL GOMEZ"
        ]
    }

    for categoria, valores in defaults.items():
        for valor in valores:
            cur.execute("""
                INSERT OR IGNORE INTO catalogos (categoria, valor, activo)
                VALUES (?, ?, 1)
            """, (categoria, valor))


def seed_productos_basicos(cur):
    productos = [
        ("90178000272", "BON O BON LECHE 20x15x15G", "02.- Unidal", "L04 - BOB"),
        ("90178001016", "OBLEA BON O BON 12X8X27G", "02.- Unidal", "L07- Oblea"),
        ("90178001783", "COBERTURA CORONA", "01.- Mondelēz", "L17 - Coberturas"),
        ("90178160006", "PALETA DUVAL.FRESA GNEL.400X18", "01.- Mondelēz", "L11 - Paletas"),
        ("90178000740", "POOSH FRESA 18X40X4G", "02.- Unidal", "L02 - Chicle Relleno")
    ]

    for item, descripcion, cliente, familia in productos:
        cur.execute("""
            INSERT OR IGNORE INTO productos (item, descripcion, cliente, familia, activo)
            VALUES (?, ?, ?, ?, 1)
        """, (item, descripcion, cliente, familia))


def seed_defectos_basicos(cur):
    defectos = [
        ("12", "ANÁLISIS PARA PATOGENOS", "Contaminación", "Salubridad", ""),
        ("44", "PROD_OLOR_NO_CARACTERISTICO", "Funcional", "Calidad", ""),
        ("58", "PROD_SABOR/OLOR_AMARGO", "Funcional", "Calidad", ""),
        ("63", "PROD_SABOR/OLOR_QUEMADO", "Funcional", "Calidad", ""),
        ("67", "PROD_SABOR_ACIDO", "Funcional", "Calidad", ""),
        ("86", "OBJ-EXTR_METALES", "Contaminación", "Inocuidad", ""),
        ("99", "ENV_EMPAQUE_ROTO", "Funcional", "Calidad", ""),
        ("122", "ALERGENOS_PRESENCIA/ROTULADO ERRONEO", "Contaminación", "Inocuidad", ""),
        ("128", "OBJ-EXTR_PLASTICO_DURO/VIDRIO/ACRILICO/POLICARBONATO", "Contaminación", "Inocuidad", ""),
        ("136", "OBJ-EXTR_CABELLO", "Contaminación", "Salubridad", ""),
        ("146", "OBJ-EXTR_PLASTICO_BLANDO/CERDAS", "Contaminación", "Salubridad", "")
    ]

    for codigo, defecto, tipo, clasificacion, observaciones in defectos:
        cur.execute("""
            INSERT OR IGNORE INTO defectos (
                codigo,
                defecto,
                tipo_defecto,
                clasificacion,
                observaciones,
                activo
            )
            VALUES (?, ?, ?, ?, ?, 1)
        """, (codigo, defecto, tipo, clasificacion, observaciones))


def audit(usuario, accion, detalle):
    exec_sql("""
        INSERT INTO auditoria (usuario, accion, detalle, fecha_hora)
        VALUES (?, ?, ?, ?)
    """, (usuario, accion, detalle, now_iso()))


def force_reset_admin():
    password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM usuarios
        WHERE usuario = ?
    """, (DEFAULT_ADMIN_USER,))

    existe = cur.fetchone()

    if existe:
        cur.execute("""
            UPDATE usuarios
            SET nombre = ?,
                password_hash = ?,
                rol = ?,
                activo = 1,
                debe_cambiar_password = 0,
                actualizado_en = ?
            WHERE usuario = ?
        """, (
            "Administrador del sistema",
            password_hash,
            "desarrollador",
            now_iso(),
            DEFAULT_ADMIN_USER
        ))
    else:
        cur.execute("""
            INSERT INTO usuarios (
                usuario,
                nombre,
                password_hash,
                rol,
                activo,
                debe_cambiar_password,
                creado_en
            )
            VALUES (?, ?, ?, ?, 1, 0, ?)
        """, (
            DEFAULT_ADMIN_USER,
            "Administrador del sistema",
            password_hash,
            "desarrollador",
            now_iso()
        ))

    conn.commit()
    conn.close()


def authenticate(usuario, password):
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

    user, nombre, password_hash_db, rol, activo, debe_cambiar_password = row

    if activo != 1:
        conn.close()
        return None

    if not check_password(password, password_hash_db):
        conn.close()
        return None

    cur.execute("""
        UPDATE usuarios
        SET ultimo_login = ?
        WHERE usuario = ?
    """, (now_iso(), user))

    conn.commit()
    conn.close()

    return {
        "usuario": user,
        "nombre": nombre,
        "rol": rol,
        "debe_cambiar_password": bool(debe_cambiar_password)
    }


def require_login():
    if "auth" not in st.session_state:
        st.session_state.auth = None

    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now()

    if st.session_state.auth:
        inactive_time = datetime.now() - st.session_state.last_activity

        if inactive_time > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            user = st.session_state.auth.get("usuario", "desconocido")
            st.session_state.auth = None
            audit(user, "SESSION_TIMEOUT", "Sesión cerrada por inactividad")
            st.warning("Tu sesión expiró por inactividad. Ingresa nuevamente.")
            st.stop()

        st.session_state.last_activity = datetime.now()
        return st.session_state.auth

    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">Sistema de Calidad</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="login-subtitle">Acceso privado para registros PNC y ME.</div>',
        unsafe_allow_html=True
    )

    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")

    st.markdown('</div>', unsafe_allow_html=True)

    if submit:
        auth = authenticate(usuario.strip(), password.strip())

        if auth:
            st.session_state.auth = auth
            st.session_state.last_activity = datetime.now()
            audit(auth["usuario"], "LOGIN", "Ingreso correcto al sistema")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos, o usuario inactivo.")

    st.stop()


def is_dev():
    return st.session_state.auth and st.session_state.auth["rol"] == "desarrollador"


def get_catalog(categoria):
    df = read_df("""
        SELECT valor
        FROM catalogos
        WHERE categoria = ? AND activo = 1
        ORDER BY valor
    """, (categoria,))

    return df["valor"].tolist() if not df.empty else []


def generate_folio():
    prefix = f"PNC-{datetime.now().year}-"

    df = read_df("""
        SELECT folio
        FROM pnc_registros
        WHERE folio LIKE ?
        ORDER BY folio DESC
        LIMIT 1
    """, (f"{prefix}%",))

    consecutivo = 0

    if not df.empty:
        try:
            consecutivo = int(str(df.iloc[0]["folio"]).split("-")[-1])
        except Exception:
            consecutivo = 0

    return f"{prefix}{consecutivo + 1:05d}"


def save_files(files, registro_id, folio, usuario):
    saved = 0
    folder = UPLOAD_DIR / folio
    folder.mkdir(parents=True, exist_ok=True)

    for file in files or []:
        suffix = Path(file.name).suffix.lower()
        path = folder / f"{uuid4().hex}{suffix}"
        data = file.getbuffer()

        with open(path, "wb") as out:
            out.write(data)

        exec_sql("""
            INSERT INTO adjuntos (
                registro_id,
                folio,
                nombre_original,
                ruta_archivo,
                tipo_archivo,
                tamano_bytes,
                subido_por,
                subido_en
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            registro_id,
            folio,
            file.name,
            str(path),
            file.type,
            len(data),
            usuario,
            now_iso()
        ))

        saved += 1

    return saved


def import_workbook(uploaded_file):
    sheets = pd.read_excel(
        uploaded_file,
        sheet_name=None,
        header=None,
        dtype=str,
        engine="openpyxl"
    )

    imported_products = 0
    imported_defects = 0

    conn = get_conn()
    cur = conn.cursor()

    for name, df in sheets.items():
        lname = str(name).lower()

        if "item" in lname:
            for _, row in df.iterrows():
                values = ["" if pd.isna(x) else str(x).strip() for x in row.tolist()]

                if len(values) >= 4 and values[0].replace(".0", "").isdigit() and valuesitem = values[0].replace(".0", "")

                    cur.execute("""
                        INSERT OR REPLACE INTO productos (
                            item,
                            descripcion,
                            cliente,
                            familia,
                            activo
                        )
                        VALUES (?, ?, ?, ?, 1)
                    """, (
                        item,
                        values[1],
                        values[2],
                        values[3]
                    ))

                    imported_products += 1

    for name, df in sheets.items():
        lname = str(name).lower()

        if "codigo" in lname or "código" in lname:
            for _, row in df.iterrows():
                values = ["" if pd.isna(x) else str(x).strip() for x in row.tolist()]

                if len(values) >= 5 and values[0].replace(".0", "").isdigit() and valuescodigo = values[0].replace(".0", "")
                    observaciones = values[5] if len(values) > 5 else ""

                    cur.execute("""
                        INSERT OR REPLACE INTO defectos (
                            codigo,
                            defecto,
                            tipo_defecto,
                            clasificacion,
                            observaciones,
                            activo
                        )
                        VALUES (?, ?, ?, ?, ?, 1)
                    """, (
                        codigo,
                        values[1],
                        values[2],
                        values[3],
                        observaciones
                    ))

                    imported_defects += 1

    conn.commit()
    conn.close()

    return imported_products, imported_defects


def page_inicio():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Sistema de Calidad PNC y ME</div>
            <div class="hero-subtitle">
                Registro, trazabilidad, evidencias y seguimiento de Producto No Conforme y Materia Extraña.
            </div>
            <span class="chip">PNC</span>
            <span class="chip">Materia Extraña</span>
            <span class="chip">Auditoría</span>
            <span class="chip">Evidencias</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    df = read_df("SELECT * FROM pnc_registros")

    total = len(df)
    abiertos = int((df["status"] == "ABIERTO").sum()) if not df.empty else 0
    cerrados = int((df["status"] == "CERRADO").sum()) if not df.empty else 0
    con_me = int(df["material_hallado"].fillna("").astype(str).str.len().gt(0).sum()) if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros", total)
    c2.metric("Abiertos", abiertos)
    c3.metric("Cerrados", cerrados)
    c4.metric("Con ME", con_me)

    st.subheader("Últimos registros")

    latest = read_df("""
        SELECT
            folio,
            fecha_apertura,
            linea_sector,
            item,
            descripcion_producto,
            codigo_defecto,
            defecto,
            status,
            creado_por
        FROM pnc_registros
        ORDER BY id DESC
        LIMIT 12
    """)

    st.dataframe(latest, use_container_width=True, hide_index=True)


def page_registro_pnc():
    st.title("Nuevo registro PNC / ME")

    productos = read_df("""
        SELECT item, descripcion, cliente, familia
        FROM productos
        WHERE activo = 1
        ORDER BY descripcion
    """)

    defectos = read_df("""
        SELECT codigo, defecto, tipo_defecto, clasificacion
        FROM defectos
        WHERE activo = 1
        ORDER BY CAST(codigo AS INTEGER)
    """)

    with st.form("registro_pnc"):
        st.subheader("Identificación del producto")

        c1, c2, c3 = st.columns(3)

        with c1:
            fecha_apertura = st.date_input("Fecha de apertura", value=date.today())
            linea_sector = st.selectbox("Línea / Sector", get_catalog("linea_sector"))
            nave = st.selectbox("Nave", get_catalog("nave"))

        with c2:
            if not productos.empty:
                product_option = st.selectbox(
                    "ITEM / Producto",
                    [f"{r.item} | {r.descripcion}" for r in productos.itertuples()]
                )

                item = product_option.split("|")[0].strip()
                producto_row = productos[productos["item"] == item].iloc[0]

                descripcion_producto[0 = str(productoow["descripcion"])
                cliente = str(producto_row["cliente"])
                familia = str(producto_row["familia"])

                st.text_input("Descripción", value=descripcion_producto, disabled=True)
                st.text_input("Cliente", value=cliente, disabled=True)
                st.text_input("Familia", value=familia, disabled=True)
            else:
                item = st.text_input("ITEM")
                descripcion_producto = st.text_input("Descripción")
                cliente = st.text_input("Cliente")
                familia = st.text_input("Familia")

            lote = st.text_area("Lote", height=82)

        with c3:
            etapa = st.selectbox("Etapa", get_catalog("etapa"))
            semana = int(fecha_apertura.isocalendar().week)
            st.text_input("Semana", value=str(semana), disabled=True)
            turno = st.selectbox("Turno", get_catalog("turno"))

        st.subheader("Identificación del defecto")

        c4, c5 = st.columns(2)

        with c4:
            if not defectos.empty:
                def_option = st.selectbox(
                    "Código / Defecto",
                    [f"{r.codigo} | {r.defecto}" for r in defectos.itertuples()]
                )

                codigo_defecto = def_option.split("|")[0].strip()
                defecto_row = defectos[defectos["codigo"] == codigo_defecto].iloc[0]

                defecto = str(defecto_row["defecto"])
                tipo_defecto = str(defecto_row["tipo_defecto"])
                clasificacion = str(defecto_row["clasificacion"])

                st.text_input("Tipo de defecto", value=tipo_defecto, disabled=True)
                st.text_input("Clasificación", value=clasificacion, disabled=True)
            else:
                codigo_defecto = st.text_input("Código")
                defecto = st.text_input("Defecto")
                tipo_defecto = st.selectbox("Tipo de defecto", get_catalog("tipo_defecto"))
                clasificacion = st.selectbox("Clasificación", get_catalog("clasificacion"))

        with c5:
            descripcion_defecto = st.text_area("Descripción del defecto", height=110)
            acciones_inmediatas = st.text_area(
                "Acciones inmediatas",
                value="Se detiene línea, se segrega e identifica el producto.",
                height=110
            )

        st.subheader("Responsables y disposición")

        c6, c7, c8 = st.columns(3)

        supervisor = c6.selectbox("Supervisor responsable", get_catalog("supervisor"))
        analista = c6.selectbox("Analista que detecta", get_catalog("analista"))

        responsable_detecta = c7.selectbox(
            "Responsable de detectar PNC",
            get_catalog("responsable_detecta")
        )
        disposicion = c7.selectbox("Disposición", get_catalog("disposicion"))

        status = c8.selectbox("Status", get_catalog("status"))
        fecha_final = None

        if status == "CERRADO":
            fecha_final = c8.date_input("Fecha final de tratamiento", value=date.today())

        st.subheader("Cantidades y tratamiento")

        q1, q2, q3, q4, q5 = st.columns(5)

        cantidad_observada = q1.number_input("Cantidad observada kg", min_value=0.0, step=0.1)
        cantidad_reproceso = q2.number_input("Reproceso / Retrabajo kg", min_value=0.0, step=0.1)
        cantidad_decomiso = q3.number_input("Decomiso kg", min_value=0.0, step=0.1)
        cantidad_aprobado = q4.number_input("Aprobado 2da instancia kg", min_value=0.0, step=0.1)

        cantidad_total = q5.number_input(
            "Cantidad REAL TOTAL PNC kg",
            min_value=0.0,
            step=0.1,
            value=float(cantidad_reproceso + cantidad_decomiso + cantidad_aprobado)
        )

        t1, t2, t3 = st.columns(3)

        dias = t1.number_input("Días", min_value=0.0, step=0.5)
        horas = t2.number_input("Horas", min_value=0.0, step=0.5)
        personas = t3.number_input("N° de personas", min_value=0, step=1)

        observaciones = st.text_area("Observaciones")

        st.subheader("Materia Extraña / Hallazgo, opcional")

        m1, m2 = st.columns(2)

        sector_me = m1.text_input("Sector del hallazgo")
        equipo_me = m2.text_input("Equipo donde se tuvo el hallazgo")

        material_hallado = st.text_area("Descripción del material hallado")
        numero_particulas = st.text_input("No. de partículas")
        investigacion_origen = st.text_area("Investigación del origen")

        evidencias = st.file_uploader(
            "Adjuntar evidencia",
            type=["pdf", "png", "jpg", "jpeg", "xlsx", "csv", "txt", "docx"],
            accept_multiple_files=True
        )

        guardar = st.form_submit_button("Guardar registro")

    if guardar:
        if not descripcion_defecto.strip():
            st.warning("Agrega la descripción del defecto antes de guardar.")
            return

        folio = generate_folio()

        registro_id = exec_sql("""
            INSERT INTO pnc_registros (
                folio,
                fecha_apertura,
                linea_sector,
                nave,
                item,
                descripcion_producto,
                cliente,
                familia,
                lote,
                etapa,
                codigo_defecto,
                defecto,
                tipo_defecto,
                clasificacion,
                turno,
                supervisor,
                analista,
                responsable_detecta,
                descripcion_defecto,
                acciones_inmediatas,
                disposicion,
                cantidad_observada,
                cantidad_reproceso,
                cantidad_decomiso,
                cantidad_aprobado_segunda,
                cantidad_total_pnc,
                status,
                fecha_final_tratamiento,
                dias,
                horas,
                personas,
                observaciones,
                sector_me,
                equipo_me,
                material_hallado,
                numero_particulas,
                investigacion_origen,
                creado_por,
                creado_en
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            folio,
            fecha_apertura.isoformat(),
            linea_sector,
            nave,
            item,
            descripcion_producto,
            cliente,
            familia,
            lote,
            etapa,
            codigo_defecto,
            defecto,
            tipo_defecto,
            clasificacion,
            turno,
            supervisor,
            analista,
            responsable_detecta,
            descripcion_defecto,
            acciones_inmediatas,
            disposicion,
            cantidad_observada,
            cantidad_reproceso,
            cantidad_decomiso,
            cantidad_aprobado,
            cantidad_total,
            status,
            fecha_final.isoformat() if fecha_final else None,
            dias,
            horas,
            int(personas),
            observaciones,
            sector_me,
            equipo_me,
            material_hallado,
            numero_particulas,
            investigacion_origen,
            st.session_state.auth["usuario"],
            now_iso()
        ))

        adjuntos = save_files(
            evidencias,
            registro_id,
            folio,
            st.session_state.auth["usuario"]
        )

        audit(
            st["usuario"(
.session_state.auth["usuario"],
"CREAR_PNC",
            f"Folio={folio}, Adjuntos={adjuntos}"
        )

        st.success(f"Registro guardado correctamente: {folio}")


def page_consulta():
    st.title("Consulta, seguimiento y descarga")

    df = read_df("""
        SELECT *
        FROM pnc_registros
        ORDER BY id DESC
    """)

    if df.empty:
        st.info("No hay registros capturados.")
        return

    c1, c2, c3 = st.columns(3)

    status_filter = c1.multiselect("Status", sorted(df["status"].dropna().unique()))
    linea_filter = c2.multiselect("Línea/Sector", sorted(df["linea_sector"].dropna().unique()))
    search = c3.text_input("Buscar folio, item, producto, lote o defecto")

    filtered = df.copy()

    if status_filter:
        filtered = filtered[filtered["status"].isin(status_filter)]

    if linea_filter:
        filtered = filtered[filtered["linea_sector"].isin(linea_filter)]

    if search.strip():
        q = search.lower().strip()

        cols = [
            "folio",
            "item",
            "descripcion_producto",
            "lote",
            "defecto",
            "descripcion_defecto"
        ]

        mask = pd.Series(False, index=filtered.index)

        for col in cols:
            mask[
folio | filtered[col].fillna("").astype(str).str.lower().str.contains(q, na=False)

        filtered = filtered[mask]

    st.dataframe(filtered, use_container_width=True, hide_index=True)

    st.download_button(
        "Descargar registros CSV",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"pnc_me_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


def page_catalogos():
    if not is_dev():
        st.error("No tienes permisos para esta sección.")
        return

    st.title("Catálogos y carga desde Excel")

    uploaded = st.file_uploader("Cargar Excel de catálogos", type=["xlsx"])

    if uploaded and st.button("Importar catálogos desde Excel"):
        try:
            productos, defectos = import_workbook(uploaded)

            audit(
                st.session_state.auth["usuario"],
                "IMPORTAR_EXCEL",
                f"Productos={productos}, Defectos={defectos}"
            )

            st.success(f"Importación finalizada. Productos: {productos}. Defectos: {defectos}.")
        except Exception as e:
            st.error(f"No se pudo importar el archivo: {e}")

    tab1, tab2, tab3 = st.tabs(["Productos", "Defectos", "Listas"])

    with tab1:
        st.dataframe(
            read_df("SELECT * FROM productos ORDER BY descripcion"),
            use_container_width=True,
            hide_index=True
        )

    with tab2:
        st.dataframe(
            read_df("SELECT * FROM defectos ORDER BY CAST(codigo AS INTEGER)"),
            use_container_width=True,
            hide_index=True
        )

    with tab3:
        st.dataframe(
            read_df("SELECT * FROM catalogos ORDER BY categoria, valor"),
            use_container_width=True,
            hide_index=True
        )

        with st.form("add_catalog"):
            categoria = st.text_input("Categoría")
            valor = st.text_input("Valor")
            add = st.form_submit_button("Agregar valor")

        if add and categoria.strip() and valor.strip():
            exec_sql("""
                INSERT OR IGNORE INTO catalogos (categoria, valor, activo)
                VALUES (?, ?, 1)
            """, (categoria.strip(), valor.strip()))

            st.success("Valor agregado.")
            st.rerun()


def page_usuarios():
    if not is_dev():
        st.error("No tienes permisos para esta sección.")
        return

    st.title("Usuarios")

    with st.form("create_user"):
        c1, c2 = st.columns(2)

        usuario = c1.text_input("Usuario")
        nombre = c1.text_input("Nombre")
        password = c2.text_input("Contraseña temporal", type="password")
        rol = c2.selectbox("Rol", ["usuario", "desarrollador"])

        crear = st.form_submit_button("Crear usuario")

    if crear:
        if not usuario.strip() or not nombre.strip() or len(password) < 8:
            st.warning("Completa usuario, nombre y contraseña mínima de 8 caracteres.")
        else:
            try:
                exec_sql("""
                    INSERT INTO usuarios (
                        usuario,
                        nombre,
                        password_hash,
                        rol,
                        activo,
                        debe_cambiar_password,
                        creado_en
                    )
                    VALUES (?, ?, ?, ?, 1, 1, ?)
                """, (
                    usuario.strip(),
                    nombre.strip(),
                    hash_password(password),
                    rol,
                    now_iso()
                ))

                st.success("Usuario creado. Deberá cambiar contraseña al ingresar.")
            except sqlite3.IntegrityError:
                st.error("Ese usuario ya existe.")

    users = read_df("""
        SELECT
            id,
            usuario,
            nombre,
            rol,
            activo,
            debe_cambiar_password,
            ultimo_login,
            creado_en
        FROM usuarios
        ORDER BY id
    """)

    st.dataframe(users, use_container_width=True, hide_index=True)


def page_auditoria():
    if not is_dev():
        st.error("No tienes permisos para esta sección.")
        return

    st.title("Auditoría")

    df = read_df("""
        SELECT *
        FROM auditoria
        ORDER BY id DESC
        LIMIT 1000
    """)

    st.dataframe(df, use_container_width=True, hide_index=True)

    if not df.empty:
        st.download_button(
            "Descargar auditoría",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="auditoria.csv",
            mime="text/csv"
        )


def main():
    apply_styles()
    init_db()

    if FORCE_RESET_ADMIN:
        force_reset_admin()
        st.warning(
            "Modo recuperación activo: usuario admin restablecido. "
            "Ingresa con admin / Cambiar123!. "
            "Después cambia FORCE_RESET_ADMIN a False."
        )

    auth = require_login()

    with st.sidebar:
        st.title("✅ Calidad")
        st.caption("PNC y Materia Extraña")
        st.write(f"**Usuario:** {auth['nombre']}")
        st.write(f"**Rol:** {auth['rol']}")
        st.divider()

        opciones = [
            "Inicio",
            "Nuevo registro",
            "Consulta y descarga"
        ]

        if is_dev():
            opciones[
Inicio",
Nuevo registro",
Consulta               "Usuarios",
                "Auditoría"
            ]

        page = st.radio("Menú", opciones)

        st.divider()

        if st.button("Cerrar sesión"):
            audit[
Catálogos",
Usuarios",
Auditoría"
 st.radio("Menú", opciones)

.sion_state.auth = None
            st.rerun()

    if page == "Inicio":
        page_inicio()
    elif page == "Nuevo registro":
        page_registro_pnc()
    elif page == "Consulta y descarga":
        page_consulta()
    elif page == "Catálogos":
        page_catalogos()
    elif page == "Usuarios":
        page_usuarios()
    elif page == "Auditoría":
        page_auditoria()


if __name__ == "__main__":
    main()
