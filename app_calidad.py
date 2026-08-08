import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import os
import base64
from datetime import datetime, timedelta, date
from pathlib import Path
from uuid import uuid4

APP_NAME = "Calidad MD | PNC y ME"
DB_PATH = "calidad.db"
UPLOAD_DIR = Path("evidencias_calidad")
SESSION_TIMEOUT_MINUTES = 30
FORCE_RESET_ADMIN = True
ADMIN_USER = "admin"
ADMIN_PASS = "Cambiar123!"

st.set_page_config(page_title=APP_NAME, page_icon="✅", layout="wide", initial_sidebar_state="expanded")


def apply_styles():
    st.markdown("""
    <style>
    :root{
      --primary:#143c4b; --primary2:#0f2f3b; --accent:#12a594; --accent2:#6d5dfc;
      --bg:#f5f7fa; --card:#ffffff; --text:#3f4658; --muted:#7b8498; --line:#dfe6ee;
      --shadow:0 10px 28px rgba(15,23,42,.08);
    }
    .stApp{background:var(--bg);} header[data-testid="stHeader"]{display:none;}
    .main .block-container{padding-top:0rem; padding-left:2rem; padding-right:2rem; max-width:100%;}
    [data-testid="stSidebar"]{background:var(--primary);} [data-testid="stSidebar"] *{color:#fff!important;}
    [data-testid="stSidebar"] hr{border-color:rgba(255,255,255,.18);} 
    .side-logo{font-size:1.55rem;font-weight:900;display:flex;gap:.75rem;align-items:center;margin:1rem 0 1.5rem .2rem;}
    .side-section{font-size:.76rem;font-weight:900;opacity:.48;text-transform:uppercase;letter-spacing:.05rem;margin:1.2rem 0 .55rem 0;}
    .side-card{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);border-radius:14px;padding:.8rem .9rem;margin-bottom:1rem;}
    .topbar{height:78px;background:#fff;display:flex;justify-content:flex-end;align-items:center;margin-left:-2rem;margin-right:-2rem;padding:0 2.2rem;box-shadow:0 1px 0 rgba(15,23,42,.06);}
    .topbar-user{display:flex;gap:1rem;align-items:center;color:#6b7280;font-size:.92rem;letter-spacing:.02rem;}
    .topbar-bell{font-size:1.35rem;color:#c5cad7;padding-right:1.6rem;border-right:1px solid #e5e7eb;margin-right:1rem;}
    .avatar{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#d8fff6,#d8dbff);display:flex;align-items:center;justify-content:center;color:var(--primary);font-weight:900;}
    .nav-title{font-size:.76rem;font-weight:900;color:#7a8498;text-transform:uppercase;letter-spacing:.08rem;margin:1.15rem 0 .3rem 0;}
    div[role="radiogroup"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;overflow-x:auto!important;gap:.65rem!important;padding:.35rem .15rem .7rem .15rem!important;scrollbar-width:thin;}
    div[role="radiogroup"] label{min-width:max-content!important;background:#fff!important;border:1px solid #dce5ee!important;border-radius:999px!important;padding:.55rem 1.05rem!important;box-shadow:0 6px 18px rgba(20,60,75,.06)!important;}
    div[role="radiogroup"] label:hover{border-color:var(--accent)!important;box-shadow:0 9px 24px rgba(18,165,148,.14)!important;}
    div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child{display:none!important;}
    div[role="radiogroup"] label p{color:var(--primary)!important;font-weight:800!important;white-space:nowrap!important;}
    div[role="radiogroup"] label:has(input:checked){background:linear-gradient(135deg,var(--primary) 0%,var(--accent) 100%)!important;border-color:var(--accent)!important;}
    div[role="radiogroup"] label:has(input:checked) p{color:white!important;}
    .dash-title{font-size:2.12rem;line-height:1.15;font-weight:850;color:#545b6d;margin:1.4rem 0 1.8rem 0;}
    .kpi{background:#fff;border-radius:14px;min-height:132px;padding:1.75rem 1.6rem;box-shadow:var(--shadow);border:1px solid #e5e7eb;position:relative;overflow:hidden;}
    .kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--c);} .kpi-label{font-size:.82rem;font-weight:900;color:var(--c);text-transform:uppercase;margin-bottom:.65rem;}
    .kpi-value{font-size:1.68rem;color:#555b6e;font-weight:850;} .kpi-icon{position:absolute;right:1.5rem;top:1.9rem;color:#d8dbe6;font-size:2.25rem;}
    .progress-track{display:inline-block;width:150px;height:10px;background:#e9ecf4;border-radius:999px;margin-left:.8rem;vertical-align:middle;overflow:hidden;}.progress-fill{height:100%;background:var(--accent2);border-radius:999px;}
    .panel{background:#fff;border:1px solid #e0e4ee;border-radius:10px;box-shadow:var(--shadow);margin-top:2rem;min-height:390px;overflow:hidden;}.panel-header{height:66px;display:flex;align-items:center;padding:0 1.4rem;border-bottom:1px solid #e2e8f0;color:var(--primary);font-weight:900;font-size:1.15rem;background:#fbfcff;}.panel-body{padding:1.6rem;}
    .fake-chart{height:300px;display:flex;align-items:flex-end;gap:15px;border-left:1px solid #e5e7eb;border-bottom:2px solid #444;padding:0 1.5rem 1.5rem 1.5rem;position:relative;}.fake-chart:before{content:"Tendencia de registros - Gestión 2026";position:absolute;top:-.8rem;left:26%;font-size:1.18rem;color:#151923;font-weight:850;}.bar-group{display:flex;align-items:flex-end;gap:4px;height:100%;}.bar{width:10px;border-radius:4px 4px 0 0;}
    .donut{width:145px;height:145px;border-radius:50%;background:conic-gradient(#6d5dfc 0 42%, #12a594 42% 100%);margin:4.8rem auto 1rem auto;position:relative;}.donut:after{content:"";width:66px;height:66px;background:white;border-radius:50%;position:absolute;top:39px;left:39px;}.donut-title{text-align:center;font-size:1.15rem;font-weight:900;color:#111827;margin-top:1.2rem;}
    .login-card{max-width:490px;margin:5vh auto 0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:28px;padding:34px;box-shadow:0 24px 70px rgba(15,23,42,.12)}.login-title{font-size:2rem;font-weight:850;color:var(--primary);}.login-subtitle{color:#64748b;margin-bottom:18px;}
    .stButton > button,.stDownloadButton > button{border-radius:11px!important;font-weight:750!important;} div[data-testid="stAlert"]{display:none;}
    </style>
    """, unsafe_allow_html=True)


