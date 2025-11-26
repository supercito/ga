import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Análisis de Producción")

st.title("📊 Análisis Automático de Órdenes de Producción")

# ------------------------------------------------------
# Función para detectar columnas automáticamente
# ------------------------------------------------------
def detectar_columnas(df, posibles):
    cols = [str(c).strip().lower() for c in df.columns.astype(str)]
    for i, c in enumerate(cols):
        for key in posibles:
            if key in c:
                return df.columns[i]
    return None

# ------------------------------------------------------
# SUBIR ARCHIVOS
# ------------------------------------------------------

st.header("1️⃣ Cargar archivos")

uploaded_tr = st.file_uploader("Tiempo Real", type=["csv", "xlsx"])
uploaded_comp = st.file_uploader("Componentes", type=["csv", "xlsx"])
uploaded_ti = st.file_uploader("Tiempos Informados", type=["csv", "xlsx"])
uploaded_prod = st.file_uploader("Producción", type=["csv", "xlsx"])

if not (uploaded_tr and uploaded_comp and uploaded_ti and uploaded_prod):
    st.stop()

def cargar(f):
    if f.name.endswith(".csv"):
        return pd.read_csv(f, dtype=str)
    return pd.read_excel(f, dtype=str)

raw_tr = cargar(uploaded_tr)
raw_comp = cargar(uploaded_comp)
raw_ti = cargar(uploaded_ti)
raw_prod = cargar(uploaded_prod)

# ------------------------------------------------------
# 2️⃣ DETECCIÓN AUTOMÁTICA DE COLUMNAS
# ------------------------------------------------------

st.header("2️⃣ Detección automática de columnas")

# -------- TIEMPO REAL --------
col_tr_orden = detectar_columnas(raw_tr, ["orden"])
col_tr_tiempo = detectar_columnas(raw_tr, ["tiempo real"])

if not col_tr_orden or not col_tr_tiempo:
    st.error("No se detectaron columnas necesarias en Tiempo Real.")
    st.stop()

tr = raw_tr.rename(columns={
    col_tr_orden: "orden",
    col_tr_tiempo: "tiempo_real"
})
tr["orden"] = tr["orden"].astype(str).str.strip()
tr["tiempo_real"] = pd.to_numeric(tr["tiempo_real"], errors="coerce")

# -------- COMPONENTES --------
col_c_orden = detectar_columnas(raw_comp, ["orden"])
col_c_nec = detectar_columnas(raw_comp, ["cantidad necesaria"])
col_c_tom = detectar_columnas(raw_comp, ["cantidad tomada"])

if None in [col_c_orden, col_c_nec, col_c_tom]:
    st.error("No se detectaron columnas necesarias en Componentes.")
    st.stop()

comp = raw_comp.rename(columns={
    col_c_orden: "orden",
    col_c_nec: "cant_nec",
    col_c_tom: "cant_tom",
})
comp["orden"] = comp["orden"].astype(str).str.strip()
comp["cant_nec"] = pd.to_numeric(comp["cant_nec"], errors="coerce")
comp["cant_tom"] = pd.to_numeric(comp["cant_tom"], errors="coerce")

# -------- TIEMPOS INFORMADOS --------
col_ti_orden = detectar_columnas(raw_ti, ["orden"])
col_ti_dur = detectar_columnas(raw_ti, ["duración", "tratamiento"])

if None in [col_ti_orden, col_ti_dur]:
    st.error("No se detectaron columnas necesarias en Tiempos Informados.")
    st.stop()

ti = raw_ti.rename(columns={
    col_ti_orden: "orden",
    col_ti_dur: "tiempo_inf",
})
ti["orden"] = ti["orden"].astype(str).str.strip()
ti["tiempo_inf"] = pd.to_numeric(ti["tiempo_inf"], errors="coerce")

# -------- PRODUCCIÓN --------
col_p_orden = detectar_columnas(raw_prod, ["orden"])
col_p_cant_ord = detectar_columnas(raw_prod, ["cantidad orden"])
col_p_cant_conf = detectar_columnas(raw_prod, ["cantidad buena"])

if None in [col_p_orden, col_p_cant_ord, col_p_cant_conf]:
    st.error("No se detectaron columnas necesarias en Producción.")
    st.stop()

prod = raw_prod.rename(columns={
    col_p_orden: "orden",
    col_p_cant_ord: "cant_ord",
    col_p_cant_conf: "cant_conf"
})
prod["orden"] = prod["orden"].astype(str).str.strip()
prod["cant_ord"] = pd.to_numeric(prod["cant_ord"], errors="coerce")
prod["cant_conf"] = pd.to_numeric(prod["cant_conf"], errors="coerce")

# ------------------------------------------------------
# 3️⃣ AGRUPAR DATOS
# ------------------------------------------------------

tr_group = tr.groupby("orden", as_index=False)["tiempo_real"].sum()
comp_group = comp.groupby("orden", as_index=False).agg({"cant_nec": "sum", "cant_tom": "sum"})
ti_group = ti.groupby("orden", as_index=False)["tiempo_inf"].sum()
prod_group = prod.groupby("orden", as_index=False).agg({"cant_ord": "sum", "cant_conf": "sum"})

# ------------------------------------------------------
# 4️⃣ UNIFICAR TODO EN UN SOLO DF FINAL
# ------------------------------------------------------

df = (
    prod_group
    .merge(comp_group, on="orden", how="outer")
    .merge(tr_group, on="orden", how="outer")
    .merge(ti_group, on="orden", how="outer")
)

df = df.fillna(0)

# ------------------------------------------------------
# 5️⃣ REGLAS Y DIFERENCIAS
# ------------------------------------------------------

df["dif_componentes"] = df["cant_nec"] - df["cant_tom"]
df["dif_tiempos"] = df["tiempo_real"] - df["tiempo_inf"]

df["componentes_faltante"] = df["dif_componentes"].apply(lambda x: x if x > 0 else 0)
df["tiempo_faltante"] = df["dif_tiempos"].apply(lambda x: x if x > 0 else 0)

df["flag_problema"] = (
    (df["dif_componentes"] != 0) |
    (df["dif_tiempos"] != 0) |
    (df["cant_conf"] != df["cant_ord"])
)

# ------------------------------------------------------
# 6️⃣ MOSTRAR RESULTADOS
# ------------------------------------------------------

st.header("3️⃣ Resultado del análisis")

st.subheader("Órdenes con errores detectados")
st.dataframe(df[df["flag_problema"] == True], use_container_width=True)

st.subheader("Todas las órdenes analizadas")
st.dataframe(df, use_container_width=True)

