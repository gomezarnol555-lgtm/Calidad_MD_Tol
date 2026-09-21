"""Carga idempotente de los catálogos antes embebidos en Python hacia Supabase."""
import json
from pathlib import Path
from supabase_db import conn

DATA=json.loads(Path(__file__).with_name('seed_data.json').read_text(encoding='utf-8'))

def many(cur, sql, rows):
    if rows:
        cur.executemany(sql, rows)

def main():
    with conn() as db:
        try:
            with db.cursor() as cur:
                many(cur, "insert into productos(item,descripcion,cliente,familia,activo) values(%s,%s,%s,%s,1) on conflict(item) do update set descripcion=excluded.descripcion,cliente=excluded.cliente,familia=excluded.familia,activo=1", DATA['SEED_PRODUCTS'])
                many(cur, "insert into defectos(codigo,defecto,tipo_defecto,clasificacion,activo) values(%s,%s,%s,%s,1) on conflict(codigo) do update set defecto=excluded.defecto,tipo_defecto=excluded.tipo_defecto,clasificacion=excluded.clasificacion,activo=1", DATA['SEED_DEFECTS'])
                cats=[]
                for category, values in DATA['SEED_CATALOGS'].items():
                    cats.extend((category,v) for v in values)
                many(cur, "insert into catalogos(categoria,valor,activo) values(%s,%s,1) on conflict(categoria,valor) do update set activo=1", cats)
                many(cur, "insert into catalogo_naves_lineas(nave,linea,sector,linea_norm,sector_norm,orden,activo) values(%s,%s,%s,upper(trim(%s)),upper(trim(%s)),%s,1) on conflict(nave,linea,sector) do update set orden=excluded.orden,activo=1", [(n,l,s,l,s,o) for n,l,s,o in DATA['SEED_NAVES_LINEAS']])
                many(cur, "insert into catalogo_formatos_entrega(formato_nave,tipo,linea,sector,tipo_analisis,orden_linea,orden_sector,activo) values(%s,%s,%s,%s,%s,%s,%s,1) on conflict(formato_nave,tipo,linea,sector,tipo_analisis) do update set orden_linea=excluded.orden_linea,orden_sector=excluded.orden_sector,activo=1", DATA['SEED_FORMATOS_ENTREGA'])
            db.commit()
        except Exception:
            db.rollback(); raise
    print('Catálogos migrados correctamente a Supabase.')

if __name__=='__main__': main()
