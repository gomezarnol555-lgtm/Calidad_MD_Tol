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


def css(compact=False):
    side_w = "94px" if compact else "288px"
    text_display = "none" if compact else "inline"
    detail_display = "none" if compact else "block"
    justify = "center" if compact else "flex-start"
    st.markdown(f"""
    <style>
    :root{{--primary:#143c4b;--accent:#12a594;--accent2:#6d5dfc;--warn:#f59e0b;--danger:#ef476f;--bg:#f5f7fa;--shadow:0 10px 28px rgba(15,23,42,.08);}}
    .stApp{{background:var(--bg);}} header[data-testid="stHeader"]{{display:none;}}
    .main .block-container{{padding-top:0;padding-left:2rem;padding-right:2rem;max-width:100%;}}
    section[data-testid="stSidebar"]{{width:{side_w}!important;min-width:{side_w}!important;background:var(--primary);}}
    section[data-testid="stSidebar"]>div{{width:{side_w}!important;min-width:{side_w}!important;}}
    section[data-testid="stSidebar"] *{{color:#fff!important;}}
    .logo{{font-size:1.45rem;font-weight:900;display:flex;gap:.7rem;align-items:center;margin:1rem 0 1.15rem .15rem;white-space:nowrap;}}
    .logo-text{{display:{text_display};}}
    .side-section{{display:{detail_display};font-size:.76rem;font-weight:900;opacity:.50;text-transform:uppercase;letter-spacing:.05rem;margin:1.1rem 0 .55rem 0;}}
    .side-card{{display:{detail_display};border:1px solid rgba(255,255,255,.15);background:rgba(255,255,255,.08);border-radius:14px;padding:.85rem .95rem;margin-bottom:1rem;}}
    section[data-testid="stSidebar"] details{{background:rgba(255,255,255,.08)!important;border:1px solid rgba(255,255,255,.16)!important;border-radius:14px!important;padding:.25rem .35rem!important;margin-top:.35rem!important;}}
    section[data-testid="stSidebar"] details summary{{font-weight:900!important;color:#fff!important;}}
    section[data-testid="stSidebar"] div[role="radiogroup"] label{{justify-content:{justify}!important;background:rgba(255,255,255,.08)!important;border:1px solid rgba(255,255,255,.12)!important;border-radius:12px!important;padding:.72rem .8rem!important;margin-bottom:.25rem!important;}}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover{{background:rgba(255,255,255,.15)!important;}}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){{background:linear-gradient(135deg,#12a594,#6d5dfc)!important;border-color:rgba(255,255,255,.35)!important;}}
    section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"]>div:first-child{{display:none!important;}}
    section[data-testid="stSidebar"] div[role="radiogroup"] label p{{font-weight:850!important;white-space:nowrap!important;}}
    .topbar{{height:78px;background:#fff;display:flex;justify-content:flex-end;align-items:center;margin-left:-2rem;margin-right:-2rem;padding:0 2.2rem;box-shadow:0 1px 0 rgba(15,23,42,.06);}}
    .topbar-user{{display:flex;gap:1rem;align-items:center;color:#6b7280;font-size:.92rem;letter-spacing:.02rem;}}
    .topbar-bell{{font-size:1.35rem;color:#c5cad7;padding-right:1.6rem;border-right:1px solid #e5e7eb;margin-right:1rem;}}
    .avatar{{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#d8fff6,#d8dbff);display:flex;align-items:center;justify-content:center;color:var(--primary);font-weight:900;}}
    .dash-title{{font-size:2.1rem;font-weight:850;color:#545b6d;margin:1.4rem 0 1.1rem 0;}}
    .subtle{{color:#7b8498;font-size:.92rem;margin-bottom:1.2rem;}}
    .kpi{{background:#fff;border-radius:14px;min-height:132px;padding:1.55rem 1.45rem;box-shadow:var(--shadow);border:1px solid #e5e7eb;position:relative;overflow:hidden;}}
    .kpi:before{{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--c);}}
    .kpi-label{{font-size:.78rem;font-weight:900;color:var(--c);text-transform:uppercase;margin-bottom:.55rem;}}
    .kpi-value{{font-size:1.62rem;color:#555b6e;font-weight:850;}}
    .kpi-foot{{font-size:.78rem;color:#8a93a6;margin-top:.35rem;}}
    .kpi-icon{{position:absolute;right:1.35rem;top:1.7rem;color:#d8dbe6;font-size:2.15rem;}}
    .progress-track{{display:inline-block;width:120px;height:10px;background:#e9ecf4;border-radius:999px;margin-left:.6rem;vertical-align:middle;overflow:hidden;}}
    .progress-fill{{height:100%;background:var(--accent2);border-radius:999px;}}
    .panel{{background:#fff;border:1px solid #e0e4ee;border-radius:12px;box-shadow:var(--shadow);margin-top:1.35rem;overflow:hidden;}}
    .panel-header{{min-height:62px;display:flex;align-items:center;padding:0 1.35rem;border-bottom:1px solid #e2e8f0;color:var(--primary);font-weight:900;font-size:1.08rem;background:#fbfcff;}}
    .panel-body{{padding:1.25rem;}}
    .login-card{{max-width:490px;margin:5vh auto 0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:28px;padding:34px;box-shadow:0 24px 70px rgba(15,23,42,.12)}}
    .login-title{{font-size:2rem;font-weight:850;color:var(--primary);}} .login-subtitle{{color:#64748b;margin-bottom:18px;}}
    .stButton>button,.stDownloadButton>button{{border-radius:11px!important;font-weight:750!important;}}
    div[data-testid="stAlert"]{{display:none;}}
    </style>
    """, unsafe_allow_html=True)


