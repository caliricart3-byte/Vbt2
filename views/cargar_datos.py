# -*- coding: utf-8 -*-
"""Página de carga de datos: archivo del usuario o datos de ejemplo + config de sesión."""

import pandas as pd
import streamlit as st

from estilos import encabezado_pagina
from vbt_core import (
    COLUMNAS_REQUERIDAS,
    MVT_POR_EJERCICIO,
    cargar_archivo,
    generar_datos_ejemplo,
    limpiar_dataframe,
    validar_columnas,
)

encabezado_pagina(
    "📂 Cargar Datos de Entrenamiento",
    "Sube tu archivo del encoder VBT (CSV/Excel) o prueba la app con datos de ejemplo.",
)

col_izq, col_der = st.columns([1.3, 1])

# --------------------------------------------------------------------------
# COLUMNA IZQUIERDA — Origen de los datos
# --------------------------------------------------------------------------
with col_izq:
    st.subheader("1️⃣ Origen de los datos")
    archivo_subido = st.file_uploader("Sube tu archivo (CSV o Excel)", type=["csv", "xlsx", "xls"])

    usar_ejemplo = False
    if archivo_subido is None:
        usar_ejemplo = st.checkbox(
            "📊 Usar datos de ejemplo (test progresivo simulado)",
            value=(st.session_state.get("df") is None),
        )

    if archivo_subido is not None:
        try:
            df = cargar_archivo(archivo_subido)
            st.success(f"Archivo '{archivo_subido.name}' cargado correctamente.")
        except ValueError as err:
            st.error(str(err))
            st.stop()
    elif usar_ejemplo:
        df = generar_datos_ejemplo()
        st.info(
            "Usando **datos de ejemplo**: test progresivo de Press de Banca "
            "(40kg → 60kg → 80kg → 90kg)."
        )
    else:
        df = st.session_state.get("df")
        if df is None:
            st.warning("Sube un archivo o activa los datos de ejemplo para continuar.")
            st.stop()

    es_valido, faltantes = validar_columnas(df)
    if not es_valido:
        st.error(
            f"El archivo no contiene las columnas requeridas. Faltan: "
            f"{', '.join(faltantes)}.\n\nColumnas esperadas: {', '.join(COLUMNAS_REQUERIDAS)}"
        )
        st.stop()

    df = limpiar_dataframe(df)
    if df.empty:
        st.error(
            "No quedaron filas válidas tras la limpieza de datos. Verifica que "
            "las columnas numéricas no contengan texto o valores vacíos."
        )
        st.stop()

# --------------------------------------------------------------------------
# COLUMNA DERECHA — Metadatos de la sesión
# --------------------------------------------------------------------------
with col_der:
    st.subheader("2️⃣ Datos de la sesión")

    atleta = st.text_input("Nombre del atleta", value=st.session_state.get("atleta", ""))

    ejercicios = list(MVT_POR_EJERCICIO.keys())
    ejercicio_previo = st.session_state.get("ejercicio", "Press de Banca")
    idx_previo = ejercicios.index(ejercicio_previo) if ejercicio_previo in ejercicios else 0
    ejercicio = st.selectbox("Ejercicio", ejercicios, index=idx_previo)

    if MVT_POR_EJERCICIO[ejercicio] is None:
        mvt = st.number_input(
            "MVT personalizado (m/s)", min_value=0.01, max_value=1.5,
            value=float(st.session_state.get("mvt", 0.2)), step=0.01,
        )
    else:
        mvt = MVT_POR_EJERCICIO[ejercicio]
        st.metric("MVT del ejercicio", f"{mvt} m/s")

    fecha_sesion = st.date_input("Fecha de la sesión", value=pd.Timestamp.today())

# --------------------------------------------------------------------------
# Persistir en session_state para que las demás páginas lo usen
# --------------------------------------------------------------------------
st.session_state["df"] = df
st.session_state["atleta"] = atleta
st.session_state["ejercicio"] = ejercicio
st.session_state["mvt"] = mvt
st.session_state["fecha_sesion"] = str(fecha_sesion)

st.divider()
st.subheader("👁️ Vista previa de los datos")
st.dataframe(df, use_container_width=True, height=300)

st.success("✅ Datos listos. Continúa con el análisis desde el menú lateral.")
if st.button("📈 Ir al Perfil Fuerza-Velocidad →", type="primary"):
    st.switch_page("views/perfil_fuerza_velocidad.py")
