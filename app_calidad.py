import streamlit as st
import pandas as pd
import sqlite3, hashlib, os, base64
from datetime import datetime, date
from pathlib import Path
from uuid import uuid4

APP_NAME = "Calidad MD | PNC y ME"
DB_PATH = "calidad.db"
UPLOAD_DIR = Path("evidencias_calidad")
FORCE_RESET_ADMIN = True
ADMIN_USER = "admin"
ADMIN_PASS = "Cambiar123!"

st.set_page_config(page_title=APP_NAME, page_icon="✅", layout="wide", initial_sidebar_state="expanded")


def now_iso(): return datetime.now().isoformat(timespec="seconds")

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return base64.b64encode(salt + key).decode("utf-8")

def check_password(password: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored.encode("utf-8"))
        salt, old_key = raw[:16], raw[16:]
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
        return old_key == new_key
    except Exception:
        return False

def conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def read_df(q, params=()):
    c = conn()
    try: return pd.read_sql_query(q, c, params=params)
    finally: c.close()

def exec_sql(q, params=()):
    c = conn(); cur = c.cursor(); cur.execute(q, params); c.commit(); lid = cur.lastrowid; c.close(); return lid


def init_db():
    UPLOAD_DIR.mkdir(exist_ok=True)
    c = conn(); cur = c.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE, nombre TEXT, password_hash TEXT, rol TEXT, activo INTEGER DEFAULT 1, creado_en TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS catalogos(id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT, valor TEXT, activo INTEGER DEFAULT 1, UNIQUE(categoria,valor))")
    cur.execute("CREATE TABLE IF NOT EXISTS productos(id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT UNIQUE, descripcion TEXT, cliente TEXT, familia TEXT, activo INTEGER DEFAULT 1)")
    cur.execute("CREATE TABLE IF NOT EXISTS defectos(id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE, defecto TEXT, tipo_defecto TEXT, clasificacion TEXT, activo INTEGER DEFAULT 1)")
    cur.execute("""CREATE TABLE IF NOT EXISTS pnc_registros(
        id INTEGER PRIMARY KEY AUTOINCREMENT, folio TEXT UNIQUE, fecha_apertura TEXT, linea_sector TEXT, nave TEXT,
        item TEXT, descripcion_producto TEXT, cliente TEXT, familia TEXT, lote TEXT, etapa TEXT, codigo_defecto TEXT,
        defecto TEXT, tipo_defecto TEXT, clasificacion TEXT, turno TEXT, supervisor TEXT, analista TEXT,
        responsable_detecta TEXT, descripcion_defecto TEXT, acciones_inmediatas TEXT, disposicion TEXT,
        cantidad_observada REAL DEFAULT 0, cantidad_reproceso REAL DEFAULT 0, cantidad_decomiso REAL DEFAULT 0,
        cantidad_aprobado_segunda REAL DEFAULT 0, cantidad_total_pnc REAL DEFAULT 0, status TEXT DEFAULT 'ABIERTO',
        fecha_final_tratamiento TEXT, observaciones TEXT, material_hallado TEXT, creado_por TEXT, creado_en TEXT
    )""")
    cur.execute("CREATE TABLE IF NOT EXISTS adjuntos(id INTEGER PRIMARY KEY AUTOINCREMENT, registro_id INTEGER, folio TEXT, nombre_original TEXT, ruta_archivo TEXT, tipo_archivo TEXT, subido_por TEXT, subido_en TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, accion TEXT, detalle TEXT, fecha_hora TEXT)")
    seed(cur); c.commit(); c.close()

