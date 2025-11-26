import streamlit as st
import pandas as pd

st.set_page_config(page_title="Analizador de Producción", layout="wide")

st.title("📊 Analizador Automático de Producción")

# ------------------------------------------
# Función: detectar columnas clave
# ------------------------------------------
def detectar_columnas(df, posibles_nombres):
    cols = df.columns.str.lower().str.strip()
    for name in posibles_nombres:
        if name in cols.values:
            return df.columns[cols == name][0]
    return None

# ------------------------------------------
# SUBIDA DE ARCHIVOS
# ------------------------------------------
st.header("📁 Cargar Archivos (4 archivos obligatorios)")

files = st.file_uploader(
    "Sube los 4 archivos (Tiempo Real, Componentes, Tiempos Informados, Producción)",
    accept_multiple_files=True,
    type=["xlsx", "xls"]
)

if len(files) != 4:
    st.warning("Debes subir exactamente 4 archivos.")
    st.stop()

dfs = {}
for f in files:
    dfs[f.name] = pd.read_excel(f)

st.success("Archivos cargados correctamente.")

# ------------------------------------------
# IDENTIFICACIÓN AUTOMÁTICA DE CADA ARCHIVO
# ------------------------------------------
def clasificar_archivo(df):
    cols = df.columns.str.lower()

    if "tiempo real" in cols[0]:
        return "tiempo_real"

    if "recursos" in cols.values and "duración tratamiento" in cols.values:
        return "tiempos_informados"

    if "cantidad orden" in cols.values and "cantidad buena confirmada" in cols.values:
        return "produccion"

    if "cantidad necesaria" in cols.values and "cantidad tomada" in cols.values:
        return "componentes"

    return None

data = {}

for name, df in dfs.items():
    tipo = clasificar_archivo(df)
    if not tipo:
        st.error(f"No pude identificar el archivo: {name}")
        st.stop()
    data[tipo] = df

# Verificación
requeridos = ["tiempo_real", "componentes", "tiempos_informados", "produccion"]
for r in requeridos:
    if r not in data:
        st.error(f"Falta cargar el archivo de {r}")
        st.stop()

st.success("✔ Archivos identificados correctamente")

# ------------------------------------------
# NORMALIZAR COLUMNAS (detectar automáticamente)
# ------------------------------------------

# Tiempo Real
tr = data["tiempo_real"]
col_tr_orden = detectar_columnas(tr, ["orden", "tiempo real por orden de producción"])
if not col_tr_orden:
    st.error("No encuentro columna 'orden' en Tiempo Real")
    st.stop()
tr = tr.rename(columns={col_tr_orden: "orden"})

# Componentes
comp = data["componentes"]
col_c_orden = detectar_columnas(comp, ["orden"])
col_c_nec = detectar_columnas(comp, ["cantidad necesaria"])
col_c_tom = detectar_columnas(comp, ["cantidad tomada"])
if None in [col_c_orden, col_c_nec, col_c_tom]:
    st.error("Faltan columnas (orden / cantidad necesaria / cantidad tomada) en Componentes.")
    st.stop()
comp = comp.rename(columns={col_c_orden:"orden", col_c_nec:"cant_nec", col_c_tom:"cant_tom"})

# Tiempos Informados
ti = data["tiempos_informados"]
col_ti_orden = detectar_columnas(ti, ["orden"])
col_ti_dur = detectar_columnas(ti, ["duración tratamiento"])
if None in [col_ti_orden, col_ti_dur]:
    st.error("No encuentro columnas necesarias en Tiempos Informados.")
    st.stop()
ti = ti.rename(columns={col_ti_orden:"orden", col_ti_dur:"tiempo_info"})

# Producción
prod = data["produccion"]
col_p_orden = detectar_columnas(prod, ["orden"])
col_p_cant_ord = detectar_columnas(prod, ["cantidad orden"])
col_p_cant_conf = detectar_columnas(prod, ["cantidad buena confirmada"])
if None in [col_p_orden, col_p_cant_ord, col_p_cant_conf]:
    st.error("No encuentro columnas clave en Producción.")
    st.stop()
prod = prod.rename(columns={col_p_orden:"orden", col_p_cant_ord:"cant_ord", col_p_cant_conf:"cant_conf"})

# ------------------------------------------
# AGRUPAR DATOS POR ORDEN
# ------------------------------------------
st.header("🔍 Analizando datos…")

# Tiempo Real (sumamos si hay varias filas por orden)
tr_group = tr.groupby("orden").sum(numeric_only=True)

# Componentes
comp_group = comp.groupby("orden").agg({"cant_nec":"sum","cant_tom":"sum"})

# Tiempos Informados
ti_group = ti.groupby("orden").agg({"tiempo_info":"sum"})

# Producción
prod_group = prod.groupby("orden").agg({"cant_ord":"sum","cant_conf":"sum"})

# Combinación total
df_final = (
    tr_group
    .merge(comp_group, on="orden", how="outer")
    .merge(ti_group, on="orden", how="outer")
    .merge(prod_group, on="orden", how="outer")
)

# ------------------------------------------
# CÁLCULOS DE DIFERENCIAS
# ------------------------------------------
df_final["dif_tiempo"] = df_final.get("tiempo real por orden de producción", 0) - df_final["tiempo_info"]
df_final["dif_componentes"] = df_final["cant_nec"] - df_final["cant_tom"]
df_final["dif_produccion"] = df_final["cant_ord"] - df_final["cant_conf"]

# Mostrar solo diferencias si el usuario lo pidió (tu respuesta 6 = b)
df_diff = df_final[
    (df_final["dif_tiempo"] != 0) |
    (df_final["dif_componentes"] != 0) |
    (df_final["dif_produccion"] != 0)
]

st.subheader("📌 Resultado: Órdenes que requieren revisión")
st.dataframe(df_diff)

# ------------------------------------------
# MOSTRAR RECOMENDACIONES: CUÁNTO INFORMAR O RESTAR
# ------------------------------------------
st.subheader("🛠 Acciones sugeridas")

acciones = []

for idx, row in df_diff.iterrows():
    orden = idx

    if row["dif_tiempo"] != 0:
        acciones.append(f"🕒 Orden {orden}: informar **{row['dif_tiempo']}** min de tiempo faltante/sobrante")

    if row["dif_componentes"] != 0:
        acciones.append(f"🔩 Orden {orden}: ajustar componentes en **{row['dif_componentes']}**")

    if row["dif_produccion"] != 0:
        acciones.append(f"📦 Orden {orden}: ajustar producción en **{row['dif_produccion']}** unidades")

st.write("\n".join(acciones))
