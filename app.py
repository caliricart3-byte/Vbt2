# -*- coding: utf-8 -*-
"""
================================================================================
 APP DE ANÁLISIS VBT (VELOCITY-BASED TRAINING)
 Autor: Desarrollador Senior Python / Científico de Datos Deportivo
--------------------------------------------------------------------------------
 Aplicación interactiva para entrenadores y atletas de fuerza que permite:
   1. Cargar datos de velocidad de levantamientos (CSV/Excel) o generar
      un set de datos de ejemplo simulado.
   2. Calcular el Perfil Carga-Velocidad (regresión lineal) y estimar el
      1RM diario (e1RM) mediante extrapolación al Umbral Mínimo de
      Velocidad (MVT).
   3. Analizar la pérdida de velocidad dentro de una serie (fatiga
      neuromuscular intra-serie).
   4. Calcular el Perfil de Potencia y detectar la carga óptima de
      máxima potencia.
   5. Interpretar los resultados con fundamentos de biomecánica y
      fisiología del entrenamiento de fuerza.

 Instalación:
     pip install streamlit pandas numpy plotly scipy openpyxl

 Ejecución:
     streamlit run app.py
================================================================================
"""

import io
from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

# ==============================================================================
# 1. CONFIGURACIÓN GENERAL DE LA PÁGINA Y CONSTANTES DEL DOMINIO VBT
# ==============================================================================

