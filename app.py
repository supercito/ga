import streamlit as st
import pandas as pd

file = st.file_uploader("Subí el archivo Tiempo Real")

if file:
    df = pd.read_excel(file, header=None)

    st.write("Excel cargado completo:")
    st.dataframe(df)

    # Orden buscada
    buscada = "202357"

    # Filtrar por la columna 3 (orden)
    filtrado = df[df[3].astype(str).str.contains(buscada, na=False)]

    st.write(f"Filtrado por orden {buscada}:")
    st.dataframe(filtrado)
