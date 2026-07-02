# -*- coding: utf-8 -*-
"""
================================================================================
 estilos.py — Identidad visual de la app (CSS + componentes reutilizables)
================================================================================
"""

import streamlit as st


def aplicar_estilos() -> None:
    """Inyecta el CSS global de la aplicación. Llamar una sola vez, en app.py."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Cabecera degradado de cada página */
        .vbt-header {
            background: linear-gradient(135deg, #1E293B 0%, #2563EB 100%);
            padding: 1.8rem 2.2rem;
            border-radius: 18px;
            color: white;
            margin-bottom: 1.6rem;
            box-shadow: 0 8px 24px rgba(37, 99, 235, 0.25);
        }
        .vbt-header h1 {
            margin: 0;
            font-size: 1.7rem;
            font-weight: 800;
            color: white;
        }
        .vbt-header p {
            margin: 0.4rem 0 0 0;
            opacity: 0.88;
            font-size: 0.98rem;
            color: #E2E8F0;
        }

        /* Tarjetas de st.metric */
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 14px;
            padding: 0.9rem 1.1rem;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stMetricLabel"] {
            font-weight: 600;
            color: #475569;
        }
        div[data-testid="stMetricValue"] {
            color: #0F172A;
        }

        /* Botones primarios */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
            border: none;
            border-radius: 10px;
            font-weight: 700;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        }

        /* Separadores con más aire */
        hr {
            margin: 1.6rem 0;
        }

        /* Tarjetas informativas (st.info / st.success / st.warning) */
        div[data-testid="stAlert"] {
            border-radius: 12px;
        }

        /* Reducir espacio superior general */
        .block-container {
            padding-top: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def encabezado_pagina(titulo: str, subtitulo: str) -> None:
    """Renderiza un encabezado degradado consistente para cada página."""
    st.markdown(
        f"""
        <div class="vbt-header">
            <h1>{titulo}</h1>
            <p>{subtitulo}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
