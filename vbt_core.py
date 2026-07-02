# -*- coding: utf-8 -*-
"""
================================================================================
 vbt_core.py — Lógica de negocio del análisis VBT (Velocity-Based Training)
--------------------------------------------------------------------------------
 Este módulo NO contiene código de interfaz (Streamlit). Solo funciones puras
 de cálculo, validación y generación de gráficos Plotly, para poder ser
 reutilizadas desde cualquier página de la app sin duplicar lógica.
================================================================================
"""

from dataclasses import dataclass
from typing import Tuple, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

# ==============================================================================
# CONSTANTES DEL DOMINIO VBT
# ==============================================================================

GRAVEDAD = 9.81  # m/s^2

# Umbrales Mínimos de Velocidad (MVT) estándar reportados en la literatura VBT.
MVT_POR_EJERCICIO = {
    "Press de Banca": 0.15,
    "Sentadilla": 0.30,
    "Peso Muerto": 0.15,
    "Press Militar": 0.15,
    "Remo con Barra": 0.20,
    "Personalizado": None,
}

COLUMNAS_REQUERIDAS = [
    "Carga (kg)",
    "Velocidad Media (m/s)",
    "Velocidad Pico (m/s)",
    "Repetición",
    "Número de Serie",
]

# Configuración estándar de Plotly para TODOS los gráficos de la app.
# displayModeBar=True es la clave para que funcione bien en móvil: por defecto
# Plotly solo muestra la barra de herramientas "al pasar el mouse" (hover),
# un gesto que NO existe en pantallas táctiles, así que en el celular la
# barra nunca aparecía y parecía que el gráfico "no era interactivo" ni se
# podía resetear el zoom. Forzarla a visible soluciona ambos problemas.
CONFIG_PLOTLY = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": True,  # permite hacer pellizco (pinch) para zoom en móvil
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "doubleClick": "reset+autosize",  # doble toque = resetear zoom
    "responsive": True,
}


@dataclass
class ResultadoRegresion:
    """Contenedor de los resultados de la regresión Carga-Velocidad."""
    pendiente: float
    intercepto: float
    r_cuadrado: float
    e1rm: float
    mvt_usado: float


# ==============================================================================
# GENERACIÓN Y CARGA DE DATOS
# ==============================================================================

def generar_datos_ejemplo(semilla: int = 42) -> pd.DataFrame:
    """Simula un test progresivo de cargas (Press de Banca) con fatiga intra-serie."""
    rng = np.random.default_rng(semilla)

    plan_series = [
        {"carga": 40, "reps": 3},
        {"carga": 60, "reps": 3},
        {"carga": 80, "reps": 2},
        {"carga": 90, "reps": 2},
    ]

    filas = []
    for num_serie, serie in enumerate(plan_series, start=1):
        carga = serie["carga"]
        reps = serie["reps"]
        velocidad_base = max(1.10 - (carga / 100) * 0.95, 0.05)

        for rep in range(1, reps + 1):
            perdida_fatiga = (rep - 1) * rng.uniform(0.03, 0.07)
            ruido = rng.normal(0, 0.015)
            v_media = max(velocidad_base - perdida_fatiga + ruido, 0.03)
            v_pico = v_media * rng.uniform(1.15, 1.30)

            filas.append(
                {
                    "Número de Serie": num_serie,
                    "Carga (kg)": carga,
                    "Repetición": rep,
                    "Velocidad Media (m/s)": round(v_media, 3),
                    "Velocidad Pico (m/s)": round(v_pico, 3),
                }
            )

    return pd.DataFrame(filas)


def cargar_archivo(archivo_subido) -> pd.DataFrame:
    """Lee un archivo CSV o Excel subido por el usuario."""
    nombre = archivo_subido.name.lower()
    try:
        if nombre.endswith(".csv"):
            df = pd.read_csv(archivo_subido)
        elif nombre.endswith((".xlsx", ".xls")):
            df = pd.read_excel(archivo_subido)
        else:
            raise ValueError("Formato no soportado. Sube un archivo .csv, .xlsx o .xls.")
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"No se pudo leer el archivo. Detalle técnico: {exc}") from exc
    return df


