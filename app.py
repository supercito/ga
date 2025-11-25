import streamlit as st
import pandas as pd
import re

st.title("Analisis de Producción: Tiempos y Materiales")
st.write("Subí los 4 archivos: tiempos reales, tiempos informados, producción y componentes.")

# -------------------------
# Funciones de soporte
# -------------------------

def load(f):
    if f is None:
        return None
    if f.name.endswith(".csv"):
        return pd.read_csv(f)
    return pd.read_excel(f)

def normalize_columns(df):
    df = df.copy()
    df.columns = (
        df.columns.str.lower()
        .str.strip()
        .str.replace("\n", " ")
        .str.replace("  +", " ", regex=True)
    )
    return df

def find_order_column(df):
    posibles = ["orden", "order", "ord", "orden de produccion", "orden de fabricación"]

    for col in df.columns:
        c = col.lower().strip()
        if any(p in c for p in posibles):
            return col

    return None  # no se encontró

# -------------------------
# Subida de archivos
# -------------------------

tiempos_reales = st.file_uploader("Tiempos reales", type=["xlsx","csv"])
tiempos_inf = st.file_uploader("Tiempos informados", type=["xlsx","csv"])
produccion = st.file_uploader("Producción", type=["xlsx","csv"])
componentes = st.file_uploader("Componentes", type=["xlsx","csv"])

if st.button("Procesar"):

    try:
        # Cargar
        df_real = normalize_columns(load(tiempos_reales))
        df_inf  = normalize_columns(load(tiempos_inf))
        df_prod = normalize_columns(load(produccion))
        df_comp = normalize_columns(load(componentes))

        # -------------------------
        # Detectar columnas de Orden
        # -------------------------
        ord_real = find_order_column(df_real)
        ord_inf  = find_order_column(df_inf)
        ord_prod = find_order_column(df_prod)
        ord_comp = find_order_column(df_comp)

        if None in [ord_real, ord_inf, ord_prod, ord_comp]:
            st.error("❌ No se pudo identificar la columna de Orden en todos los archivos.")
            st.write("Encontrado:")
            st.write(f"Tiempos reales: {ord_real}")
            st.write(f"Tiempos informados: {ord_inf}")
            st.write(f"Producción: {ord_prod}")
            st.write(f"Componentes: {ord_comp}")
            st.stop()

        # -------------------------
        # Comparación de tiempos
        # -------------------------

        # Detectar columnas de tiempo
        col_real_time = [c for c in df_real.columns if "maquina" in c or "máquina" in c or "tiempo" in c][0]
        col_inf_time  = [c for c in df_inf.columns if "activ" in c][0]

        df_time = pd.merge(
            df_real[[ord_real, col_real_time]],
            df_inf[[ord_inf, col_inf_time]],
            left_on=ord_real,
            right_on=ord_inf,
            how="outer",
            suffixes=("_real","_inf")
        )

        df_time["dif_tiempo"] = df_time[col_real_time] - df_time[col_inf_time]

        def classify_time(row):
            if pd.isna(row[col_real_time]): return "Falta tiempo REAL"
            if pd.isna(row[col_inf_time]): return "Falta notificación SAP"
            if row["dif_tiempo"] > 0: return "SAP sub-informado (falta sumar)"
            if row["dif_tiempo"] < 0: return "SAP sobre-informado (reducir)"
            return "OK"

        df_time["accion"] = df_time.apply(classify_time, axis=1)

        st.subheader("Resultados de tiempos")
        st.dataframe(df_time)

        # -------------------------
        # Comparación de materiales
        # -------------------------

        col_nec = [c for c in df_comp.columns if "necesaria" in c or "necesario" in c][0]
        col_tom = [c for c in df_comp.columns if "tomada" in c or "consumo" in c][0]

        df_comp["diff"] = df_comp[col_tom] - df_comp[col_nec]
        df_comp["pct"] = (df_comp["diff"] / df_comp[col_nec].replace(0, pd.NA)) * 100

        st.subheader("Desvíos de materiales")
        st.dataframe(df_comp)

        # Alerta si supera ±5%
        df_alert = df_comp[(df_comp["pct"] > 5) | (df_comp["pct"] < -5)]
        st.subheader("Materiales a corregir (>5% desvío)")
        st.dataframe(df_alert)

        st.success("Proceso completado.")

    except Exception as e:
        st.error("⚠️ Ocurrió un error procesando los archivos.")
        st.write(str(e))
