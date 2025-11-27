import streamlit as st
import pandas as pd

st.title("Analizador Automático de Producción")

# ------------------ SUBIDA DE ARCHIVOS ------------------
st.header("Cargar archivos")

tr_file = st.file_uploader("Tiempo Real", type=["xlsx"])
cp_file = st.file_uploader("Componentes", type=["xlsx"])
ti_file = st.file_uploader("Tiempos Informados", type=["xlsx"])
pr_file = st.file_uploader("Producción", type=["xlsx"])


def leer_excel(file):
    if file is None:
        return None
    return pd.read_excel(file)


# ------------------ PROCESAR SI ESTÁN LOS 4 ------------------
if tr_file and cp_file and ti_file and pr_file:

    tr_raw = leer_excel(tr_file)
    cp = leer_excel(cp_file)
    ti = leer_excel(ti_file)
    pr = leer_excel(pr_file)

    st.success("Archivos cargados correctamente")

    # ------------------ LIMPIEZA TIEMPO REAL ------------------
    # Extraemos orden y tiempo de máquina desde posiciones fijas
    tr = pd.DataFrame()
    tr["orden"] = tr_raw["Tiempo real por orden de producción"].astype(str).str.replace(".0", "", regex=False)
    tr["tiempo_real"] = tr_raw.iloc[:, 9]  # Columna J = índice 9
    tr["tiempo_real"] = pd.to_numeric(tr["tiempo_real"], errors="coerce").fillna(0)

    # ------------------ NORMALIZACIÓN GENERAL ------------------
    cp.columns = cp.columns.str.lower().str.strip()
    ti.columns = ti.columns.str.lower().str.strip()
    pr.columns = pr.columns.str.lower().str.strip()

    # Estandarizamos columna orden
    cp["orden"] = cp["orden"].astype(str).str.replace(".0", "", regex=False)
    ti["orden"] = ti["orden"].astype(str).str.replace(".0", "", regex=False)
    pr["orden"] = pr["orden"].astype(str).str.replace(".0", "", regex=False)

    # ------------------ AGRUPAR TIEMPOS INFORMADOS ------------------
    ti["duración tratamiento"] = pd.to_numeric(ti["duración tratamiento"], errors="coerce").fillna(0)

    tiempos_inf = (
        ti.groupby("orden")["duración tratamiento"]
        .sum()
        .reset_index()
        .rename(columns={"duración tratamiento": "tiempo_informado"})
    )

    # ------------------ UNIR TODO POR ORDEN ------------------
    df = pr[["orden", "cantidad orden", "cantidad buena confirmada"]].copy()

    df = df.merge(tr, on="orden", how="left")
    df = df.merge(tiempos_inf, on="orden", how="left")

    df["tiempo_informado"] = df["tiempo_informado"].fillna(0)
    df["tiempo_real"] = df["tiempo_real"].fillna(0)

    # ------------------ PROCESO DE MATERIALES ------------------
    cp["cantidad necesaria"] = pd.to_numeric(cp["cantidad necesaria"], errors="coerce").fillna(0)
    cp["cantidad tomada"] = pd.to_numeric(cp["cantidad tomada"], errors="coerce").fillna(0)

    materiales = cp.copy()

    # ------------------ ANÁLISIS FINAL ------------------
    resultados_materiales = []
    resultados_tiempos = []

    for orden in df["orden"].unique():

        fila = df[df["orden"] == orden].iloc[0]

        cant_ord = fila["cantidad orden"]
        cant_buena = fila["cantidad buena confirmada"]

        if cant_ord == 0:
            relacion = 1
        else:
            relacion = cant_buena / cant_ord

        # ----- TIEMPOS -----
        real = fila["tiempo_real"]
        inf = fila["tiempo_informado"]
        desvio_t = inf - real
        ajuste_t = -desvio_t  # Lo que falta informar para que quede 0

        estado_t = "OK" if abs(desvio_t) < 0.01 else "REVISAR"

        resultados_tiempos.append({
            "orden": orden,
            "tiempo real": real,
            "tiempo informado": inf,
            "desvío": desvio_t,
            "ajuste necesario": ajuste_t,
            "estado": estado_t
        })

        # ----- MATERIALES -----
        mat = materiales[materiales["orden"] == orden]

        for _, m in mat.iterrows():
            esperado = m["cantidad necesaria"] * relacion
            desvio_m = m["cantidad tomada"] - esperado
            ajuste_m = -desvio_m
            estado_m = "OK" if abs(desvio_m) < 0.01 else "REVISAR"

            resultados_materiales.append({
                "orden": orden,
                "material": m["material"],
                "texto": m["texto breve material"],
                "cant necesaria": m["cantidad necesaria"],
                "cant tomada": m["cantidad tomada"],
                "esperado": esperado,
                "desvío": desvio_m,
                "ajuste necesario": ajuste_m,
                "estado": estado_m
            })


    # ------------------ MOSTRAR RESULTADOS ------------------

    st.header("Resultados de Tiempos")
    df_ti = pd.DataFrame(resultados_tiempos)
    st.dataframe(df_ti)

    st.header("Resultados de Materiales")
    df_mat = pd.DataFrame(resultados_materiales)
    st.dataframe(df_mat)

else:
    st.info("Cargá los 4 archivos para comenzar.")