def seed(cur):
    catalogs = {
        "linea_sector":["BON O BON","OBLEAS","MOLDEO","CARAMELO","BUTTER","DUVALIN","POOSH"],
        "nave":["1","2","3","FABRIMA","DELTA","J&R","CIMIS"],
        "etapa":["PT","SE","MP"], "turno":["A","B","C","MIXTO"], "status":["ABIERTO","CERRADO"],
        "responsable_detecta":["AUTONOMO","CALIDAD"], "disposicion":["Reproceso","Retrabajo","Decomiso","Inspección","Aprobado en segunda instancia","Otro"],
        "supervisor":["AGUSTIN ABEL","JAVIER PACHECO","MARTIN TRUJILLO","ARNOL GOMEZ"],
        "analista":["ELIZABETH ALMAZAN","ALEJANDRO BECERRIL","ARNOL GOMEZ"]
    }
    for cat, values in catalogs.items():
        for v in values: cur.execute("INSERT OR IGNORE INTO catalogos(categoria,valor,activo) VALUES(?,?,1)",(cat,v))
    for p in [("90178000272","BON O BON LECHE 20x15x15G","02.- Unidal","L04 - BOB"),("90178001016","OBLEA BON O BON 12X8X27G","02.- Unidal","L07 - Oblea")]:
        cur.execute("INSERT OR IGNORE INTO productos(item,descripcion,cliente,familia,activo) VALUES(?,?,?,?,1)", p)
    for d in [("12","ANÁLISIS PARA PATOGENOS","Contaminación","Salubridad"),("86","OBJ-EXTR_METALES","Contaminación","Inocuidad"),("99","ENV_EMPAQUE_ROTO","Funcional","Calidad")]:
        cur.execute("INSERT OR IGNORE INTO defectos(codigo,defecto,tipo_defecto,clasificacion,activo) VALUES(?,?,?,?,1)", d)

def reset_admin():
    pw = hash_password(ADMIN_PASS); c = conn(); cur = c.cursor(); cur.execute("SELECT id FROM usuarios WHERE usuario=?",(ADMIN_USER,)); exists = cur.fetchone()
    if exists: cur.execute("UPDATE usuarios SET nombre=?, password_hash=?, rol=?, activo=1 WHERE usuario=?",("Administrador del sistema",pw,"desarrollador",ADMIN_USER))
    else: cur.execute("INSERT INTO usuarios(usuario,nombre,password_hash,rol,activo,creado_en) VALUES(?,?,?,?,1,?)",(ADMIN_USER,"Administrador del sistema",pw,"desarrollador",now_iso()))
    c.commit(); c.close()

def auth_user(u,p):
    c=conn(); cur=c.cursor(); cur.execute("SELECT usuario,nombre,password_hash,rol,activo FROM usuarios WHERE usuario=?",(u,)); row=cur.fetchone(); c.close()
    if not row: return None
    user,nombre,pw,rol,activo=row
    return {"usuario":user,"nombre":nombre,"rol":rol} if activo==1 and check_password(p,pw) else None

def audit(u,a,d): exec_sql("INSERT INTO auditoria(usuario,accion,detalle,fecha_hora) VALUES(?,?,?,?)",(u,a,d,now_iso()))
def cat(c):
    df=read_df("SELECT valor FROM catalogos WHERE categoria=? AND activo=1 ORDER BY valor",(c,)); return df["valor"].tolist() if not df.empty else []
def is_dev(): return st.session_state.get("auth",{}).get("rol")=="desarrollador"
def new_folio():
    pref=f"PNC-{datetime.now().year}-"; df=read_df("SELECT folio FROM pnc_registros WHERE folio LIKE ? ORDER BY folio DESC LIMIT 1",(f"{pref}%",)); n=0
    if not df.empty:
        try: n=int(str(df.iloc[0]["folio"]).split("-")[-1])
        except Exception: n=0
    return f"{pref}{n+1:05d}"


