import streamlit as st
import pandas as pd

st.title("Analizador Automático de Producción")

# ----------------------------------------------------------
# FUNCIÓN: LECTURA & NORMALIZACIÓN NUMÉRICA
# ----------------------------------------------------------
def leer_excel(file):
    if file is None:
        return None
    return pd.read_excel(file)

def normalizar_num(x):
    """Convierte números con punto y coma a float seguro"""
    if pd.isna(x):
        return 0
    x = str(x).replace(".", "").replace(",", ".")
    try:
        return float(x)
    except:
        return 0

# ----------------------------------------------------------
# SUBIDA DE ARCHIVOS
# ----------------------------------------------------------
st.header("Cargar archivos")

tr_file = st.file_uploader("Tiempo Real", type=["xlsx"])
cp_file = st.file_uploader("Componentes", type=["xlsx"])
ti_file = st.file_uploader("Tiempos Informados", type=["xlsx"])
pr_file = st.file_uploader("Producción", type=["xlsx"])

if tr_file and cp_file and ti_file and pr_file:

    tr_raw = leer_excel(tr_file)
    cp = leer_excel(cp_file)
    ti = leer_excel(ti_file)
    pr = leer_excel(pr_file)

    st.success("Archivos cargados correctamente")

    # ----------------------------------------------------------
    # LIMPIEZA TIEMPO REAL (solo 2 columnas reales)
    # ----------------------------------------------------------
    tr = pd.DataFrame()
    tr["orden"] = tr_raw.iloc[:, 0].astype(str).str.replace(".0", "", regex=False)
    tr["tiempo_real"] = tr_raw.iloc[:, 9].apply(normalizar_num)

    # ----------------------------------------------------------
    # NORMALIZACIÓN GENERAL
    # ----------------------------------------------------------
    for df in [cp, ti, pr]:
        df.columns = df.columns.str.lower().str.strip()

    # CORREGIR FORMATO ORDEN
    cp["orden"] = cp["orden"].astype(str).str.replace(".0", "", regex=False)
    ti["orden"] = ti["orden"].astype(str).str.replace(".0", "", regex=False)
    pr["orden"] = pr["orden"].astype(str).str.replace(".0", "", regex=False)

    # ----------------------------------------------------------
    # TIEMPOS INFORMADOS – convertir a horas reales
    # ----------------------------------------------------------
    ti["duración tratamiento"] = ti["duración tratamiento"].apply(normalizar_num)

    tiempos_inf = (
        ti.groupby("orden")["duración tratamiento"]
        .sum()
        .reset_index()
        .rename(columns={"duración tratamiento": "tiempo_informado"})
    )

    # ----------------------------------------------------------
    # PRODUCCIÓN: cantidades correctas
    # ----------------------------------------------------------
    pr["cantidad orden"] = pr["cantidad orden"].apply(normalizar_num)
    pr["cantidad buena confirmada"] = pr["cantidad buena confirmada"].apply(normalizar_num)

    df = pr[["orden", "cantidad orden", "cantidad buena confirmada"]].copy()

    # ----------------------------------------------------------
    # UNIÓN
    # ----------------------------------------------------------
    df = df.merge(tr, on="orden", how="left")
    df = df.merge(tiempos_inf, on="orden", how="left")

    df["tiempo_real"] = df["tiempo_real"].fillna(0)
    df["tiempo_informado"] = df["tiempo_informado"].fillna(0)

    # ----------------------------------------------------------
    # COMPONENTES: normalizar cantidades
    # ----------------------------------------------------------
    cp["cantidad necesaria"] = cp["cantidad necesaria"].apply(normalizar_num)
    cp["cantidad tomada"] = cp["cantidad tomada"].apply(normalizar_num)

    # ----------------------------------------------------------
    # ANÁLISIS FINAL
    # ----------------------------------------------------------
    resultados_materiales = []
    resultados_tiempos = []

    for orden in df["orden"].unique():

        fila = df[df["orden"] == orden].iloc[0]

        cant_ord = fila["cantidad orden"]
        cant_buena = fila["cantidad buena confirmada"]

        relacion = (cant_buena / cant_ord) if cant_ord != 0 else 1

        # ---- TIEMPOS ----
        real = fila["tiempo_real"]
        inf = fila["tiempo_informado"]
        desvio_t = inf - real
        ajuste_t = -desvio_t
        estado_t = "OK" if abs(desvio_t) < 0.01 else "REVISAR"

        resultados_tiempos.append({
            "orden": orden,
            "tiempo real (hrs)": real,
            "tiempo informado (hrs)": inf,
            "desvío (hrs)": desvio_t,
            "ajuste necesario": ajuste_t,
            "estado": estado_t
        })

        # ---- MATERIALES ----
        mat = cp[cp["orden"] == orden]

        for _, m in mat.iterrows():
            esperado = m["cantidad necesaria"] * relacion
            desvio_m = m["cantidad tomada"] - esperado
            ajuste_m = -desvio_m
            estado_m = "OK" if abs(desvio_m) < 0.01 else "REVISAR"

            resultados_materiales.append({
                "orden": orden,
                "material": m["material"],
                "texto": m["texto breve material"],
                "cantidad necesaria": m["cantidad necesaria"],
                "cantidad tomada": m["cantidad tomada"],
                "esperado según producción": esperado,
                "desvío": desvio_m,
                "ajuste necesario": ajuste_m,
                "estado": estado_m
            })

    # ----------------------------------------------------------
    # MOSTRAR RESULTADOS
    # ----------------------------------------------------------

    st.header("Resultados de Tiempos")
    st.dataframe(pd.DataFrame(resultados_tiempos))

    st.header("Resultados de Materiales")
    st.dataframe(pd.DataFrame(resultados_materiales))

else:
    st.info("Cargá los 4 archivos para comenzar.")