def now_iso(): return datetime.now().isoformat(timespec="seconds")

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120000)
    return base64.b64encode(salt + key).decode()

def check_password(password: str, stored_hash: str) -> bool:
    try:
        data = base64.b64decode(stored_hash.encode())
        salt, original_key = data[:16], data[16:]
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120000)
        return original_key == new_key
    except Exception:
        return False

def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def read_df(query: str, params=()):
    conn = get_conn()
    try: return pd.read_sql_query(query, conn, params=params)
    finally: conn.close()

def exec_sql(query: str, params=()):
    conn = get_conn(); cur = conn.cursor(); cur.execute(query, params); conn.commit(); lid = cur.lastrowid; conn.close(); return lid


def init_db():
    UPLOAD_DIR.mkdir(exist_ok=True)
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL, password_hash TEXT NOT NULL, rol TEXT NOT NULL CHECK(rol IN ('usuario','desarrollador')), activo INTEGER NOT NULL DEFAULT 1, ultimo_login TEXT, creado_en TEXT NOT NULL, actualizado_en TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS catalogos(id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT NOT NULL, valor TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1, UNIQUE(categoria, valor))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS productos(id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT UNIQUE NOT NULL, descripcion TEXT NOT NULL, cliente TEXT, familia TEXT, activo INTEGER NOT NULL DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS defectos(id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE NOT NULL, defecto TEXT NOT NULL, tipo_defecto TEXT, clasificacion TEXT, observaciones TEXT, activo INTEGER NOT NULL DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pnc_registros(id INTEGER PRIMARY KEY AUTOINCREMENT, folio TEXT UNIQUE NOT NULL, fecha_apertura TEXT NOT NULL, linea_sector TEXT, nave TEXT, item TEXT, descripcion_producto TEXT, cliente TEXT, familia TEXT, lote TEXT, etapa TEXT, codigo_defecto TEXT, defecto TEXT, tipo_defecto TEXT, clasificacion TEXT, turno TEXT, supervisor TEXT, analista TEXT, responsable_detecta TEXT, descripcion_defecto TEXT, acciones_inmediatas TEXT, disposicion TEXT, cantidad_observada REAL DEFAULT 0, cantidad_reproceso REAL DEFAULT 0, cantidad_decomiso REAL DEFAULT 0, cantidad_aprobado_segunda REAL DEFAULT 0, cantidad_total_pnc REAL DEFAULT 0, status TEXT DEFAULT 'ABIERTO', fecha_final_tratamiento TEXT, dias REAL DEFAULT 0, horas REAL DEFAULT 0, personas INTEGER DEFAULT 0, observaciones TEXT, sector_me TEXT, equipo_me TEXT, material_hallado TEXT, numero_particulas TEXT, investigacion_origen TEXT, creado_por TEXT NOT NULL, creado_en TEXT NOT NULL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS adjuntos(id INTEGER PRIMARY KEY AUTOINCREMENT, registro_id INTEGER NOT NULL, folio TEXT NOT NULL, nombre_original TEXT NOT NULL, ruta_archivo TEXT NOT NULL, tipo_archivo TEXT, tamano_bytes INTEGER, subido_por TEXT NOT NULL, subido_en TEXT NOT NULL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, accion TEXT NOT NULL, detalle TEXT NOT NULL, fecha_hora TEXT NOT NULL)""")
    seed_catalogs(cur); seed_productos_basicos(cur); seed_defectos_basicos(cur)
    conn.commit(); conn.close()


def seed_catalogs(cur):
    defaults = {
        "etapa":["PT","SE","MP"], "status":["ABIERTO","CERRADO"], "turno":["A","B","C","MIXTO"], "responsable_detecta":["AUTONOMO","CALIDAD"],
        "tipo_defecto":["Funcional","Contaminación"], "clasificacion":["Inocuidad","Calidad","Salubridad","Legalidad"],
        "disposicion":["Reproceso","Retrabajo","Decomiso","Inspección","Aprobado en segunda instancia","Otro"],
        "linea_sector":["BON O BON","OBLEAS","MOLDEO","CARAMELO","BUTTER","DUVALIN","POOSH","TETRA","STICK","CONFORMADO HUEVITO","CONFITADO"],
        "nave":["1","2","3","FABRIMA","DELTA","J&R","CIMIS","MOLINOS","CONCAS","EUROMEC","ENVAFLEX","MBP","GD´S","PFM","MULTIFORMATO","HD","C2","C1"],
        "supervisor":["AGUSTIN ABEL","JAVIER PACHECO","MARTIN TRUJILLO","SANDRA GAMBOA","ARNOL GOMEZ"],
        "analista":["ELIZABETH ALMAZAN","ALEJANDRO BECERRIL","ALFREDO CHAVEZ","JENNIFER CARRILLO","ARNOL GOMEZ"]}
    for cat, vals in defaults.items():
        for v in vals: cur.execute("INSERT OR IGNORE INTO catalogos(categoria,valor,activo) VALUES(?,?,1)", (cat, v))

def seed_productos_basicos(cur):
    rows = [("90178000272","BON O BON LECHE 20x15x15G","02.- Unidal","L04 - BOB"),("90178001016","OBLEA BON O BON 12X8X27G","02.- Unidal","L07- Oblea"),("90178001783","COBERTURA CORONA","01.- Mondelēz","L17 - Coberturas"),("90178160006","PALETA DUVAL.FRESA GNEL.400X18","01.- Mondelēz","L11 - Paletas"),("90178000740","POOSH FRESA 18X40X4G","02.- Unidal","L02 - Chicle Relleno")]
    for r in rows: cur.execute("INSERT OR IGNORE INTO productos(item,descripcion,cliente,familia,activo) VALUES(?,?,?,?,1)", r)

def seed_defectos_basicos(cur):
    rows = [("12","ANÁLISIS PARA PATOGENOS","Contaminación","Salubridad",""),("44","PROD_OLOR_NO_CARACTERISTICO","Funcional","Calidad",""),("58","PROD_SABOR/OLOR_AMARGO","Funcional","Calidad",""),("63","PROD_SABOR/OLOR_QUEMADO","Funcional","Calidad",""),("67","PROD_SABOR_ACIDO","Funcional","Calidad",""),("86","OBJ-EXTR_METALES","Contaminación","Inocuidad",""),("99","ENV_EMPAQUE_ROTO","Funcional","Calidad",""),("122","ALERGENOS_PRESENCIA/ROTULADO ERRONEO","Contaminación","Inocuidad",""),("128","OBJ-EXTR_PLASTICO_DURO/VIDRIO/ACRILICO/POLICARBONATO","Contaminación","Inocuidad",""),("136","OBJ-EXTR_CABELLO","Contaminación","Salubridad",""),("146","OBJ-EXTR_PLASTICO_BLANDO/CERDAS","Contaminación","Salubridad","")]
    for r in rows: cur.execute("INSERT OR IGNORE INTO defectos(codigo,defecto,tipo_defecto,clasificacion,observaciones,activo) VALUES(?,?,?,?,?,1)", r)

def audit(usuario, accion, detalle): exec_sql("INSERT INTO auditoria(usuario,accion,detalle,fecha_hora) VALUES(?,?,?,?)", (usuario, accion, detalle, now_iso()))

def force_reset_admin():
    pw = hash_password(ADMIN_PASS); conn = get_conn(); cur = conn.cursor(); cur.execute("SELECT id FROM usuarios WHERE usuario=?", (ADMIN_USER,)); exists = cur.fetchone()
    if exists: cur.execute("UPDATE usuarios SET nombre=?, password_hash=?, rol=?, activo=1, actualizado_en=? WHERE usuario=?", ("Administrador del sistema", pw, "desarrollador", now_iso(), ADMIN_USER))
    else: cur.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol,activo,creado_en) VALUES(?,?,?,?,1,?)", (ADMIN_USER, "Administrador del sistema", pw, "desarrollador", now_iso()))
    conn.commit(); conn.close()

def authenticate(usuario, password):
    conn = get_conn(); cur = conn.cursor(); cur.execute("SELECT usuario,nombre,password_hash,rol,activo FROM usuarios WHERE usuario=?", (usuario,)); row = cur.fetchone()
    if not row: conn.close(); return None
    user, nombre, pw, rol, activo = row
    if activo != 1 or not check_password(password, pw): conn.close(); return None
    cur.execute("UPDATE usuarios SET ultimo_login=? WHERE usuario=?", (now_iso(), user)); conn.commit(); conn.close()
    return {"usuario":user, "nombre":nombre, "rol":rol}

def require_login():
    if "auth" not in st.session_state: st.session_state.auth = None
    if "last_activity" not in st.session_state: st.session_state.last_activity = datetime.now()
    if st.session_state.auth:
        if datetime.now() - st.session_state.last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            st.session_state.auth = None; st.stop()
        st.session_state.last_activity = datetime.now(); return st.session_state.auth
    st.markdown('<div class="login-card"><div class="login-title">Sistema de Calidad</div><div class="login-subtitle">Acceso privado para registros PNC y ME.</div>', unsafe_allow_html=True)
    with st.form("login_form"):
        usuario = st.text_input("Usuario"); password = st.text_input("Contraseña", type="password"); submit = st.form_submit_button("Ingresar")
    st.markdown('</div>', unsafe_allow_html=True)
    if submit:
        auth = authenticate(usuario.strip(), password.strip())
        if auth: st.session_state.auth = auth; audit(auth["usuario"], "LOGIN", "Ingreso correcto"); st.rerun()
        else: st.error("Usuario o contraseña incorrectos, o usuario inactivo.")
    st.stop()

def is_dev(): return st.session_state.auth and st.session_state.auth["rol"] == "desarrollador"
def get_catalog(cat):
    df = read_df("SELECT valor FROM catalogos WHERE categoria=? AND activo=1 ORDER BY valor", (cat,)); return df["valor"].tolist() if not df.empty else []
def generate_folio():
    prefix = f"PNC-{datetime.now().year}-"; df = read_df("SELECT folio FROM pnc_registros WHERE folio LIKE ? ORDER BY folio DESC LIMIT 1", (f"{prefix}%",)); n = 0
    if not df.empty:
        try: n = int(str(df.iloc[0]["folio"]).split("-")[-1])
        except Exception: n = 0
    return f"{prefix}{n+1:05d}"
def save_files(files, registro_id, folio, usuario):
    saved=0; folder=UPLOAD_DIR/folio; folder.mkdir(parents=True, exist_ok=True)
    for file in files or []:
        path=folder/f"{uuid4().hex}{Path(file.name).suffix.lower()}"; data=file.getbuffer(); path.write_bytes(data)
        exec_sql("INSERT INTO adjuntos(registro_id,folio,nombre_original,ruta_archivo,tipo_archivo,tamano_bytes,subido_por,subido_en) VALUES(?,?,?,?,?,?,?,?)", (registro_id, folio, file.name, str(path), file.type, len(data), usuario, now_iso())); saved += 1
    return saved

def import_workbook(uploaded_file):
    sheets = pd.read_excel(uploaded_file, sheet_name=None, header=None, dtype=str, engine="openpyxl"); ip=0; idf=0; conn=get_conn(); cur=conn.cursor()
    for name, df in sheets.items():
        if "item" in str(name).lower():
            for _, row in df.iterrows():
                vals=["" if pd.isna(x) else str(x).strip() for x in row.tolist()]
                if len(vals)>=4 and vals[0].replace(".0","").isdigit() and vals[1]: cur.execute("INSERT OR REPLACE INTO productos(item,descripcion,cliente,familia,activo) VALUES(?,?,?,?,1)", (vals[0].replace(".0",""), vals[1], vals[2], vals[3])); ip+=1
    for name, df in sheets.items():
        lname=str(name).lower()
        if "codigo" in lname or "código" in lname:
            for _, row in df.iterrows():
                vals=["" if pd.isna(x) else str(x).strip() for x in row.tolist()]
                if len(vals)>=5 and vals[0].replace(".0","").isdigit() and vals[1]: cur.execute("INSERT OR REPLACE INTO defectos(codigo,defecto,tipo_defecto,clasificacion,observaciones,activo) VALUES(?,?,?,?,?,1)", (vals[0].replace(".0",""), vals[1], vals[2], vals[3], vals[5] if len(vals)>5 else "")); idf+=1
    conn.commit(); conn.close(); return ip,idf

def render_topbar(auth):
    initials = ''.join([p[0] for p in str(auth.get('nombre','AC')).split()[:2]]).upper() or 'AC'
    st.markdown(f'<div class="topbar"><div class="topbar-user"><span class="topbar-bell">🔔</span><span>{auth.get("nombre","USUARIO").upper()}</span><span class="avatar">{initials}</span></div></div>', unsafe_allow_html=True)

def render_sidebar_brand():
    st.markdown('<div class="side-logo"><span>◆</span><span>CALIDAD MD</span></div><hr>', unsafe_allow_html=True)
    st.markdown('<div class="side-section">SISTEMA PRIVADO</div><div class="side-card">PNC y Materia Extraña</div><div class="side-section">ACCESO</div>', unsafe_allow_html=True)

def page_inicio():
    df = read_df("SELECT * FROM pnc_registros"); total=len(df); abiertos=int((df["status"]=="ABIERTO").sum()) if not df.empty else 0; cerrados=int((df["status"]=="CERRADO").sum()) if not df.empty else 0; con_me=int(df["material_hallado"].fillna("").astype(str).str.len().gt(0).sum()) if not df.empty else 0; avance=int((cerrados/total)*100) if total else 0
    st.markdown('<div class="dash-title">Panel Calidad Mundo Dulce</div>', unsafe_allow_html=True)
    k1,k2,k3,k4=st.columns(4)
    with k1: st.markdown(f'<div class="kpi" style="--c:#12a594"><div class="kpi-label">PNC abiertos</div><div class="kpi-value">{abiertos}</div><div class="kpi-icon">●</div></div>', unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="kpi" style="--c:#6d5dfc"><div class="kpi-label">Avance cierre 2026</div><div class="kpi-value">{avance}% <span class="progress-track"><span class="progress-fill" style="width:{avance}%"></span></span></div><div class="kpi-icon">▣</div></div>', unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="kpi" style="--c:#f59e0b"><div class="kpi-label">Registros 2026</div><div class="kpi-value">{total}<br>Registros</div><div class="kpi-icon">▥</div></div>', unsafe_allow_html=True)
    with k4: st.markdown(f'<div class="kpi" style="--c:#ef476f"><div class="kpi-label">Hallazgos ME</div><div class="kpi-value">{con_me}</div><div class="kpi-icon">☑</div></div>', unsafe_allow_html=True)
    left,right=st.columns([2.1,1])
    with left:
        st.markdown('<div class="panel"><div class="panel-header">▥ Tendencia mensual</div><div class="panel-body"><div class="fake-chart">', unsafe_allow_html=True)
        bars=[(3,26,22),(2,21,19),(37,23,19),(31,28,19),(44,42,24),(47,29,12),(37,63,42),(9,4,2),(0,0,0),(0,0,0),(0,0,0),(0,0,0)]
        html=""; scale=4
        for g,r,y in bars: html += f'<div class="bar-group"><div class="bar" style="height:{g*scale}px;background:#12a594"></div><div class="bar" style="height:{r*scale}px;background:#6d5dfc"></div><div class="bar" style="height:{y*scale}px;background:#f59e0b"></div></div>'
        st.markdown(html+'</div></div></div>', unsafe_allow_html=True)
    with right: st.markdown('<div class="panel"><div class="panel-header">◔ Resumen visual</div><div class="panel-body"><div class="donut-title">Calidad MD</div><div class="donut"></div><div style="display:flex;justify-content:space-around;color:#143c4b;font-weight:800"><span>Abiertos</span><span>Cerrados</span></div></div></div>', unsafe_allow_html=True)

def page_registro_pnc():
    st.title("Nuevo registro PNC / ME"); productos=read_df("SELECT item,descripcion,cliente,familia FROM productos WHERE activo=1 ORDER BY descripcion"); defectos=read_df("SELECT codigo,defecto,tipo_defecto,clasificacion FROM defectos WHERE activo=1 ORDER BY CAST(codigo AS INTEGER)")
    with st.form("registro_pnc"):
        c1,c2,c3=st.columns(3)
        with c1: fecha_apertura=st.date_input("Fecha de apertura", value=date.today()); linea_sector=st.selectbox("Línea / Sector", get_catalog("linea_sector")); nave=st.selectbox("Nave", get_catalog("nave"))
        with c2:
            if not productos.empty:
                opt=st.selectbox("ITEM / Producto", [f"{r.item} | {r.descripcion}" for r in productos.itertuples()]); item=opt.split("|")[0].strip(); p=productos[productos["item"]==item].iloc[0]; descripcion_producto=str(p["descripcion"]); cliente=str(p["cliente"]); familia=str(p["familia"]); st.text_input("Descripción", value=descripcion_producto, disabled=True); st.text_input("Cliente", value=cliente, disabled=True); st.text_input("Familia", value=familia, disabled=True)
            else: item=st.text_input("ITEM"); descripcion_producto=st.text_input("Descripción"); cliente=st.text_input("Cliente"); familia=st.text_input("Familia")
            lote=st.text_area("Lote", height=82)
        with c3: etapa=st.selectbox("Etapa", get_catalog("etapa")); semana=int(fecha_apertura.isocalendar().week); st.text_input("Semana", value=str(semana), disabled=True); turno=st.selectbox("Turno", get_catalog("turno"))
        c4,c5=st.columns(2)
        with c4:
            if not defectos.empty:
                opt=st.selectbox("Código / Defecto", [f"{r.codigo} | {r.defecto}" for r in defectos.itertuples()]); codigo_defecto=opt.split("|")[0].strip(); d=defectos[defectos["codigo"]==codigo_defecto].iloc[0]; defecto=str(d["defecto"]); tipo_defecto=str(d["tipo_defecto"]); clasificacion=str(d["clasificacion"]); st.text_input("Tipo", value=tipo_defecto, disabled=True); st.text_input("Clasificación", value=clasificacion, disabled=True)
            else: codigo_defecto=st.text_input("Código"); defecto=st.text_input("Defecto"); tipo_defecto=st.selectbox("Tipo", get_catalog("tipo_defecto")); clasificacion=st.selectbox("Clasificación", get_catalog("clasificacion"))
        with c5: descripcion_defecto=st.text_area("Descripción del defecto", height=110); acciones_inmediatas=st.text_area("Acciones inmediatas", value="Se detiene línea, se segrega e identifica el producto.", height=110)
        c6,c7,c8=st.columns(3); supervisor=c6.selectbox("Supervisor", get_catalog("supervisor")); analista=c6.selectbox("Analista", get_catalog("analista")); responsable_detecta=c7.selectbox("Responsable detecta", get_catalog("responsable_detecta")); disposicion=c7.selectbox("Disposición", get_catalog("disposicion")); status=c8.selectbox("Status", get_catalog("status")); fecha_final=c8.date_input("Fecha final", value=date.today()) if status=="CERRADO" else None
        q1,q2,q3,q4,q5=st.columns(5); cantidad_observada=q1.number_input("Observada kg", min_value=0.0, step=0.1); cantidad_reproceso=q2.number_input("Reproceso kg", min_value=0.0, step=0.1); cantidad_decomiso=q3.number_input("Decomiso kg", min_value=0.0, step=0.1); cantidad_aprobado=q4.number_input("Aprobado 2da kg", min_value=0.0, step=0.1); cantidad_total=q5.number_input("Total PNC kg", min_value=0.0, step=0.1, value=float(cantidad_reproceso+cantidad_decomiso+cantidad_aprobado))
        t1,t2,t3=st.columns(3); dias=t1.number_input("Días", min_value=0.0, step=0.5); horas=t2.number_input("Horas", min_value=0.0, step=0.5); personas=t3.number_input("N° personas", min_value=0, step=1); observaciones=st.text_area("Observaciones")
        m1,m2=st.columns(2); sector_me=m1.text_input("Sector hallazgo"); equipo_me=m2.text_input("Equipo hallazgo"); material_hallado=st.text_area("Material hallado"); numero_particulas=st.text_input("No. partículas"); investigacion_origen=st.text_area("Investigación origen"); evidencias=st.file_uploader("Adjuntar evidencia", type=["pdf","png","jpg","jpeg","xlsx","csv","txt","docx"], accept_multiple_files=True); guardar=st.form_submit_button("Guardar registro")
    if guardar:
        if not descripcion_defecto.strip(): st.warning("Agrega la descripción del defecto antes de guardar."); return
        folio=generate_folio(); rid=exec_sql("""INSERT INTO pnc_registros(folio,fecha_apertura,linea_sector,nave,item,descripcion_producto,cliente,familia,lote,etapa,codigo_defecto,defecto,tipo_defecto,clasificacion,turno,supervisor,analista,responsable_detecta,descripcion_defecto,acciones_inmediatas,disposicion,cantidad_observada,cantidad_reproceso,cantidad_decomiso,cantidad_aprobado_segunda,cantidad_total_pnc,status,fecha_final_tratamiento,dias,horas,personas,observaciones,sector_me,equipo_me,material_hallado,numero_particulas,investigacion_origen,creado_por,creado_en) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (folio,fecha_apertura.isoformat(),linea_sector,nave,item,descripcion_producto,cliente,familia,lote,etapa,codigo_defecto,defecto,tipo_defecto,clasificacion,turno,supervisor,analista,responsable_detecta,descripcion_defecto,acciones_inmediatas,disposicion,cantidad_observada,cantidad_reproceso,cantidad_decomiso,cantidad_aprobado,cantidad_total,status,fecha_final.isoformat() if fecha_final else None,dias,horas,int(personas),observaciones,sector_me,equipo_me,material_hallado,numero_particulas,investigacion_origen,st.session_state.auth["usuario"],now_iso()))
        save_files(evidencias,rid,folio,st.session_state.auth["usuario"]); audit(st.session_state.auth["usuario"],"CREAR_PNC",folio); st.success(f"Registro guardado correctamente: {folio}")

def page_consulta():
    st.title("Consulta, seguimiento y descarga"); df=read_df("SELECT * FROM pnc_registros ORDER BY id DESC")
    if df.empty: st.info("No hay registros capturados."); return
    c1,c2,c3=st.columns(3); sf=c1.multiselect("Status", sorted(df["status"].dropna().unique())); lf=c2.multiselect("Línea/Sector", sorted(df["linea_sector"].dropna().unique())); search=c3.text_input("Buscar")
    filtered=df.copy()
    if sf: filtered=filtered[filtered["status"].isin(sf)]
    if lf: filtered=filtered[filtered["linea_sector"].isin(lf)]
    if search.strip():
        q=search.lower().strip(); mask=pd.Series(False,index=filtered.index)
        for col in ["folio","item","descripcion_producto","lote","defecto","descripcion_defecto"]: mask=mask|filtered[col].fillna("").astype(str).str.lower().str.contains(q,na=False)
        filtered=filtered[mask]
    st.dataframe(filtered,use_container_width=True,hide_index=True); st.download_button("Descargar registros CSV", data=filtered.to_csv(index=False).encode("utf-8-sig"), file_name=f"pnc_me_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")

def page_catalogos():
    if not is_dev(): st.error("No tienes permisos para esta sección."); return
    st.title("Catálogos y carga desde Excel"); uploaded=st.file_uploader("Cargar Excel de catálogos", type=["xlsx"])
    if uploaded and st.button("Importar catálogos desde Excel"):
        try: p,d=import_workbook(uploaded); audit(st.session_state.auth["usuario"],"IMPORTAR_EXCEL",f"Productos={p}, Defectos={d}"); st.success(f"Importación finalizada. Productos: {p}. Defectos: {d}.")
        except Exception as e: st.error(f"No se pudo importar el archivo: {e}")
    tab1,tab2,tab3=st.tabs(["Productos","Defectos","Listas"])
    with tab1: st.dataframe(read_df("SELECT * FROM productos ORDER BY descripcion"),use_container_width=True,hide_index=True)
    with tab2: st.dataframe(read_df("SELECT * FROM defectos ORDER BY CAST(codigo AS INTEGER)"),use_container_width=True,hide_index=True)
    with tab3: st.dataframe(read_df("SELECT * FROM catalogos ORDER BY categoria, valor"),use_container_width=True,hide_index=True)

def page_usuarios():
    if not is_dev(): st.error("No tienes permisos para esta sección."); return
    st.title("Usuarios")
    with st.form("create_user"):
        c1,c2=st.columns(2); usuario=c1.text_input("Usuario"); nombre=c1.text_input("Nombre"); password=c2.text_input("Contraseña temporal", type="password"); rol=c2.selectbox("Rol",["usuario","desarrollador"]); crear=st.form_submit_button("Crear usuario")
    if crear:
        if not usuario.strip() or not nombre.strip() or len(password)<8: st.warning("Completa usuario, nombre y contraseña mínima de 8 caracteres.")
        else:
            try: exec_sql("INSERT INTO usuarios(usuario,nombre,password_hash,rol,activo,creado_en) VALUES(?,?,?,?,1,?)", (usuario.strip(),nombre.strip(),hash_password(password),rol,now_iso())); st.success("Usuario creado.")
            except sqlite3.IntegrityError: st.error("Ese usuario ya existe.")
    st.dataframe(read_df("SELECT id, usuario, nombre, rol, activo, ultimo_login, creado_en FROM usuarios ORDER BY id"),use_container_width=True,hide_index=True)

def page_auditoria():
    if not is_dev(): st.error("No tienes permisos para esta sección."); return
    st.title("Auditoría"); df=read_df("SELECT * FROM auditoria ORDER BY id DESC LIMIT 1000"); st.dataframe(df,use_container_width=True,hide_index=True)
    if not df.empty: st.download_button("Descargar auditoría", data=df.to_csv(index=False).encode("utf-8-sig"), file_name="auditoria.csv", mime="text/csv")

def main():
    apply_styles(); init_db()
    if FORCE_RESET_ADMIN: force_reset_admin()
    auth=require_login(); render_topbar(auth)
    opciones=["Inicio","Nuevo registro","Consulta y descarga"]
    if is_dev(): opciones += ["Catálogos","Usuarios","Auditoría"]
    st.markdown('<div class="nav-title">Módulos principales</div>', unsafe_allow_html=True)
    page=st.radio("Módulos principales", opciones, horizontal=True, label_visibility="collapsed", key="main_nav")
    with st.sidebar:
        render_sidebar_brand()
        if st.button("Cerrar sesión"):
            audit(auth["usuario"],"LOGOUT","Cierre de sesión"); st.session_state.auth=None; st.rerun()
    if page=="Inicio": page_inicio()
    elif page=="Nuevo registro": page_registro_pnc()
    elif page=="Consulta y descarga": page_consulta()
    elif page=="Catálogos": page_catalogos()
    elif page=="Usuarios": page_usuarios()
    elif page=="Auditoría": page_auditoria()

if __name__ == "__main__": main()