def validar_columnas(df: pd.DataFrame) -> Tuple[bool, list]:
    """Verifica que el DataFrame contenga las columnas mínimas necesarias."""
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    return (len(faltantes) == 0), faltantes


def limpiar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte las columnas numéricas y descarta filas inválidas."""
    df = df.copy()
    for col in COLUMNAS_REQUERIDAS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=COLUMNAS_REQUERIDAS)


# ==============================================================================
# MÓDULO 1: PERFIL CARGA-VELOCIDAD Y e1RM
# ==============================================================================

def construir_df_perfil(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye el subconjunto usado para el perfil Carga-Velocidad: la
    repetición más rápida de cada carga (evita contaminar la regresión con
    la fatiga acumulada dentro de la serie).
    """
    return (
        df.sort_values("Velocidad Media (m/s)", ascending=False)
        .drop_duplicates(subset=["Carga (kg)"], keep="first")
        .sort_values("Carga (kg)")
    )


def calcular_perfil_carga_velocidad(df_perfil: pd.DataFrame, mvt: float) -> ResultadoRegresion:
    """
    Ajusta una regresión lineal Carga-Velocidad y extrapola el e1RM al MVT.

        e1RM = (MVT - intercepto) / pendiente
    """
    cargas_unicas = df_perfil["Carga (kg)"].nunique()
    if cargas_unicas < 3:
        raise ValueError(
            "Se necesitan al menos 3 cargas distintas para que la regresión "
            "Carga-Velocidad y el e1RM sean estadísticamente fiables. "
            f"Actualmente hay {cargas_unicas} carga(s) distinta(s)."
        )

    x = df_perfil["Carga (kg)"].to_numpy(dtype=float)
    y = df_perfil["Velocidad Media (m/s)"].to_numpy(dtype=float)

    pendiente, intercepto, r_valor, _p, _err = stats.linregress(x, y)
    r_cuadrado = r_valor ** 2

    if pendiente >= 0:
        raise ValueError(
            "La pendiente de la regresión es positiva o nula (no físicamente "
            "coherente: la velocidad debería disminuir al aumentar la carga). "
            "Revisa la calidad de los datos."
        )

    e1rm = (mvt - intercepto) / pendiente

    return ResultadoRegresion(pendiente, intercepto, r_cuadrado, e1rm, mvt)


def velocidad_primera_repeticion(df: pd.DataFrame) -> float:
    """Velocidad de la primera repetición de la carga más alta (frescura neuromuscular)."""
    carga_max = df["Carga (kg)"].max()
    subset = df[(df["Carga (kg)"] == carga_max) & (df["Repetición"] == df["Repetición"].min())]
    if subset.empty:
        return float("nan")
    return float(subset["Velocidad Media (m/s)"].iloc[0])


def graficar_perfil_carga_velocidad(df_perfil: pd.DataFrame, resultado: ResultadoRegresion) -> go.Figure:
    """Gráfico de dispersión Carga vs. Velocidad Media + línea de regresión + e1RM."""
    x = df_perfil["Carga (kg)"].to_numpy(dtype=float)
    y = df_perfil["Velocidad Media (m/s)"].to_numpy(dtype=float)

    x_max_grafico = max(resultado.e1rm, x.max()) * 1.05
    x_linea = np.linspace(0, x_max_grafico, 100)
    y_linea = resultado.pendiente * x_linea + resultado.intercepto

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers", name="Repeticiones registradas",
        marker=dict(size=12, color="#2563EB", line=dict(width=1, color="white")),
    ))
    fig.add_trace(go.Scatter(
        x=x_linea, y=y_linea, mode="lines", name="Regresión lineal (ajuste)",
        line=dict(color="#F97316", width=3),
    ))
    fig.add_hline(
        y=resultado.mvt_usado, line_dash="dot", line_color="#DC2626",
        annotation_text=f"MVT = {resultado.mvt_usado} m/s", annotation_position="top left",
    )
    fig.add_trace(go.Scatter(
        x=[resultado.e1rm], y=[resultado.mvt_usado], mode="markers+text",
        name="e1RM estimado", marker=dict(size=16, color="#DC2626", symbol="star"),
        text=[f"e1RM ≈ {resultado.e1rm:.1f} kg"], textposition="bottom center",
    ))

    fig.update_layout(
        title="Perfil Carga-Velocidad y Estimación del e1RM",
        xaxis_title="Carga (kg)", yaxis_title="Velocidad Media (m/s)",
        template="plotly_white", dragmode="pan",  # 'pan' es más natural en móvil que el zoom por caja
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="closest", margin=dict(t=60),
    )
    return fig


