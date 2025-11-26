import streamlit as st
import pandas as pd

st.title("Analizador de Producción")

# ---------------- 1. SUBIDA DE ARCHIVOS ----------------
st.header("Cargar archivos")
tiempo_real_file = st.file_uploader("Tiempo real", type=["xlsx"])
componentes_file = st.file_uploader("Componentes", type=["xlsx"])
tiempos_inf_file = st.file_uploader("Tiempos informados", type=["xlsx"])
produccion_file = st.file_uploader("Producción", type=["xlsx"])

def leer_excel(file):
    if file is None:
        return None
    return pd.read_excel(file)

# ---------------- 2. PROCESAR CUANDO ESTÉN TODOS ----------------
if (
    tiempo_real_file is not None
    and componentes_file is not None
    and tiempos_inf_file is not None
    and produccion_file is not None
):

    df_tr = leer_excel(tiempo_real_file)
    df_comp = leer_excel(componentes_file)
    df_tinf = leer_excel(tiempos_inf_file)
    df_prod = leer_excel(produccion_file)

    st.success("Archivos cargados correctamente")

    # --- CONFIGURAR MÁRGENES ---
    st.header("Configuración de tolerancias (%)")
    margen_inferior = st.number_input("Margen inferior (%)", value=-10.0)
    margen_superior = st.number_input("Margen superior (%)", value=10.0)

    margen_inf = margen_inferior / 100
    margen_sup = margen_superior / 100

    # --- Resultados acumulados ---
    resultados_materiales = []
    resultados_tiempos = []

    # ---------------- 3. RECORRER TODAS LAS ÓRDENES ----------------
    for orden in df_prod["Orden"].unique():

        prod = df_prod[df_prod["Orden"] == orden].iloc[0]
        cantidad_orden = prod["Cantidad orden"]
        cantidad_buena = prod["Cantidad buena confirmada"]

        if cantidad_orden == 0:
            continue

        relacion = cantidad_buena / cantidad_orden

        # ----- MATERIALES -----
        comp_ord = df_comp[df_comp["Orden"] == orden].copy()

        if len(comp_ord):
            comp_ord["Esperado"] = comp_ord["Cantidad tomada"] * relacion
            comp_ord["Desvío"] = comp_ord["Cantidad tomada"] - comp_ord["Esperado"]

            def estado_material(row):
                if row["Esperado"] == 0:
                    return "OK"
                ratio = row["Desvío"] / row["Esperado"]
                return "OK" if margen_inf <= ratio <= margen_sup else "REVISAR"

            comp_ord["Estado"] = comp_ord.apply(estado_material, axis=1)
            comp_ord["Orden"] = orden

            resultados_materiales.append(comp_ord)

        # ----- TIEMPOS -----
        t_real = df_tr[df_tr["Orden Producción"] == orden]
        t_inf = df_tinf[df_tinf["Orden"] == orden]

        tiempo_real = float(t_real["Tiempo"].iloc[0]) if len(t_real) else 0
        tiempo_inf = float(t_inf["Tiempo"].iloc[0]) if len(t_inf) else 0
        desvio = tiempo_inf - tiempo_real

        estado_tiempo = "OK" if margen_inf <= desvio <= margen_sup else "REVISAR"

        resultados_tiempos.append({
            "Orden": orden,
            "Tiempo real": tiempo_real,
            "Tiempo informado": tiempo_inf,
            "Desvío": desvio,
            "Estado": estado_tiempo
        })

    # ---------------- 4. MOSTRAR RESULTADOS ----------------
    if resultados_materiales:
        df_res_mat = pd.concat(resultados_materiales)
        st.subheader("Desvíos en Materiales")
        st.dataframe(df_res_mat[[
            "Orden",
            "Texto breve material",
            "Cantidad tomada",
            "Esperado",
            "Desvío",
            "Estado"
        ]])

    df_res_tiempos = pd.DataFrame(resultados_tiempos)
    st.subheader("Desvíos en Tiempos")
    st.dataframe(df_res_tiempos)
else:
    st.info("Sube todos los archivos para comenzar.")
