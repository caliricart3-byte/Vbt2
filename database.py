# -*- coding: utf-8 -*-
"""
================================================================================
 database.py — Persistencia local del historial de sesiones VBT (SQLite)
--------------------------------------------------------------------------------
 Guarda cada sesión analizada (atleta, ejercicio, fecha, métricas calculadas)
 para poder comparar la progresión de un atleta a lo largo del tiempo.

 NOTA IMPORTANTE SOBRE PERSISTENCIA EN STREAMLIT COMMUNITY CLOUD:
 El archivo .db vive en el sistema de archivos del contenedor de la app.
 Esto persiste mientras el contenedor esté activo (incluida la app "dormida"
 y reactivada), PERO se reinicia desde cero cada vez que se hace un nuevo
 deploy (push a GitHub) o un "reboot" manual. Para persistencia garantizada
 a largo plazo en producción real, lo recomendable es migrar esta capa a una
 base de datos externa (por ejemplo, Supabase o Postgres) sin cambiar el
 resto de la app, ya que todas las demás páginas solo hablan con este
 módulo, nunca con SQLite directamente.
================================================================================
"""

import sqlite3
from contextlib import closing
from datetime import datetime

import pandas as pd

DB_PATH = "vbt_historial.db"


def inicializar_db() -> None:
    """Crea la tabla de sesiones si no existe todavía."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sesiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                atleta TEXT NOT NULL,
                ejercicio TEXT NOT NULL,
                fecha TEXT NOT NULL,
                mvt REAL,
                e1rm REAL,
                r2 REAL,
                pendiente REAL,
                intercepto REAL,
                velocidad_primera_rep REAL,
                fatiga_max REAL,
                carga_optima_potencia REAL,
                potencia_maxima REAL,
                notas TEXT
            )
            """
        )
        conn.commit()


def guardar_sesion(atleta: str, ejercicio: str, mvt: float, metricas: dict, notas: str = "") -> None:
    """Inserta una nueva sesión en el historial."""
    inicializar_db()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            INSERT INTO sesiones (
                atleta, ejercicio, fecha, mvt, e1rm, r2, pendiente, intercepto,
                velocidad_primera_rep, fatiga_max, carga_optima_potencia,
                potencia_maxima, notas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                atleta,
                ejercicio,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                mvt,
                metricas.get("e1rm"),
                metricas.get("r2"),
                metricas.get("pendiente"),
                metricas.get("intercepto"),
                metricas.get("velocidad_primera_rep"),
                metricas.get("fatiga_max"),
                metricas.get("carga_optima_potencia"),
                metricas.get("potencia_maxima"),
                notas,
            ),
        )
        conn.commit()


def obtener_atletas() -> list:
    """Devuelve la lista de nombres de atletas con al menos una sesión guardada."""
    inicializar_db()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        filas = conn.execute("SELECT DISTINCT atleta FROM sesiones ORDER BY atleta").fetchall()
    return [f[0] for f in filas]


def obtener_historial(atleta: str = None, ejercicio: str = None) -> pd.DataFrame:
    """Recupera el historial de sesiones, opcionalmente filtrado por atleta/ejercicio."""
    inicializar_db()
    query = "SELECT * FROM sesiones WHERE 1=1"
    params = []
    if atleta:
        query += " AND atleta = ?"
        params.append(atleta)
    if ejercicio:
        query += " AND ejercicio = ?"
        params.append(ejercicio)
    query += " ORDER BY fecha ASC"

    with closing(sqlite3.connect(DB_PATH)) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df


def eliminar_sesion(id_sesion: int) -> None:
    """Elimina una sesión del historial por su id."""
    inicializar_db()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("DELETE FROM sesiones WHERE id = ?", (id_sesion,))
        conn.commit()
