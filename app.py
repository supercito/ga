import streamlit as st
import pandas as pd
import re

st.title("Análisis de Producción – Tiempos y Materiales")
st.write("Subí los 4 archivos: Tiempo real, Tiempo informado, Producción y Componentes.")

# ============================================================
# Funciones auxiliares
# ============================================================

def load(f):
    if f is None:
        return None
    if f.name.endswith(".csv"):
        return pd.read_csv(f)
    return pd.read_excel(f)

def normalize_columns(df):
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.lower()
        .str.strip()
        .str.replace("\n", " ", regex=False)
        .str.replace(" +", " ", regex=True)
    )
    return df

def fix_duplicate_columns(df):
    """Renombra columnas duplicadas automáticamente."""
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        dup_idx = cols[cols == dup].index.tolist()
        for i, idx in enumerate(dup_idx):
            cols[idx] = f"{dup}_{i+1}"
    df.columns = cols
    return df

def find_order_column(df):
    patrones = ["orden", "order", "ord", "o.p", "orden de produccion", "orden de fabricación"]
    for col in df.columns:
        c = col.lower().strip()
        if any(p in c for p in patrones):
            return col
    return None

def find_time_real_col(df):
    posibles = ["tiempo", "máquina", "maquina", "real"]
    for col in df.columns:
        if any(p in col for p in posibles):
            return col
    return None

def find_time_inf_col(df):
    posibles = ["activ", "notificada", "notificado"]
    for col in df.columns:
        if any(p in col for p in posibles):
            return col
    return None

def find_required_material_col(df):
    posibles = ["necesaria", "necesario", "req", "requerida"]
    for col in df.columns:
        if any(p in col for p in posibles):
            return col
    return None

def find_taken_material_col(df):
    posibles = ["tomada", "tomado", "consumo", "tom"]
    for col in df.columns:
        if any(p in col for p in posibles):
            return col
    return None


# ============================================================
# Subida de archivos
# ============================================================

tiempos_reales = st.file_uploader("Tiempos Reales (excel/csv)", type=["xlsx", "csv"])
tiempos_inf = st.file_uploader("Tiempos Informados SAP", type=["xlsx", "csv"])
produccion = st.file_uploader("Producción", type=["xlsx", "csv"])
componentes = st.file_uploader("Componentes", type=["xlsx", "csv"])

if st.button("Procesar"):
    try:
        # Cargar y normalizar
        df_real = fix_duplicate_columns(normalize_columns(load(tiempos_reales)))
        df_inf  = fix_duplicate_columns(normalize_columns(load(tiempos_inf)))
        df_prod = fix_duplicate_columns(normalize_columns(load(produccion)))
        df_comp = fix_duplicate_columns(normalize_columns(load(componentes)))

        # ====================================================
        # Detección automática de columnas claves
        # ====================================================

        col_ord_real = find_order_column(df_real)
        col_ord_inf  = find_order_column(df_inf)
        col_ord_prod = find_order_column(df_prod)
        col_ord_comp = find_order_column(df_comp)

        col_treal = find_time_real_col(df_real)
        col_tinf  = find_time_inf_col(df_inf)

        col_mat_req = find_required_material_col(df_comp)
        col_mat_tom = find_taken_material_col(df_comp)

        if None in [col_ord_real, col_ord_inf, col_ord_prod, col_ord_comp]:
            st.error("❌ No se pudo identificar correctamente la columna de Orden en uno o más archivos.")
            st.stop()

        if None in [col_treal, col_tinf]:
            st.error("❌ No se encontraron columnas de tiempo real o tiempo informado.")
            st.write("Real:", col_treal)
            st.write("Informado:", col_tinf)
            st.stop()

        if None in [col_mat_req, col_mat_tom]:
            st.error("❌ No se detectaron columnas de materiales tomados/necesarios.")
            st.stop()

        # ====================================================
        # Comparación de tiempos
        # ====================================================

        df_time = pd.merge(
            df_real[[col_ord_real, col_treal]],
            df_inf[[col_ord_inf, col_tinf]],
            left_on=col_ord_real,
            right_on=col_ord_inf,
            how="outer",
            suffixes=("_real", "_inf")
        )

        df_time["dif_tiempo"] = df_time[col_treal] - df_time[col_tinf]

        def action_time(row):
            if pd.isna(row[col_treal]): return "❗ Falta tiempo REAL"
            if pd.isna(row[col_tinf]): return "❗ Falta tiempo informado SAP"
            if row["dif_tiempo"] > 0: return "↑ SAP sub-informado (falta sumar)"
            if row["dif_tiempo"] < 0: return "↓ SAP sobre-informado (reducir)"
            return "OK"

        df_time["accion"] = df_time.apply(action_time, axis=1)

        st.subheader("Comparación de tiempos (Real vs SAP)")
        st.dataframe(df_time)

        # ====================================================
        # Comparación de materiales
        # ====================================================

        df_comp["diff"] = df_comp[col_mat_tom] - df_comp[col_mat_req]
        df_comp["pct"] = (df_comp["diff"] / df_comp[col_mat_req].replace(0, pd.NA)) * 100

        st.subheader("Desvíos de materiales")
        st.dataframe(df_comp)

        df_alert = df_comp[(df_comp["pct"] > 5) | (df_comp["pct"] < -5)]
        st.subheader("Materiales a corregir (desvío > ±5%)")
        st.dataframe(df_alert)

        st.success("✔ Proceso completado con éxito.")

    except Exception as e:
        st.error("⚠ Ocurrió un error procesando los datos.")
        st.write(str(e))