def styles(compact=False):
    w = "94px" if compact else "292px"
    display = "none" if compact else "inline"
    st.markdown(f"""
    <style>
    :root {{--primary:#0b3440;--accent:#00a884;--violet:#5850ec;--bg:#f4f6f9;--text:#253044;}}
    .stApp{{background:var(--bg);}} header[data-testid="stHeader"]{{display:none;}}
    .main .block-container{{padding-top:0;padding-left:2rem;padding-right:2rem;max-width:100%;}}
    section[data-testid="stSidebar"]{{background:var(--primary);width:{w}!important;min-width:{w}!important;}}
    section[data-testid="stSidebar"]>div{{width:{w}!important;min-width:{w}!important;}}
    section[data-testid="stSidebar"] *{{color:#fff!important;}}
    .logo{{font-size:1.45rem;font-weight:900;margin:1rem 0 1rem 0;display:flex;gap:.65rem;align-items:center;}}
    .logo-text{{display:{display};}}
    .side-box{{display:{display};background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.18);border-radius:14px;padding:.9rem;margin-bottom:1rem;}}
    .menu-title{{display:block;color:#ffffff;font-weight:900;font-size:.8rem;letter-spacing:.06rem;margin:.9rem 0 .35rem 0;}}
    section[data-testid="stSidebar"] div[data-baseweb="select"]>div{{background:rgba(255,255,255,.13)!important;border:1px solid rgba(255,255,255,.30)!important;border-radius:12px!important;}}
    section[data-testid="stSidebar"] label{{font-weight:900!important;}}
    .topbar{{height:78px;background:#fff;display:flex;justify-content:flex-end;align-items:center;margin-left:-2rem;margin-right:-2rem;padding:0 2rem;box-shadow:0 1px 0 rgba(15,23,42,.08);}}
    .avatar{{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#ccfff4,#d9dbff);display:flex;align-items:center;justify-content:center;color:#0b3440;font-weight:900;}}
    .topbar-user{{display:flex;gap:1rem;align-items:center;color:#526078;font-weight:700;}}
    .page-title{{color:#243042;font-size:2.15rem;font-weight:900;margin:1.5rem 0 .15rem;}}
    .page-subtitle{{color:#566176;font-size:1rem;margin-bottom:1.1rem;}}
    .kpi{{background:#fff;border-radius:14px;padding:1.4rem;min-height:128px;border:1px solid #e3e8ef;box-shadow:0 10px 28px rgba(15,23,42,.08);position:relative;overflow:hidden;}}
    .kpi:before{{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--c);}}
    .kpi-label{{color:var(--c);font-size:.78rem;font-weight:900;text-transform:uppercase;}}
    .kpi-value{{color:#394356;font-size:1.65rem;font-weight:900;margin-top:.35rem;}}
    .kpi-foot{{color:#7c8798;font-size:.78rem;margin-top:.35rem;}}
    .panel{{background:#fff;border:1px solid #e0e6ee;border-radius:12px;box-shadow:0 10px 28px rgba(15,23,42,.08);margin-top:1.25rem;}}
    .panel-header{{padding:1rem 1.25rem;border-bottom:1px solid #e2e8f0;color:#0b3440;font-weight:900;}}
    .panel-body{{padding:1.25rem;}}
    .login-card{{max-width:480px;margin:6vh auto;background:#fff;border-radius:24px;padding:32px;box-shadow:0 20px 60px rgba(15,23,42,.12);}}
    .login-title{{color:#0b3440;font-size:2rem;font-weight:900;}}
    .login-subtitle{{color:#64748b;margin-bottom:18px;}}
    </style>
    """, unsafe_allow_html=True)


def login():
    if "auth" in st.session_state and st.session_state.auth: return st.session_state.auth
    styles(False)
    st.markdown('<div class="login-card"><div class="login-title">Sistema de Calidad</div><div class="login-subtitle">Acceso privado para registros PNC y ME.</div>', unsafe_allow_html=True)
    with st.form("login_form"):
        u=st.text_input("Usuario"); p=st.text_input("Contraseña",type="password"); ok=st.form_submit_button("Ingresar")
    st.markdown('</div>', unsafe_allow_html=True)
    if ok:
        au=auth_user(u.strip(),p.strip())
        if au: st.session_state.auth=au; audit(au["usuario"],"LOGIN","Ingreso correcto"); st.rerun()
        else: st.error("Usuario o contraseña incorrectos.")
    st.stop()


