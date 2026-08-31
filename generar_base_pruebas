import os
import sqlite3
import importlib.util
from pathlib import Path
from datetime import date, datetime, timedelta


# ============================================================
# CONFIGURACIÓN
# ============================================================

CARPETA_ACTUAL = Path(__file__).resolve().parent
ARCHIVO_APP = CARPETA_ACTUAL / "app_calidad.py"

BASE_TEMPORAL = CARPETA_ACTUAL / "calidad.db"
BASE_SALIDA = CARPETA_ACTUAL / "calidad_pruebas_agosto_2026.db"

USUARIO_PRUEBA = "prueba"
FECHA_CREACION = datetime.now().isoformat(timespec="seconds")

FECHA_INICIAL = date(2026, 8, 23)
FECHAS_PRUEBA = [
    FECHA_INICIAL + timedelta(days=i)
    for i in range(8)
]

TABLAS_MUESTRAS = [
    "muestras_10_meses",
    "muestras_12_meses_alergeno",
    "muestras_12_meses_duvalin",
    "muestras_12_meses_nave2",
    "muestras_15_meses",
    "muestras_18_meses",
    "muestras_24_meses",
]


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def cargar_aplicacion():
    if not ARCHIVO_APP.exists():
        raise FileNotFoundError(
            "No se encontró app_calidad.py en la misma carpeta."
        )

    especificacion = importlib.util.spec_from_file_location(
        "app_calidad",
        ARCHIVO_APP
    )

    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)

    return modulo


def preparar_base(app):
    """
    Crea una base nueva usando exactamente la estructura definida
    en app_calidad.py.
    """

    if BASE_SALIDA.exists():
        BASE_SALIDA.unlink()

    base_original = None

    if BASE_TEMPORAL.exists():
        base_original = CARPETA_ACTUAL / "calidad_respaldo_antes_pruebas.db"

        contador = 1
        while base_original.exists():
            base_original = CARPETA_ACTUAL / (
                f"calidad_respaldo_antes_pruebas_{contador}.db"
            )
            contador += 1

        BASE_TEMPORAL.rename(base_original)

    try:
        os.chdir(CARPETA_ACTUAL)

        app.DB_PATH = str(BASE_SALIDA)
        app.init_db()

    finally:
        if base_original and base_original.exists():
            base_original.rename(BASE_TEMPORAL)


def obtener_uno(cursor, consulta, parametros=()):
    return cursor.execute(consulta, parametros).fetchone()


def obtener_todos(cursor, consulta, parametros=()):
    return cursor.execute(consulta, parametros).fetchall()


def obtener_folio_pnc(cursor, consecutivo):
    return f"PNC-2026-PRUEBA-{consecutivo:03d}"


def obtener_nave_indicador(cursor, app, linea, sector, nave_formato):
    linea_normalizada = app.normalizar_catalogo(linea)
    sector_normalizado = app.normalizar_catalogo(sector)

    resultado = cursor.execute(
        """
        SELECT nave
        FROM catalogo_naves_lineas
        WHERE activo = 1
          AND (
                linea_norm = ?
                OR sector_norm = ?
              )
        ORDER BY id
        LIMIT 1
        """,
        (
            linea_normalizada,
            sector_normalizado
        )
    ).fetchone()

    if resultado and resultado["nave"] in [
        "Nave 1",
        "Nave 2",
        "Nave 3"
    ]:
        return resultado["nave"]

    return nave_formato


# ============================================================
# REGISTROS DE PNC
# ============================================================

