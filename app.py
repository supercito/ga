import streamlit as st
import pandas as pd

st.title("Analizador de Producción")

# ------- 1. SUBIDA DE ARCHIVOS -------
st.header("Cargar archivos")
tiempo_real_file = st.file_uploader("Tiempo real", type=["xlsx"])
componentes_file = st.file_uploader("Componentes", type=["xlsx"])
tiempos_inf_file = st.file_uploader("Tiempos informados", type=["xlsx"])
produccion_file = st.file_uploader("Producción", type=["xlsx"])


def leer_excel(file):
    if file is None:
        return None
    return pd.read_excel(file)


# ------- 2. PROCESAR CUANDO ESTÉN TODOS -------
if (
    tiempo_real_file
    and componentes_file
    and tiempos_inf_file
    and produccion_file
):

    df_tr = leer_excel(tiempo_real_file)
    df_comp = leer_excel(componentes_file)
    df_tinf = leer_excel(tiempos_inf_file)
    df_prod = leer_excel(produccion_file)

    st.success("Archivos cargados correctamente")

    # Listar órdenes disponibles
    ordenes = df_prod["Orden"].unique()
    orden_sel = st.selectbox("Seleccionar orden:", ordenes)

    if orden_sel:

        # --- Producción ---
        prod = df_prod[df_prod["Orden"] == orden_sel].iloc[0]
        cantidad_orden = prod["Cantidad orden"]
        cantidad_buena = prod["Cantidad buena confirmada"]

        relacion = cantidad_buena / cantidad_orden

        st.subheader(f"Orden {orden_sel}")
        st.write(f"**Relación producción:** {relacion:.2%}")

        # --- Materiales ---
        comp = df_comp[df_comp["Orden"] == orden_sel].copy()
        comp["Esperado"] = comp["Cantidad tomada"] * relacion
        comp["Desvío"] = comp["Cantidad tomada"] - comp["Esperado"]

        st.subheader("Materiales")
        st.dataframe(comp[["Texto Breve Material", "Cantidad tomada", "Esperado", "Desvío"]])

        # --- Tiempos ---
        t_real = df_tr[df_tr["Orden Producción"] == orden_sel]
        t_inf = df_tinf[df_tinf["Orden"] == orden_sel]

        tiempo_real = float(t_real["Tiempo"].iloc[0]) if len(t_real) else 0
        tiempo_inf = float(t_inf["Tiempo"].iloc[0]) if len(t_inf) else 0

        desvio_tiempo = tiempo_inf - tiempo_real

        st.subheader("Tiempo")
        st.write(f"Tiempo real: **{tiempo_real}**")
        st.write(f"Tiempo informado: **{tiempo_inf}**")
        st.write(
            f"Desvío tiempo: "
            f"**{desvio_tiempo:+.2f}** {'(OK)' if desvio_tiempo == 0 else '(Revisar)'}"
        )