def topbar(user):
    initials="".join([x[0] for x in user["nombre"].split()[:2]]).upper() or "AC"
    st.markdown(f'<div class="topbar"><div class="topbar-user"><span>🔔</span><span>{user["nombre"].upper()}</span><span class="avatar">{initials}</span></div></div>', unsafe_allow_html=True)

def sidebar_menu(compact=False):
    logo_text="" if compact else "CALIDAD MD"
    st.markdown(f'<div class="logo"><span>◆</span><span class="logo-text">{logo_text}</span></div><div class="side-box">PNC y Materia Extraña</div><div class="menu-title">☰ MENÚ PRINCIPAL</div>', unsafe_allow_html=True)
    options=[("Inicio","🏠 Inicio"),("Nuevo registro","📝 Nuevo registro"),("Consulta y descarga","📊 Consulta y descarga")]
    if is_dev(): options += [("Catálogos","🧩 Catálogos"),("Usuarios","👤 Usuarios"),("Auditoría","🧾 Auditoría")]
    labels=[o[1].split()[0] if compact else o[1] for o in options]
    mapping={o[1].split()[0] if compact else o[1]:o[0] for o in options}
    selected=st.selectbox("☰ Menú principal",labels,key="menu_principal_visible")
    st.caption("Menú vertical desplegable")
    return mapping[selected]


def page_inicio():
    df=read_df("SELECT * FROM pnc_registros")
    if df.empty: df=pd.DataFrame(columns=["fecha_apertura","status","linea_sector","clasificacion","material_hallado","cantidad_total_pnc"])
    df["fecha_apertura"]=pd.to_datetime(df["fecha_apertura"],errors="coerce")
    with st.expander("Filtros dinámicos de indicadores", expanded=False):
        c1,c2,c3,c4=st.columns(4)
        f_status=c1.multiselect("Status", sorted(df["status"].dropna().unique()))
        f_linea=c2.multiselect("Línea/Sector", sorted(df["linea_sector"].dropna().unique()))
        f_clas=c3.multiselect("Clasificación", sorted(df["clasificacion"].dropna().unique()))
        focus=c4.radio("Enfoque",["Todos","Abiertos","Cerrados","Con ME"])
    data=df.copy()
    if f_status: data=data[data["status"].isin(f_status)]
    if f_linea: data=data[data["linea_sector"].isin(f_linea)]
    if f_clas: data=data[data["clasificacion"].isin(f_clas)]
    if focus=="Abiertos": data=data[data["status"]=="ABIERTO"]
    if focus=="Cerrados": data=data[data["status"]=="CERRADO"]
    if focus=="Con ME": data=data[data["material_hallado"].fillna("").astype(str).str.len()>0]
    total=len(data); abiertos=int((data["status"]=="ABIERTO").sum()) if not data.empty else 0; cerrados=int((data["status"]=="CERRADO").sum()) if not data.empty else 0; me=int(data["material_hallado"].fillna("").astype(str).str.len().gt(0).sum()) if not data.empty else 0; kg=float(data["cantidad_total_pnc"].fillna(0).sum()) if not data.empty else 0; avance=int(cerrados/total*100) if total else 0
    st.markdown('<div class="page-title">Panel Calidad Mundo Dulce</div><div class="page-subtitle">Indicadores dinámicos de Producto No Conforme y Materia Extraña</div>', unsafe_allow_html=True)
    k1,k2,k3,k4=st.columns(4)
    with k1: st.markdown(f'<div class="kpi" style="--c:#00a884"><div class="kpi-label">PNC abiertos</div><div class="kpi-value">{abiertos}</div><div class="kpi-foot">Registros pendientes</div></div>', unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="kpi" style="--c:#5850ec"><div class="kpi-label">Avance de cierre</div><div class="kpi-value">{avance}%</div><div class="kpi-foot">Cerrados vs total</div></div>', unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="kpi" style="--c:#f59e0b"><div class="kpi-label">Registros filtrados</div><div class="kpi-value">{total}</div><div class="kpi-foot">Coincidencias</div></div>', unsafe_allow_html=True)
    with k4: st.markdown(f'<div class="kpi" style="--c:#e11d48"><div class="kpi-label">Kg PNC / ME</div><div class="kpi-value">{kg:,.1f}</div><div class="kpi-foot">Hallazgos ME: {me}</div></div>', unsafe_allow_html=True)
    l,r=st.columns([2,1])
    with l:
        st.markdown('<div class="panel"><div class="panel-header">Tendencia mensual dinámica</div><div class="panel-body">', unsafe_allow_html=True)
        if not data.empty:
            t=data.dropna(subset=["fecha_apertura"]).copy(); t["Mes"]=t["fecha_apertura"].dt.strftime("%Y-%m"); st.bar_chart(t.groupby(["Mes","status"]).size().unstack(fill_value=0),use_container_width=True)
        else: st.info("No hay registros para graficar.")
        st.markdown('</div></div>', unsafe_allow_html=True)
    with r:
        st.markdown('<div class="panel"><div class="panel-header">Distribución por clasificación</div><div class="panel-body">', unsafe_allow_html=True)
        if not data.empty: st.dataframe(data["clasificacion"].fillna("Sin clasificación").value_counts().rename_axis("Clasificación").reset_index(name="Registros"),use_container_width=True,hide_index=True)
        else: st.info("No hay datos.")
        st.markdown('</div></div>', unsafe_allow_html=True)


