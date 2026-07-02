# -*- coding: utf-8 -*-
"""
================================================================================
 app.py — Punto de entrada de VBT Analytics (navegación multi-página)
--------------------------------------------------------------------------------
 Instalación:
     pip install -r requirements.txt

 Ejecución:
     streamlit run app.py
================================================================================
"""

import streamlit as st

import database
from estilos import aplicar_estilos

st.set_page_config(
    page_title="VBT Analytics | Entrenamiento Basado en Velocidad",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_estilos()
database.inicializar_db()

# Valores por defecto del estado de la sesión (compartidos entre páginas)
valores_por_defecto = {
    "df": None,
    "ejercicio": "Press de Banca",
    "mvt": 0.15,
    "atleta": "",
    "fecha_sesion": None,
}
for clave, valor in valores_por_defecto.items():
    st.session_state.setdefault(clave, valor)

# --------------------------------------------------------------------------
# Definición de páginas y navegación
# --------------------------------------------------------------------------
pagina_inicio = st.Page("views/inicio.py", title="Inicio", icon="🏠", default=True)
pagina_carga = st.Page("views/cargar_datos.py", title="Cargar Datos", icon="📂")
pagina_perfil = st.Page("views/perfil_fuerza_velocidad.py", title="Perfil Fuerza-Velocidad", icon="📈")
pagina_fatiga = st.Page("views/fatiga_intra_serie.py", title="Fatiga Intra-Serie", icon="📉")
pagina_potencia = st.Page("views/perfil_potencia.py", title="Perfil de Potencia", icon="💥")
pagina_progresion = st.Page("views/progresion_historica.py", title="Progresión Histórica", icon="📊")

pg = st.navigation(
    {
        "Panel Principal": [pagina_inicio],
        "Análisis de Sesión": [pagina_carga, pagina_perfil, pagina_fatiga, pagina_potencia],
        "Seguimiento a Largo Plazo": [pagina_progresion],
    }
)

with st.sidebar:
    st.markdown("### 🏋️ VBT Analytics")
    st.caption("Entrenamiento Basado en Velocidad")
    st.divider()

pg.run()