st.set_page_config(
    page_title="VBT Analytics | Entrenamiento Basado en Velocidad",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

GRAVEDAD = 9.81  # m/s^2 -> constante física para el cálculo de potencia

# Umbrales Mínimos de Velocidad (MVT) estándar reportados en la literatura VBT
# para distintos ejercicios. Estos valores representan la velocidad a la cual
# se asume que la carga movilizada corresponde al 100% de 1RM (fallo concéntrico
# funcional). Fuente: González-Badillo & Sánchez-Medina; Jovanović & Flanagan, etc.
MVT_POR_EJERCICIO = {
    "Press de Banca": 0.15,
    "Sentadilla": 0.30,
    "Peso Muerto": 0.15,
    "Press Militar": 0.15,
    "Remo con Barra": 0.20,
    "Personalizado": None,  # El usuario define su propio MVT
}

COLUMNAS_REQUERIDAS = [
    "Carga (kg)",
    "Velocidad Media (m/s)",
    "Velocidad Pico (m/s)",
    "Repetición",
    "Número de Serie",
]


# ==============================================================================
# 2. ESTRUCTURAS DE DATOS Y RESULTADOS DEL MODELO
# ==============================================================================

@dataclass
class ResultadoRegresion:
    """Contenedor de los resultados de la regresión Carga-Velocidad."""
    pendiente: float
    intercepto: float
    r_cuadrado: float
    e1rm: float
    mvt_usado: float


# ==============================================================================
# 3. GENERACIÓN DE DATOS DE EJEMPLO (SIMULACIÓN DE TEST PROGRESIVO DE CARGAS)
# ==============================================================================

def generar_datos_ejemplo(semilla: int = 42) -> pd.DataFrame:
    """
    Simula un test progresivo de cargas típico de un protocolo VBT
    (Press de Banca) con series a distintos porcentajes de 1RM.

    Se simula ruido biológico realista (variabilidad inter-repetición e
    inter-serie) y una caída de velocidad progresiva dentro de cada serie
    para representar fatiga neuromuscular.

    Retorna
    -------
    pd.DataFrame
        Dataset sintético con las columnas estándar requeridas por la app.
    """
    rng = np.random.default_rng(semilla)

    # Cargas de un test progresivo típico y repeticiones planificadas por serie.
    # A mayor carga, menos repeticiones (protocolo estándar de perfilado).
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

        # Relación Carga-Velocidad aproximadamente lineal (perfil sintético
        # de un atleta con 1RM teórico ~100 kg y MVT ~0.15 m/s).
        velocidad_base = 1.10 - (carga / 100) * 0.95
        velocidad_base = max(velocidad_base, 0.05)

        for rep in range(1, reps + 1):
            # Fatiga intra-serie: cada repetición sucesiva pierde velocidad.
            perdida_fatiga = (rep - 1) * rng.uniform(0.03, 0.07)
            ruido = rng.normal(0, 0.015)

            v_media = max(velocidad_base - perdida_fatiga + ruido, 0.03)
            v_pico = v_media * rng.uniform(1.15, 1.30)  # la pico siempre > media

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


# ==============================================================================
# 4. CARGA Y VALIDACIÓN DE DATOS DEL USUARIO
# ==============================================================================

def cargar_archivo(archivo_subido) -> pd.DataFrame:
    """
    Lee un archivo CSV o Excel subido por el usuario y lo convierte
    en un DataFrame de pandas.

    Parámetros
    ----------
    archivo_subido : UploadedFile
        Objeto de archivo entregado por st.file_uploader.

    Retorna
    -------
    pd.DataFrame

    Lanza
    -----
    ValueError
        Si la extensión del archivo no es soportada o el archivo está
        corrupto/ilegible.
    """
    nombre = archivo_subido.name.lower()
    try:
        if nombre.endswith(".csv"):
            df = pd.read_csv(archivo_subido)
        elif nombre.endswith((".xlsx", ".xls")):
            df = pd.read_excel(archivo_subido)
        else:
            raise ValueError(
                "Formato de archivo no soportado. Sube un archivo .csv, .xlsx o .xls."
            )
    except Exception as exc:  # pragma: no cover - manejo defensivo genérico
        raise ValueError(f"No se pudo leer el archivo. Detalle técnico: {exc}") from exc

    return df


def validar_columnas(df: pd.DataFrame) -> Tuple[bool, list]:
    """
    Verifica que el DataFrame contenga las columnas mínimas necesarias
    para el análisis VBT.

    Retorna
    -------
    (bool, list)
        Booleano indicando si es válido, y lista de columnas faltantes.
    """
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    return (len(faltantes) == 0), faltantes


# ==============================================================================
# 5. MÓDULO 1: PERFIL CARGA-VELOCIDAD Y ESTIMACIÓN DEL 1RM (e1RM)
# ==============================================================================

def calcular_perfil_carga_velocidad(
    df: pd.DataFrame, mvt: float
) -> ResultadoRegresion:
    """
    Ajusta una regresión lineal simple (mínimos cuadrados) entre la Carga (kg)
    y la Velocidad Media (m/s), y extrapola el 1RM estimado (e1RM) evaluando
    la recta de regresión en el Umbral Mínimo de Velocidad (MVT).

    Fundamento físico:
        Se asume una relación lineal Carga-Velocidad (modelo de
        González-Badillo). La recta ajustada es:
            V = pendiente * Carga + intercepto
        Despejando Carga cuando V = MVT (velocidad a la que el atleta
        alcanzaría el fallo concéntrico funcional):
            e1RM = (MVT - intercepto) / pendiente

    Parámetros
    ----------
    df : pd.DataFrame
        Debe contener 'Carga (kg)' y 'Velocidad Media (m/s)'. Se recomienda
        usar únicamente la repetición más rápida (o la primera repetición
        "limpia") de cada carga para evitar contaminar el perfil con fatiga.
    mvt : float
        Umbral mínimo de velocidad (m/s) del ejercicio.

    Retorna
    -------
    ResultadoRegresion

    Lanza
    -----
    ValueError
        Si hay menos de 3 cargas distintas (la regresión no sería fiable).
    """
    cargas_unicas = df["Carga (kg)"].nunique()
    if cargas_unicas < 3:
        raise ValueError(
            "Se necesitan al menos 3 cargas distintas para que la regresión "
            "Carga-Velocidad y el e1RM sean estadísticamente fiables. "
            f"Actualmente hay {cargas_unicas} carga(s) distinta(s) en los datos."
        )

    x = df["Carga (kg)"].to_numpy(dtype=float)
    y = df["Velocidad Media (m/s)"].to_numpy(dtype=float)

    pendiente, intercepto, r_valor, _p_valor, _err_std = stats.linregress(x, y)
    r_cuadrado = r_valor ** 2

    if pendiente >= 0:
        # Físicamente, la velocidad SIEMPRE debe disminuir al aumentar la carga
        # (F = m*a; a mayor masa a desplazar, para una fuerza muscular similar,
        # la aceleración -y por ende la velocidad- disminuye). Una pendiente
        # positiva indica datos anómalos o insuficientes.
        raise ValueError(
            "La pendiente de la regresión es positiva o nula, lo cual no es "
            "físicamente coherente (la velocidad debería disminuir al "
            "aumentar la carga). Revisa la calidad de los datos ingresados."
        )

    e1rm = (mvt - intercepto) / pendiente

    return ResultadoRegresion(
        pendiente=pendiente,
        intercepto=intercepto,
        r_cuadrado=r_cuadrado,
        e1rm=e1rm,
        mvt_usado=mvt,
    )


def graficar_perfil_carga_velocidad(
    df: pd.DataFrame, resultado: ResultadoRegresion
) -> go.Figure:
    """
    Construye el gráfico de dispersión Carga vs. Velocidad Media junto con
    la línea de regresión y el punto de e1RM extrapolado.
    """
    x = df["Carga (kg)"].to_numpy(dtype=float)
    y = df["Velocidad Media (m/s)"].to_numpy(dtype=float)

    # Línea de regresión extendida hasta el e1RM para visualizar la extrapolación.
    x_max_grafico = max(resultado.e1rm, x.max()) * 1.05
    x_linea = np.linspace(0, x_max_grafico, 100)
    y_linea = resultado.pendiente * x_linea + resultado.intercepto

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="markers",
            name="Repeticiones registradas",
            marker=dict(size=11, color="#2563EB", line=dict(width=1, color="white")),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x_linea,
            y=y_linea,
            mode="lines",
            name="Regresión lineal (ajuste)",
            line=dict(color="#F97316", width=3),
        )
    )

    # Línea horizontal del MVT
    fig.add_hline(
        y=resultado.mvt_usado,
        line_dash="dot",
        line_color="#DC2626",
        annotation_text=f"MVT = {resultado.mvt_usado} m/s",
        annotation_position="top left",
    )

    # Punto del e1RM extrapolado
    fig.add_trace(
        go.Scatter(
            x=[resultado.e1rm],
            y=[resultado.mvt_usado],
            mode="markers+text",
            name="e1RM estimado",
            marker=dict(size=15, color="#DC2626", symbol="star"),
            text=[f"e1RM ≈ {resultado.e1rm:.1f} kg"],
            textposition="bottom center",
        )
    )

    fig.update_layout(
        title="Perfil Carga-Velocidad y Estimación del e1RM",
        xaxis_title="Carga (kg)",
        yaxis_title="Velocidad Media (m/s)",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="closest",
    )

    return fig


