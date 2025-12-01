import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard Control Producción", layout="wide", page_icon="📊")

st.title("📊 Dashboard de Control: SAP vs Real")
st.markdown("""
Analiza los desvíos directamente en pantalla. Utiliza las pestañas de abajo para navegar entre **Horas** y **Materiales**.
Si detectas errores, puedes descargar el reporte Excel corregido al final.
""")

# --- FUNCIONES DE LIMPIEZA ---
def limpiar_orden(df, col_name):
    if col_name in df.columns:
        return df[col_name].astype(str).str.split('.').str[0].str.strip()
    return df[col_name]

def limpiar_numero(val):
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        val = val.strip()
        val = val.replace('.', '').replace(',', '.') 
        try:
            return float(val)
        except ValueError:
            return 0.0
    return 0.0

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Configuración")

st.sidebar.subheader("1. Parámetros Materiales")
merma_input = st.sidebar.number_input(
    "Merma Permitida (%)", 
    min_value=0.0, max_value=20.0, value=3.0, step=0.1
) / 100

tolerancia_filtro = st.sidebar.slider(
    "Ocultar desvíos menores al (%):", 
    min_value=0.0, max_value=50.0, value=1.0, step=0.5,
    help="Filtra errores pequeños que no valen la pena corregir."
)

st.sidebar.markdown("---")
st.sidebar.subheader("2. Subir Archivos")

file_mat = st.sidebar.file_uploader("Materiales (SAP)", type=["xlsx", "xls"])
file_prod = st.sidebar.file_uploader("Producción (Excel)", type=["xlsx", "xls"]) 
file_real_time = st.sidebar.file_uploader("Tiempos Reales (Piso)", type=["xlsx", "xls"])
file_sap_time = st.sidebar.file_uploader("Tiempos SAP", type=["xlsx", "xls"])