def now_iso(): return datetime.now().isoformat(timespec="seconds")

def hash_password(password):
    salt=os.urandom(16); key=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,120000); return base64.b64encode(salt+key).decode()

def check_password(password, stored):
    try:
        data=base64.b64decode(stored.encode()); salt=data[:16]; old=data[16:]; new=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,120000); return old==new
    except Exception: return False

def conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def read_df(q, params=()):
    c=conn()
    try: return pd.read_sql_query(q,c,params=params)
    finally: c.close()

def exec_sql(q, params=()):
    c=conn(); cur=c.cursor(); cur.execute(q,params); c.commit(); lid=cur.lastrowid; c.close(); return lid


def init_db():
    UPLOAD_DIR.mkdir(exist_ok=True); c=conn(); cur=c.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY AUTOINCREMENT,usuario TEXT UNIQUE NOT NULL,nombre TEXT NOT NULL,password_hash TEXT NOT NULL,rol TEXT NOT NULL CHECK(rol IN ('usuario','desarrollador')),activo INTEGER NOT NULL DEFAULT 1,ultimo_login TEXT,creado_en TEXT NOT NULL,actualizado_en TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS catalogos(id INTEGER PRIMARY KEY AUTOINCREMENT,categoria TEXT NOT NULL,valor TEXT NOT NULL,activo INTEGER NOT NULL DEFAULT 1,UNIQUE(categoria,valor))")
    cur.execute("CREATE TABLE IF NOT EXISTS productos(id INTEGER PRIMARY KEY AUTOINCREMENT,item TEXT UNIQUE NOT NULL,descripcion TEXT NOT NULL,cliente TEXT,familia TEXT,activo INTEGER NOT NULL DEFAULT 1)")
    cur.execute("CREATE TABLE IF NOT EXISTS defectos(id INTEGER PRIMARY KEY AUTOINCREMENT,codigo TEXT UNIQUE NOT NULL,defecto TEXT NOT NULL,tipo_defecto TEXT,clasificacion TEXT,observaciones TEXT,activo INTEGER NOT NULL DEFAULT 1)")
    cur.execute("""CREATE TABLE IF NOT EXISTS pnc_registros(id INTEGER PRIMARY KEY AUTOINCREMENT,folio TEXT UNIQUE NOT NULL,fecha_apertura TEXT NOT NULL,linea_sector TEXT,nave TEXT,item TEXT,descripcion_producto TEXT,cliente TEXT,familia TEXT,lote TEXT,etapa TEXT,codigo_defecto TEXT,defecto TEXT,tipo_defecto TEXT,clasificacion TEXT,turno TEXT,supervisor TEXT,analista TEXT,responsable_detecta TEXT,descripcion_defecto TEXT,acciones_inmediatas TEXT,disposicion TEXT,cantidad_observada REAL DEFAULT 0,cantidad_reproceso REAL DEFAULT 0,cantidad_decomiso REAL DEFAULT 0,cantidad_aprobado_segunda REAL DEFAULT 0,cantidad_total_pnc REAL DEFAULT 0,status TEXT DEFAULT 'ABIERTO',fecha_final_tratamiento TEXT,dias REAL DEFAULT 0,horas REAL DEFAULT 0,personas INTEGER DEFAULT 0,observaciones TEXT,sector_me TEXT,equipo_me TEXT,material_hallado TEXT,numero_particulas TEXT,investigacion_origen TEXT,creado_por TEXT NOT NULL,creado_en TEXT NOT NULL)""")
    cur.execute("CREATE TABLE IF NOT EXISTS adjuntos(id INTEGER PRIMARY KEY AUTOINCREMENT,registro_id INTEGER NOT NULL,folio TEXT NOT NULL,nombre_original TEXT NOT NULL,ruta_archivo TEXT NOT NULL,tipo_archivo TEXT,tamano_bytes INTEGER,subido_por TEXT NOT NULL,subido_en TEXT NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT,usuario TEXT NOT NULL,accion TEXT NOT NULL,detalle TEXT NOT NULL,fecha_hora TEXT NOT NULL)")
    seed_catalogs(cur); seed_products(cur); seed_defects(cur); c.commit(); c.close()