# ==============================================================================
# 6. MÓDULO 2: PÉRDIDA DE VELOCIDAD INTRA-SERIE (FATIGA NEUROMUSCULAR)
# ==============================================================================

def calcular_perdida_velocidad(serie_df: pd.DataFrame) -> float:
    """
    Calcula el porcentaje de pérdida de velocidad dentro de una serie,
    comparando la repetición más rápida contra la más lenta.

    Fórmula:
        Fatiga (%) = ((V_max - V_min) / V_max) * 100

    Parámetros
    ----------
    serie_df : pd.DataFrame
        Subconjunto de datos filtrado para una única serie (mismo número
        de serie), ordenado por repetición.

    Retorna
    -------
    float
        Porcentaje de pérdida de velocidad (0-100).
    """
    v_max = serie_df["Velocidad Media (m/s)"].max()
    v_min = serie_df["Velocidad Media (m/s)"].min()

    if v_max == 0:
        return 0.0

    return ((v_max - v_min) / v_max) * 100


def graficar_perdida_velocidad(serie_df: pd.DataFrame, fatiga_pct: float) -> go.Figure:
    """
    Grafica la evolución de la velocidad media repetición a repetición
    dentro de una serie, para visualizar la caída por fatiga.
    """
    serie_ordenada = serie_df.sort_values("Repetición")

    # Color dinámico según severidad de la fatiga
    if fatiga_pct < 15:
        color_linea = "#16A34A"  # verde: pérdida baja
    elif fatiga_pct < 30:
        color_linea = "#F59E0B"  # ámbar: pérdida moderada
    else:
        color_linea = "#DC2626"  # rojo: pérdida alta

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=serie_ordenada["Repetición"],
            y=serie_ordenada["Velocidad Media (m/s)"],
            mode="lines+markers",
            name="Velocidad Media por Repetición",
            line=dict(color=color_linea, width=3),
            marker=dict(size=10),
        )
    )

    fig.update_layout(
        title=f"Pérdida de Velocidad Intra-Serie — Fatiga: {fatiga_pct:.1f}%",
        xaxis_title="Número de Repetición",
        yaxis_title="Velocidad Media (m/s)",
        template="plotly_white",
        xaxis=dict(dtick=1),
    )

    return fig