# ==============================================================================
# MÓDULO 2: PÉRDIDA DE VELOCIDAD INTRA-SERIE (FATIGA)
# ==============================================================================

def calcular_perdida_velocidad(serie_df: pd.DataFrame) -> float:
    """Fatiga (%) = ((V_max - V_min) / V_max) * 100."""
    v_max = serie_df["Velocidad Media (m/s)"].max()
    v_min = serie_df["Velocidad Media (m/s)"].min()
    if v_max == 0:
        return 0.0
    return ((v_max - v_min) / v_max) * 100


def calcular_fatiga_maxima_global(df: pd.DataFrame) -> float:
    """Calcula la mayor pérdida de velocidad registrada entre todas las series de la sesión."""
    valores = []
    for _num_serie, grupo in df.groupby("Número de Serie"):
        if len(grupo) >= 2:
            valores.append(calcular_perdida_velocidad(grupo))
    return max(valores) if valores else 0.0


def graficar_perdida_velocidad(serie_df: pd.DataFrame, fatiga_pct: float) -> go.Figure:
    """Evolución de la velocidad media repetición a repetición dentro de una serie."""
    serie_ordenada = serie_df.sort_values("Repetición")

    if fatiga_pct < 15:
        color_linea = "#16A34A"
    elif fatiga_pct < 30:
        color_linea = "#F59E0B"
    else:
        color_linea = "#DC2626"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=serie_ordenada["Repetición"], y=serie_ordenada["Velocidad Media (m/s)"],
        mode="lines+markers", name="Velocidad Media por Repetición",
        line=dict(color=color_linea, width=3), marker=dict(size=11),
    ))
    fig.update_layout(
        title=f"Pérdida de Velocidad Intra-Serie — Fatiga: {fatiga_pct:.1f}%",
        xaxis_title="Número de Repetición", yaxis_title="Velocidad Media (m/s)",
        template="plotly_white", xaxis=dict(dtick=1), dragmode="pan", margin=dict(t=60),
    )
    return fig


# ==============================================================================
# MÓDULO 3: PERFIL DE POTENCIA
# ==============================================================================

def calcular_potencia(df: pd.DataFrame) -> pd.DataFrame:
    """Potencia (W) = Carga (kg) * g * Velocidad Media (m/s)."""
    df_potencia = df.copy()
    df_potencia["Potencia (W)"] = df_potencia["Carga (kg)"] * GRAVEDAD * df_potencia["Velocidad Media (m/s)"]
    return df_potencia


def calcular_carga_optima_potencia(df_potencia: pd.DataFrame) -> Tuple[float, float, pd.DataFrame]:
    """Determina la carga asociada a la máxima potencia media registrada."""
    potencia_por_carga = (
        df_potencia.groupby("Carga (kg)", as_index=False)["Potencia (W)"].mean()
    ).sort_values("Carga (kg)")
    idx_max = potencia_por_carga["Potencia (W)"].idxmax()
    carga_optima = float(potencia_por_carga.loc[idx_max, "Carga (kg)"])
    potencia_maxima = float(potencia_por_carga.loc[idx_max, "Potencia (W)"])
    return carga_optima, potencia_maxima, potencia_por_carga


