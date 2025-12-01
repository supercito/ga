import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard Corrector SAP", layout="wide", page_icon="🏭")

st.title("🏭 Dashboard de Control Industrial")
st.markdown("""
**Detector Automático:** Este sistema busca automáticamente dónde empieza la tabla en tus archivos Excel, 
incluso si tienen títulos o filas vacías al principio.
""")

# --- FUNCIONES ROBUSTAS DE CARGA ---

def encontrar_fila_encabezado(df, palabras_clave):
    """
    Busca en las primeras 15 filas si existe alguna que contenga 
    las palabras clave esperadas. Retorna el índice de la fila y el DF ajustado.
    """
    # Escaneamos las primeras filas
    for i in range(min(15, len(df))):
        fila_texto = df.iloc[i].astype(str).str.lower().tolist()
        # Unimos todo el texto de la fila para buscar
        texto_unido = " ".join(fila_texto)
        
        # Si encontramos alguna de las palabras clave (ej: 'orden', 'material')
        if any(clave in texto_unido for clave in palabras_clave):
            # Esta fila 'i' es el encabezado
            df.columns = df.iloc[i] # Asignar esta fila como columnas
            df = df.iloc[i+1:].reset_index(drop=True) # Tomar los datos de ahí para abajo
            
            # Limpiar nombres de columnas (quitar espacios y saltos de linea)
            df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
            return df, i
            
    return df, 0 # Si no encuentra nada, asume que la fila 0 era la correcta

def cargar_excel_inteligente(uploaded_file, keywords, nombre_archivo):
    if uploaded_file is None: return None
    
    try:
        # Leemos sin header para ver el contenido crudo
        df_crudo = pd.read_excel(uploaded_file, header=None)
        
        # Buscamos el encabezado real
        df_limpio, fila_encontrada = encontrar_fila_encabezado(df_crudo, keywords)
        
        if fila_encontrada > 0:
            st.toast(f"✅ Tabla detectada en fila {fila_encontrada + 1} para {nombre_archivo}")
        
        return df_limpio
    except Exception as e:
        st.error(f"Error leyendo {nombre_archivo}: {e}")
        return None

def limpiar_numero(val):
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        val = val.strip()
        # Elimina letras si se colaron (ej: "100 KG")
        val = val.replace('KG', '').replace('CJ', '').replace('HRA', '').strip()
        val = val.replace('.', '').replace(',', '.') 
        try:
            return float(val)
        except ValueError:
            return 0.0
    return 0.0

def limpiar_orden(df, col_name_patterns):
    """Busca la columna orden por patrones y la limpia"""
    col_found = None
    for col in df.columns:
        # Busca si el nombre de la columna contiene 'orden' (ignora mayus/minus)
        if any(patron in col.lower() for patron in col_name_patterns):
            col_found = col
            break
            
    if col_found:
        # Estandarizar nombre interno
        df['Orden_Key'] = df[col_found].astype(str).str.split('.').str[0].str.strip()
        return df, True
    else:
        return df, False

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Configuración")

st.sidebar.subheader("Tolerancias")
merma_input = st.sidebar.number_input("Merma Permitida (%)", 0.0, 20.0, 3.0, 0.1) / 100
tolerancia_filtro = st.sidebar.slider("Filtro visual (%)", 0.0, 50.0, 1.0, 0.5)

st.sidebar.divider()
st.sidebar.subheader("Carga de Archivos")

