import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard Corrector SAP", layout="wide", page_icon="🏭")

st.title("🏭 Dashboard de Control Industrial")
st.markdown("""
**Sistema de Control:** Análisis de desvíos en Horas y Materiales.
Detecta automáticamente el inicio de las tablas en los archivos Excel.
""")

# --- FUNCIONES DE CARGA ROBUSTA ---

def encontrar_fila_encabezado(df, palabras_clave):
    """Busca dónde empieza realmente la tabla."""
    for i in range(min(15, len(df))):
        fila_texto = df.iloc[i].astype(str).str.lower().tolist()
        texto_unido = " ".join(fila_texto)
        if any(clave in texto_unido for clave in palabras_clave):
            df.columns = df.iloc[i]
            df = df.iloc[i+1:].reset_index(drop=True)
            df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
            return df, i
    return df, 0

def cargar_excel_inteligente(uploaded_file, keywords, nombre_archivo):
    if uploaded_file is None: return None
    try:
        df_crudo = pd.read_excel(uploaded_file, header=None)
        df_limpio, fila = encontrar_fila_encabezado(df_crudo, keywords)
        if fila > 0:
            st.toast(f"✅ {nombre_archivo}: Tabla detectada en fila {fila + 1}")
        return df_limpio
    except Exception as e:
        st.error(f"Error leyendo {nombre_archivo}: {e}")
        return None

def limpiar_numero(val):
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        val = val.strip()
        val = val.replace('KG', '').replace('CJ', '').replace('HRA', '').strip()
        val = val.replace('.', '').replace(',', '.') 
        try:
            return float(val)
        except ValueError:
            return 0.0
    return 0.0

def limpiar_orden(df, col_name_patterns):
    col_found = None
    for col in df.columns:
        if any(patron in col.lower() for patron in col_name_patterns):
            col_found = col
            break
    if col_found:
        df['Orden_Key'] = df[col_found].astype(str).str.split('.').str[0].str.strip()
        return df, True
    else:
        return df, False

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Configuración")
merma_input = st.sidebar.number_input("Merma Permitida (%)", 0.0, 20.0, 3.0, 0.1) / 100
tolerancia_filtro = st.sidebar.slider("Filtro visual (%)", 0.0, 50.0, 1.0, 0.5)

st.sidebar.divider()
st.sidebar.subheader("Carga de Archivos")