def page_registro():
    st.title("Nuevo registro PNC / ME")
    prod=read_df("SELECT * FROM productos WHERE activo=1 ORDER BY descripcion"); defs=read_df("SELECT * FROM defectos WHERE activo=1 ORDER BY CAST(codigo AS INTEGER)")
    with st.form("registro"):
        c1,c2,c3=st.columns(3)
        fecha=c1.date_input("Fecha",value=date.today()); linea=c1.selectbox("Línea/Sector",cat("linea_sector")); nave=c1.selectbox("Nave",cat("nave"))
        opt=c2.selectbox("ITEM / Producto",[f"{r.item} | {r.descripcion}" for r in prod.itertuples()]) if not prod.empty else ""
        item=opt.split("|")[0].strip() if opt else c2.text_input("ITEM")
        row=prod[prod["item"]==item].iloc[0] if not prod.empty and item in prod["item"].values else None
        desc=str(row["descripcion"]) if row is not None else c2.text_input("Descripción"); cliente=str(row["cliente"]) if row is not None else ""; familia=str(row["familia"]) if row is not None else ""
        lote=c2.text_area("Lote"); etapa=c3.selectbox("Etapa",cat("etapa")); turno=c3.selectbox("Turno",cat("turno")); status=c3.selectbox("Status",cat("status"))
        optd=st.selectbox("Código / Defecto",[f"{r.codigo} | {r.defecto}" for r in defs.itertuples()]) if not defs.empty else ""
        cod=optd.split("|")[0].strip() if optd else st.text_input("Código")
        dr=defs[defs["codigo"]==cod].iloc[0] if not defs.empty and cod in defs["codigo"].values else None
        defecto=str(dr["defecto"]) if dr is not None else ""; tipo=str(dr["tipo_defecto"]) if dr is not None else ""; clas=str(dr["clasificacion"]) if dr is not None else ""
        descripcion=st.text_area("Descripción del defecto"); acciones=st.text_area("Acciones inmediatas",value="Se detiene línea, se segrega e identifica el producto.")
        c4,c5,c6=st.columns(3); sup=c4.selectbox("Supervisor",cat("supervisor")); ana=c4.selectbox("Analista",cat("analista")); resp=c5.selectbox("Responsable detecta",cat("responsable_detecta")); disp=c5.selectbox("Disposición",cat("disposicion")); fecha_final=c6.date_input("Fecha final",value=date.today()) if status=="CERRADO" else None
        q1,q2,q3,q4=st.columns(4); obs=q1.number_input("Observada kg",min_value=0.0); rep=q2.number_input("Reproceso kg",min_value=0.0); dec=q3.number_input("Decomiso kg",min_value=0.0); apr=q4.number_input("Aprobado 2da kg",min_value=0.0); total=rep+dec+apr
        mat=st.text_area("Material hallado / ME"); notas=st.text_area("Observaciones"); files=st.file_uploader("Adjuntar evidencia",accept_multiple_files=True,type=["pdf","png","jpg","jpeg","xlsx","csv","txt","docx"]); ok=st.form_submit_button("Guardar registro")
    if ok:
        f=new_folio(); rid=exec_sql("INSERT INTO pnc_registros(folio,fecha_apertura,linea_sector,nave,item,descripcion_producto,cliente,familia,lote,etapa,codigo_defecto,defecto,tipo_defecto,clasificacion,turno,supervisor,analista,responsable_detecta,descripcion_defecto,acciones_inmediatas,disposicion,cantidad_observada,cantidad_reproceso,cantidad_decomiso,cantidad_aprobado_segunda,cantidad_total_pnc,status,fecha_final_tratamiento,observaciones,material_hallado,creado_por,creado_en) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(f,fecha.isoformat(),linea,nave,item,desc,cliente,familia,lote,etapa,cod,defecto,tipo,clas,turno,sup,ana,resp,descripcion,acciones,disp,obs,rep,dec,apr,total,status,fecha_final.isoformat() if fecha_final else None,notas,mat,st.session_state.auth["usuario"],now_iso()))
        save_files(files,rid,f,st.session_state.auth["usuario"]); audit(st.session_state.auth["usuario"],"CREAR_PNC",f); st.success(f"Registro guardado correctamente: {f}")

def page_consulta():
    st.title("Consulta, seguimiento y descarga"); df=read_df("SELECT * FROM pnc_registros ORDER BY id DESC")
    if df.empty: st.info("No hay registros capturados."); return
    st.dataframe(df,use_container_width=True,hide_index=True); st.download_button("Descargar registros CSV",df.to_csv(index=False).encode("utf-8-sig"),f"pnc_me_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv","text/csv")

def page_catalogos():
    st.title("Catálogos"); up=st.file_uploader("Cargar Excel de catálogos",type=["xlsx"])
    if up and st.button("Importar Excel"): st.success(f"Importados: productos/defectos {import_excel(up)}")
    st.dataframe(read_df("SELECT * FROM productos ORDER BY descripcion"),use_container_width=True,hide_index=True)
    st.dataframe(read_df("SELECT * FROM defectos ORDER BY CAST(codigo AS INTEGER)"),use_container_width=True,hide_index=True)

def page_usuarios():
    st.title("Usuarios"); st.dataframe(read_df("SELECT id,usuario,nombre,rol,activo,creado_en FROM usuarios ORDER BY id"),use_container_width=True,hide_index=True)

def page_auditoria():
    st.title("Auditoría"); st.dataframe(read_df("SELECT * FROM auditoria ORDER BY id DESC LIMIT 1000"),use_container_width=True,hide_index=True)


def main():
    init_db()
    if FORCE_RESET_ADMIN: reset_admin()
    user=login()
    with st.sidebar:
        compact=st.toggle("Acortar menú",value=False)
    styles(compact); topbar(user)
    with st.sidebar:
        page=sidebar_menu(compact)
        st.divider()
        if st.button("Salir" if compact else "Cerrar sesión"):
            audit(user["usuario"],"LOGOUT","Cierre de sesión"); st.session_state.auth=None; st.rerun()
    if page=="Inicio": page_inicio()
    elif page=="Nuevo registro": page_registro()
    elif page=="Consulta y descarga": page_consulta()
    elif page=="Catálogos": page_catalogos()
    elif page=="Usuarios": page_usuarios()
    elif page=="Auditoría": page_auditoria()

if __name__=="__main__": main()