def graficar_perfil_potencia(df_potencia: pd.DataFrame) -> Tuple[go.Figure, float, float]:
    """Curva Carga vs. Potencia con la Zona de Máxima Potencia resaltada."""
    carga_optima, potencia_maxima, potencia_por_carga = calcular_carga_optima_potencia(df_potencia)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_potencia["Carga (kg)"], y=df_potencia["Potencia (W)"], mode="markers",
        name="Repeticiones individuales", marker=dict(size=8, color="#94A3B8", opacity=0.6),
    ))
    fig.add_trace(go.Scatter(
        x=potencia_por_carga["Carga (kg)"], y=potencia_por_carga["Potencia (W)"],
        mode="lines+markers", name="Potencia media por carga",
        line=dict(color="#7C3AED", width=3, shape="spline"), marker=dict(size=12),
    ))
    fig.add_trace(go.Scatter(
        x=[carga_optima], y=[potencia_maxima], mode="markers+text", name="Zona de Máxima Potencia",
        marker=dict(size=17, color="#DC2626", symbol="diamond"),
        text=[f"{carga_optima:.0f} kg / {potencia_maxima:.0f} W"], textposition="top center",
    ))

    fig.update_layout(
        title="Perfil de Potencia: Carga vs. Potencia Media Generada",
        xaxis_title="Carga (kg)", yaxis_title="Potencia (W)", template="plotly_white",
        dragmode="pan", margin=dict(t=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig, carga_optima, potencia_maxima


# ==============================================================================
# CÁLCULO CONSOLIDADO PARA GUARDAR UNA SESIÓN EN EL HISTORIAL
# ==============================================================================

def calcular_metricas_sesion(df: pd.DataFrame, mvt: float) -> dict:
    """
    Calcula, de una sola vez y de forma independiente a qué páginas haya
    visitado el usuario, todas las métricas necesarias para guardar una
    sesión en el historial de progresión.
    """
    df_perfil = construir_df_perfil(df)
    resultado = calcular_perfil_carga_velocidad(df_perfil, mvt)

    df_potencia = calcular_potencia(df)
    carga_optima, potencia_maxima, _ = calcular_carga_optima_potencia(df_potencia)

    return {
        "e1rm": resultado.e1rm,
        "r2": resultado.r_cuadrado,
        "pendiente": resultado.pendiente,
        "intercepto": resultado.intercepto,
        "velocidad_primera_rep": velocidad_primera_repeticion(df),
        "fatiga_max": calcular_fatiga_maxima_global(df),
        "carga_optima_potencia": carga_optima,
        "potencia_maxima": potencia_maxima,
    }


# ==============================================================================
# INTERPRETACIONES FÍSICAS / FISIOLÓGICAS (TEXTO DINÁMICO)
# ==============================================================================

def interpretar_perfil_fuerza_velocidad(resultado: ResultadoRegresion, ejercicio: str) -> str:
    pendiente_abs = abs(resultado.pendiente)

    if pendiente_abs < 0.006:
        perfil_texto = (
            "un perfil orientado hacia la **Fuerza Máxima** ('fuerte-lento'). "
            "Su velocidad decae relativamente poco por cada kilogramo añadido, "
            "lo que sugiere una alta capacidad de reclutamiento de unidades "
            "motoras de alto umbral incluso a cargas elevadas."
        )
    elif pendiente_abs > 0.010:
        perfil_texto = (
            "un perfil orientado hacia la **Velocidad/Explosividad** "
            "('rápido-explosivo'). Su velocidad cae abruptamente a medida que "
            "aumenta la carga, lo que indica mayor dependencia de fibras "
            "rápidas (tipo II) y menor tolerancia a cargas pesadas en términos "
            "de velocidad de ejecución."
        )
    else:
        perfil_texto = (
            "un perfil **equilibrado** entre fuerza y velocidad, sin una "
            "inclinación marcada hacia ninguno de los dos extremos del "
            "continuo Fuerza-Velocidad."
        )

    calidad_r2 = (
        "excelente (R² ≥ 0.95, típico de encoders lineales en condiciones controladas)"
        if resultado.r_cuadrado >= 0.95
        else "aceptable, aunque se recomienda revisar la técnica o el número de "
        "puntos de carga para mejorar la fiabilidad"
        if resultado.r_cuadrado >= 0.85
        else "baja, por lo que el e1RM calculado debe interpretarse con cautela"
    )

    return f"""
**🔬 Relación Fuerza-Velocidad (Ley de Hill y 2ª Ley de Newton)**

La pendiente de la regresión obtenida es **{resultado.pendiente:.4f} (m/s)/kg**, con un
coeficiente de determinación **R² = {resultado.r_cuadrado:.3f}** ({calidad_r2}).

Según la 2ª Ley de Newton (F = m·a), para desplazar una carga mayor con la misma
fuerza muscular disponible, la aceleración —y por tanto la velocidad de
ejecución— debe reducirse necesariamente. La curva de Hill describe esta misma
relación a nivel de la fibra muscular: a mayor tensión requerida, menor es la
velocidad de acortamiento posible del sarcómero.

En este caso, el atleta muestra {perfil_texto}
"""


def interpretar_e1rm(resultado: ResultadoRegresion, ejercicio: str) -> str:
    return f"""
**📐 Interpretación Física del e1RM**

El **1RM Estimado (e1RM)** de **{resultado.e1rm:.1f} kg** se obtiene extrapolando la
recta de regresión Carga-Velocidad hasta el punto en que la velocidad teórica
iguala el **Umbral Mínimo de Velocidad (MVT = {resultado.mvt_usado} m/s)** definido
para {ejercicio}.

Físicamente, el MVT representa la velocidad a la cual se asume que el atleta
alcanzaría el **fallo concéntrico funcional**: el punto en el que la fuerza
muscular disponible iguala exactamente la fuerza requerida por la carga
externa, y la aceleración neta tiende a cero.

Es una **extrapolación matemática**, no una carga levantada realmente ese día.
Su precisión depende del ajuste lineal (R² = {resultado.r_cuadrado:.3f}) y del
número de cargas submáximas usadas para construir el perfil.
"""


def interpretar_fatiga(fatiga_pct: float) -> str:
    if fatiga_pct < 15:
        categoria = "**BAJA** 🟢"
        explicacion = (
            "Una pérdida de velocidad inferior al 15% se asocia con un "
            "predominio del **estrés mecánico** sobre el metabólico. El "
            "reclutamiento de unidades motoras de alto umbral se mantiene "
            "estable durante toda la serie, favoreciendo adaptaciones "
            "neurales de **fuerza y potencia** con mínima fatiga periférica."
        )
    elif fatiga_pct < 30:
        categoria = "**MODERADA** 🟡"
        explicacion = (
            "Una pérdida de velocidad entre 15% y 30% indica fatiga "
            "neuromuscular moderada, con acumulación relevante de metabolitos "
            "y disminución progresiva en el reclutamiento de fibras rápidas "
            "(tipo II). Rango habitual del trabajo de hipertrofia con control "
            "de fatiga."
        )
    else:
        categoria = "**ALTA** 🔴"
        explicacion = (
            "Una pérdida de velocidad superior al 30% refleja un **alto "
            "estrés metabólico**: las fibras rápidas reducen drásticamente su "
            "capacidad de generar fuerza, obligando a un reclutamiento "
            "compensatorio de fibras lentas. Maximiza el estímulo de "
            "hipertrofia metabólica, pero incrementa el tiempo de recuperación "
            "necesario."
        )

    return f"""
**🧬 Fisiología de la Fatiga Neuromuscular**

Pérdida de velocidad calculada: **{fatiga_pct:.1f}%** → Categoría: {categoria}

{explicacion}
"""
