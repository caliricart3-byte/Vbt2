# -*- coding: utf-8 -*-
"""Página — Módulo 3: Perfil de Potencia."""

import streamlit as st

from estilos import encabezado_pagina
from vbt_core import CONFIG_PLOTLY, GRAVEDAD, calcular_potencia, graficar_perfil_potencia

encabezado_pagina(
    "💥 Perfil de Potencia",
    "Identifica la carga con la que generas la máxima potencia mecánica ('Zona de Máxima Potencia').",
)

df = st.session_state.get("df")
if df is None:
    st.warning("Primero carga tus datos en **📂 Cargar Datos**.")
    if st.button("📂 Ir a Cargar Datos", type="primary"):
        st.switch_page("views/cargar_datos.py")
    st.stop()

df_potencia = calcular_potencia(df)
fig, carga_optima, potencia_maxima = graficar_perfil_potencia(df_potencia)

col1, col2 = st.columns(2)
col1.metric("🏆 Carga Óptima (Máxima Potencia)", f"{carga_optima:.1f} kg")
col2.metric("⚙️ Potencia Máxima Registrada", f"{potencia_maxima:.0f} W")

st.plotly_chart(fig, use_container_width=True, config=CONFIG_PLOTLY)

st.markdown(
    f"""
**⚙️ Interpretación del Perfil de Potencia**

La potencia mecánica se calculó como **P = Carga (kg) × g × Velocidad Media (m/s)**,
donde *g* = {GRAVEDAD} m/s² representa la aceleración de la gravedad.

La relación Carga-Potencia sigue típicamente una curva **parabólica** (invertida):
a cargas muy bajas la velocidad es alta pero la fuerza es insuficiente para generar
mucha potencia; a cargas muy altas (cerca del 1RM) la fuerza es máxima pero la
velocidad cae drásticamente, reduciendo también la potencia. Entre ambos extremos
existe una **"Zona de Máxima Potencia"**, en este caso alrededor de
**{carga_optima:.1f} kg**, donde el producto Fuerza × Velocidad se maximiza —clave
para el entrenamiento de potencia orientado a gestos explosivos (saltos, sprints,
lanzamientos).
"""
)

st.divider()
st.caption(
    "⚠️ Aviso: Los cálculos de e1RM y potencia son estimaciones basadas en modelos "
    "matemáticos estándar de la literatura VBT y deben ser interpretados por un "
    "profesional cualificado en Fuerza y Acondicionamiento."
)