def seed_catalogs(cur):
    defaults={"etapa":["PT","SE","MP"],"status":["ABIERTO","CERRADO"],"turno":["A","B","C","MIXTO"],"responsable_detecta":["AUTONOMO","CALIDAD"],"tipo_defecto":["Funcional","Contaminación"],"clasificacion":["Inocuidad","Calidad","Salubridad","Legalidad"],"disposicion":["Reproceso","Retrabajo","Decomiso","Inspección","Aprobado en segunda instancia","Otro"],"linea_sector":["BON O BON","OBLEAS","MOLDEO","CARAMELO","BUTTER","DUVALIN","POOSH","TETRA","STICK","CONFORMADO HUEVITO","CONFITADO"],"nave":["1","2","3","FABRIMA","DELTA","J&R","CIMIS","MOLINOS","CONCAS","EUROMEC","ENVAFLEX","MBP","GD´S","PFM","MULTIFORMATO","HD","C2","C1"],"supervisor":["AGUSTIN ABEL","JAVIER PACHECO","MARTIN TRUJILLO","SANDRA GAMBOA","ARNOL GOMEZ"],"analista":["ELIZABETH ALMAZAN","ALEJANDRO BECERRIL","ALFREDO CHAVEZ","JENNIFER CARRILLO","ARNOL GOMEZ"]}
    for cat, vals in defaults.items():
        for v in vals: cur.execute("INSERT OR IGNORE INTO catalogos(categoria,valor,activo) VALUES(?,?,1)",(cat,v))

def seed_products(cur):
    rows=[("90178000272","BON O BON LECHE 20x15x15G","02.- Unidal","L04 - BOB"),("90178001016","OBLEA BON O BON 12X8X27G","02.- Unidal","L07- Oblea"),("90178001783","COBERTURA CORONA","01.- Mondelēz","L17 - Coberturas"),("90178160006","PALETA DUVAL.FRESA GNEL.400X18","01.- Mondelēz","L11 - Paletas"),("90178000740","POOSH FRESA 18X40X4G","02.- Unidal","L02 - Chicle Relleno")]
    for r in rows: cur.execute("INSERT OR IGNORE INTO productos(item,descripcion,cliente,familia,activo) VALUES(?,?,?,?,1)",r)

def seed_defects(cur):
    rows=[("12","ANÁLISIS PARA PATOGENOS","Contaminación","Salubridad",""),("44","PROD_OLOR_NO_CARACTERISTICO","Funcional","Calidad",""),("58","PROD_SABOR/OLOR_AMARGO","Funcional","Calidad",""),("63","PROD_SABOR/OLOR_QUEMADO","Funcional","Calidad",""),("67","PROD_SABOR_ACIDO","Funcional","Calidad",""),("86","OBJ-EXTR_METALES","Contaminación","Inocuidad",""),("99","ENV_EMPAQUE_ROTO","Funcional","Calidad",""),("122","ALERGENOS_PRESENCIA/ROTULADO ERRONEO","Contaminación","Inocuidad","")]
    for r in rows: cur.execute("INSERT OR IGNORE INTO defectos(codigo,defecto,tipo_defecto,clasificacion,observaciones,activo) VALUES(?,?,?,?,?,1)",r)

