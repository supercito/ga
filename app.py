import streamlit as st
import pandas as pd

st.title("Analisis de Producción: Tiempos y Materiales")

st.write("Subí los archivos: tiempos reales, tiempos informados, produccion y componentes.")

tiempos_reales = st.file_uploader("Tiempos reales", type=["xlsx","csv"])
tiempos_inf = st.file_uploader("Tiempos informados", type=["xlsx","csv"])
produccion = st.file_uploader("Produccion", type=["xlsx","csv"])
componentes = st.file_uploader("Componentes", type=["xlsx","csv"])

if st.button("Procesar"):
    def load(f):
        if f.name.endswith('.csv'): return pd.read_csv(f)
        return pd.read_excel(f)

    df_real = load(tiempos_reales)
    df_inf = load(tiempos_inf)
    df_prod = load(produccion)
    df_comp = load(componentes)

    # rename heuristic
    real_col = 'tiempo de máquina'
    inf_col = 'activ.1 notificada'

    df_time = pd.merge(df_real, df_inf, on='Orden', how='outer', suffixes=('_real','_inf'))
    df_time['time_diff'] = df_time[real_col] - df_time[inf_col]

    def action(row):
        if pd.isna(row[real_col]): return 'falta_medicion_real'
        if pd.isna(row[inf_col]): return 'informar_tiempo_en_SAP'
        if row['time_diff'] > 0: return 'aumentar_tiempo_en_SAP'
        if row['time_diff'] < 0: return 'reducir_tiempo_informado_en_SAP'
        return 'ok'

    df_time['accion'] = df_time.apply(action, axis=1)
    st.subheader("Resultado Tiempos")
    st.dataframe(df_time)

    # materiales
    df_comp['consumo_real'] = df_comp['cantidad tomada']
    df_comp['consumo_esp'] = df_comp['cantidad necesaria']
    df_comp['diff'] = df_comp['consumo_real'] - df_comp['consumo_esp']
    df_comp['pct'] = df_comp['diff'] / df_comp['consumo_esp'] * 100
    st.subheader("Resultado Materiales")
    st.dataframe(df_comp)

    alerts = df_comp[(df_comp['pct'] > 5) | (df_comp['pct'] < -5)]
    st.subheader("Alertas Materiales")
    st.dataframe(alerts)

    st.success("Proceso terminado.")