f_mat = st.sidebar.file_uploader("1. Materiales (SAP)", type=["xlsx"])
f_prod = st.sidebar.file_uploader("2. Producción (Excel)", type=["xlsx"]) 
f_real = st.sidebar.file_uploader("3. Tiempos Reales (Piso)", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("4. Tiempos SAP", type=["xlsx"])

# --- ESTILOS DE COLOR (SIN MATPLOTLIB) ---
def estilo_horas(val):
    """Pinta rojo si falta sumar (positivo), azul si hay que restar (negativo)"""
    if val > 0.05:
        return 'color: #d32f2f; font-weight: bold;' # Rojo
    elif val < -0.05:
        return 'color: #1976d2; font-weight: bold;' # Azul
    return 'color: gray;'

def estilo_materiales(val):
    """Pinta fondo rojo si es excedente, naranja si falta cargar"""
    if val == 'EXCEDENTE':
        return 'background-color: #ffcdd2; color: black;' # Rojo claro
    elif val == 'FALTA CARGAR':
        return 'background-color: #ffe0b2; color: black;' # Naranja claro
    return ''

# --- LÓGICA PRINCIPAL ---
if f_mat and f_prod and f_real and f_sap_t:
    
    # 1. CARGA
    df_mat = cargar_excel_inteligente(f_mat, ['cantidad necesaria', 'texto breve'], "Materiales")
    df_prod = cargar_excel_inteligente(f_prod, ['cantidad buena', 'cantidad orden'], "Producción")
    df_real = cargar_excel_inteligente(f_real, ['tiempo de máquina', 'sector', 'planta'], "Tiempos Reales")
    df_sap_t = cargar_excel_inteligente(f_sap_t, ['activ.1', 'recursos'], "Tiempos SAP")

    if all(v is not None for v in [df_mat, df_prod, df_real, df_sap_t]):
        try:
            # 2. NORMALIZACIÓN
            df_mat, ok1 = limpiar_orden(df_mat, ['orden'])
            df_real, ok2 = limpiar_orden(df_real, ['orden']) 
            df_sap_t, ok3 = limpiar_orden(df_sap_t, ['orden'])
            
            if not (ok1 and ok2 and ok3):
                st.error("❌ No se encontró columna 'Orden'. Revisa los archivos.")
                st.stop()

            # 3. LIMPIEZA NUMÉRICA
            def buscar_col(df, keywords):
                for col in df.columns:
                    if any(k in col.lower() for k in keywords): return col
                return None

            # Materiales
            c_necesaria = buscar_col(df_mat, ['necesaria'])
            c_tomada = buscar_col(df_mat, ['tomada', 'real'])
            if c_necesaria and c_tomada:
                df_mat['Nec_Num'] = df_mat[c_necesaria].apply(limpiar_numero)
                df_mat['Tom_Num'] = df_mat[c_tomada].apply(limpiar_numero)
            
            # Tiempos
            c_tiempo_real = buscar_col(df_real, ['tiempo de máquina', 'tiempo maquina', 'machine'])
            if c_tiempo_real:
                df_real['Real_Time_Num'] = df_real[c_tiempo_real].apply(limpiar_numero)
            else:
                st.error("No se encontró columna de Tiempos Reales.")
                st.stop()

            c_tiempo_sap = buscar_col(df_sap_t, ['activ.1', 'notificada'])
            if c_tiempo_sap:
                df_sap_t['Sap_Time_Num'] = df_sap_t[c_tiempo_sap].apply(limpiar_numero)

            # ----------------------------------------------------
            # CÁLCULOS
            # ----------------------------------------------------

            # A. HORAS
            g_sap = df_sap_t.groupby('Orden_Key')['Sap_Time_Num'].sum().reset_index()
            g_real = df_real.groupby('Orden_Key')['Real_Time_Num'].sum().reset_index()
            
            df_horas = pd.merge(g_sap, g_real, on='Orden_Key', how='outer').fillna(0)
            df_horas['Diferencia'] = df_horas['Real_Time_Num'] - df_horas['Sap_Time_Num']
            
            df_horas['Acción'] = np.select(
                [df_horas['Diferencia'] > 0.05, df_horas['Diferencia'] < -0.05],
                ['SUMAR A SAP', 'RESTAR A SAP'],
                default='OK'
            )
            
            df_horas_final = df_horas[df_horas['Acción'] != 'OK'].copy()
            df_horas_final = df_horas_final.sort_values('Diferencia', ascending=False)
            df_horas_final.columns = ['Orden', 'Horas SAP', 'Horas Reales', 'Ajuste Necesario', 'Acción']

            # B. MATERIALES
            df_mat['Max_Teorico'] = df_mat['Nec_Num'] * (1 + merma_input)
            
            condiciones = [
                (df_mat['Tom_Num'] < df_mat['Nec_Num']),
                (df_mat['Tom_Num'] > df_mat['Max_Teorico'])
            ]
            opciones = ['FALTA CARGAR', 'EXCEDENTE']
            df_mat['Estado'] = np.select(condiciones, opciones, default='OK')
            
            df_mat['Ajuste'] = np.select(
                [df_mat['Estado'] == 'FALTA CARGAR', df_mat['Estado'] == 'EXCEDENTE'],
                [df_mat['Nec_Num'] - df_mat['Tom_Num'], df_mat['Tom_Num'] - df_mat['Max_Teorico']],
                default=0
            )
            
            df_mat['% Desvio'] = np.where(df_mat['Nec_Num'] > 0, 
                                          (df_mat['Tom_Num'] - df_mat['Nec_Num']) / df_mat['Nec_Num'] * 100, 0)
            
            df_mat_final = df_mat[
                (df_mat['Estado'] != 'OK') & 
                (abs(df_mat['% Desvio']) >= tolerancia_filtro)
            ].copy()
            
            col_material = buscar_col(df_mat, ['material'])
            col_texto = buscar_col(df_mat, ['texto', 'descrip'])
            
            cols_export = ['Orden_Key']
            if col_material: cols_export.append(col_material)
            if col_texto: cols_export.append(col_texto)
            cols_export.extend(['Nec_Num', 'Tom_Num', 'Estado', 'Ajuste', '% Desvio'])
            
            df_mat_view = df_mat_final[cols_export].copy()
            df_mat_view.rename(columns={'Orden_Key': 'Orden', 'Nec_Num': 'Necesaria', 'Tom_Num': 'Tomada'}, inplace=True)

            # ----------------------------------------------------
            # VISUALIZACIÓN
            # ----------------------------------------------------
            
            tab1, tab2 = st.tabs(["⏱️ Corrección Horas", "📦 Corrección Materiales"])
            
            with tab1:
                col1, col2 = st.columns(2)
                col1.metric("Órdenes con Error", len(df_horas_final))
                col2.metric("Horas Netas a Ajustar", f"{df_horas_final['Ajuste Necesario'].sum():.2f}")
                
                # APLICAMOS EL ESTILO MANUAL SIN MATPLOTLIB
                st.dataframe(
                    df_horas_final.style.applymap(estilo_horas, subset=['Ajuste Necesario'])
                    .format({'Horas SAP': '{:.2f}', 'Horas Reales': '{:.2f}', 'Ajuste Necesario': '{:+.2f}'}),
                    use_container_width=True
                )
                
                buffer_h = io.BytesIO()
                with pd.ExcelWriter(buffer_h) as writer:
                    df_horas_final.to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel Horas", buffer_h.getvalue(), "Correccion_Horas.xlsx")

            with tab2:
                col1, col2 = st.columns(2)
                col1.metric("Registros a Revisar", len(df_mat_view))
                criticos = len(df_mat_view[df_mat_view['Estado']=='EXCEDENTE'])
                col2.metric("Excedentes Críticos", criticos, delta_color="inverse")
                
                st.dataframe(
                    df_mat_view.style.applymap(estilo_materiales, subset=['Estado'])
                    .format({'Necesaria': '{:.3f}', 'Tomada': '{:.3f}', 'Ajuste': '{:.3f}', '% Desvio': '{:.1f}%'}),
                    use_container_width=True
                )
                
                buffer_m = io.BytesIO()
                with pd.ExcelWriter(buffer_m) as writer:
                    df_mat_view.to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel Materiales", buffer_m.getvalue(), "Correccion_Materiales.xlsx")

        except Exception as e:
            st.error(f"Error inesperado: {e}")
            st.write(e)
    else:
        st.warning("Verifica que los archivos no estén corruptos.")
else:
    st.info("Sube los 4 archivos para comenzar.")