def audit(u,a,d): exec_sql("INSERT INTO auditoria(usuario,accion,detalle,fecha_hora) VALUES(?,?,?,?)",(u,a,d,now_iso()))

def reset_admin():
    pw=hash_password(ADMIN_PASS); c=conn(); cur=c.cursor(); cur.execute("SELECT id FROM usuarios WHERE usuario=?",(ADMIN_USER,)); exists=cur.fetchone()
    if exists: cur.execute("UPDATE usuarios SET nombre=?,password_hash=?,rol=?,activo=1,actualizado_en=? WHERE usuario=?",("Administrador del sistema",pw,"desarrollador",now_iso(),ADMIN_USER))
    else: cur.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol,activo,creado_en) VALUES(?,?,?,?,1,?)",(ADMIN_USER,"Administrador del sistema",pw,"desarrollador",now_iso()))
    c.commit(); c.close()

def auth_user(u,p):
    c=conn(); cur=c.cursor(); cur.execute("SELECT usuario,nombre,password_hash,rol,activo FROM usuarios WHERE usuario=?",(u,)); row=cur.fetchone()
    if not row: c.close(); return None
    user,nombre,pw,rol,activo=row
    if activo!=1 or not check_password(p,pw): c.close(); return None
    cur.execute("UPDATE usuarios SET ultimo_login=? WHERE usuario=?",(now_iso(),user)); c.commit(); c.close(); return {"usuario":user,"nombre":nombre,"rol":rol}

def require_login():
    if "auth" not in st.session_state: st.session_state.auth=None
    if "last_activity" not in st.session_state: st.session_state.last_activity=datetime.now()
    if st.session_state.auth:
        if datetime.now()-st.session_state.last_activity>timedelta(minutes=SESSION_TIMEOUT_MINUTES): st.session_state.auth=None; st.stop()
        st.session_state.last_activity=datetime.now(); return st.session_state.auth
    st.markdown('<div class="login-card"><div class="login-title">Sistema de Calidad</div><div class="login-subtitle">Acceso privado para registros PNC y ME.</div>',unsafe_allow_html=True)
    with st.form("login"):
        u=st.text_input("Usuario"); p=st.text_input("Contraseña",type="password"); ok=st.form_submit_button("Ingresar")
    st.markdown('</div>',unsafe_allow_html=True)
    if ok:
        au=auth_user(u.strip(),p.strip())
        if au: st.session_state.auth=au; audit(au["usuario"],"LOGIN","Ingreso correcto"); st.rerun()
        else: st.error("Usuario o contraseña incorrectos, o usuario inactivo.")
    st.stop()

def is_dev(): return st.session_state.auth and st.session_state.auth["rol"]=="desarrollador"
def cat(c):
    df=read_df("SELECT valor FROM catalogos WHERE categoria=? AND activo=1 ORDER BY valor",(c,)); return df["valor"].tolist() if not df.empty else []
def folio():
    pref=f"PNC-{datetime.now().year}-"; df=read_df("SELECT folio FROM pnc_registros WHERE folio LIKE ? ORDER BY folio DESC LIMIT 1",(f"{pref}%",)); n=0
    if not df.empty:
        try: n=int(str(df.iloc[0]["folio"]).split("-")[-1])
        except Exception: n=0
    return f"{pref}{n+1:05d}"
def save_files(files,rid,f,u):
    folder=UPLOAD_DIR/f; folder.mkdir(parents=True,exist_ok=True)
    for file in files or []:
        path=folder/f"{uuid4().hex}{Path(file.name).suffix.lower()}"; data=file.getbuffer(); path.write_bytes(data); exec_sql("INSERT INTO adjuntos(registro_id,folio,nombre_original,ruta_archivo,tipo_archivo,tamano_bytes,subido_por,subido_en) VALUES(?,?,?,?,?,?,?,?)",(rid,f,file.name,str(path),file.type,len(data),u,now_iso()))

