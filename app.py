import streamlit as st
import pandas as pd

st.title("Verificación de Columnas - Archivos de Producción")

# --- 1. Subir archivos ---
st.header("Cargar archivos")

tr_file = st.file_uploader("Tiempo Real", type=["xlsx"])
cp_file = st.file_uploader("Componentes", type=["xlsx"])
ti_file = st.file_uploader("Tiempos Informados", type=["xlsx"])
pr_file = st.file_uploader("Producción", type=["xlsx"])

def leer_excel(file):
    if file is None:
        return None
    return pd.read_excel(file)

# --- 2. Cargar y mostrar columnas ---
if tr_file and cp_file and ti_file and pr_file:
    st.success("Archivos cargados correctamente")

    # Leer archivos
    tr = leer_excel(tr_file)
    cp = leer_excel(cp_file)
    ti = leer_excel(ti_file)
    pr = leer_excel(pr_file)

    # Mostrar columnas detectadas
    st.subheader("Columnas encontradas")

    st.write("### ⏱ Tiempo Real")
    st.write(tr.columns.tolist())

    st.write("### 🧩 Componentes")
    st.write(cp.columns.tolist())

    st.write("### 🕒 Tiempos Informados")
    st.write(ti.columns.tolist())

    st.write("### 🏭 Producción")
    st.write(pr.columns.tolist())

else:
    st.info("Por favor carga los 4 archivos para continuar.")
