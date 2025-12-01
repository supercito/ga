import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control Producción Dinámico", layout="wide", page_icon="🏭")
st.title("🏭 Dashboard de Control: Ajustado a Producción Real")
st.markdown("""
**Nueva Lógica Implementada:**
El consumo teórico de materiales ahora se recalcula basado en las **Cajas Realmente Producidas**, 
no solo en lo que pedía la orden original.
""")

# --- FUNCIONES DE AYUDA (Mismas que antes) ---
def encontrar_fila_encabezado(df, palabras_clave):
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
        return df_limpio
    except Exception as e:
        st.error(f"Error en {nombre_archivo}: {e}")
        return None

def limpiar_numero(val):
    if isinstance(val, (int, float)): return val
    if isinstance(val, str):
        val = val.strip().replace('KG', '').replace('CJ', '').replace('HRA', '').strip()
        val = val.replace('.', '').replace(',', '.') 
        try: return float(val)
        except: return 0.0
    return 0.0

def limpiar_orden(df, patterns):
    col_found = None
    for col in df.columns:
        if any(p in col.lower() for p in patterns):
            col_found = col; break
    if col_found:
        df['Orden_Key'] = df[col_found].astype(str).str.split('.').str[0].str.strip()
        return df, True
    return df, False

def buscar_col(df, keywords):
    for col in df.columns:
        if any(k in col.lower() for k in keywords): return col
    return None

# --- ESTILOS VISUALES ---
def estilo_estado(val):
    if val == 'EXCEDENTE REAL': return 'background-color: #ffcdd2; color: black; font-weight: bold' # Rojo
    if val == 'AHORRO/BAJO CONSUMO': return 'background-color: #c8e6c9; color: black' # Verde
    if val == 'FALTA CARGAR': return 'background-color: #ffe0b2; color: black; font-weight: bold' # Naranja
    return ''

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuración")
merma_input = st.sidebar.number_input("Merma Permitida (%)", 0.0, 20.0, 3.0, 0.1) / 100
tolerancia_filtro = st.sidebar.slider("Filtro Tolerancia (%)", 0.0, 50.0, 1.0, 0.5)