def import_excel(uploaded):
    sheets=pd.read_excel(uploaded,sheet_name=None,header=None,dtype=str,engine="openpyxl"); ip=0; idf=0; c=conn(); cur=c.cursor()
    for name,df in sheets.items():
        if "item" in str(name).lower():
            for _,r in df.iterrows():
                v=["" if pd.isna(x) else str(x).strip() for x in r.tolist()]
                if len(v)>=4 and v[0].replace(".0","").isdigit() and v[1]: cur.execute("INSERT OR REPLACE INTO productos(item,descripcion,cliente,familia,activo) VALUES(?,?,?,?,1)",(v[0].replace(".0",""),v[1],v[2],v[3])); ip+=1
    for name,df in sheets.items():
        ln=str(name).lower()
        if "codigo" in ln or "código" in ln:
            for _,r in df.iterrows():
                v=["" if pd.isna(x) else str(x).strip() for x in r.tolist()]
                if len(v)>=5 and v[0].replace(".0","").isdigit() and v[1]: cur.execute("INSERT OR REPLACE INTO defectos(codigo,defecto,tipo_defecto,clasificacion,observaciones,activo) VALUES(?,?,?,?,?,1)",(v[0].replace(".0",""),v[1],v[2],v[3],v[5] if len(v)>5 else "")); idf+=1
    c.commit(); c.close(); return ip,idf

def topbar(a):
    initials="".join([p[0] for p in str(a.get("nombre","AC")).split()[:2]]).upper() or "AC"
    st.markdown(f'<div class="topbar"><div class="topbar-user"><span class="topbar-bell">🔔</span><span>{a.get("nombre","USUARIO").upper()}</span><span class="avatar">{initials}</span></div></div>',unsafe_allow_html=True)
def brand(compact):
    logo="" if compact else "CALIDAD MD"; detail="" if compact else '<div class="side-section">SISTEMA PRIVADO</div><div class="side-card">PNC y Materia Extraña</div><div class="side-section">MENÚ PRINCIPAL</div>'
    st.markdown(f'<div class="logo"><span>◆</span><span class="logo-text">{logo}</span></div><hr>{detail}',unsafe_allow_html=True)

def dashboard_filters(df):
    with st.expander("Filtros dinámicos de indicadores",expanded=False):
        c1,c2,c3,c4=st.columns(4); stt=c1.multiselect("Status",sorted(df["status"].dropna().unique()) if not df.empty else []); lin=c2.multiselect("Línea/Sector",sorted(df["linea_sector"].dropna().unique()) if not df.empty else []); cla=c3.multiselect("Clasificación",sorted(df["clasificacion"].dropna().unique()) if not df.empty else []); enf=c4.radio("Enfoque",["Todos","Abiertos","Cerrados","Con ME"])
    data=df.copy()
    if stt: data=data[data["status"].isin(stt)]
    if lin: data=data[data["linea_sector"].isin(lin)]
    if cla: data=data[data["clasificacion"].isin(cla)]
    if enf=="Abiertos": data=data[data["status"]=="ABIERTO"]
    elif enf=="Cerrados": data=data[data["status"]=="CERRADO"]
    elif enf=="Con ME": data=data[data["material_hallado"].fillna("").astype(str).str.len()>0]
    return data,enf