f_mat = st.sidebar.file_uploader("1. Materiales (SAP)", type=["xlsx"])
f_prod = st.sidebar.file_uploader("2. Producción (Excel)", type=["xlsx"]) 
f_real = st.sidebar.file_uploader("3. Tiempos Reales (Piso)", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("4. Tiempos SAP", type=["xlsx"])

# --- LÓGICA DE NEGOCIO ---
if f_mat and f_prod and f_real and f_sap_t:
    
    # 1. CARGA INTELIGENTE
    # Definimos palabras clave únicas que seguro están en el encabezado de cada archivo
    df_mat = cargar_excel_inteligente(f_mat, ['cantidad necesaria', 'texto breve'], "Materiales")
    df_prod = cargar_excel_inteligente(f_prod, ['cantidad buena', 'cantidad orden'], "Producción")
    df_real = cargar_excel_inteligente(f_real, ['tiempo de máquina', 'sector', 'planta'], "Tiempos Reales")
    df_sap_t = cargar_excel_inteligente(f_sap_t, ['activ.1', 'recursos'], "Tiempos SAP")

    if all(v is not None for v in [df_mat, df_prod, df_real, df_sap_t]):
        try:
            # 2. NORMALIZACIÓN DE LLAVES (Orden)
            df_mat, ok1 = limpiar_orden(df_mat, ['orden'])
            df_real, ok2 = limpiar_orden(df_real, ['orden']) # Busca "orden producción" o "orden"
            df_sap_t, ok3 = limpiar_orden(df_sap_t, ['orden'])
            
            if not (ok1 and ok2 and ok3):
                st.error("❌ No se pudo identificar la columna 'Orden' en alguno de los archivos. Revisa los nombres de encabezados.")
                st.stop()

            # 3. LIMPIEZA DE VALORES NUMÉRICOS
            # Buscamos columnas críticas dinámicamente (por si cambian un poco el nombre)
            def buscar_col(df, keywords):
                for col in df.columns:
                    if any(k in col.lower() for k in keywords):
                        return col
                return None

            # Materiales
            c_necesaria = buscar_col(df_mat, ['necesaria'])
            c_tomada = buscar_col(df_mat, ['tomada', 'real'])
            if c_necesaria and c_tomada:
                df_mat['Nec_Num'] = df_mat[c_necesaria].apply(limpiar_numero)
                df_mat['Tom_Num'] = df_mat[c_tomada].apply(limpiar_numero)
            
            # Tiempos Reales
            c_tiempo_real = buscar_col(df_real, ['tiempo de máquina', 'tiempo maquina', 'machine'])
            if c_tiempo_real:
                df_real['Real_Time_Num'] = df_real[c_tiempo_real].apply(limpiar_numero)
            else:
                st.error("No encontré columna de 'Tiempo de Máquina'")
                st.stop()

            # Tiempos SAP
            c_tiempo_sap = buscar_col(df_sap_t, ['activ.1', 'notificada'])
            if c_tiempo_sap:
                df_sap_t['Sap_Time_Num'] = df_sap_t[c_tiempo_sap].apply(limpiar_numero)

            # ----------------------------------------------------
            # CÁLCULOS
            # ----------------------------------------------------

            # --- A. HORAS ---
            g_sap = df_sap_t.groupby('Orden_Key')['Sap_Time_Num'].sum().reset_index()
            g_real = df_real.groupby('Orden_Key')['Real_Time_Num'].sum().reset_index()
            
            df_horas = pd.merge(g_sap, g_real, on='Orden_Key', how='outer').fillna(0)
            df_horas['Diferencia'] = df_horas['Real_Time_Num'] - df_horas['Sap_Time_Num']
            
            # Etiqueta de acción
            df_horas['Acción'] = np.select(
                [df_horas['Diferencia'] > 0.05, df_horas['Diferencia'] < -0.05],
                ['SUMAR A SAP (Falta)', 'RESTAR A SAP (Sobra)'],
                default='OK'
            )
            
            # Tabla final Horas
            df_horas_final = df_horas[df_horas['Acción'] != 'OK'].copy()
            df_horas_final = df_horas_final.sort_values('Diferencia', ascending=False)
            df_horas_final.columns = ['Orden', 'Horas SAP', 'Horas Reales', 'Ajuste Necesario', 'Acción']

            # --- B. MATERIALES ---
            # Unimos con los datos limpios
            df_mat['Max_Teorico'] = df_mat['Nec_Num'] * (1 + merma_input)
            
            # Estados
            condiciones = [
                (df_mat['Tom_Num'] < df_mat['Nec_Num']), # Menos que la base técnica
                (df_mat['Tom_Num'] > df_mat['Max_Teorico']) # Más que base + merma
            ]
            opciones = ['FALTA CARGAR', 'EXCEDENTE']
            df_mat['Estado'] = np.select(condiciones, opciones, default='OK')
            
            # Cálculo de ajuste exacto
            df_mat['Ajuste'] = np.select(
                [df_mat['Estado'] == 'FALTA CARGAR', df_mat['Estado'] == 'EXCEDENTE'],
                [df_mat['Nec_Num'] - df_mat['Tom_Num'], df_mat['Tom_Num'] - df_mat['Max_Teorico']],
                default=0
            )
            
            # Filtro porcentaje
            df_mat['% Desvio'] = np.where(df_mat['Nec_Num'] > 0, 
                                          (df_mat['Tom_Num'] - df_mat['Nec_Num']) / df_mat['Nec_Num'] * 100, 0)
            
            # Aplicar filtro usuario
            df_mat_final = df_mat[
                (df_mat['Estado'] != 'OK') & 
                (abs(df_mat['% Desvio']) >= tolerancia_filtro)
            ].copy()
            
            # Columnas a mostrar (Busca columnas originales de nombre/texto si existen)
            col_material = buscar_col(df_mat, ['material'])
            col_texto = buscar_col(df_mat, ['texto', 'descrip'])
            
            cols_export = ['Orden_Key']
            if col_material: cols_export.append(col_material)
            if col_texto: cols_export.append(col_texto)
            cols_export.extend(['Nec_Num', 'Tom_Num', 'Estado', 'Ajuste', '% Desvio'])
            
            df_mat_view = df_mat_final[cols_export].copy()
            df_mat_view.rename(columns={'Orden_Key': 'Orden', 'Nec_Num': 'Necesaria', 'Tom_Num': 'Tomada'}, inplace=True)

            # ----------------------------------------------------
            # VISUALIZACIÓN (DASHBOARD)
            # ----------------------------------------------------
            
            tab1, tab2 = st.tabs(["⏱️ Corrección Horas", "📦 Corrección Materiales"])
            
            with tab1:
                col1, col2 = st.columns(2)
                col1.metric("Órdenes con Error", len(df_horas_final))
                col2.metric("Total Horas a Ajustar (Abs)", f"{df_horas_final['Ajuste Necesario'].abs().sum():.2f}")
                
                st.dataframe(
                    df_horas_final.style.background_gradient(subset=['Ajuste Necesario'], cmap='RdYlGn', vmin=-10, vmax=10)
                    .format({'Horas SAP': '{:.2f}', 'Horas Reales': '{:.2f}', 'Ajuste Necesario': '{:+.2f}'}),
                    use_container_width=True
                )
                
                # Descarga Excel
                buffer_h = io.BytesIO()
                with pd.ExcelWriter(buffer_h) as writer:
                    df_horas_final.to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel Horas", buffer_h.getvalue(), "Correccion_Horas.xlsx")

            with tab2:
                col1, col2 = st.columns(2)
                col1.metric("Materiales a Revisar", len(df_mat_view))
                criticos = len(df_mat_view[df_mat_view['Estado']=='EXCEDENTE'])
                col2.metric("Excedentes Críticos", criticos, delta_color="inverse")
                
                def color_mat(val):
                    if val == 'EXCEDENTE': return 'color: red; font-weight: bold'
                    if val == 'FALTA CARGAR': return 'color: orange; font-weight: bold'
                    return ''
                
                st.dataframe(
                    df_mat_view.style.applymap(color_mat, subset=['Estado'])
                    .format({'Necesaria': '{:.3f}', 'Tomada': '{:.3f}', 'Ajuste': '{:.3f}', '% Desvio': '{:.1f}%'}),
                    use_container_width=True
                )
                
                buffer_m = io.BytesIO()
                with pd.ExcelWriter(buffer_m) as writer:
                    df_mat_view.to_excel(writer, index=False)
                st.download_button("📥 Descargar Excel Materiales", buffer_m.getvalue(), "Correccion_Materiales.xlsx")

        except Exception as e:
            st.error(f"Ocurrió un error inesperado en el procesamiento: {e}")
            st.write("Detalle técnico:", e)
    else:
        st.warning("No se pudieron leer correctamente los archivos. Verifica que no estén corruptos.")

else:
    st.info("Esperando archivos... (Sube los 4 archivos en el menú lateral)")
