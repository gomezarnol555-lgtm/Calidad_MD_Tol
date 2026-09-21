-- Ejecuto este archivo una sola vez en Supabase > SQL Editor.

-- 1. Creo mi bucket privado para evidencias.
insert into storage.buckets (id, name, public, file_size_limit)
values ('evidencias-calidad', 'evidencias-calidad', false, 52428800)
on conflict (id) do update
set name = excluded.name,
    public = excluded.public,
    file_size_limit = excluded.file_size_limit;

-- 2. Creo mi función para guardar una entrega completa en una sola transacción.
create or replace function public.guardar_entrega_turno_completa(
    p_encabezado jsonb,
    p_lineas jsonb,
    p_seguimientos jsonb,
    p_matriz jsonb
) returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
    v_entrega_id bigint;
    v_linea jsonb;
    v_seguimiento jsonb;
begin
    insert into entregas_turno(
        nave, fecha, analista, turno, referencia,
        total_carga_datos, total_horas_trabajadas, creado_por, creado_en
    ) values (
        p_encabezado->>'nave',
        (p_encabezado->>'fecha')::date,
        p_encabezado->>'analista',
        p_encabezado->>'turno',
        p_encabezado->>'referencia',
        coalesce((p_encabezado->>'total_carga_datos')::numeric, 0),
        coalesce((p_encabezado->>'total_horas_trabajadas')::numeric, 0),
        p_encabezado->>'creado_por',
        now()
    ) returning id into v_entrega_id;

    for v_linea in
        select * from jsonb_array_elements(coalesce(p_lineas, '[]'::jsonb))
    loop
        insert into entregas_turno_lineas(
            entrega_id, grupo, linea, producto_descripcion,
            horas_trabajadas, carga_spac, observaciones,
            orden_fila, nave_catalogo
        ) values (
            v_entrega_id,
            v_linea->>'grupo',
            v_linea->>'linea',
            v_linea->>'producto_descripcion',
            coalesce((v_linea->>'horas_trabajadas')::numeric, 0),
            coalesce((v_linea->>'carga_spac')::numeric, 0),
            v_linea->>'observaciones',
            coalesce((v_linea->>'orden_fila')::integer, 0),
            v_linea->>'nave_catalogo'
        );
    end loop;

    for v_seguimiento in
        select * from jsonb_array_elements(coalesce(p_seguimientos, '[]'::jsonb))
    loop
        insert into entregas_turno_seguimientos(
            entrega_id, bloque, registro_numero, hoja_fisica,
            carga_electronica, correo, descripcion_seguimiento,
            datos_json, orden_fila
        ) values (
            v_entrega_id,
            v_seguimiento->>'bloque',
            v_seguimiento->>'registro_numero',
            v_seguimiento->>'hoja_fisica',
            v_seguimiento->>'carga_electronica',
            v_seguimiento->>'correo',
            v_seguimiento->>'descripcion_seguimiento',
            coalesce(v_seguimiento->'datos_json', '{}'::jsonb),
            coalesce((v_seguimiento->>'orden_fila')::integer, 0)
        );
    end loop;

    insert into matriz_entrega(
        fecha, analista, entrega_id, total_carga_datos,
        horas_nave1, horas_nave2, horas_nave3, actualizado_en
    ) values (
        (p_matriz->>'fecha')::date,
        p_matriz->>'analista',
        v_entrega_id,
        coalesce((p_matriz->>'total_carga_datos')::numeric, 0),
        coalesce((p_matriz->>'horas_nave1')::numeric, 0),
        coalesce((p_matriz->>'horas_nave2')::numeric, 0),
        coalesce((p_matriz->>'horas_nave3')::numeric, 0),
        now()
    )
    on conflict(fecha, analista) do update set
        entrega_id = excluded.entrega_id,
        total_carga_datos = excluded.total_carga_datos,
        horas_nave1 = excluded.horas_nave1,
        horas_nave2 = excluded.horas_nave2,
        horas_nave3 = excluded.horas_nave3,
        actualizado_en = excluded.actualizado_en;

    return v_entrega_id;
end;
$$;

-- 3. Evito que una clave pública ejecute esta función.
revoke all on function public.guardar_entrega_turno_completa(jsonb,jsonb,jsonb,jsonb)
from public, anon, authenticated;

grant execute on function public.guardar_entrega_turno_completa(jsonb,jsonb,jsonb,jsonb)
to service_role;

-- 4. Confirmo que mi bucket quedó creado.
select id, name, public, file_size_limit
from storage.buckets
where id = 'evidencias-calidad';
