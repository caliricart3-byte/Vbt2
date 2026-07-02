# -*- coding: utf-8 -*-
"""Página — Módulo 2: Pérdida de velocidad intra-serie (fatiga neuromuscular)."""

import pandas as pd
import streamlit as st

from estilos import encabezado_pagina
from vbt_core import CONFIG_PLOTLY, calcular_perdida_velocidad, graficar_perdida_velocidad, interpretar_fatiga

encabezado_pagina(
    "📉 Pérdida de Velocidad Intra-Serie",
    "Mide la fatiga neuromuscular dentro de una serie comparando la repetición más rápida contra la más lenta.",
)

df = st.session_state.get("df")
if df is None:
    st.warning("Primero carga tus datos en **📂 Cargar Datos**.")
    if st.button("📂 Ir a Cargar Datos", type="primary"):
        st.switch_page("views/cargar_datos.py")
    st.stop()

series_disponibles = sorted(df["Número de Serie"].unique())
serie_sel = st.selectbox("Selecciona la serie a analizar", series_disponibles)
df_serie = df[df["Número de Serie"] == serie_sel]

if len(df_serie) < 2:
    st.warning(
        "⚠️ Esta serie tiene menos de 2 repeticiones; se necesitan al menos 2 "
        "para calcular la pérdida de velocidad."
    )
    st.stop()

fatiga_pct = calcular_perdida_velocidad(df_serie)

col1, col2 = st.columns(2)
col1.metric("🔻 Pérdida de Velocidad", f"{fatiga_pct:.1f}%")
col2.metric("🏋️ Carga de la Serie", f"{df_serie['Carga (kg)'].iloc[0]:.1f} kg")

fig = graficar_perdida_velocidad(df_serie, fatiga_pct)
st.plotly_chart(fig, use_container_width=True, config=CONFIG_PLOTLY)

st.markdown(interpretar_fatiga(fatiga_pct))

st.divider()
st.subheader("📋 Fatiga en todas las series de la sesión")

filas_resumen = []
for num_serie, grupo in df.groupby("Número de Serie"):
    if len(grupo) >= 2:
        filas_resumen.append({
            "Serie": num_serie,
            "Carga (kg)": grupo["Carga (kg)"].iloc[0],
            "Repeticiones": len(grupo),
            "Pérdida de Velocidad (%)": round(calcular_perdida_velocidad(grupo), 1),
        })

if filas_resumen:
    st.dataframe(pd.DataFrame(filas_resumen), use_container_width=True, hide_index=True)
else:
    st.caption("No hay series con al menos 2 repeticiones para resumir.")
