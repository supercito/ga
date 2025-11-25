import streamlit as st
import pandas as pd

st.title("📊 Análisis de Producción por Orden")

# --------------------------
# UPLOAD DE ARCHIVOS
# --------------------------
st.header("1️⃣ Cargar archivos")

file_debe = st.file_uploader("Archivo con cantidades **a producir**", type=["xlsx"])
file_real = st.file_uploader("Archivo con cantidades **producidas**", type=["xlsx"])
file_tiempo = st.file_uploader("Archivo con **tiempos reales por orden**", type=["xlsx"])


# Si faltan archivos → no seguimos
if not (file_debe and file_real):
    st.warning("Subí los archivos para continuar.")
    st.stop()

# --------------------------
# LECTURA DE ARCHIVOS
# --------------------------
df_debe = pd.read_excel(file_debe)
df_real = pd.read_excel(file_real)

if file_tiempo:
    df_tiempo = pd.read_excel(file_tiempo)
else:
    df_tiempo = None

st.success("Archivos cargados correctamente.")


# --------------------------
# PARÁMETROS
# --------------------------
st.header("2️⃣ Configuración del análisis")

# Límites de tolerancia
lim_inf = st.number_input("📉 Límite inferior (%)", value=-10.0)
lim_sup = st.number_input("📈 Límite superior (%)", value=10.0)

# Seleccionar materiales para excluir
materiales_unicos = df_debe["material"].unique()
excluir = st.multiselect("❌ Materiales a excluir del análisis", materiales_unicos)


# --------------------------
# PROCESAMIENTO
# --------------------------
st.header("3️⃣ Resultados")

# Merge por número de orden y material
df = pd.merge(df_debe, df_real, on=["orden", "material"], suffixes=("_debe", "_real"))

# Calcular diferencia
df["dif_cant"] = df["cantidad_real"] - df["cantidad_debe"]
df["dif_pct"] = (df["dif_cant"] / df["cantidad_debe"]) * 100

# Excluir materiales seleccionados
if excluir:
    df = df[~df["material"].isin(excluir)]


# Aplicar límites
df_fuera_limite = df[(df["dif_pct"] < lim_inf) | (df["dif_pct"] > lim_sup)]

st.subheader("📌 Órdenes con diferencias fuera de límites")
st.dataframe(df_fuera_limite)


# --------------------------
# ANÁLISIS DE TIEMPO
# --------------------------
if df_tiempo is not None:
    st.header("⏱ Comparación de tiempos (hrs)")
    
    df_full = pd.merge(df_fuera_limite, df_tiempo, on="orden", how="left")
    st.dataframe(df_full)

    # Exportar
    st.download_button(
        "⬇ Descargar Excel con diferencias + tiempos",
        df_full.to_excel(index=False),
        file_name="resultado_con_tiempos.xlsx"
    )
else:
    # Exportar sin tiempos
    st.download_button(
        "⬇ Descargar Excel con diferencias",
        df_fuera_limite.to_excel(index=False),
        file_name="resultado.xlsx"
    )