def crear_registros_pnc(
    cursor,
    productos,
    defectos,
    analistas,
    supervisores,
    lineas
):
    for numero in range(10):
        producto = productos[numero % len(productos)]
        defecto = defectos[numero % len(defectos)]
        fecha_registro = FECHAS_PRUEBA[numero % len(FECHAS_PRUEBA)]

        nave = str((numero % 3) + 1)
        turno = ["A", "B", "C"][numero % 3]
        status = "CERRADO" if numero % 2 else "ABIERTO"

        cantidad_observada = float(10 + numero)
        cantidad_reproceso = 2.0
        cantidad_decomiso = 1.0
        cantidad_aprobada = 1.0

        cantidad_total = (
            cantidad_reproceso
            + cantidad_decomiso
            + cantidad_aprobada
        )

        cursor.execute(
            """
            INSERT INTO pnc_registros
            (
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
                observaciones,
                material_hallado,
                creado_por,
                creado_en,
                semana,
                categoria_inicial_pnc,
                categoria_final_pnc
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                obtener_folio_pnc(cursor, numero + 1),
                fecha_registro.isoformat(),
                lineas[numero % len(lineas)],
                nave,
                producto["item"],
                producto["descripcion"],
                producto["cliente"],
                producto["familia"],
                f"PRUEBA-PNC-{numero + 1:02d}",
                "PT",
                defecto["codigo"],
                defecto["defecto"],
                defecto["tipo_defecto"],
                defecto["clasificacion"],
                turno,
                supervisores[numero % len(supervisores)],
                analistas[numero % len(analistas)],
                "CALIDAD",
                "REGISTRO SINTÉTICO PARA PRUEBA DE LA APLICACIÓN",
                "Contención simulada para validación del sistema",
                "Inspección",
                cantidad_observada,
                cantidad_reproceso,
                cantidad_decomiso,
                cantidad_aprobada,
                cantidad_total,
                status,
                (
                    fecha_registro.isoformat()
                    if status == "CERRADO"
                    else None
                ),
                "DATOS SINTÉTICOS DE PRUEBA",
                "",
                USUARIO_PRUEBA,
                FECHA_CREACION,
                int(fecha_registro.isocalendar().week),
                "1",
                "2" if status == "CERRADO" else ""
            )
        )


# ============================================================
# REGISTROS DE MATERIA EXTRAÑA Y DDM/RX
# ============================================================

def crear_registros_hallazgos(
    cursor,
    tabla,
    prefijo,
    productos,
    defectos,
    analistas,
    supervisores,
    lineas
):
    for numero in range(10):
        producto = productos[(numero + 10) % len(productos)]
        defecto = defectos[(numero + 10) % len(defectos)]
        fecha_registro = FECHAS_PRUEBA[numero % len(FECHAS_PRUEBA)]

        tipo_hallazgo = (
            "Metal"
            if tabla == "ddm_rx_registros"
            else "Otro"
        )

        cursor.execute(
            f"""
            INSERT INTO {tabla}
            (
                dia,
                mes,
                anio,
                nave,
                linea_sector,
                familia,
                equipo_hallazgo,
                item,
                producto,
                lote,
                descripcion_hallazgo,
                tipo,
                particulas_halladas,
                accion_contingente,
                investigacion_origen,
                analista_detecta,
                supervisor_responsable,
                acciones_evitar_incidencia,
                creado_por,
                creado_en,
                etapa,
                codigo_defecto,
                semana,
                turno,
                responsable_detecta,
                acciones_inmediatas,
                disposicion,
                cantidad_observada,
                status,
                categoria_inicial
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                fecha_registro.day,
                fecha_registro.month,
                fecha_registro.year,
                str((numero % 3) + 1),
                lineas[(numero + 3) % len(lineas)],
                producto["familia"],
                f"EQUIPO DE PRUEBA {numero + 1}",
                producto["item"],
                producto["descripcion"],
                f"PRUEBA-{prefijo}-{numero + 1:02d}",
                "HALLAZGO SINTÉTICO PARA VALIDACIÓN",
                tipo_hallazgo,
                numero + 1,
                "Segregación simulada del producto",
                "Investigación sintética de prueba",
                analistas[(numero + 2) % len(analistas)],
                supervisores[(numero + 2) % len(supervisores)],
                "Acción preventiva simulada",
                USUARIO_PRUEBA,
                FECHA_CREACION,
                "PT",
                defecto["codigo"],
                int(fecha_registro.isocalendar().week),
                ["A", "B", "C"][numero % 3],
                "CALIDAD",
                "Acción inmediata simulada",
                "Inspección",
                float(5 + numero),
                "ABIERTO",
                defecto["clasificacion"]
            )
        )


