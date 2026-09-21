[README_MIGRACION_SUPABASE.md](https://github.com/user-attachments/files/32480822/README_MIGRACION_SUPABASE.md)
# Migración de Calidad MD a Supabase

## Entregables

- `app_calidad_supabase.py`: aplicación Streamlit limpia, sin SQLite y sin catálogos masivos embebidos.
- `supabase_db.py`: única capa de acceso a PostgreSQL y Supabase Storage.
- `supabase_schema.sql`: esquema PostgreSQL completo.
- `seed_data.json`: datos maestros extraídos del código original.
- `migrate_seed_data.py`: migración idempotente de catálogos.
- `secrets.toml.example`: plantilla de secretos.
- `requirements_supabase.txt`: dependencias.

## Instalación

1. Cree un proyecto en Supabase.
2. Abra **SQL Editor**, pegue y ejecute `supabase_schema.sql`.
3. Cree un bucket privado llamado `evidencias-calidad` en Storage.
4. Copie `secrets.toml.example` como `.streamlit/secrets.toml` y sustituya los valores.
5. Instale dependencias:

```bash
pip install -r requirements_supabase.txt
```

6. Migre los catálogos que estaban escritos en Python:

```bash
python migrate_seed_data.py
```

7. Ejecute por primera vez con `CALIDAD_FORCE_RESET_ADMIN = "1"` y una contraseña temporal robusta. Después del primer acceso, cambie esa variable a `"0"`.
8. Inicie la aplicación:

```bash
streamlit run app_calidad_supabase.py
```

## Migración de registros históricos de SQLite

Este paquete no inventa ni sobrescribe datos históricos. Si existe `calidad.db`, exporte sus tablas de registros y cárguelas después de ejecutar el esquema. La migración debe conservar los IDs para mantener relaciones entre `entregas_turno`, sus líneas, seguimientos y `matriz_entrega`. No elimine la base SQLite hasta validar conteos, sumas e integridad referencial en Supabase.

## Seguridad

La clave `SUPABASE_SERVICE_ROLE_KEY` y la URL con contraseña de PostgreSQL deben existir solo en el servidor de Streamlit. Nunca deben subirse al repositorio. El SQL revoca acceso directo a las tablas para los roles `anon` y `authenticated`; la aplicación conserva su control de acceso interno y conecta desde servidor.