def page_inicio():
    df=read_df("SELECT * FROM pnc_registros")
    if df.empty: df=pd.DataFrame(columns=["fecha_apertura","status","linea_sector","clasificacion","material_hallado","cantidad_total_pnc"])
    df["fecha_apertura"]=pd.to_datetime(df["fecha_apertura"],errors="coerce"); data,enf=dashboard_filters(df)
    total=len(data); abiertos=int((data["status"]=="ABIERTO").sum()) if not data.empty else 0; cerrados=int((data["status"]=="CERRADO").sum()) if not data.empty else 0; con_me=int(data["material_hallado"].fillna("").astype(str).str.len().gt(0).sum()) if not data.empty else 0; kilos=float(data["cantidad_total_pnc"].fillna(0).sum()) if not data.empty else 0; avance=int((cerrados/total)*100) if total else 0
    st.markdown('<div class="dash-title">Panel Calidad Mundo Dulce</div>',unsafe_allow_html=True); st.markdown(f'<div class="subtle">Indicadores actualizados con filtro: <b>{enf}</b></div>',unsafe_allow_html=True)
    k1,k2,k3,k4=st.columns(4)
    with k1: st.markdown(f'<div class="kpi" style="--c:#12a594"><div class="kpi-label">PNC abiertos</div><div class="kpi-value">{abiertos}</div><div class="kpi-foot">Registros pendientes</div><div class="kpi-icon">●</div></div>',unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="kpi" style="--c:#6d5dfc"><div class="kpi-label">Avance de cierre</div><div class="kpi-value">{avance}% <span class="progress-track"><span class="progress-fill" style="width:{avance}%"></span></span></div><div class="kpi-foot">Cerrados vs total</div><div class="kpi-icon">▣</div></div>',unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="kpi" style="--c:#f59e0b"><div class="kpi-label">Registros filtrados</div><div class="kpi-value">{total}</div><div class="kpi-foot">Coincidencias</div><div class="kpi-icon">▥</div></div>',unsafe_allow_html=True)
    with k4: st.markdown(f'<div class="kpi" style="--c:#ef476f"><div class="kpi-label">Kg PNC / ME</div><div class="kpi-value">{kilos:,.1f}</div><div class="kpi-foot">Hallazgos ME: {con_me}</div><div class="kpi-icon">☑</div></div>',unsafe_allow_html=True)
    left,right=st.columns([2,1])
    with left:
        st.markdown('<div class="panel"><div class="panel-header">Tendencia mensual dinámica</div><div class="panel-body">',unsafe_allow_html=True)
        if not data.empty:
            t=data.dropna(subset=["fecha_apertura"]).copy(); t["Mes"]=t["fecha_apertura"].dt.strftime("%Y-%m"); st.bar_chart(t.groupby(["Mes","status"]).size().unstack(fill_value=0),use_container_width=True)
        else: st.info("No hay registros para graficar con los filtros actuales.")
        st.markdown('</div></div>',unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel"><div class="panel-header">Distribución por clasificación</div><div class="panel-body">',unsafe_allow_html=True)
        if not data.empty: st.dataframe(data["clasificacion"].fillna("Sin clasificación").value_counts().rename_axis("Clasificación").reset_index(name="Registros"),use_container_width=True,hide_index=True)
        else: st.info("No hay datos para mostrar.")
        st.markdown('</div></div>',unsafe_allow_html=True)

def page_registro():
    st.title("Nuevo registro PNC / ME"); productos=read_df("SELECT item,descripcion,cliente,familia FROM productos WHERE activo=1 ORDER BY descripcion"); defectos=read_df("SELECT codigo,defecto,tipo_defecto,clasificacion FROM defectos WHERE activo=1 ORDER BY CAST(codigo AS INTEGER)")
    with st.form("registro_pnc"):
        c1,c2,c3=st.columns(3)
        with c1: fecha=date.today(); fecha_apertura=st.date_input("Fecha de apertura",value=fecha); linea=st.selectbox("Línea / Sector",cat("linea_sector")); nave=st.selectbox("Nave",cat("nave"))
        with c2:
            if not productos.empty:
                opt=st.selectbox("ITEM / Producto",[f"{r.item} | {r.descripcion}" for r in productos.itertuples()]); item=opt.split("|")[0].strip(); p=productos[productos["item"]==item].iloc[0]; desc=str(p["descripcion"]); cliente=str(p["cliente"]); familia=str(p["familia"]); st.text_input("Descripción",value=desc,disabled=True); st.text_input("Cliente",value=cliente,disabled=True); st.text_input("Familia",value=familia,disabled=True)
            else: item=st.text_input("ITEM"); desc=st.text_input("Descripción"); cliente=st.text_input("Cliente"); familia=st.text_input("Familia")
            lote=st.text_area("Lote",height=82)
        with c3: etapa=st.selectbox("Etapa",cat("etapa")); st.text_input("Semana",value=str(fecha_apertura.isocalendar().week),disabled=True); turno=st.selectbox("Turno",cat("turno"))
        c4,c5=st.columns(2)
        with c4:
            if not defectos.empty:
                opt=st.selectbox("Código / Defecto",[f"{r.codigo} | {r.defecto}" for r in defectos.itertuples()]); cod=opt.split("|")[0].strip(); d=defectos[defectos["codigo"]==cod].iloc[0]; defecto=str(d["defecto"]); tipo=str(d["tipo_defecto"]); clas=str(d["clasificacion"]); st.text_input("Tipo",value=tipo,disabled=True); st.text_input("Clasificación",value=clas,disabled=True)
            else: cod=st.text_input("Código"); defecto=st.text_input("Defecto"); tipo=st.selectbox("Tipo",cat("tipo_defecto")); clas=st.selectbox("Clasificación",cat("clasificacion"))
        with c5: descripcion=st.text_area("Descripción del defecto",height=110); acciones=st.text_area("Acciones inmediatas",value="Se detiene línea, se segrega e identifica el producto.",height=110)
        c6,c7,c8=st.columns(3); supervisor=c6.selectbox("Supervisor",cat("supervisor")); analista=c6.selectbox("Analista",cat("analista")); resp=c7.selectbox("Responsable detecta",cat("responsable_detecta")); disposicion=c7.selectbox("Disposición",cat("disposicion")); status=c8.selectbox("Status",cat("status")); fecha_final=c8.date_input("Fecha final",value=date.today()) if status=="CERRADO" else None
        q1,q2,q3,q4,q5=st.columns(5); obs=q1.number_input("Observada kg",min_value=0.0,step=0.1); rep=q2.number_input("Reproceso kg",min_value=0.0,step=0.1); dec=q3.number_input("Decomiso kg",min_value=0.0,step=0.1); apr=q4.number_input("Aprobado 2da kg",min_value=0.0,step=0.1); total=q5.number_input("Total PNC kg",min_value=0.0,step=0.1,value=float(rep+dec+apr))
        t1,t2,t3=st.columns(3); dias=t1.number_input("Días",min_value=0.0,step=0.5); horas=t2.number_input("Horas",min_value=0.0,step=0.5); personas=t3.number_input("N° personas",min_value=0,step=1); notas=st.text_area("Observaciones")
        m1,m2=st.columns(2); sector=m1.text_input("Sector hallazgo"); equipo=m2.text_input("Equipo hallazgo"); material=st.text_area("Material hallado"); particulas=st.text_input("No. partículas"); investigacion=st.text_area("Investigación origen"); evidencias=st.file_uploader("Adjuntar evidencia",type=["pdf","png","jpg","jpeg","xlsx","csv","txt","docx"],accept_multiple_files=True); guardar=st.form_submit_button("Guardar registro")
    if guardar:
        if not descripcion.strip(): st.warning("Agrega la descripción del defecto antes de guardar."); return
        f=folio(); rid=exec_sql("""INSERT INTO pnc_registros(folio,fecha_apertura,linea_sector,nave,item,descripcion_producto,cliente,familia,lote,etapa,codigo_defecto,defecto,tipo_defecto,clasificacion,turno,supervisor,analista,responsable_detecta,descripcion_defecto,acciones_inmediatas,disposicion,cantidad_observada,cantidad_reproceso,cantidad_decomiso,cantidad_aprobado_segunda,cantidad_total_pnc,status,fecha_final_tratamiento,dias,horas,personas,observaciones,sector_me,equipo_me,material_hallado,numero_particulas,investigacion_origen,creado_por,creado_en) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(f,fecha_apertura.isoformat(),linea,nave,item,desc,cliente,familia,lote,etapa,cod,defecto,tipo,clas,turno,supervisor,analista,resp,descripcion,acciones,disposicion,obs,rep,dec,apr,total,status,fecha_final.isoformat() if fecha_final else None,dias,horas,int(personas),notas,sector,equipo,material,particulas,investigacion,st.session_state.auth["usuario"],now_iso()))
        save_files(evidencias,rid,f,st.session_state.auth["usuario"]); audit(st.session_state.auth["usuario"],"CREAR_PNC",f); st.success(f"Registro guardado correctamente: {f}")

def page_consulta():
    st.title("Consulta, seguimiento y descarga"); df=read_df("SELECT * FROM pnc_registros ORDER BY id DESC")
    if df.empty: st.info("No hay registros capturados."); return
    c1,c2,c3=st.columns(3); sf=c1.multiselect("Status",sorted(df["status"].dropna().unique())); lf=c2.multiselect("Línea/Sector",sorted(df["linea_sector"].dropna().unique())); search=c3.text_input("Buscar")
    filtered=df.copy()
    if sf: filtered=filtered[filtered["status"].isin(sf)]
    if lf: filtered=filtered[filtered["linea_sector"].isin(lf)]
    if search.strip():
        q=search.lower().strip(); mask=pd.Series(False,index=filtered.index)
        for col in ["folio","item","descripcion_producto","lote","defecto","descripcion_defecto"]: mask=mask|filtered[col].fillna("").astype(str).str.lower().str.contains(q,na=False)
        filtered=filtered[mask]
    st.dataframe(filtered,use_container_width=True,hide_index=True); st.download_button("Descargar registros CSV",filtered.to_csv(index=False).encode("utf-8-sig"),f"pnc_me_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv","text/csv")

def page_catalogos():
    if not is_dev(): st.error("No tienes permisos."); return
    st.title("Catálogos y carga desde Excel"); up=st.file_uploader("Cargar Excel de catálogos",type=["xlsx"])
    if up and st.button("Importar catálogos desde Excel"):
        try: p,d=import_excel(up); audit(st.session_state.auth["usuario"],"IMPORTAR_EXCEL",f"Productos={p}, Defectos={d}"); st.success(f"Importación finalizada. Productos: {p}. Defectos: {d}.")
        except Exception as e: st.error(f"No se pudo importar el archivo: {e}")
    tab1,tab2,tab3=st.tabs(["Productos","Defectos","Listas"])
    with tab1: st.dataframe(read_df("SELECT * FROM productos ORDER BY descripcion"),use_container_width=True,hide_index=True)
    with tab2: st.dataframe(read_df("SELECT * FROM defectos ORDER BY CAST(codigo AS INTEGER)"),use_container_width=True,hide_index=True)
    with tab3: st.dataframe(read_df("SELECT * FROM catalogos ORDER BY categoria,valor"),use_container_width=True,hide_index=True)

def page_usuarios():
    if not is_dev(): st.error("No tienes permisos."); return
    st.title("Usuarios")
    with st.form("usr"):
        c1,c2=st.columns(2); u=c1.text_input("Usuario"); n=c1.text_input("Nombre"); p=c2.text_input("Contraseña temporal",type="password"); r=c2.selectbox("Rol",["usuario","desarrollador"]); ok=st.form_submit_button("Crear usuario")
    if ok:
        if not u.strip() or not n.strip() or len(p)<8: st.warning("Completa usuario, nombre y contraseña mínima de 8 caracteres.")
        else:
            try: exec_sql("INSERT INTO usuarios(usuario,nombre,password_hash,rol,activo,creado_en) VALUES(?,?,?,?,1,?)",(u.strip(),n.strip(),hash_password(p),r,now_iso())); st.success("Usuario creado.")
            except sqlite3.IntegrityError: st.error("Ese usuario ya existe.")
    st.dataframe(read_df("SELECT id,usuario,nombre,rol,activo,ultimo_login,creado_en FROM usuarios ORDER BY id"),use_container_width=True,hide_index=True)

def page_auditoria():
    if not is_dev(): st.error("No tienes permisos."); return
    st.title("Auditoría"); df=read_df("SELECT * FROM auditoria ORDER BY id DESC LIMIT 1000"); st.dataframe(df,use_container_width=True,hide_index=True)
    if not df.empty: st.download_button("Descargar auditoría",df.to_csv(index=False).encode("utf-8-sig"),"auditoria.csv","text/csv")

def main():
    init_db();
    if FORCE_RESET_ADMIN: reset_admin()
    user=require_login()
    with st.sidebar:
        compact=st.toggle("Acortar menú",value=False)
    css(compact); topbar(user)
    options=[("Inicio","🏠 Inicio"),("Nuevo registro","📝 Nuevo registro"),("Consulta y descarga","📊 Consulta y descarga")]
    if is_dev(): options += [("Catálogos","🧩 Catálogos"),("Usuarios","👤 Usuarios"),("Auditoría","🧾 Auditoría")]
    labels=[o[1].split()[0] if compact else o[1] for o in options]; mapping={o[1].split()[0] if compact else o[1]:o[0] for o in options}
    with st.sidebar:
        brand(compact)
        title="☰" if compact else "☰ Menú principal"
        with st.expander(title,expanded=True): selected=st.radio("Selecciona módulo",labels,label_visibility="collapsed",key="vertical_nav")
        st.divider()
        if st.button("Salir" if compact else "Cerrar sesión"):
            audit(user["usuario"],"LOGOUT","Cierre de sesión"); st.session_state.auth=None; st.rerun()
    page=mapping[selected]
    if page=="Inicio": page_inicio()
    elif page=="Nuevo registro": page_registro()
    elif page=="Consulta y descarga": page_consulta()
    elif page=="Catálogos": page_catalogos()
    elif page=="Usuarios": page_usuarios()
    elif page=="Auditoría": page_auditoria()

if __name__=="__main__": main()