# ==============================================================================
# 7. MÓDULO 3: PERFIL DE POTENCIA
# ==============================================================================

def calcular_potencia(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula la potencia relativa aproximada para cada registro:
        Potencia (W) = Carga (kg) * g (9.81 m/s^2) * Velocidad Media (m/s)

    Este cálculo aproxima la potencia mecánica desarrollada durante la fase
    concéntrica, asumiendo un desplazamiento vertical de la carga (trabajo
    contra la gravedad), lo cual es la simplificación estándar usada por la
    mayoría de encoders lineales VBT comerciales.

    Retorna
    -------
    pd.DataFrame
        Copia del DataFrame original con la columna añadida 'Potencia (W)'.
    """
    df_potencia = df.copy()
    df_potencia["Potencia (W)"] = (
        df_potencia["Carga (kg)"] * GRAVEDAD * df_potencia["Velocidad Media (m/s)"]
    )
    return df_potencia


def graficar_perfil_potencia(df_potencia: pd.DataFrame) -> Tuple[go.Figure, float, float]:
    """
    Grafica la curva Carga vs. Potencia (relación parabólica esperada según
    la Ley de Hill) y determina la carga asociada a la máxima potencia media
    registrada (Zona de Máxima Potencia).

    Retorna
    -------
    (go.Figure, float, float)
        Figura de Plotly, carga óptima (kg) y potencia máxima (W).
    """
    # Promedio de potencia por carga (para suavizar el ruido inter-repetición)
    potencia_por_carga = (
        df_potencia.groupby("Carga (kg)", as_index=False)["Potencia (W)"].mean()
    ).sort_values("Carga (kg)")

    idx_max = potencia_por_carga["Potencia (W)"].idxmax()
    carga_optima = potencia_por_carga.loc[idx_max, "Carga (kg)"]
    potencia_maxima = potencia_por_carga.loc[idx_max, "Potencia (W)"]

    fig = go.Figure()

    # Todos los puntos individuales (repetición a repetición)
    fig.add_trace(
        go.Scatter(
            x=df_potencia["Carga (kg)"],
            y=df_potencia["Potencia (W)"],
            mode="markers",
            name="Repeticiones individuales",
            marker=dict(size=8, color="#94A3B8", opacity=0.6),
        )
    )

    # Curva promedio por carga
    fig.add_trace(
        go.Scatter(
            x=potencia_por_carga["Carga (kg)"],
            y=potencia_por_carga["Potencia (W)"],
            mode="lines+markers",
            name="Potencia media por carga",
            line=dict(color="#7C3AED", width=3, shape="spline"),
            marker=dict(size=11),
        )
    )

    # Punto de máxima potencia
    fig.add_trace(
        go.Scatter(
            x=[carga_optima],
            y=[potencia_maxima],
            mode="markers+text",
            name="Zona de Máxima Potencia",
            marker=dict(size=16, color="#DC2626", symbol="diamond"),
            text=[f"{carga_optima:.0f} kg / {potencia_maxima:.0f} W"],
            textposition="top center",
        )
    )

    fig.update_layout(
        title="Perfil de Potencia: Carga vs. Potencia Media Generada",
        xaxis_title="Carga (kg)",
        yaxis_title="Potencia (W)",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig, carga_optima, potencia_maxima


# ==============================================================================
# 8. TEXTOS DE INTERPRETACIÓN FÍSICA, BIOMECÁNICA Y FISIOLÓGICA (DINÁMICOS)
# ==============================================================================

def interpretar_perfil_fuerza_velocidad(resultado: ResultadoRegresion, ejercicio: str) -> str:
    """
    Genera un texto explicativo dinámico sobre el perfil Fuerza-Velocidad
    del atleta, en función de la pendiente obtenida y la calidad del ajuste (R²).
    """
    pendiente_abs = abs(resultado.pendiente)

    # Clasificación cualitativa del perfil según la magnitud de la pendiente.
    # Pendientes más "planas" (valor absoluto bajo) -> el atleta pierde poca
    # velocidad por cada kg añadido -> perfil orientado a fuerza máxima.
    # Pendientes más "pronunciadas" -> pierde mucha velocidad por kg -> perfil
    # más orientado a velocidad/explosividad, con menor capacidad de fuerza
    # máxima absoluta relativa a su velocidad a cargas ligeras.
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
            "aumenta la carga, lo que indica una mayor dependencia de fibras "
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
        else "aceptable, aunque se recomienda revisar la técnica de ejecución o el "
        "número de puntos de carga para mejorar la fiabilidad"
        if resultado.r_cuadrado >= 0.85
        else "baja, por lo que el e1RM calculado debe interpretarse con cautela"
    )

    texto = f"""
**🔬 Relación Fuerza-Velocidad (Ley de Hill y 2ª Ley de Newton)**

La pendiente de la regresión obtenida es **{resultado.pendiente:.4f} (m/s)/kg**, con un
coeficiente de determinación **R² = {resultado.r_cuadrado:.3f}** ({calidad_r2}).

Según la 2ª Ley de Newton (F = m·a), para desplazar una carga mayor con la misma
fuerza muscular disponible, la aceleración —y por tanto la velocidad de
ejecución— debe reducirse necesariamente. La curva de Hill describe esta misma
relación a nivel de la fibra muscular: a mayor tensión (carga) requerida, menor
es la velocidad de acortamiento posible del sarcómero, debido a la cinética de
los puentes cruzados de actina-miosina.

En este caso, el atleta muestra {perfil_texto}
"""
    return texto


def interpretar_e1rm(resultado: ResultadoRegresion, ejercicio: str) -> str:
    """
    Genera el texto explicativo sobre la extrapolación física del e1RM.
    """
    texto = f"""
**📐 Interpretación Física del e1RM**

El **1RM Estimado (e1RM)** de **{resultado.e1rm:.1f} kg** se obtiene extrapolando la
recta de regresión Carga-Velocidad hasta el punto en que la velocidad teórica
iguala el **Umbral Mínimo de Velocidad (MVT = {resultado.mvt_usado} m/s)** definido
para {ejercicio}.

Físicamente, el MVT representa la velocidad de ejecución a la cual se asume que
el atolete alcanzaría el **fallo concéntrico funcional**: el punto en el que la
fuerza muscular disponible iguala exactamente la fuerza requerida por la carga
externa (más el peso corporal del segmento movilizado), y la aceleración neta
tiende a cero. Por debajo de esta velocidad, la contracción muscular ya no
puede seguir venciendo la resistencia de forma efectiva y el movimiento se
detiene o colapsa técnicamente.

Es importante notar que el e1RM es una **extrapolación matemática**, no una
carga levantada realmente ese día. Su precisión depende directamente de la
calidad del ajuste lineal (R² = {resultado.r_cuadrado:.3f}) y del número de
cargas submáximas utilizadas para construir el perfil.
"""
    return texto


def interpretar_fatiga(fatiga_pct: float) -> str:
    """
    Genera el texto explicativo sobre la fisiología de la fatiga
    neuromuscular en función del porcentaje de pérdida de velocidad.
    """
    if fatiga_pct < 15:
        categoria = "**BAJA** 🟢"
        explicacion = (
            "Una pérdida de velocidad inferior al 15% se asocia en la literatura "
            "científica (González-Badillo et al.) con un predominio del **estrés "
            "mecánico** sobre el metabólico. El reclutamiento de unidades motoras "
            "de alto umbral se mantiene relativamente estable durante toda la serie, "
            "favoreciendo adaptaciones neurales de **fuerza y potencia** con una "
            "acumulación de fatiga periférica y metabolitos (lactato, H+) mínima. "
            "Es el rango recomendado para el desarrollo de fuerza máxima y potencia "
            "sin comprometer la calidad de la ejecución."
        )
    elif fatiga_pct < 30:
        categoria = "**MODERADA** 🟡"
        explicacion = (
            "Una pérdida de velocidad entre 15% y 30% indica una fatiga "
            "neuromuscular moderada. Comienza a producirse una acumulación "
            "relevante de metabolitos y una disminución progresiva en la "
            "capacidad de reclutamiento de fibras rápidas (tipo II), que van "
            "siendo parcialmente sustituidas por mayor reclutamiento y frecuencia "
            "de disparo de unidades motoras de umbral más bajo para intentar "
            "mantener la producción de fuerza. Este rango suele emplearse en "
            "trabajo de hipertrofia con control de fatiga."
        )
    else:
        categoria = "**ALTA** 🔴"
        explicacion = (
            "Una pérdida de velocidad superior al 30% refleja un **alto estrés "
            "metabólico**. A este nivel, las fibras rápidas (tipo II), con menor "
            "resistencia a la fatiga, reducen drásticamente su capacidad de "
            "generar fuerza, obligando a un reclutamiento compensatorio de fibras "
            "lentas (tipo I) para sostener el movimiento. La acumulación de "
            "iones H+ y metabolitos interfiere con el ciclo de "
            "excitación-contracción y con la reabsorción de calcio en el retículo "
            "sarcoplásmico, comprometiendo la velocidad de contracción. Series "
            "con pérdidas tan elevadas maximizan el estímulo de hipertrofia "
            "metabólica, pero incrementan considerablemente el tiempo de "
            "recuperación necesario y el riesgo de sobreentrenamiento si se "
            "repiten de forma crónica."
        )

    texto = f"""
**🧬 Fisiología de la Fatiga Neuromuscular**

Pérdida de velocidad calculada: **{fatiga_pct:.1f}%** → Categoría de fatiga: {categoria}

{explicacion}
"""
    return texto


# ==============================================================================
# 9. INTERFAZ DE USUARIO — BARRA LATERAL (CARGA DE DATOS Y CONFIGURACIÓN)
# ==============================================================================

def render_sidebar() -> Tuple[pd.DataFrame, str, float]:
    """
    Renderiza la barra lateral de la aplicación: carga de archivo o
    generación de datos de ejemplo, y selección del ejercicio / MVT.

    Retorna
    -------
    (pd.DataFrame, str, float)
        DataFrame de datos, nombre del ejercicio seleccionado y MVT a usar.
    """
    st.sidebar.title("🏋️ VBT Analytics")
    st.sidebar.markdown(
        "Sube tus datos de velocímetro lineal (encoder VBT) o utiliza el "
        "generador de datos de ejemplo para explorar la aplicación."
    )

    st.sidebar.header("1️⃣ Datos de Entrenamiento")
    archivo_subido = st.sidebar.file_uploader(
        "Sube tu archivo (CSV o Excel)", type=["csv", "xlsx", "xls"]
    )

    usar_ejemplo = False
    if archivo_subido is None:
        usar_ejemplo = st.sidebar.checkbox(
            "📊 Usar datos de ejemplo (test progresivo simulado)", value=True
        )

    # --- Carga de datos ---
    if archivo_subido is not None:
        try:
            df = cargar_archivo(archivo_subido)
            st.sidebar.success(f"Archivo '{archivo_subido.name}' cargado correctamente.")
        except ValueError as err:
            st.sidebar.error(str(err))
            st.stop()
    elif usar_ejemplo:
        df = generar_datos_ejemplo()
        st.sidebar.info(
            "Usando **datos de ejemplo**: test progresivo de Press de Banca "
            "(40kg → 60kg → 80kg → 90kg)."
        )
    else:
        st.sidebar.warning("Sube un archivo o activa el generador de datos de ejemplo para continuar.")
        st.stop()

    # --- Validación de columnas ---
    es_valido, faltantes = validar_columnas(df)
    if not es_valido:
        st.sidebar.error(
            "El archivo no contiene las columnas requeridas.\n\n"
            f"Faltan: {', '.join(faltantes)}\n\n"
            f"Columnas esperadas: {', '.join(COLUMNAS_REQUERIDAS)}"
        )
        st.stop()

    st.sidebar.header("2️⃣ Configuración del Ejercicio")
    ejercicio = st.sidebar.selectbox(
        "Selecciona el ejercicio",
        options=list(MVT_POR_EJERCICIO.keys()),
        index=0,
    )

    if MVT_POR_EJERCICIO[ejercicio] is None:
        mvt = st.sidebar.number_input(
            "Define el MVT personalizado (m/s)",
            min_value=0.01,
            max_value=1.50,
            value=0.20,
            step=0.01,
        )
    else:
        mvt = MVT_POR_EJERCICIO[ejercicio]
        st.sidebar.metric("MVT del ejercicio", f"{mvt} m/s")

    return df, ejercicio, mvt


# ==============================================================================
# 10. APLICACIÓN PRINCIPAL
# ==============================================================================

def main() -> None:
    """Punto de entrada principal de la aplicación Streamlit."""

    st.title("🏋️ Panel de Análisis VBT — Entrenamiento Basado en Velocidad")
    st.markdown(
        "Analiza el **perfil de fuerza**, estima el **1RM diario (e1RM)** y "
        "controla la **fatiga neuromuscular** de tus levantamientos usando "
        "datos de velocidad de la barra."
    )

    df, ejercicio, mvt = render_sidebar()

    # Limpieza básica de tipos numéricos, por si el archivo viene con
    # formatos de texto o separadores decimales inconsistentes.
    columnas_numericas = ["Carga (kg)", "Velocidad Media (m/s)", "Velocidad Pico (m/s)", "Repetición", "Número de Serie"]
    for col in columnas_numericas:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=columnas_numericas)

    if df.empty:
        st.error(
            "No quedaron filas válidas tras la limpieza de datos. Verifica que "
            "las columnas numéricas no contengan texto o valores vacíos."
        )
        st.stop()

    with st.expander("👁️ Ver datos crudos cargados", expanded=False):
        st.dataframe(df, use_container_width=True)

    # --------------------------------------------------------------------
    # MÓDULO 1: PERFIL CARGA-VELOCIDAD Y e1RM
    # --------------------------------------------------------------------
    st.header("📈 Módulo 1 — Perfil Carga-Velocidad y Estimación del 1RM")

    # Para un perfil de carga-velocidad fiable, se recomienda usar la
    # repetición más rápida de cada carga (evita contaminar la regresión
    # con la fatiga acumulada dentro de la serie).
    df_perfil = (
        df.sort_values("Velocidad Media (m/s)", ascending=False)
        .drop_duplicates(subset=["Carga (kg)"], keep="first")
        .sort_values("Carga (kg)")
    )

    try:
        resultado_regresion = calcular_perfil_carga_velocidad(df_perfil, mvt)
    except ValueError as err:
        st.warning(f"⚠️ {err}")
        resultado_regresion = None

    if resultado_regresion is not None:
        col1, col2, col3, col4 = st.columns(4)

        primera_rep_freskura = df.loc[df["Repetición"] == df["Repetición"].min()]
        velocidad_primera_rep = (
            primera_rep_freskura.sort_values("Carga (kg)", ascending=False)
            ["Velocidad Media (m/s)"].iloc[0]
            if not primera_rep_freskura.empty
            else np.nan
        )

        col1.metric("🎯 1RM Estimado (e1RM)", f"{resultado_regresion.e1rm:.1f} kg")
        col2.metric(
            "⚡ Velocidad 1ª Rep (carga más alta)",
            f"{velocidad_primera_rep:.3f} m/s" if not np.isnan(velocidad_primera_rep) else "N/D",
        )
        col3.metric("📊 R² del Perfil", f"{resultado_regresion.r_cuadrado:.3f}")
        col4.metric("🚦 MVT usado", f"{resultado_regresion.mvt_usado} m/s")

        fig_perfil = graficar_perfil_carga_velocidad(df_perfil, resultado_regresion)
        st.plotly_chart(fig_perfil, use_container_width=True)

        st.markdown(interpretar_perfil_fuerza_velocidad(resultado_regresion, ejercicio))
        st.markdown(interpretar_e1rm(resultado_regresion, ejercicio))
    else:
        st.info(
            "No fue posible calcular el e1RM. Asegúrate de registrar al menos "
            "3 cargas distintas en tu sesión de entrenamiento."
        )

    st.divider()

    # --------------------------------------------------------------------
    # MÓDULO 2: PÉRDIDA DE VELOCIDAD INTRA-SERIE (FATIGA)
    # --------------------------------------------------------------------
    st.header("📉 Módulo 2 — Pérdida de Velocidad Intra-Serie (Fatiga)")

    series_disponibles = sorted(df["Número de Serie"].unique())
    serie_seleccionada = st.selectbox(
        "Selecciona la serie a analizar", options=series_disponibles
    )

    df_serie = df[df["Número de Serie"] == serie_seleccionada]

    if len(df_serie) < 2:
        st.warning(
            "⚠️ La serie seleccionada tiene menos de 2 repeticiones. Se necesitan "
            "al menos 2 repeticiones para calcular la pérdida de velocidad."
        )
    else:
        fatiga_pct = calcular_perdida_velocidad(df_serie)

        col1, col2 = st.columns(2)
        col1.metric("🔻 Pérdida de Velocidad en la Serie", f"{fatiga_pct:.1f}%")
        col2.metric(
            "🏋️ Carga de la Serie",
            f"{df_serie['Carga (kg)'].iloc[0]:.1f} kg",
        )

        fig_fatiga = graficar_perdida_velocidad(df_serie, fatiga_pct)
        st.plotly_chart(fig_fatiga, use_container_width=True)

        st.markdown(interpretar_fatiga(fatiga_pct))

    st.divider()

    # --------------------------------------------------------------------
    # MÓDULO 3: PERFIL DE POTENCIA
    # --------------------------------------------------------------------
    st.header("💥 Módulo 3 — Perfil de Potencia")

    df_potencia = calcular_potencia(df)
    fig_potencia, carga_optima, potencia_maxima = graficar_perfil_potencia(df_potencia)

    col1, col2 = st.columns(2)
    col1.metric("🏆 Carga Óptima (Máxima Potencia)", f"{carga_optima:.1f} kg")
    col2.metric("⚙️ Potencia Máxima Registrada", f"{potencia_maxima:.0f} W")

    st.plotly_chart(fig_potencia, use_container_width=True)

    st.markdown(
        f"""
**⚙️ Interpretación del Perfil de Potencia**

La potencia mecánica se calculó como **P = Carga (kg) × g × Velocidad Media (m/s)**,
donde *g* = {GRAVEDAD} m/s² representa la aceleración de la gravedad (el trabajo
se realiza venciendo el peso de la carga en su desplazamiento vertical).

La relación Carga-Potencia sigue típicamente una curva **parabólica** (invertida):
a cargas muy bajas, la velocidad es alta pero la fuerza (carga) es insuficiente
para generar mucha potencia; a cargas muy altas (cercanas al 1RM), la fuerza es
máxima pero la velocidad cae drásticamente, reduciendo también la potencia.
Entre ambos extremos existe una **"Zona de Máxima Potencia"**, en este caso
alrededor de **{carga_optima:.1f} kg**, donde el producto Fuerza × Velocidad se
maximiza. Esta zona es clave para el entrenamiento de potencia orientado a
deportes que requieren gestos explosivos (saltos, sprints, lanzamientos).
"""
    )

    st.divider()
    st.caption(
        "⚠️ Aviso: Los cálculos de e1RM y potencia son estimaciones basadas en "
        "modelos matemáticos estándar de la literatura VBT y deben ser "
        "interpretados por un profesional cualificado en Fuerza y "
        "Acondicionamiento. No sustituyen un test directo de 1RM ni la "
        "supervisión técnica de un entrenador."
    )


# ==============================================================================
# 11. EJECUCIÓN
# ==============================================================================

if __name__ == "__main__":
    main()