# ============================================================
# MUESTRAS DE RETENCIÓN
# ============================================================

def crear_muestras_retencion(
    cursor,
    productos,
    analistas
):
    for numero_tabla, tabla in enumerate(TABLAS_MUESTRAS):
        for numero in range(10):
            producto = productos[
                (numero_tabla * 3 + numero) % len(productos)
            ]

            fecha_referencia = FECHAS_PRUEBA[
                numero % len(FECHAS_PRUEBA)
            ]

            cursor.execute(
                f"""
                INSERT INTO {tabla}
                (
                    item,
                    descripcion,
                    lote,
                    destino,
                    numero_muestras,
                    numero_corrugado,
                    responsable,
                    observaciones,
                    creado_por,
                    creado_en
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    producto["item"],
                    producto["descripcion"],
                    f"PRUEBA-{numero_tabla + 1}-{numero + 1:02d}",
                    (
                        "Nacional"
                        if numero % 2 == 0
                        else "Exportación"
                    ),
                    float(numero + 1),
                    float((numero % 3) + 1),
                    analistas[
                        (numero_tabla + numero) % len(analistas)
                    ],
                    (
                        "DATOS SINTÉTICOS DE PRUEBA. "
                        f"Fecha de referencia "
                        f"{fecha_referencia.isoformat()}"
                    ),
                    USUARIO_PRUEBA,
                    FECHA_CREACION
                )
            )


# ============================================================
# ENTREGAS DE TURNO
# ============================================================

def crear_entregas_turno(
    cursor,
    app,
    analistas
):
    referencia = "RE-CAL01-2301-00002-2013 Rev. 1"
    combinaciones_utilizadas = set()

    for numero_nave, nave in enumerate(
        ["Nave 1", "Nave 2", "Nave 3"]
    ):
        estructura = obtener_todos(
            cursor,
            """
            SELECT
                linea,
                sector,
                orden_linea,
                orden_sector
            FROM catalogo_formatos_entrega
            WHERE formato_nave = ?
              AND tipo = 'PROCESO'
              AND activo = 1
            ORDER BY orden_linea, orden_sector, id
            """,
            (nave,)
        )

        if not estructura:
            raise RuntimeError(
                f"No existe estructura para {nave}."
            )

        for numero in range(10):
            fecha_registro = FECHAS_PRUEBA[
                numero % len(FECHAS_PRUEBA)
            ]

            indice_analista = (
                numero_nave * 10 + numero
            ) % len(analistas)

            while (
                fecha_registro.isoformat(),
                analistas[indice_analista]
            ) in combinaciones_utilizadas:
                indice_analista = (
                    indice_analista + 1
                ) % len(analistas)

            analista = analistas[indice_analista]

            combinaciones_utilizadas.add(
                (
                    fecha_registro.isoformat(),
                    analista
                )
            )

            posicion_inicial = (
                numero * 2
            ) % len(estructura)

            filas_seleccionadas = estructura[
                posicion_inicial:posicion_inicial + 3
            ]

            if not filas_seleccionadas:
                filas_seleccionadas = estructura[:3]

            filas_entrega = []
            total_carga = 0.0

            totales_horas = {
                "Nave 1": 0.0,
                "Nave 2": 0.0,
                "Nave 3": 0.0
            }

            for posicion, fila in enumerate(
                filas_seleccionadas
            ):
                horas = float(posicion + 1)
                carga = float(
                    ((numero + posicion) % 4) + 1
                )

                total_carga += carga

                nave_indicador = obtener_nave_indicador(
                    cursor,
                    app,
                    fila["linea"],
                    fila["sector"],
                    nave
                )

                totales_horas[nave_indicador] += horas

                filas_entrega.append(
                    {
                        "grupo": fila["linea"],
                        "sector": fila["sector"],
                        "horas": horas,
                        "carga": carga,
                        "nave_indicador": nave_indicador
                    }
                )

            total_horas = sum(totales_horas.values())

            cursor.execute(
                """
                INSERT INTO entregas_turno
                (
                    nave,
                    fecha,
                    analista,
                    turno,
                    referencia,
                    total_carga_datos,
                    total_horas_trabajadas,
                    creado_por,
                    creado_en
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nave,
                    fecha_registro.isoformat(),
                    analista,
                    ["A", "B", "C"][numero % 3],
                    referencia,
                    total_carga,
                    total_horas,
                    USUARIO_PRUEBA,
                    FECHA_CREACION
                )
            )

            entrega_id = cursor.lastrowid

            for orden, fila in enumerate(filas_entrega):
                cursor.execute(
                    """
                    INSERT INTO entregas_turno_lineas
                    (
                        entrega_id,
                        grupo,
                        linea,
                        producto_descripcion,
                        horas_trabajadas,
                        carga_spac,
                        observaciones,
                        orden_fila,
                        nave_catalogo
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entrega_id,
                        fila["grupo"],
                        fila["sector"],
                        "PRODUCTO SINTÉTICO DE PRUEBA",
                        fila["horas"],
                        fila["carga"],
                        "REGISTRO DE PRUEBA",
                        orden,
                        fila["nave_indicador"]
                    )
                )

            cursor.execute(
                """
                INSERT INTO matriz_entrega
                (
                    fecha,
                    analista,
                    entrega_id,
                    total_carga_datos,
                    horas_nave1,
                    horas_nave2,
                    horas_nave3,
                    actualizado_en
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fecha_registro.isoformat(),
                    analista,
                    entrega_id,
                    total_carga,
                    totales_horas["Nave 1"],
                    totales_horas["Nave 2"],
                    totales_horas["Nave 3"],
                    FECHA_CREACION
                )
            )


