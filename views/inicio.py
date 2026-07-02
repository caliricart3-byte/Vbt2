# -*- coding: utf-8 -*-
"""Página de inicio: bienvenida, estado actual y navegación guiada."""

import streamlit as st

import database
from estilos import encabezado_pagina

encabezado_pagina(
    "🏋️ VBT Analytics",
    "Analiza tu perfil de fuerza, estima tu 1RM diario y controla la fatiga "
    "neuromuscular con Entrenamiento Basado en Velocidad.",
)

df = st.session_state.get ( "df")

if df is None:
    st.info(
        "👋 Aún no has cargado datos de entrenamiento. Ve a **📂 Cargar Datos** "
        "en el menú lateral para empezar (puedes usar los datos de ejemplo ) ."
    )
    if st.button ( "📂 Ir a Cargar Datos", type="primary" ) :
        st.switch_page ( "views/cargar_datos.py")
else:
    col1, col2, col3 = st.columns ( 3)
    col1.metric ( "👤 Atleta", st.session_state.get ( "atleta") or "Sin nombre")
    col2.metric ( "🏋️ Ejercicio", st.session_state.get ( "ejercicio" ) )
    col3.metric ( "📋 Series registradas", int ( df["Número de Serie"].nunique (  )  ) )
    st.success ( "✅ Datos cargados. Explora los módulos de análisis en el menú lateral.")

st.divider ( )
st.markdown ( "### 🧭 ¿Qué puedes hacer aquí?")

c1, c2, c3, c4 = st.columns ( 4)
with c1:
    st.markdown ( "**📈 Perfil Fuerza-Velocidad**")
    st.caption ( "Estima tu 1RM del día y la calidad de tu perfil carga-velocidad.")
with c2:
    st.markdown ( "**📉 Fatiga Intra-Serie**")
    st.caption ( "Mide la pérdida de velocidad dentro de cada serie.")
with c3:
    st.markdown ( "**💥 Perfil de Potencia**")
    st.caption ( "Encuentra la carga con la que generas máxima potencia.")
with c4:
    st.markdown ( "**📊 Progresión Histórica**")
    st.caption ( "Compara tus sesiones guardadas a lo largo del tiempo.")

historial = database.obtener_historial ( )
if not historial.empty:
    st.divider ( )
    st.markdown(
        f"📚 Tienes **{len ( historial ) } sesiones** guardadas en el historial de "
        f"**{historial['atleta'].nunique (  ) } atleta ( s ) **."
    )
