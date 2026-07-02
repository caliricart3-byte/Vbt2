# -*- coding: utf-8 -*-
"""Página — Módulo 1: Perfil Carga-Velocidad y estimación del e1RM."""

import streamlit as st

import database
from estilos import encabezado_pagina
from vbt_core import (
    CONFIG_PLOTLY,
    calcular_metricas_sesion,
    calcular_perfil_carga_velocidad,
    construir_df_perfil,
    graficar_perfil_carga_velocidad,
    interpretar_e1rm,
    interpretar_perfil_fuerza_velocidad,
    velocidad_primera_repeticion,
)

encabezado_pagina(
    "📈 Perfil Carga-Velocidad y Estimación del 1RM",
    "Regresión lineal Carga-Velocidad y extrapolación del e1RM al umbral mínimo de velocidad (MVT).",
)

df = st.session_state.get("df")
if df is None:
    st.warning("Primero carga tus datos en **📂 Cargar Datos**.")
    if st.button("📂 Ir a Cargar Datos", type="primary"):
        st.switch_page("views/cargar_datos.py")
    st.stop()

mvt = st.session_state["mvt"]
ejercicio = st.session_state["ejercicio"]

df_perfil = construir_df_perfil(df)

try:
    resultado = calcular_perfil_carga_velocidad(df_perfil, mvt)
except ValueError as err:
    st.warning(f"⚠️ {err}")
    st.stop()

v1 = velocidad_primera_repeticion(df)

col1, col2, col3, col4 = st.columns(4)
col1.metric("🎯 1RM Estimado (e1RM)", f"{resultado.e1rm:.1f} kg")
col2.metric("⚡ Velocidad 1ª Rep (carga máx.)", f"{v1:.3f} m/s" if v1 == v1 else "N/D")
col3.metric("📊 R² del Perfil", f"{resultado.r_cuadrado:.3f}")
col4.metric("🚦 MVT usado", f"{resultado.mvt_usado} m/s")

fig = graficar_perfil_carga_velocidad(df_perfil, resultado)
st.plotly_chart(fig, use_container_width=True, config=CONFIG_PLOTLY)
st.caption(
    "💡 Usa dos dedos para hacer zoom (pellizco), arrastra para mover el gráfico, "
    "y toca el ícono 🏠 de la barra de herramientas (o doble toque) para resetear la vista."
)

st.markdown(interpretar_perfil_fuerza_velocidad(resultado, ejercicio))
st.markdown(interpretar_e1rm(resultado, ejercicio))

st.divider()
st.subheader("💾 Guardar esta sesión en el historial")

atleta = st.session_state.get("atleta", "")
if not atleta:
    st.info("Añade el nombre del atleta en **📂 Cargar Datos** para poder guardar la sesión.")
else:
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.caption(
            f"Se guardarán todas las métricas calculadas (e1RM, R², fatiga máxima de la "
            f"sesión y potencia) para **{atleta} — {ejercicio}**."
        )
    with col_b:
        if st.button("💾 Guardar sesión", type="primary", use_container_width=True):
            try:
                metricas = calcular_metricas_sesion(df, mvt)
                database.guardar_sesion(atleta, ejercicio, mvt, metricas)
                st.success("✅ Sesión guardada. Consulta la evolución en 📊 Progresión Histórica.")
            except ValueError as err:
                st.error(f"No se pudo guardar: {err}")