# ============================================================
# AUDITORÍA
# ============================================================

def crear_auditoria(cursor):
    resumenes = [
        (
            "PRUEBA_CARGA_PNC",
            "10 registros sintéticos de PNC"
        ),
        (
            "PRUEBA_CARGA_ME",
            "10 registros sintéticos de Materia Extraña"
        ),
        (
            "PRUEBA_CARGA_DDM",
            "10 registros sintéticos de Detector de Metales y RX"
        ),
        (
            "PRUEBA_CARGA_MUESTRAS",
            "70 registros sintéticos de muestras de retención"
        ),
        (
            "PRUEBA_CARGA_ENTREGAS",
            "30 registros sintéticos de entregas de turno"
        ),
    ]

    for accion, detalle in resumenes:
        cursor.execute(
            """
            INSERT INTO auditoria
            (
                usuario,
                accion,
                detalle,
                fecha_hora
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                USUARIO_PRUEBA,
                accion,
                (
                    f"{detalle}. Periodo de referencia: "
                    "2026-08-23 a 2026-08-30"
                ),
                FECHA_CREACION
            )
        )


# ============================================================
# VALIDACIÓN FINAL
# ============================================================

def validar_base(cursor):
    resultados = {
        "PNC": obtener_uno(
            cursor,
            "SELECT COUNT(*) AS total FROM pnc_registros"
        )["total"],

        "Materia Extraña": obtener_uno(
            cursor,
            "SELECT COUNT(*) AS total FROM me_registros"
        )["total"],

        "Detector de Metales y RX": obtener_uno(
            cursor,
            "SELECT COUNT(*) AS total FROM ddm_rx_registros"
        )["total"],

        "Entregas de turno": obtener_uno(
            cursor,
            "SELECT COUNT(*) AS total FROM entregas_turno"
        )["total"],

        "Matriz de entrega": obtener_uno(
            cursor,
            "SELECT COUNT(*) AS total FROM matriz_entrega"
        )["total"],
    }

    total_muestras = 0

    for tabla in TABLAS_MUESTRAS:
        total_muestras += obtener_uno(
            cursor,
            f"SELECT COUNT(*) AS total FROM {tabla}"
        )["total"]

    resultados["Muestras de retención"] = total_muestras

    integridad = obtener_uno(
        cursor,
        "PRAGMA integrity_check"
    )[0]

    print()
    print("=" * 60)
    print("BASE SQLITE GENERADA CORRECTAMENTE")
    print("=" * 60)

    for nombre, total in resultados.items():
        print(f"{nombre}: {total}")

    print(f"Integridad SQLite: {integridad}")
    print(f"Archivo generado: {BASE_SALIDA}")
    print("=" * 60)


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================

def main():
    print("Cargando estructura de app_calidad.py...")

    app = cargar_aplicacion()

    print("Creando base SQLite local...")

    preparar_base(app)

    conexion = sqlite3.connect(BASE_SALIDA)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()

    try:
        productos = obtener_todos(
            cursor,
            """
            SELECT
                item,
                descripcion,
                cliente,
                familia
            FROM productos
            WHERE activo = 1
            ORDER BY id
            LIMIT 40
            """
        )

        defectos = obtener_todos(
            cursor,
            """
            SELECT
                codigo,
                defecto,
                tipo_defecto,
                clasificacion
            FROM defectos
            WHERE activo = 1
            ORDER BY CAST(codigo AS INTEGER)
            LIMIT 40
            """
        )

        analistas = [
            fila["valor"]
            for fila in obtener_todos(
                cursor,
                """
                SELECT valor
                FROM catalogos
                WHERE categoria = 'analista'
                  AND activo = 1
                ORDER BY valor
                """
            )
        ]

        supervisores = [
            fila["valor"]
            for fila in obtener_todos(
                cursor,
                """
                SELECT valor
                FROM catalogos
                WHERE categoria = 'supervisor'
                  AND activo = 1
                ORDER BY valor
                """
            )
        ]

        lineas = [
            fila["valor"]
            for fila in obtener_todos(
                cursor,
                """
                SELECT valor
                FROM catalogos
                WHERE categoria = 'linea_sector'
                  AND activo = 1
                ORDER BY valor
                """
            )
        ]

        if not productos:
            raise RuntimeError(
                "No se encontraron productos activos."
            )

        if not defectos:
            raise RuntimeError(
                "No se encontraron defectos activos."
            )

        if not analistas:
            raise RuntimeError(
                "No se encontraron analistas activos."
            )

        if not supervisores:
            raise RuntimeError(
                "No se encontraron supervisores activos."
            )

        if not lineas:
            raise RuntimeError(
                "No se encontraron líneas activas."
            )

        print("Generando 10 registros de PNC...")

        crear_registros_pnc(
            cursor,
            productos,
            defectos,
            analistas,
            supervisores,
            lineas
        )

        print("Generando 10 registros de Materia Extraña...")

        crear_registros_hallazgos(
            cursor,
            "me_registros",
            "ME",
            productos,
            defectos,
            analistas,
            supervisores,
            lineas
        )

        print("Generando 10 registros de Detector de Metales y RX...")

        crear_registros_hallazgos(
            cursor,
            "ddm_rx_registros",
            "DDM",
            productos,
            defectos,
            analistas,
            supervisores,
            lineas
        )

        print("Generando 70 registros de muestras de retención...")

        crear_muestras_retencion(
            cursor,
            productos,
            analistas
        )

        print("Generando 30 entregas de turno...")

        crear_entregas_turno(
            cursor,
            app,
            analistas
        )

        print("Registrando auditoría...")

        crear_auditoria(cursor)

        conexion.commit()

        validar_base(cursor)

    except Exception:
        conexion.rollback()

        if BASE_SALIDA.exists():
            conexion.close()
            BASE_SALIDA.unlink()

        raise

    finally:
        try:
            conexion.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
