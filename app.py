import streamlit as st
import pandas as pd

st.title("Diagnóstico de Estructura de Archivos")

# ---------------- 1. SUBIDA DE ARCHIVOS ----------------
st.header("Cargar archivos")
tiempo_real_file = st.file_uploader("Tiempo real", type=["xlsx"])
componentes_file = st.file_uploader("Componentes", type=["xlsx"])
tiempos_inf_file = st.file_uploader("Tiempos informados", type=["xlsx"])
produccion_file = st.file_uploader("Producción", type=["xlsx"])

def leer_excel(file):
    if file is None:
        return None
    return pd.read_excel(file)

# ---------------- 2. PROCESAR CUANDO ESTÉN TODOS ----------------

if (
    tiempo_real_file
    and componentes_file
    and tiempos_inf_file
    and produccion_file
):

    df_tr = leer_excel(tiempo_real_file)
    df_comp = leer_excel(componentes_file)
    df_tinf = leer_excel(tiempos_inf_file)
    df_prod = leer_excel(produccion_file)

    st.success("Archivos cargados correctamente")

    st.header("Columnas detectadas en cada archivo")

    # Copias sin procesar para inspección
    raw_tr = df_tr.copy()
    raw_comp = df_comp.copy()
    raw_tinf = df_tinf.copy()
    raw_prod = df_prod.copy()

    # Listas de columnas normalizadas (solo visualización)
    cols_tr = [str(c).strip().lower() for c in raw_tr.columns.astype(str)]
    cols_comp = [str(c).strip().lower() for c in raw_comp.columns.astype(str)]
    cols_tinf = [str(c).strip().lower() for c in raw_tinf.columns.astype(str)]
    cols_prod = [str(c).strip().lower() for c in raw_prod.columns.astype(str)]

    st.subheader("Tiempo Real")
    st.write(cols_tr)

    st.subheader("Componentes")
    st.write(cols_comp)

    st.subheader("Tiempos Informados")
    st.write(cols_tinf)

    st.subheader("Producción")
    st.write(cols_prod)

    st.info("⚠️ Con estos datos vamos a construir la lógica completa. Enviame la salida para avanzar.")

else:
    st.info("Sube los 4 archivos para inspeccionar la estructura.")
