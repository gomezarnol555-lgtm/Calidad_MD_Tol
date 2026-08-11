import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import os
import base64
from urllib.parse import quote
from datetime import datetime, date
from pathlib import Path
from uuid import uuid4

APP_NAME = "Calidad MD | PNC y ME"
DB_PATH = "calidad.db"
UPLOAD_DIR = Path("evidencias_calidad")
FORCE_RESET_ADMIN = True
ADMIN_USER = "admin"
ADMIN_PASS = "Cambiar123!"

st.set_page_config(page_title=APP_NAME, page_icon="✅", layout="wide", initial_sidebar_state="collapsed")

# =========================
# Seguridad, base de datos y utilidades
# =========================

def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return base64.b64encode(salt + key).decode("utf-8")


def check_password(password: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored.encode("utf-8"))
        salt = raw[:16]
        old_key = raw[16:]
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
        return old_key == new_key
    except Exception:
        return False


def conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def read_df(query: str, params=()):
    c = conn()
    try:
        return pd.read_sql_query(query, c, params=params)
    finally:
        c.close()


def exec_sql(query: str, params=()):
    c = conn()
    cur = c.cursor()
    cur.execute(query, params)
    c.commit()
    last_id = cur.lastrowid
    c.close()
    return last_id


def init_db():
    UPLOAD_DIR.mkdir(exist_ok=True)
    c = conn()
    cur = c.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE, nombre TEXT, password_hash TEXT, rol TEXT, activo INTEGER DEFAULT 1, creado_en TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS catalogos(id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT, valor TEXT, activo INTEGER DEFAULT 1, UNIQUE(categoria,valor))")
    cur.execute("CREATE TABLE IF NOT EXISTS productos(id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT UNIQUE, descripcion TEXT, cliente TEXT, familia TEXT, activo INTEGER DEFAULT 1)")
    cur.execute("CREATE TABLE IF NOT EXISTS defectos(id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE, defecto TEXT, tipo_defecto TEXT, clasificacion TEXT, activo INTEGER DEFAULT 1)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pnc_registros(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE,
            fecha_apertura TEXT,
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
            observaciones TEXT,
            material_hallado TEXT,
            creado_por TEXT,
            creado_en TEXT
        )
    """)
    cur.execute("CREATE TABLE IF NOT EXISTS adjuntos(id INTEGER PRIMARY KEY AUTOINCREMENT, registro_id INTEGER, folio TEXT, nombre_original TEXT, ruta_archivo TEXT, tipo_archivo TEXT, subido_por TEXT, subido_en TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, accion TEXT, detalle TEXT, fecha_hora TEXT)")
    seed_data(cur)
    extra_cols = {
        "semana": "INTEGER",
        "categoria_inicial": "TEXT",
        "dias": "REAL DEFAULT 0",
        "horas": "REAL DEFAULT 0",
        "no_personas": "INTEGER DEFAULT 0",
        "sector": "TEXT",
        "equipo": "TEXT",
        "descripcion_material_hallado": "TEXT",
        "no_particulas": "INTEGER DEFAULT 0",
        "investigacion_origen": "TEXT"
    }
    cur.execute("PRAGMA table_info(pnc_registros)")
    actuales = {row[1] for row in cur.fetchall()}
    for col, col_type in extra_cols.items():
        if col not in actuales:
            cur.execute(f"ALTER TABLE pnc_registros ADD COLUMN {col} {col_type}")
    c.commit()
    c.close()


def seed_data(cur):
    catalogs = {
        "linea_sector": ["BON O BON", "OBLEAS", "MOLDEO", "CARAMELO", "BUTTER", "DUVALIN", "POOSH"],
        "nave": ["1", "2", "3", "FABRIMA", "DELTA", "J&R", "CIMIS"],
        "etapa": ["PT", "SE", "MP"],
        "turno": ["A", "B", "C", "MIXTO"],
        "status": ["ABIERTO", "CERRADO"],
        "responsable_detecta": ["AUTONOMO", "CALIDAD"],
        "disposicion": ["Reproceso", "Retrabajo", "Decomiso", "Inspección", "Aprobado en segunda instancia", "Otro"],
        "supervisor": ["AGUSTIN ABEL", "JAVIER PACHECO", "MARTIN TRUJILLO", "ARNOL GOMEZ"],
        "analista": ["ELIZABETH ALMAZAN", "ALEJANDRO BECERRIL", "ARNOL GOMEZ"],
    }
    for categoria, values in catalogs.items():
        for value in values:
            cur.execute("INSERT OR IGNORE INTO catalogos(categoria, valor, activo) VALUES(?, ?, 1)", (categoria, value))

    products = [
        ("90178000272", "BON O BON LECHE 20x15x15G", "02.- Unidal", "L04 - BOB"),
        ("90178001016", "OBLEA BON O BON 12X8X27G", "02.- Unidal", "L07 - Oblea"),
        ("90178001783", "COBERTURA CORONA", "01.- Mondelēz", "L17 - Coberturas"),
    ]
    for row in products:
        cur.execute("INSERT OR IGNORE INTO productos(item, descripcion, cliente, familia, activo) VALUES(?, ?, ?, ?, 1)", row)

    defectos = [
        ("12", "ANÁLISIS PARA PATOGENOS", "Contaminación", "Salubridad"),
        ("86", "OBJ-EXTR_METALES", "Contaminación", "Inocuidad"),
        ("99", "ENV_EMPAQUE_ROTO", "Funcional", "Calidad"),
        ("136", "OBJ-EXTR_CABELLO", "Contaminación", "Salubridad"),
    ]
    for row in defectos:
        cur.execute("INSERT OR IGNORE INTO defectos(codigo, defecto, tipo_defecto, clasificacion, activo) VALUES(?, ?, ?, ?, 1)", row)


def reset_admin():
    pw = hash_password(ADMIN_PASS)
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT id FROM usuarios WHERE usuario=?", (ADMIN_USER,))
    exists = cur.fetchone()
    if exists:
        cur.execute("UPDATE usuarios SET nombre=?, password_hash=?, rol=?, activo=1 WHERE usuario=?", ("Administrador del sistema", pw, "desarrollador", ADMIN_USER))
    else:
        cur.execute("INSERT INTO usuarios(usuario, nombre, password_hash, rol, activo, creado_en) VALUES(?, ?, ?, ?, 1, ?)", (ADMIN_USER, "Administrador del sistema", pw, "desarrollador", now_iso()))
    c.commit()
    c.close()


def auth_user(usuario: str, password: str):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT usuario, nombre, password_hash, rol, activo FROM usuarios WHERE usuario=?", (usuario,))
    row = cur.fetchone()
    c.close()
    if not row:
        return None
    user, nombre, pw, rol, activo = row
    if activo == 1 and check_password(password, pw):
        return {"usuario": user, "nombre": nombre, "rol": rol}
    return None


def audit(usuario, accion, detalle):
    exec_sql("INSERT INTO auditoria(usuario, accion, detalle, fecha_hora) VALUES(?, ?, ?, ?)", (usuario, accion, detalle, now_iso()))


def catalog(categoria):
    df = read_df("SELECT valor FROM catalogos WHERE categoria=? AND activo=1 ORDER BY valor", (categoria,))
    return df["valor"].tolist() if not df.empty else []


def is_dev():
    return st.session_state.get("auth", {}).get("rol") == "desarrollador"


def new_folio():
    prefix = f"PNC-{datetime.now().year}-"
    df = read_df("SELECT folio FROM pnc_registros WHERE folio LIKE ? ORDER BY folio DESC LIMIT 1", (f"{prefix}%",))
    n = 0
    if not df.empty:
        try:
            n = int(str(df.iloc[0]["folio"]).split("-")[-1])
        except Exception:
            n = 0
    return f"{prefix}{n + 1:05d}"


def save_files(files, registro_id, folio, usuario):
    folder = UPLOAD_DIR / folio
    folder.mkdir(parents=True, exist_ok=True)
    for file in files or []:
        path = folder / f"{uuid4().hex}{Path(file.name).suffix.lower()}"
        data = file.getbuffer()
        path.write_bytes(data)
        exec_sql(
            "INSERT INTO adjuntos(registro_id, folio, nombre_original, ruta_archivo, tipo_archivo, subido_por, subido_en) VALUES(?, ?, ?, ?, ?, ?, ?)",
            (registro_id, folio, file.name, str(path), file.type, usuario, now_iso()),
        )

# =========================
# Estilos y layout
# =========================

def styles(collapsed=False):
    menu_width = "88px" if collapsed else "292px"
    menu_text = "none" if collapsed else "inline-block"
    menu_detail = "none" if collapsed else "block"
    item_align = "center" if collapsed else "left"
    st.markdown(f"""
    <style>
    :root {{
        --primary:#0B3440;
        --primary-2:#0E4553;
        --accent:#00A884;
        --violet:#5850EC;
        --bg:#F4F6F9;
        --text:#243042;
        --muted:#667085;
        --line:#DFE6EE;
        --shadow:0 10px 28px rgba(15,23,42,.08);
    }}
    .stApp {{ background:var(--bg); }}
    header[data-testid="stHeader"] {{ display:none; }}
    .main .block-container {{ padding:0 1.25rem 2rem 1.25rem; max-width:100%; }}
    .topbar {{ height:78px; background:#fff; display:flex; justify-content:space-between; align-items:center; padding:0 2rem; margin-bottom:1.1rem; border:1px solid #EEF2F7; border-radius:0 0 18px 18px; box-shadow:0 1px 0 rgba(15,23,42,.05); }}
    .topbar-title {{ color:#0B3440; font-weight:900; font-size:1.05rem; }}
    .topbar-user {{ display:flex; gap:1rem; align-items:center; color:#526078; font-weight:800; }}
    .avatar {{ width:42px; height:42px; border-radius:50%; background:linear-gradient(135deg,#D6FFF6,#DFE1FF); display:flex; align-items:center; justify-content:center; color:#0B3440; font-weight:900; }}
    .menu-panel {{ background:linear-gradient(180deg,var(--primary),var(--primary-2)); border-radius:24px; padding:1rem .85rem; min-height:calc(100vh - 2.5rem); box-shadow:var(--shadow); border:1px solid rgba(255,255,255,.10); }}
    .menu-logo {{ display:flex; align-items:center; gap:.65rem; color:#fff; font-size:1.35rem; font-weight:900; margin-bottom:1rem; white-space:nowrap; }}
    .menu-logo-text {{ display:{menu_text}; }}
    .menu-card {{ display:{menu_detail}; color:#E9FFFA; background:rgba(255,255,255,.09); border:1px solid rgba(255,255,255,.20); border-radius:16px; padding:.85rem; margin:.8rem 0 1.05rem; font-size:.9rem; line-height:1.25; }}
    .menu-title {{ color:#CBE7E1; font-weight:900; font-size:.78rem; letter-spacing:.06rem; margin:.85rem 0 .5rem; display:{menu_detail}; }}
    .menu-active {{ background:linear-gradient(135deg,#00A884,#5850EC); color:#fff; border-radius:13px; padding:.72rem .75rem; font-weight:900; margin:.18rem 0 .35rem; text-align:{item_align}; box-shadow:0 8px 18px rgba(0,168,132,.22); }}
    div[data-testid="column"]:first-child .stButton button {{ width:100%; text-align:{item_align}; justify-content:{item_align}; border:1px solid rgba(255,255,255,.16); background:rgba(255,255,255,.08); color:#fff; border-radius:13px; padding:.68rem .75rem; margin:.14rem 0; font-weight:850; }}
    div[data-testid="column"]:first-child .stButton button:hover {{ background:rgba(255,255,255,.18); border-color:rgba(255,255,255,.32); color:#fff; }}
    .content-card {{ background:transparent; }}
    .page-title {{ color:#243042; font-size:2.15rem; font-weight:900; margin:1.25rem 0 .15rem; letter-spacing:-.02em; }}
    .page-subtitle {{ color:#566176; font-size:1rem; margin-bottom:1.1rem; }}
    .kpi {{ background:#fff; border-radius:16px; padding:1.4rem; min-height:128px; border:1px solid #E3E8EF; box-shadow:var(--shadow); position:relative; overflow:hidden; }}
    .kpi:before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--c); }}
    .kpi-label {{ color:var(--c); font-size:.78rem; font-weight:900; text-transform:uppercase; }}
    .kpi-value {{ color:#394356; font-size:1.65rem; font-weight:900; margin-top:.35rem; }}
    .kpi-foot {{ color:#7C8798; font-size:.78rem; margin-top:.35rem; }}
    .panel {{ background:#fff; border:1px solid #E0E6EE; border-radius:14px; box-shadow:var(--shadow); margin-top:1.25rem; overflow:hidden; }}
    .panel-header {{ padding:1rem 1.25rem; border-bottom:1px solid #E2E8F0; color:#0B3440; font-weight:900; }}
    .panel-body {{ padding:1.25rem; }}
    .login-card {{ max-width:480px; margin:6vh auto; background:#fff; border-radius:24px; padding:32px; box-shadow:0 20px 60px rgba(15,23,42,.12); }}
    .login-title {{ color:#0B3440; font-size:2rem; font-weight:900; }}
    .login-subtitle {{ color:#64748B; margin-bottom:18px; }}
    </style>
    """, unsafe_allow_html=True)


def init_state():
    if "auth" not in st.session_state:
        st.session_state.auth = None
    if "page" not in st.session_state:
        st.session_state.page = "Inicio"
    if "collapsed_menu" not in st.session_state:
        st.session_state.collapsed_menu = False


def login():
    if st.session_state.auth:
        return st.session_state.auth
    styles(False)
    st.markdown('<div class="login-card"><div class="login-title">Sistema de Calidad</div><div class="login-subtitle">Acceso privado para registros PNC y ME.</div>', unsafe_allow_html=True)
    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Ingresar")
    st.markdown('</div>', unsafe_allow_html=True)
    if ok:
        au = auth_user(usuario.strip(), password.strip())
        if au:
            st.session_state.auth = au
            audit(au["usuario"], "LOGIN", "Ingreso correcto")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()


def topbar(user):
    initials = "".join([x[0] for x in user["nombre"].split()[:2]]).upper() or "AD"
    st.markdown(f'<div class="topbar"><div class="topbar-title">Sistema de Calidad MD</div><div class="topbar-user"><span>🔔</span><span>{user["nombre"].upper()}</span><span class="avatar">{initials}</span></div></div>', unsafe_allow_html=True)


def menu_item(page_name, label_full, icon_only):
    collapsed = st.session_state.collapsed_menu
    selected = st.session_state.page == page_name
    label = icon_only if collapsed else label_full
    if selected:
        st.markdown(f'<div class="menu-active">{label}</div>', unsafe_allow_html=True)
    else:
        if st.button(label, key=f"menu_{page_name}"):
            st.session_state.page = page_name
            st.rerun()


def left_menu(user):
    collapsed = st.session_state.collapsed_menu
    st.markdown('<div class="menu-panel">', unsafe_allow_html=True)
    logo_text = "" if collapsed else "CALIDAD MD"
    st.markdown(f'<div class="menu-logo"><span>◆</span><span class="menu-logo-text">{logo_text}</span></div>', unsafe_allow_html=True)
    if not collapsed:
        st.markdown('<div class="menu-card">PNC y Materia Extraña</div><div class="menu-title">MENÚ PRINCIPAL</div>', unsafe_allow_html=True)

    if st.button("☰" if collapsed else "☰ Acortar menú", key="toggle_menu"):
        st.session_state.collapsed_menu = not st.session_state.collapsed_menu
        st.rerun()

    menu_item("Inicio", "🏠 Inicio", "🏠")
    menu_item("Nuevo registro", "📝 Nuevo registro", "📝")
    menu_item("Consulta y descarga", "📊 Consulta y descarga", "📊")
    if is_dev():
        menu_item("Catálogos", "🧩 Catálogos", "🧩")
        menu_item("Usuarios", "👤 Usuarios", "👤")
        menu_item("Auditoría", "🧾 Auditoría", "🧾")

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    if st.button("Salir" if collapsed else "Cerrar sesión", key="logout"):
        audit(user["usuario"], "LOGOUT", "Cierre de sesión")
        st.session_state.auth = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# Páginas
# =========================

def page_inicio():
    df = read_df("SELECT * FROM pnc_registros")
    if df.empty:
        df = pd.DataFrame(columns=["fecha_apertura", "status", "linea_sector", "clasificacion", "material_hallado", "cantidad_total_pnc"])
    df["fecha_apertura"] = pd.to_datetime(df["fecha_apertura"], errors="coerce")
    with st.expander("Filtros dinámicos de indicadores", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        f_status = c1.multiselect("Status", sorted(df["status"].dropna().unique()))
        f_linea = c2.multiselect("Línea/Sector", sorted(df["linea_sector"].dropna().unique()))
        f_clas = c3.multiselect("Clasificación", sorted(df["clasificacion"].dropna().unique()))
        focus = c4.radio("Enfoque", ["Todos", "Abiertos", "Cerrados", "Con ME"])
    data = df.copy()
    if f_status:
        data = data[data["status"].isin(f_status)]
    if f_linea:
        data = data[data["linea_sector"].isin(f_linea)]
    if f_clas:
        data = data[data["clasificacion"].isin(f_clas)]
    if focus == "Abiertos":
        data = data[data["status"] == "ABIERTO"]
    if focus == "Cerrados":
        data = data[data["status"] == "CERRADO"]
    if focus == "Con ME":
        data = data[data["material_hallado"].fillna("").astype(str).str.len() > 0]

    total = len(data)
    abiertos = int((data["status"] == "ABIERTO").sum()) if not data.empty else 0
    cerrados = int((data["status"] == "CERRADO").sum()) if not data.empty else 0
    me = int(data["material_hallado"].fillna("").astype(str).str.len().gt(0).sum()) if not data.empty else 0
    kg = float(data["cantidad_total_pnc"].fillna(0).sum()) if not data.empty else 0
    avance = int(cerrados / total * 100) if total else 0

    st.markdown('<div class="page-title">Panel Calidad Mundo Dulce</div><div class="page-subtitle">Indicadores dinámicos de Producto No Conforme y Materia Extraña</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="kpi" style="--c:#00A884"><div class="kpi-label">PNC abiertos</div><div class="kpi-value">{abiertos}</div><div class="kpi-foot">Registros pendientes</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="kpi" style="--c:#5850EC"><div class="kpi-label">Avance de cierre</div><div class="kpi-value">{avance}%</div><div class="kpi-foot">Cerrados vs total</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="kpi" style="--c:#F59E0B"><div class="kpi-label">Registros filtrados</div><div class="kpi-value">{total}</div><div class="kpi-foot">Coincidencias</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="kpi" style="--c:#E11D48"><div class="kpi-label">Kg PNC / ME</div><div class="kpi-value">{kg:,.1f}</div><div class="kpi-foot">Hallazgos ME: {me}</div></div>', unsafe_allow_html=True)

    left, right = st.columns([2, 1])
    with left:
        st.markdown('<div class="panel"><div class="panel-header">Tendencia mensual dinámica</div><div class="panel-body">', unsafe_allow_html=True)
        if not data.empty:
            t = data.dropna(subset=["fecha_apertura"]).copy()
            t["Mes"] = t["fecha_apertura"].dt.strftime("%Y-%m")
            st.bar_chart(t.groupby(["Mes", "status"]).size().unstack(fill_value=0), use_container_width=True)
        else:
            st.info("No hay registros para graficar.")
        st.markdown('</div></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel"><div class="panel-header">Distribución por clasificación</div><div class="panel-body">', unsafe_allow_html=True)
        if not data.empty:
            st.dataframe(data["clasificacion"].fillna("Sin clasificación").value_counts().rename_axis("Clasificación").reset_index(name="Registros"), use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos.")
        st.markdown('</div></div>', unsafe_allow_html=True)


def page_registro():
    st.title("Nuevo registro")
    st.caption("Selecciona el tipo de registro y captura la información requerida. Los campos marcados como obligatorios deben completarse antes de guardar.")
    tab_pnc, tab_me, tab_ddm = st.tabs(["PNC", "MATERIA EXTRAÑA", "SEGREGADO POR EL DDM"])

    prod = read_df("SELECT * FROM productos WHERE activo=1 ORDER BY descripcion")
    defs = read_df("SELECT * FROM defectos WHERE activo=1 ORDER BY CAST(codigo AS INTEGER)")

    with tab_pnc:
        st.markdown("#### Registro de Producto No Conforme")
        st.markdown("Los campos automáticos se llenan según los catálogos de **ITEM** y **Código de defecto**.")
        with st.form("registro_pnc"):
            st.markdown("##### Datos obligatorios")
            c1, c2, c3 = st.columns(3)
            fecha = c1.date_input("Fecha *", value=date.today())
            semana_default = int(fecha.isocalendar().week)
            semana = c1.number_input("Semana *", min_value=1, max_value=53, value=semana_default, step=1)
            linea = c1.selectbox("Línea/Sector *", catalog("linea_sector"))
            nave = c1.selectbox("Nave *", catalog("nave"))

            options_producto = [f"{r.item} | {r.descripcion}" for r in prod.itertuples()] if not prod.empty else []
            opt = c2.selectbox("ITEM *", options_producto) if options_producto else ""
            item = opt.split("|")[0].strip() if opt else c2.text_input("ITEM *")
            row = prod[prod["item"] == item].iloc[0] if not prod.empty and item in prod["item"].values else None
            desc = str(row["descripcion"]) if row is not None else ""
            cliente = str(row["cliente"]) if row is not None else ""
            familia = str(row["familia"]) if row is not None else ""
            lote = c2.text_area("Lote *")
            etapa = c3.selectbox("Etapa *", catalog("etapa"))
            turno = c3.selectbox("Turno *", catalog("turno"))
            status = c3.selectbox("Status *", catalog("status"))

            options_defecto = [f"{r.codigo} | {r.defecto}" for r in defs.itertuples()] if not defs.empty else []
            optd = st.selectbox("Código *", options_defecto) if options_defecto else ""
            cod = optd.split("|")[0].strip() if optd else st.text_input("Código *")
            dr = defs[defs["codigo"] == cod].iloc[0] if not defs.empty and cod in defs["codigo"].values else None
            defecto = str(dr["defecto"]) if dr is not None else ""
            tipo = str(dr["tipo_defecto"]) if dr is not None else ""
            clas = str(dr["clasificacion"]) if dr is not None else ""

            st.markdown("##### Campos automáticos")
            a1, a2, a3 = st.columns(3)
            a1.text_input("Descripción", value=desc, disabled=True)
            a2.text_input("Cliente", value=cliente, disabled=True)
            a3.text_input("Familia", value=familia, disabled=True)
            a4, a5, a6 = st.columns(3)
            a4.text_input("Defecto", value=defecto, disabled=True)
            a5.text_input("Tipo de defecto", value=tipo, disabled=True)
            a6.text_input("Clasificación", value=clas, disabled=True)

            st.markdown("##### Cierre inicial obligatorio")
            b1, b2, b3 = st.columns(3)
            sup = b1.selectbox("Supervisor *", catalog("supervisor"))
            ana = b1.selectbox("Analista *", catalog("analista"))
            resp = b2.selectbox("Responsable de detectar el PNC *", catalog("responsable_detecta"))
            disp = b2.selectbox("Disposición *", catalog("disposicion"))
            categoria_options = ["Inocuidad", "Calidad", "Salubridad", "Legalidad", "Funcional", "Contaminación", "Otro"]
            categoria_default = categoria_options.index(clas) if clas in categoria_options else 0
            categoria_inicial = b3.selectbox("Categoría inicial *", categoria_options, index=categoria_default)
            obs = b3.number_input("Cantidad observada kg *", min_value=0.0, step=0.1)
            descripcion = st.text_area("Descripción del defecto *")
            acciones = st.text_area("Acciones inmediatas *", value="Se detiene línea, se segrega e identifica el producto.")

            with st.expander("Campos opcionales para completar después", expanded=False):
                o1, o2, o3, o4 = st.columns(4)
                rep = o1.number_input("Reproceso / Retrabajo kg", min_value=0.0, step=0.1)
                dec = o2.number_input("Decomiso kg", min_value=0.0, step=0.1)
                apr = o3.number_input("Aprobado en Segunda instancia kg", min_value=0.0, step=0.1)
                total = o4.number_input("Cantidad REAL TOTAL DE PNC kg", min_value=0.0, value=rep + dec + apr, step=0.1)
                o5, o6, o7, o8 = st.columns(4)
                fecha_final = o5.date_input("Fecha final del tratamiento", value=date.today()) if status == "CERRADO" else None
                dias = o6.number_input("Días", min_value=0.0, step=0.5)
                horas = o7.number_input("Horas", min_value=0.0, step=0.5)
                no_personas = o8.number_input("N° de personas", min_value=0, step=1)
                observaciones = st.text_area("Observaciones")
                m1, m2, m3, m4, m5 = st.columns([1, 1, 2, 1, 2])
                sector = m1.text_input("Sector")
                equipo = m2.text_input("Equipo")
                descripcion_material = m3.text_area("Descripción de material hallado")
                no_particulas = m4.number_input("No de partículas", min_value=0, step=1)
                investigacion_origen = m5.text_area("Investigación Origen")

            files = st.file_uploader("Adjuntar evidencia", accept_multiple_files=True, type=["pdf", "png", "jpg", "jpeg", "xlsx", "csv", "txt", "docx"])
            ok = st.form_submit_button("Guardar PNC")

        if ok:
            faltantes = []
            if not str(item).strip(): faltantes.append("ITEM")
            if not str(lote).strip(): faltantes.append("Lote")
            if not str(cod).strip(): faltantes.append("Código")
            if not str(descripcion).strip(): faltantes.append("Descripción del defecto")
            if not str(acciones).strip(): faltantes.append("Acciones inmediatas")
            if obs <= 0: faltantes.append("Cantidad observada")
            if faltantes:
                st.error("Completa los campos obligatorios: " + ", ".join(faltantes))
            else:
                folio = new_folio()
                rid = exec_sql(
                    "INSERT INTO pnc_registros(folio,fecha_apertura,linea_sector,nave,item,descripcion_producto,cliente,familia,lote,etapa,codigo_defecto,defecto,tipo_defecto,clasificacion,turno,supervisor,analista,responsable_detecta,descripcion_defecto,acciones_inmediatas,disposicion,cantidad_observada,cantidad_reproceso,cantidad_decomiso,cantidad_aprobado_segunda,cantidad_total_pnc,status,fecha_final_tratamiento,observaciones,material_hallado,creado_por,creado_en,semana,categoria_inicial,dias,horas,no_personas,sector,equipo,descripcion_material_hallado,no_particulas,investigacion_origen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (folio, fecha.isoformat(), linea, nave, item, desc, cliente, familia, lote, etapa, cod, defecto, tipo, clas, turno, sup, ana, resp, descripcion, acciones, disp, obs, rep, dec, apr, total, status, fecha_final.isoformat() if fecha_final else None, observaciones, descripcion_material, st.session_state.auth["usuario"], now_iso(), semana, categoria_inicial, dias, horas, no_personas, sector, equipo, descripcion_material, no_particulas, investigacion_origen),
                )
                save_files(files, rid, folio, st.session_state.auth["usuario"])
                audit(st.session_state.auth["usuario"], "CREAR_PNC", folio)
                st.success(f"Registro PNC guardado correctamente: {folio}")

    with tab_me:
        st.markdown("#### Registro de Materia Extraña")
        st.info("Ventana preparada para capturar registros de Materia Extraña. Puedes usar los campos del bloque de material hallado en PNC mientras se define el flujo final.")
        with st.form("registro_me_base"):
            c1, c2, c3 = st.columns(3)
            c1.date_input("Fecha", value=date.today(), key="me_fecha")
            c1.selectbox("Línea/Sector", catalog("linea_sector"), key="me_linea")
            c2.text_input("Sector", key="me_sector")
            c2.text_input("Equipo", key="me_equipo")
            c3.number_input("No de partículas", min_value=0, step=1, key="me_particulas")
            st.text_area("Descripción de material hallado", key="me_material")
            st.text_area("Investigación Origen", key="me_origen")
            st.form_submit_button("Guardar Materia Extraña")

    with tab_ddm:
        st.markdown("#### Segregado por el DDM")
        st.info("Ventana preparada para capturar segregados por el DDM. La estructura puede ajustarse cuando se defina el formato final de segregado.")
        with st.form("registro_ddm_base"):
            d1, d2, d3 = st.columns(3)
            d1.date_input("Fecha", value=date.today(), key="ddm_fecha")
            d1.selectbox("Línea/Sector", catalog("linea_sector"), key="ddm_linea")
            d2.text_input("ITEM", key="ddm_item")
            d2.text_area("Lote", key="ddm_lote")
            d3.number_input("Cantidad segregada kg", min_value=0.0, step=0.1, key="ddm_cantidad")
            st.text_area("Motivo / Observaciones", key="ddm_obs")
            st.form_submit_button("Guardar Segregado DDM")

def page_consulta():
    st.title("Consulta, seguimiento y descarga")
    df = read_df("SELECT * FROM pnc_registros ORDER BY id DESC")
    if df.empty:
        st.info("No hay registros capturados.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Descargar registros CSV", df.to_csv(index=False).encode("utf-8-sig"), f"pnc_me_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")


def page_catalogos():
    st.title("Catálogos")
    st.dataframe(read_df("SELECT * FROM productos ORDER BY descripcion"), use_container_width=True, hide_index=True)
    st.dataframe(read_df("SELECT * FROM defectos ORDER BY CAST(codigo AS INTEGER)"), use_container_width=True, hide_index=True)


def page_usuarios():
    st.title("Usuarios")
    st.dataframe(read_df("SELECT id,usuario,nombre,rol,activo,creado_en FROM usuarios ORDER BY id"), use_container_width=True, hide_index=True)


def page_auditoria():
    st.title("Auditoría")
    st.dataframe(read_df("SELECT * FROM auditoria ORDER BY id DESC LIMIT 1000"), use_container_width=True, hide_index=True)

# =========================
# App principal
# =========================

def main():
    init_state()
    init_db()
    if FORCE_RESET_ADMIN:
        reset_admin()
    user = login()
    styles(st.session_state.collapsed_menu)

    left_ratio, right_ratio = (0.155, 0.845) if not st.session_state.collapsed_menu else (0.055, 0.945)
    left_col, right_col = st.columns([left_ratio, right_ratio], gap="medium")

    with left_col:
        left_menu(user)

    with right_col:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        topbar(user)
        page = st.session_state.page
        if page == "Inicio":
            page_inicio()
        elif page == "Nuevo registro":
            page_registro()
        elif page == "Consulta y descarga":
            page_consulta()
        elif page == "Catálogos":
            page_catalogos()
        elif page == "Usuarios":
            page_usuarios()
        elif page == "Auditoría":
            page_auditoria()
        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
