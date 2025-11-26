import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Analizador de Producción", layout="wide")

st.title("🔎 Analizador Automático de Producción")

# ---------------- 1. SUBIDA DE ARCHIVOS ----------------
st.header("📥 Cargar archivos")
tiempo_real_file = st.file_uploader("Tiempo real", type=["xlsx"])
componentes_file = st.file_uploader("Componentes", type=["xlsx"])
tiempos_inf_file = st.file_uploader("Tiempos informados", type=["xlsx"])
produccion_file = st.file_uploader("Producción", type=["xlsx"])

def leer_excel(f):
    return pd.read_excel(f) if f else None

# ---------------- PROCESAR SI ESTÁ TODO ----------------
if tiempo_real_file and componentes_file and tiempos_inf_file and produccion_file:

    raw_tr = leer_excel(tiempo_real_file)
    raw_comp = leer_excel(componentes_file)
    raw_tinf = leer_excel(tiempos_inf_file)
    raw_prod = leer_excel(produccion_file)

    st.success("Archivos cargados correctamente ✔")

    # ---------------- NORMALIZAR COLUMNAS ----------------
    def normalizar(df):
        df.columns = (
            df.columns.astype(str)
            .str.strip()
            .str.lower()
            .str.replace("á","a")
            .str.replace("é","e")
            .str.replace("í","i")
            .str.replace("ó","o")
            .str.replace("ú","u")
        )
        return df

    raw_tr = normalizar(raw_tr)
    raw_comp = normalizar(raw_comp)
    raw_tinf = normalizar(raw_tinf)
    raw_prod = normalizar(raw_prod)

    # ---------------- TIEMPO REAL ----------------
    # La orden y el tiempo están mezclados en un solo texto
    col_tr = raw_tr.columns[0]

    tr = raw_tr.rename(columns={col_tr: "raw_text"})
    tr["raw_text"] = tr["raw_text"].astype(str)

    # Extraer orden (primera secuencia numérica de 4+ dígitos)
    tr["orden"] = tr["raw_text"].str.extract(r"(\d{4,})")

    # Extraer tiempo (último número decimal)
    tr["tiempo_real"] = tr["raw_text"].str.extract(r"(\d+[\.,]\d+)$")

    tr["tiempo_real"] = (
        tr["tiempo_real"]
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    tr["orden"] = tr["orden"].astype(str)

    # ---------------- COMPONENTES ----------------
    col_comp_orden = "orden"
    col_comp_tomada = "cantidad tomada"
    col_comp_texto = "texto breve material"

    comp = raw_comp.rename(columns={
        col_comp_orden: "orden",
        col_comp_tomada: "cant_tomada",
        col_comp_texto: "material"
    })

    comp["orden"] = comp["orden"].astype(str)

    # ---------------- TIEMPOS INFORMADOS ----------------
    tinf = raw_tinf.rename(columns={
        "orden": "orden",
        "duración tratamiento": "tiempo_inf"
    })

    tinf["orden"] = tinf["orden"].astype(str)
    tinf["tiempo_inf"] = (
        tinf["tiempo_inf"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    # ---------------- PRODUCCION ----------------
    prod = raw_prod.rename(columns={
        "orden": "orden",
        "cantidad orden": "cant_orden",
        "cantidad buena confirmada": "cant_buena"
    })

    prod["orden"] = prod["orden"].astype(str)

    # ----------- CONFIGURAR TOLERANCIAS ----------
    st.header("⚙ Configuración de tolerancias (%)")

    margen_inf = st.number_input("Margen inferior (%)", value=-10.0) / 100
    margen_sup = st.number_input("Margen superior (%)", value=10.0) / 100

    # ----------- PROCESO AUTOMÁTICO -----------
    st.header("📊 Resultados del análisis")

    resultados_mat = []
    resultados_time = []

    ordenes = prod["orden"].unique()

    for o in ordenes:

        p = prod[prod["orden"] == o].iloc[0]
        cant_ord = p["cant_orden"]
        cant_buena = p["cant_buena"]

        if cant_ord == 0:
            continue

        relacion = cant_buena / cant_ord

        # -------- MATERIALES --------
        comp_o = comp[comp["orden"] == o].copy()

        if len(comp_o):
            comp_o["esperado"] = comp_o["cant_tomada"] * relacion
            comp_o["desvio"] = comp_o["cant_tomada"] - comp_o["esperado"]
            comp_o["ratio"] = comp_o["desvio"] / comp_o["esperado"].replace(0, np.nan)

            comp_o["estado"] = comp_o["ratio"].apply(
                lambda r: "OK" if margen_inf <= r <= margen_sup else "REVISAR"
            )

            comp_o["ajuste_necesario"] = -comp_o["desvio"]

            resultados_mat.append(comp_o[[
                "orden", "material", "cant_tomada", "esperado",
                "desvio", "ajuste_necesario", "estado"
            ]])

        # -------- TIEMPOS --------
        tr_o = tr[tr["orden"] == o]
        tinf_o = tinf[tinf["orden"] == o]

        t_real = tr_o["tiempo_real"].sum() if len(tr_o) else 0
        t_inf = tinf_o["tiempo_inf"].sum() if len(tinf_o) else 0

        desvio_t = t_inf - t_real

        estado_t = "OK" if margen_inf <= (desvio_t / (t_real if t_real else 1)) <= margen_sup else "REVISAR"

        ajuste_tiempo = -desvio_t

        resultados_time.append({
            "orden": o,
            "tiempo_real": t_real,
            "tiempo_informado": t_inf,
            "desvio": desvio_t,
            "ajuste_necesario": ajuste_tiempo,
            "estado": estado_t
        })

    # Mostrar resultados
    if resultados_mat:
        st.subheader("📦 Desvíos en Materiales")
        st.dataframe(pd.concat(resultados_mat), use_container_width=True)

    st.subheader("⏱ Desvíos en Tiempos")
    st.dataframe(pd.DataFrame(resultados_time), use_container_width=True)

else:
    st.info("Sube los 4 archivos para comenzar.")
