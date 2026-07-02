# -*- coding: utf-8 -*-
"""Página — Progresión Histórica: tendencias y comparador visual entre sesiones guardadas."""

import plotly.graph_objects as go
import streamlit as st

import database
from estilos import encabezado_pagina
from vbt_core import CONFIG_PLOTLY

encabezado_pagina(
    "📊 Progresión Histórica",
    "Compara tus sesiones guardadas a lo largo del tiempo y detecta tendencias reales de rendimiento.",
)

atletas = database.obtener_atletas()

if not atletas:
    st.info(
        "Todavía no tienes sesiones guardadas. Ve a **📈 Perfil Fuerza-Velocidad** "
        "después de cargar datos, y usa el botón **'💾 Guardar sesión'**."
    )
    st.stop()

col_sel1, col_sel2 = st.columns(2)
with col_sel1:
    atleta_sel = st.selectbox("👤 Atleta", atletas)

historial_atleta = database.obtener_historial(atleta=atleta_sel)
ejercicios_disponibles = sorted(historial_atleta["ejercicio"].unique())

with col_sel2:
    ejercicio_sel = st.selectbox("🏋️ Ejercicio", ejercicios_disponibles)

historial = historial_atleta[historial_atleta["ejercicio"] == ejercicio_sel].sort_values("fecha")

if len(historial) < 2:
    st.warning(
        "⚠️ Necesitas al menos **2 sesiones guardadas** de este atleta/ejercicio "
        "para ver tendencias y comparativas."
    )
    st.dataframe(
        historial[["fecha", "e1rm", "r2", "fatiga_max", "carga_optima_potencia", "potencia_maxima"]],
        use_container_width=True, hide_index=True,
    )
    st.stop()

# --------------------------------------------------------------------------
# TENDENCIAS EN EL TIEMPO
# --------------------------------------------------------------------------
st.subheader("📈 Tendencias en el tiempo")


def grafico_tendencia(historial, columna, titulo, color, sufijo=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=historial["fecha"], y=historial[columna], mode="lines+markers+text",
        text=[f"{v:.1f}{sufijo}" for v in historial[columna]], textposition="top center",
        line=dict(color=color, width=3), marker=dict(size=10),
    ))
    fig.update_layout(
        title=titulo, template="plotly_white", height=320,
        xaxis_title="Fecha", yaxis_title=titulo, dragmode="pan", margin=dict(t=50),
    )
    return fig


c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(
        grafico_tendencia(historial, "e1rm", "1RM Estimado (kg)", "#DC2626", " kg"),
        use_container_width=True, config=CONFIG_PLOTLY,
    )
with c2:
    st.plotly_chart(
        grafico_tendencia(historial, "fatiga_max", "Fatiga Máxima Registrada (%)", "#F59E0B", "%"),
        use_container_width=True, config=CONFIG_PLOTLY,
    )

c3, c4 = st.columns(2)
with c3:
    st.plotly_chart(
        grafico_tendencia(historial, "carga_optima_potencia", "Carga Óptima de Potencia (kg)", "#7C3AED", " kg"),
        use_container_width=True, config=CONFIG_PLOTLY,
    )
with c4:
    st.plotly_chart(
        grafico_tendencia(historial, "r2", "Calidad del Perfil (R²)", "#2563EB"),
        use_container_width=True, config=CONFIG_PLOTLY,
    )

# --------------------------------------------------------------------------
# COMPARADOR DE SESIONES (VISUAL Y SENCILLO)
# --------------------------------------------------------------------------
st.divider()
st.subheader("🆚 Comparador de Sesiones")

opciones = {f"{row['fecha']}  (e1RM {row['e1rm']:.1f} kg)": row for _, row in historial.iterrows()}
etiquetas = list(opciones.keys())

col_a, col_b = st.columns(2)
with col_a:
    sel_a = st.selectbox("Sesión A (referencia)", etiquetas, index=max(0, len(etiquetas) - 2))
with col_b:
    sel_b = st.selectbox("Sesión B (a comparar)", etiquetas, index=len(etiquetas) - 1)

fila_a = opciones[sel_a]
fila_b = opciones[sel_b]

# (nombre visible, campo en la BD, unidad, color_delta)
# color_delta = "inverse" cuando un valor MÁS BAJO es la mejora deseada (ej. fatiga)
metricas_comparar = [
    ("🎯 1RM Estimado", "e1rm", "kg", "normal"),
    ("📊 R² del Perfil", "r2", "", "normal"),
    ("🔻 Fatiga Máxima", "fatiga_max", "%", "inverse"),
    ("🏆 Carga Óptima Potencia", "carga_optima_potencia", "kg", "normal"),
    ("⚙️ Potencia Máxima", "potencia_maxima", "W", "normal"),
]

cols = st.columns(len(metricas_comparar))
for col, (nombre, campo, unidad, color_delta) in zip(cols, metricas_comparar):
    valor_a = float(fila_a[campo])
    valor_b = float(fila_b[campo])
    delta = valor_b - valor_a
    col.metric(
        nombre,
        f"{valor_b:.2f} {unidad}".strip(),
        delta=f"{delta:+.2f} {unidad}".strip(),
        delta_color=color_delta,
    )

st.caption(
    f"Comparando **{fila_a['fecha']}** → **{fila_b['fecha']}**. "
    "Verde = mejora respecto a la sesión de referencia, rojo = descenso."
)

# --------------------------------------------------------------------------
# HISTORIAL COMPLETO Y GESTIÓN
# --------------------------------------------------------------------------
st.divider()
st.subheader("📜 Historial completo")

tabla_mostrar = historial[
    ["fecha", "e1rm", "r2", "fatiga_max", "carga_optima_potencia", "potencia_maxima"]
].rename(columns={
    "fecha": "Fecha", "e1rm": "e1RM (kg)", "r2": "R²", "fatiga_max": "Fatiga Máx (%)",
    "carga_optima_potencia": "Carga Óptima (kg)", "potencia_maxima": "Potencia Máx (W)",
})
st.dataframe(tabla_mostrar, use_container_width=True, hide_index=True)

with st.expander("🗑️ Eliminar una sesión del historial"):
    id_map = {f"{row['fecha']} — e1RM {row['e1rm']:.1f} kg": row["id"] for _, row in historial.iterrows()}
    sel_borrar = st.selectbox("Selecciona la sesión a eliminar", list(id_map.keys()))
    if st.button("Eliminar sesión seleccionada"):
        database.eliminar_sesion(int(id_map[sel_borrar]))
        st.success("Sesión eliminada.")
        st.rerun()
