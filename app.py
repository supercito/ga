import streamlit as st
import pandas as pd

st.title("📊 Comparador de Tiempos – Producción")

# ----------------------------------------------------------------------
# 📁 CARGA DE ARCHIVOS
# ----------------------------------------------------------------------
tiempo_real_file = st.sidebar.file_uploader("Cargar archivo de Tiempos Reales", type=["xlsx"])
tiempo_est_file = st.sidebar.file_uploader("Cargar archivo de Tiempos Estimados", type=["xlsx"])

if tiempo_real_file and tiempo_est_file:
    df_tr = pd.read_excel(tiempo_real_file)
    df_te = pd.read_excel(tiempo_est_file)

    st.write("### Vista previa Tiempos Reales")
    st.dataframe(df_tr.head())

    st.write("### Vista previa Tiempos Estimados")
    st.dataframe(df_te.head())

    # ------------------------------------------------------------------
    # 🔎 VALIDACIÓN DE COLUMNAS
    # ------------------------------------------------------------------

    col_real = "Orden Producción"
    col_est = "Orden Producción"

    if col_real not in df_tr.columns:
        st.error(f"❌ El archivo de tiempos reales NO contiene la columna: **{col_real}**")
        st.stop()

    if col_est not in df_te.columns:
        st.error(f"❌ El archivo de tiempos estimados NO contiene la columna: **{col_est}**")
        st.stop()

    # ------------------------------------------------------------------
    # 📌 SELECCIÓN DE ORDEN
    # ------------------------------------------------------------------
    ordenes = sorted(set(df_tr[col_real].unique()) | set(df_te[col_est].unique()))
    orden = st.selectbox("Selecciona una Orden de Producción", ordenes)

    # ------------------------------------------------------------------
    # 🔧 FILTRO SEGURO
    # ------------------------------------------------------------------
    t_real = df_tr[df_tr[col_real] == orden]
    t_est = df_te[df_te[col_est] == orden]

    st.write("### Registros Reales Encontrados")
    st.dataframe(t_real)

    st.write("### Registros Estimados Encontrados")
    st.dataframe(t_est)

    # ------------------------------------------------------------------
    # 🧮 CÁLCULO DE TIEMPOS
    # ------------------------------------------------------------------
    def obtener_suma(df, columna):
        if columna not in df.columns:
            return 0
        if df.empty:
            return 0
        return df[columna].fillna(0).sum()

    tiempo_real = obtener_suma(t_real, "Tiempo Real")
    tiempo_est = obtener_suma(t_est, "Tiempo Estimado")
    tiempo_dif = tiempo_real - tiempo_est

    # ------------------------------------------------------------------
    # 📊 RESULTADOS
    # ------------------------------------------------------------------
    st.write("## ⏱️ Resultado del Análisis")

    col1, col2, col3 = st.columns(3)
    col1.metric("Tiempo Real", f"{tiempo_real:.2f} min")
    col2.metric("Tiempo Estimado", f"{tiempo_est:.2f} min")
    col3.metric("Diferencia", f"{tiempo_dif:.2f} min")

else:
    st.info("📂 Sube ambos archivos para continuar.")