# --- LÓGICA PRINCIPAL ---
if file_mat and file_prod and file_real_time and file_sap_time:
    try:
        with st.spinner('Procesando datos...'):
            # Cargar DataFrames
            df_mat = pd.read_excel(file_mat)
            df_real = pd.read_excel(file_real_time)
            df_sap_time = pd.read_excel(file_sap_time)
            
            # --- LIMPIEZA ---
            # Ordenes
            df_mat['Orden'] = limpiar_orden(df_mat, 'Orden')
            df_real['Orden'] = limpiar_orden(df_real, 'Orden Producción')
            df_sap_time['Orden'] = limpiar_orden(df_sap_time, 'Orden')

            # Números
            df_mat['Cantidad necesaria'] = df_mat['Cantidad necesaria'].apply(limpiar_numero)
            df_mat['Cantidad tomada'] = df_mat['Cantidad tomada'].apply(limpiar_numero)
            df_real['Tiempo de Máquina'] = df_real['Tiempo de Máquina'].apply(limpiar_numero)
            df_sap_time['Activ.1 notificada'] = df_sap_time['Activ.1 notificada'].apply(limpiar_numero)

            # ==========================================
            # 🕒 PROCESAMIENTO HORAS
            # ==========================================
            sap_horas = df_sap_time.groupby('Orden')['Activ.1 notificada'].sum().reset_index()
            real_horas = df_real.groupby('Orden')['Tiempo de Máquina'].sum().reset_index()

            df_h = pd.merge(sap_horas, real_horas, on='Orden', how='outer').fillna(0)
            df_h.rename(columns={'Activ.1 notificada': 'Horas_SAP', 'Tiempo de Máquina': 'Horas_Real'}, inplace=True)
            
            df_h['Diferencia'] = df_h['Horas_Real'] - df_h['Horas_SAP']
            
            # Lógica de acción
            def get_action_h(val):
                if abs(val) < 0.05: return "OK"
                return "SUMAR A SAP" if val > 0 else "RESTAR A SAP"

            df_h['Acción'] = df_h['Diferencia'].apply(get_action_h)
            
            # Filtrar solo errores para mostrar
            df_h_show = df_h[df_h['Acción'] != "OK"].copy()
            df_h_show = df_h_show.sort_values(by='Diferencia', ascending=False)

            # ==========================================
            # 🧪 PROCESAMIENTO MATERIALES
            # ==========================================
            df_mat['Consumo_Maximo_OK'] = df_mat['Cantidad necesaria'] * (1 + merma_input)
            df_mat['Desvio_Abs'] = df_mat['Cantidad tomada'] - df_mat['Consumo_Maximo_OK']
            
            # Porcentaje real de desvío sobre la base
            df_mat['% Desvio'] = df_mat.apply(
                lambda x: ((x['Cantidad tomada'] - x['Cantidad necesaria']) / x['Cantidad necesaria'] * 100) 
                if x['Cantidad necesaria'] > 0 else 0, axis=1
            )

            # Filtro de tolerancia visual
            mask_tolerancia = abs(df_mat['% Desvio']) >= tolerancia_filtro
            df_mat_view = df_mat[mask_tolerancia].copy()

            # Estado
            conditions = [
                (df_mat_view['Cantidad tomada'] < df_mat_view['Cantidad necesaria']),
                (df_mat_view['Cantidad tomada'] > df_mat_view['Consumo_Maximo_OK'])
            ]
            choices = ['FALTA CARGAR', 'EXCEDENTE']
            df_mat_view['Estado'] = np.select(conditions, choices, default='EN RANGO')
            
            # Filtramos los que están "En Rango" (aunque pasen la tolerancia numérica, si están dentro de la merma, es OK)
            df_mat_final = df_mat_view[df_mat_view['Estado'] != 'EN RANGO'].copy()
            
            # Cantidad a corregir
            df_mat_final['Ajuste_Sugerido'] = np.where(
                df_mat_final['Estado'] == 'FALTA CARGAR',
                df_mat_final['Cantidad necesaria'] - df_mat_final['Cantidad tomada'],
                df_mat_final['Cantidad tomada'] - df_mat_final['Consumo_Maximo_OK']
            )

        # ==========================================
        # 🖥️ VISUALIZACIÓN ONLINE (DASHBOARD)
        # ==========================================
        
        # PESTAÑAS PRINCIPALES
        tab1, tab2 = st.tabs(["🕒 Análisis de Horas", "🧪 Análisis de Materiales"])

        # --- TAB 1: HORAS ---
        with tab1:
            st.subheader("Control de Tiempos")
            
            # KPIs
            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            errores_horas = len(df_h_show)
            horas_faltantes = df_h_show[df_h_show['Diferencia'] > 0]['Diferencia'].sum()
            horas_sobrantes = abs(df_h_show[df_h_show['Diferencia'] < 0]['Diferencia'].sum())

            col_kpi1.metric("Órdenes con Error", errores_horas, border=True)
            col_kpi2.metric("Horas que faltan cargar", f"{horas_faltantes:.2f} h", delta="Déficit SAP", delta_color="inverse", border=True)
            col_kpi3.metric("Horas excedidas en SAP", f"{horas_sobrantes:.2f} h", delta="Exceso SAP", delta_color="normal", border=True)

            st.write("### 📋 Detalle de Órdenes a Corregir")
            st.markdown("_Puedes ordenar la tabla haciendo clic en los encabezados_")
            
            # Tabla Estilizada
            st.dataframe(
                df_h_show.style.format({
                    'Horas_SAP': '{:.2f}', 
                    'Horas_Real': '{:.2f}', 
                    'Diferencia': '{:+.2f}'
                }).background_gradient(subset=['Diferencia'], cmap='RdYlGn', vmin=-5, vmax=5),
                use_container_width=True,
                height=400
            )

            # Botón Descarga Tab 1
            buffer_h = io.BytesIO()
            with pd.ExcelWriter(buffer_h, engine='xlsxwriter') as writer:
                df_h_show.to_excel(writer, index=False, sheet_name='Ajuste Horas')
            
            st.download_button(
                label="📥 Descargar Reporte de Horas (.xlsx)",
                data=buffer_h.getvalue(),
                file_name="Ajuste_Horas_SAP.xlsx",
                mime="application/vnd.ms-excel"
            )

        # --- TAB 2: MATERIALES ---
        with tab2:
            st.subheader(f"Control de Materiales (Merma: {merma_input*100}%)")
            
            # KPIs
            col_m1, col_m2 = st.columns(2)
            mat_criticos = len(df_mat_final[df_mat_final['Estado'] == 'EXCEDENTE'])
            mat_falta = len(df_mat_final[df_mat_final['Estado'] == 'FALTA CARGAR'])
            
            col_m1.metric("Materiales con Excedente Crítico", mat_criticos, border=True)
            col_m2.metric("Materiales Pendientes de Carga", mat_falta, border=True)

            st.write("### 📋 Detalle de Desvíos")
            
            # Selección de columnas para ver online
            cols_ver = ['Orden', 'Material', 'Texto breve material', 'Cantidad necesaria', 
                        'Cantidad tomada', 'Estado', 'Ajuste_Sugerido', '% Desvio']
            
            # Colores dinámicos
            def color_estado(val):
                color = '#ffcccb' if val == 'EXCEDENTE' else '#fff4cc' # Rojo suave o Naranja suave
                return f'background-color: {color}; color: black'

            st.dataframe(
                df_mat_final[cols_ver].style.format({
                    'Cantidad necesaria': '{:.2f}',
                    'Cantidad tomada': '{:.2f}',
                    'Ajuste_Sugerido': '{:.2f}',
                    '% Desvio': '{:.1f}%'
                }).applymap(color_estado, subset=['Estado']),
                use_container_width=True,
                height=500
            )

            # Botón Descarga Tab 2
            buffer_m = io.BytesIO()
            with pd.ExcelWriter(buffer_m, engine='xlsxwriter') as writer:
                df_mat_final.to_excel(writer, index=False, sheet_name='Ajuste Materiales')
            
            st.download_button(
                label="📥 Descargar Reporte de Materiales (.xlsx)",
                data=buffer_m.getvalue(),
                file_name="Ajuste_Materiales_SAP.xlsx",
                mime="application/vnd.ms-excel"
            )

    except Exception as e:
        st.error(f"⚠️ Error al procesar: {e}")
        st.write("Por favor revisa que los encabezados de los archivos Excel sean los correctos.")
else:
    # Mensaje de bienvenida cuando no hay archivos
    st.info("👈 Por favor, carga los 4 archivos en el menú lateral para comenzar el análisis.")
