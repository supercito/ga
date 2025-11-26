import streamlit as st
import pandas as pd

st.title("🔎 Analizador Automático de Producción")

# ---------------- 1. SUBIDA DE ARCHIVOS ----------------
st.header("📂 Cargar archivos")
tiempo_real_file = st.file_uploader("⏱ Tiempo real", type=["xlsx"])
componentes_file = st.file_uploader("📦 Componentes", type=["xlsx"])
tiempos_inf_file = st.file_uploader("📝 Tiempos informados", type=["xlsx"])
produccion_file = st.file_uploader("🏭 Producción", type=["xlsx"])

def leer_excel(file):
    if file is None:
        return None
    return pd.read_excel(file)

# ---------------- 2. PROCESAR CUANDO ESTÉN TODOS ----------------

if tiempo_real_file and componentes_file and tiempos_inf_file and produccion_file:

    df_tr = leer_excel(tiempo_real_file)
    df_comp = leer_excel(componentes_file)
    df_tinf = leer_excel(tiempos_inf_file)
    df_prod = leer_excel(produccion_file)

    st.success("✔ Archivos cargados correctamente")

    # -------- Normalizar nombres de columnas --------
    def normalizar(df):
        df.columns = (
            df.columns.str.strip()
            .str.lower()
            .str.replace("á","a")
            .str.replace("é","e")
            .str.replace("í","i")
            .str.replace("ó","o")
            .str.replace("ú","u")
        )
        return df

    df_tr = normalizar(df_tr)
    df_comp = normalizar(df_comp)
    df_tinf = normalizar(df_tinf)
    df_prod = normalizar(df_prod)

    # ------- Función para detectar columnas --------
    def detectar_columna(df, palabra):
        for c in df.columns:
            if palabra in c:
                return c
        return None

    # Detectar columnas de orden
    col_orden_prod = detectar_columna(df_prod, "orden")
    col_orden_comp = detectar_columna(df_comp, "orden")
    col_orden_tr = detectar_columna(df_tr, "orden")
    col_orden_tinf = detectar_columna(df_tinf, "orden")

    # Detectar columnas de tiempo
    col_tiempo_real = detectar_columna(df_tr, "tiempo")
    col_tiempo_inf = detectar_columna(df_tinf, "tiempo")

    if not col_tiempo_real:
        st.error("❌ No se encontró columna de tiempo real.")
        st.write(df_tr.columns)
        st.stop()

    if not col_tiempo_inf:
        st.error("❌ No se encontró columna de tiempo informado.")
        st.write(df_tinf.columns)
        st.stop()

    # -------- Configurar márgenes --------
    st.header("⚙ Configuración de tolerancias (%)")
    margen_inferior = st.number_input("Margen inferior (%)", value=-10.0)
    margen_superior = st.number_input("Margen superior (%)", value=10.0)

    margen_inf = margen_inferior / 100
    margen_sup = margen_superior / 100

    resultados_materiales = []
    resultados_tiempos = []

    st.divider()
    st.header("📊 Resultados del análisis")

    # --------- Procesar TODAS las órdenes ---------
    for orden in df_prod[col_orden_prod].unique():

        prod = df_prod[df_prod[col_orden_prod] == orden].iloc[0]

        cantidad_orden = prod.get("cantidad orden", 0)
        cantidad_buena = prod.get("cantidad buena confirmada", 0)

        if cantidad_orden == 0:
            continue

        relacion = cantidad_buena / cantidad_orden

        # -------- MATERIALES --------
        comp_ord = df_comp[df_comp[col_orden_comp] == orden].copy()

        if len(comp_ord):

            col_tomada = detectar_columna(comp_ord, "tomada")
            col_texto = detectar_columna(comp_ord, "texto")

            comp_ord["esperado"] = comp_ord[col_tomada] * relacion
            comp_ord["desvio"] = comp_ord[col_tomada] - comp_ord["esperado"]

            comp_ord["% desvio"] = (comp_ord["desvio"] / comp_ord["esperado"]) * 100
            comp_ord["% desvio"] = comp_ord["% desvio"].replace([float("inf"), -float("inf")], 0)

            def estado_material(row):
                if row["esperado"] == 0:
                    return "🟢 OK"
                ratio = row["desvio"] / row["esperado"]
                return "🟢 OK" if margen_inf <= ratio <= margen_sup else "🔴 REVISAR"

            comp_ord["estado"] = comp_ord.apply(estado_material, axis=1)
            comp_ord["orden"] = orden

            resultados_materiales.append(comp_ord[[ 
                "orden",
                col_texto,
                col_tomada,
                "esperado",
                "desvio",
                "% desvio",
                "estado"
            ]])

        # -------- TIEMPOS --------
        t_real = df_tr[df_tr[col_orden_tr] == orden]
        t_inf = df_tinf[df_tinf[col_orden_tinf] == orden]

        tiempo_real = float(t_real[col_tiempo_real].sum()) if len(t_real) else 0
        tiempo_inf = float(t_inf[col_tiempo_inf].sum()) if len(t_inf) else 0

        desvio_t = tiempo_inf - tiempo_real
        pct_desvio = ((tiempo_inf - tiempo_real) / tiempo_real * 100) if tiempo_real != 0 else 0

        estado_tiempo = (
            "🟢 OK" if margen_inf <= pct_desvio/100 <= margen_sup else "🔴 REVISAR"
        )

        resultados_tiempos.append({
            "orden": orden,
            "tiempo real": tiempo_real,
            "tiempo informado": tiempo_inf,
            "desvio (min)": desvio_t,
            "% desvio": pct_desvio,
            "estado": estado_tiempo
        })

    # ------------- Mostrar resultados -------------
    if resultados_materiales:
        st.subheader("📦 Desvíos en Materiales")
        df_res_mat = pd.concat(resultados_materiales)
        st.dataframe(df_res_mat)

    st.subheader("⏱ Desvíos en Tiempos")
    df_res_tiempo = pd.DataFrame(resultados_tiempos)
    st.dataframe(df_res_tiempo)

else:
    st.info("⏳ Sube todos los archivos para comenzar.")
