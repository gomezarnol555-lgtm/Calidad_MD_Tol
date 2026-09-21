# Mi conexión simple con Supabase

## Archivos que subo a GitHub

Mantengo solo estos archivos principales:

```text
app.py
supabase.py
requirements.txt
configurar_supabase.sql
README.md
.gitignore
```

No subo `.streamlit/secrets.toml`, claves privadas, bases `.db` o evidencias locales.

## 1. Configuro Supabase

1. Abro mi proyecto en Supabase.
2. Entro a **SQL Editor**.
3. Creo una consulta nueva.
4. Pego todo el contenido de `configurar_supabase.sql`.
5. Presiono **Run**.
6. Confirmo que aparece el bucket `evidencias-calidad`.

Antes de ejecutar el archivo, debo haber creado las tablas de mi aplicación con el esquema principal.

## 2. Busco mis dos credenciales

Entro a:

```text
Project Settings > API Keys
```

Copio solamente:

```text
Project URL
Secret key que inicia con sb_secret_
```

No busco `Connect`, `Session pooler`, puertos o cadenas PostgreSQL.

## 3. Creo mis secretos locales

Creo:

```text
.streamlit/secrets.toml
```

Agrego:

```toml
SUPABASE_URL = "https://PROJECT_REF.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_REEMPLAZAR"
SUPABASE_STORAGE_BUCKET = "evidencias-calidad"
CALIDAD_ADMIN_USER = "admin"
CALIDAD_ADMIN_PASS = "PASSWORD_TEMPORAL_SEGURA"
CALIDAD_FORCE_RESET_ADMIN = "1"
```

Después del primer ingreso cambio:

```toml
CALIDAD_FORCE_RESET_ADMIN = "0"
```

## 4. Instalo

En Windows PowerShell ejecuto:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

En Linux o macOS ejecuto:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Conecto mi aplicación

En `app.py` agrego:

```python
from supabase import cliente, dataframe, subir_evidencia, comprobar_conexion
```

Consulto datos así:

```python
respuesta = (
    cliente()
    .table("productos")
    .select("id,item,descripcion,cliente,familia")
    .eq("activo", 1)
    .order("descripcion")
    .execute()
)
productos = dataframe(respuesta)
```

Inserto así:

```python
respuesta = cliente().table("productos").insert({
    "item": item,
    "descripcion": descripcion,
    "cliente": cliente,
    "familia": familia,
    "activo": 1,
}).execute()
producto_id = respuesta.data[0]["id"]
```

Actualizo así:

```python
cliente().table("productos").update({
    "descripcion": descripcion,
    "cliente": cliente,
    "familia": familia,
}).eq("id", producto_id).execute()
```

Desactivo así:

```python
cliente().table("productos").update({"activo": 0}).eq("id", producto_id).execute()
```

Guardo mi entrega completa así:

```python
respuesta = cliente().rpc(
    "guardar_entrega_turno_completa",
    {
        "p_encabezado": encabezado,
        "p_lineas": lineas,
        "p_seguimientos": seguimientos,
        "p_matriz": matriz,
    },
).execute()
entrega_id = respuesta.data
```

Guardo una evidencia así:

```python
ruta = subir_evidencia(archivo, folio)
```

## 6. Ejecuto mi aplicación

```bash
streamlit run app.py
```

## 7. Configuro Streamlit Cloud

Uso:

```text
Main file: app.py
```

En **Advanced settings > Secrets** pego mis secretos reales y mantengo:

```toml
CALIDAD_FORCE_RESET_ADMIN = "0"
```

## 8. Valido

Compruebo:

1. Inicio de sesión.
2. Productos y defectos.
3. PNC, Materia Extraña y DDM/RX.
4. Reclamos y Devoluciones.
5. Entrega de turno y SPAC.
6. Evidencias en el bucket privado.
7. PDFs y auditoría.