st.sidebar.divider()
f_mat = st.sidebar.file_uploader("1. Materiales (SAP)", type=["xlsx"])
f_prod = st.sidebar.file_uploader("2. Producción (Excel)", type=["xlsx"]) 
f_real = st.sidebar.file_uploader("3. Tiempos Reales", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("4. Tiempos SAP", type=["xlsx"])

# --- PROCESAMIENTO ---
if f_mat and f_prod and f_real and f_sap_t:
    
    # 1. Carga
    df_mat = cargar_excel_inteligente(f_mat, ['cantidad necesaria', 'texto breve'], "Materiales")
    df_prod = cargar_excel_inteligente(f_prod, ['cantidad buena', 'cantidad orden'], "Producción")
    df_real = cargar_excel_inteligente(f_real, ['tiempo de máquina', 'sector'], "Tiempos Reales")
    df_sap_t = cargar_excel_inteligente(f_sap_t, ['activ.1', 'recursos'], "Tiempos SAP")

    if all(v is not None for v in [df_mat, df_prod, df_real, df_sap_t]):
        # 2. Normalizar Keys
        df_mat, ok1 = limpiar_orden(df_mat, ['orden'])
        df_prod, ok2 = limpiar_orden(df_prod, ['orden'])
        df_real, ok3 = limpiar_orden(df_real, ['orden'])
        df_sap_t, ok4 = limpiar_orden(df_sap_t, ['orden'])

        if not (ok1 and ok2 and ok3 and ok4):
            st.error("Error: No se encontró la columna 'Orden' en alguno de los archivos.")
            st.stop()

        # 3. Limpieza Numérica
        # -- Materiales --
        c_nec = buscar_col(df_mat, ['necesaria'])
        c_tom = buscar_col(df_mat, ['tomada', 'real'])
        df_mat['Mat_Plan_Total'] = df_mat[c_nec].apply(limpiar_numero)
        df_mat['Mat_Real_Usado'] = df_mat[c_tom].apply(limpiar_numero)

        # -- Producción (CRÍTICO PARA TU SOLICITUD) --
        c_prod_plan = buscar_col(df_prod, ['cantidad orden', 'plan'])
        c_prod_real = buscar_col(df_prod, ['cantidad buena', 'real', 'producida'])
        
        # Agrupamos producción por orden (por si hay líneas duplicadas)
        if c_prod_plan and c_prod_real:
            df_prod['Prod_Plan_Qty'] = df_prod[c_prod_plan].apply(limpiar_numero)
            df_prod['Prod_Real_Qty'] = df_prod[c_prod_real].apply(limpiar_numero)
            
            # Crear tabla maestra de producción por orden
            df_prod_master = df_prod.groupby('Orden_Key')[['Prod_Plan_Qty', 'Prod_Real_Qty']].sum().reset_index()
        else:
            st.error("No se encontraron columnas de Cantidad Planificada o Real en el archivo de Producción.")
            st.stop()

        # 4. LÓGICA DE MATERIALES "DINÁMICA" (TU REQUERIMIENTO)
        # Cruzamos Materiales con Producción
        df_analisis = pd.merge(df_mat, df_prod_master, on='Orden_Key', how='left')
        
        # Si no hay dato de producción, asumimos que Real = Plan (Fallback)
        df_analisis['Prod_Plan_Qty'] = df_analisis['Prod_Plan_Qty'].fillna(1)
        df_analisis['Prod_Real_Qty'] = df_analisis['Prod_Real_Qty'].fillna(df_analisis['Prod_Plan_Qty'])

        # --- CÁLCULO DEL COEFICIENTE TÉCNICO ---
        # Cuánto material se necesita POR UNIDAD producida (según SAP original)
        # Evitamos división por cero
        df_analisis['Coef_Tecnico'] = np.where(
            df_analisis['Prod_Plan_Qty'] > 0,
            df_analisis['Mat_Plan_Total'] / df_analisis['Prod_Plan_Qty'],
            0
        )

        # --- NUEVO CONSUMO TEÓRICO ---
        # Base recalculada a la realidad
        df_analisis['Teorico_Recalculado'] = df_analisis['Coef_Tecnico'] * df_analisis['Prod_Real_Qty']
        
        # Aplicamos Merma sobre el teórico recalculado
        df_analisis['Maximo_Permitido'] = df_analisis['Teorico_Recalculado'] * (1 + merma_input)
        
        # --- DETERMINACIÓN DE ESTADO ---
        # 1. Si consumí más que lo permitido para la producción real -> EXCEDENTE
        # 2. Si consumí menos que el teórico recalculado -> AHORRO o FALTA CARGAR (Depende criterio)
        #    Para seguridad, si es mucho menos, puede ser FALTA CARGAR.
        
        df_analisis['Desvio_Abs'] = df_analisis['Mat_Real_Usado'] - df_analisis['Maximo_Permitido']
        
        # Porcentaje de desvío sobre la nueva base
        df_analisis['% Desvio'] = np.where(
            df_analisis['Teorico_Recalculado'] > 0,
            (df_analisis['Desvio_Abs'] / df_analisis['Teorico_Recalculado']) * 100,
            0
        )

        # Lógica de estados
        condiciones = [
            (df_analisis['Mat_Real_Usado'] > df_analisis['Maximo_Permitido']), # Se pasó del límite ajustado
            (df_analisis['Mat_Real_Usado'] < df_analisis['Teorico_Recalculado'] * 0.95) # Consumió menos del 95% de lo necesario (Posible falta de carga)
        ]
        opciones = ['EXCEDENTE REAL', 'FALTA CARGAR'] # O "AHORRO"
        df_analisis['Estado'] = np.select(condiciones, opciones, default='OK')

        # Filtro de usuario
        df_final_mat = df_analisis[
            (df_analisis['Estado'] != 'OK') & 
            (abs(df_analisis['% Desvio']) >= tolerancia_filtro)
        ].copy()

        # Columnas para mostrar
        c_mat_name = buscar_col(df_mat, ['material'])
        c_mat_desc = buscar_col(df_mat, ['texto', 'descrip'])
        cols_show = ['Orden_Key']
        if c_mat_name: cols_show.append(c_mat_name)
        if c_mat_desc: cols_show.append(c_mat_desc)
        cols_show.extend(['Prod_Real_Qty', 'Teorico_Recalculado', 'Mat_Real_Usado', 'Estado', 'Desvio_Abs', '% Desvio'])

        df_view_mat = df_final_mat[cols_show].copy()
        df_view_mat.rename(columns={
            'Orden_Key': 'Orden',
            'Prod_Real_Qty': 'Cajas Hechas',
            'Teorico_Recalculado': 'Debió Usar',
            'Mat_Real_Usado': 'Usó Realmente',
            'Desvio_Abs': 'Ajuste Cant.'
        }, inplace=True)

        # --- DASHBOARD ---
        st.subheader("📦 Análisis Ajustado a Producción Real")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Registros Fuera de Rango", len(df_view_mat))
        
        # Total Excedente en Unidades (Suma de ajustes positivos)
        total_excedente = df_view_mat[df_view_mat['Ajuste Cant.'] > 0]['Ajuste Cant.'].sum()
        col2.metric("Total Excedente (Unidades)", f"{total_excedente:,.2f}", delta_color="inverse")
        
        st.markdown(f"**Nota:** El cálculo 'Debió Usar' considera las **Cajas Hechas** y la merma del **{merma_input*100}%**.")

        st.dataframe(
            df_view_mat.style.applymap(estilo_estado, subset=['Estado'])
            .format({
                'Cajas Hechas': '{:,.0f}',
                'Debió Usar': '{:,.2f}', 
                'Usó Realmente': '{:,.2f}', 
                'Ajuste Cant.': '{:+.2f}', 
                '% Desvio': '{:.1f}%'
            }),
            use_container_width=True
        )

        # Descarga
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer) as writer:
            df_view_mat.to_excel(writer, index=False)
        st.download_button("📥 Descargar Reporte Ajustado", buffer.getvalue(), "Ajuste_Materiales_Real.xlsx")

else:
    st.info("Sube los archivos para calcular.")
