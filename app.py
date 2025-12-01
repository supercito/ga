import streamlit as st
import pandas as pd
import io
import numpy as np

st.set_page_config(page_title="Control Manual y Preciso", layout="wide", page_icon="🎛️")
st.title("🎛️ Dashboard de Control: Selección de Columnas")
st.markdown("""
**Instrucciones:**
1. Sube los archivos.
2. En los menús que aparecen abajo, **selecciona la columna correcta** para cada dato.
3. El sistema calculará los desvíos basándose en tu selección.
""")

# --- FUNCIONES DE CARGA Y LIMPIEZA ---
def cargar_excel_simple(file):
    """Carga el excel tratando de adivinar dónde empieza el encabezado"""
    if not file: return None
    try:
        # Leemos primeras 10 lineas para ver donde hay mas columnas no nulas
        df_temp = pd.read_excel(file, header=None, nrows=10)
        max_cols = 0
        header_row = 0
        for i in range(len(df_temp)):
            # Contar columnas con texto
            non_na = df_temp.iloc[i].count()
            if non_na > max_cols:
                max_cols = non_na
                header_row = i
        
        # Cargar con ese header
        df = pd.read_excel(file, header=header_row)
        # Limpiar nombres columnas
        df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
        return df
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return None

def clean_key(val):
    """Limpia la Orden para que cruce bien (quita .0 y espacios)"""
    return str(val).split('.')[0].strip()

def clean_num(val):
    """Limpia números europeos y textos"""
    if isinstance(val, (int, float)): return val
    if isinstance(val, str):
        val = val.upper().strip()
        # Eliminar unidades comunes
        for unidad in ['KG', 'CJ', 'HRA', 'HR', 'UN', 'M', 'L']:
            val = val.replace(unidad, '')
        val = val.strip()
        # Formato europeo 1.000,00 -> 1000.00
        val = val.replace('.', '').replace(',', '.')
        try: return float(val)
        except: return 0.0
    return 0.0

# --- SIDEBAR ---
st.sidebar.header("1. Configuración")
merma = st.sidebar.number_input("Merma (%)", 0.0, 20.0, 3.0) / 100
tolerancia = st.sidebar.slider("Filtro Tolerancia (%)", 0.0, 50.0, 0.0)

st.sidebar.divider()
st.sidebar.header("2. Archivos")
f_mat = st.sidebar.file_uploader("Materiales (SAP)", type=["xlsx"])
f_prod = st.sidebar.file_uploader("Producción (Excel)", type=["xlsx"])
f_real = st.sidebar.file_uploader("Tiempos Reales", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("Tiempos SAP", type=["xlsx"])

# --- LÓGICA PRINCIPAL ---
if f_mat and f_prod and f_real and f_sap_t:
    
    # 1. CARGA INICIAL
    df_mat = cargar_excel_simple(f_mat)
    df_prod = cargar_excel_simple(f_prod)
    df_real = cargar_excel_simple(f_real)
    df_sap_t = cargar_excel_simple(f_sap_t)

    st.divider()
    st.subheader("🛠️ Paso 2: Selecciona las Columnas Correctas")
    
    # --- SELECTORES DE COLUMNAS (USER MAPPING) ---
    c1, c2, c3, c4 = st.columns(4)
    
    # Helper para pre-seleccionar si encontramos palabras clave
    def index_col(df, keywords):
        cols_lower = [str(c).lower() for c in df.columns]
        for i, col in enumerate(cols_lower):
            if any(k in col for k in keywords): return i
        return 0

    with c1:
        st.info("📦 Materiales")
        col_mat_orden = st.selectbox("Columna Orden:", df_mat.columns, index=index_col(df_mat, ['orden']), key='mo')
        col_mat_nec = st.selectbox("Col. Cant. Necesaria:", df_mat.columns, index=index_col(df_mat, ['necesaria']), key='mn')
        col_mat_real = st.selectbox("Col. Cant. Tomada/Real:", df_mat.columns, index=index_col(df_mat, ['tomada', 'real', 'actual']), key='mr')
        col_mat_desc = st.selectbox("Col. Descripción:", df_mat.columns, index=index_col(df_mat, ['texto', 'desc', 'material']), key='md')

    with c2:
        st.info("🏭 Producción")
        col_prod_orden = st.selectbox("Columna Orden:", df_prod.columns, index=index_col(df_prod, ['orden']), key='po')
        # AQUÍ ES DONDE FALLABA ANTES: Asegúrate de elegir la columna que tiene los números reales (ej: 445)
        col_prod_hecha = st.selectbox("Col. Cajas Real (Hechas):", df_prod.columns, index=index_col(df_prod, ['buena', 'real', 'confirmada']), key='ph')
        col_prod_plan = st.selectbox("Col. Cajas Plan (Orden):", df_prod.columns, index=index_col(df_prod, ['orden', 'plan', 'cantidad']), key='pp')

    with c3:
        st.info("⏱️ Tiempos Reales")
        col_real_orden = st.selectbox("Columna Orden:", df_real.columns, index=index_col(df_real, ['orden']), key='ro')
        col_real_time = st.selectbox("Col. Tiempo (Máquina):", df_real.columns, index=index_col(df_real, ['tiempo', 'maquina']), key='rt')

    with c4:
        st.info("⏱️ Tiempos SAP")
        col_sap_orden = st.selectbox("Columna Orden:", df_sap_t.columns, index=index_col(df_sap_t, ['orden']), key='so')
        col_sap_time = st.selectbox("Col. Tiempo (Notificado):", df_sap_t.columns, index=index_col(df_sap_t, ['activ', 'notif']), key='st')

    # --- PROCESAMIENTO CON COLUMNAS SELECCIONADAS ---
    if st.button("🚀 CALCULAR CON ESTAS COLUMNAS", type="primary"):
        
        # 1. LIMPIEZA DE LLAVES (KEYS)
        df_mat['KEY'] = df_mat[col_mat_orden].apply(clean_key)
        df_prod['KEY'] = df_prod[col_prod_orden].apply(clean_key)
        df_real['KEY'] = df_real[col_real_orden].apply(clean_key)
        df_sap_t['KEY'] = df_sap_t[col_sap_orden].apply(clean_key)

        # 2. LIMPIEZA DE VALORES
        df_mat['Nec'] = df_mat[col_mat_nec].apply(clean_num)
        df_mat['Tom'] = df_mat[col_mat_real].apply(clean_num)
        
        df_prod['Hecha'] = df_prod[col_prod_hecha].apply(clean_num)
        df_prod['Plan'] = df_prod[col_prod_plan].apply(clean_num)
        
        df_real['V_Real'] = df_real[col_real_time].apply(clean_num)
        df_sap_t['V_Sap'] = df_sap_t[col_sap_time].apply(clean_num)

        # ------------------------------------
        # CÁLCULO MATERIALES
        # ------------------------------------
        # Agrupar producción (por si hay líneas duplicadas)
        prod_grouped = df_prod.groupby('KEY')[['Plan', 'Hecha']].sum().reset_index()
        
        # Cruzar
        df_m = pd.merge(df_mat, prod_grouped, on='KEY', how='left')
        
        # Lógica de seguridad: Si no cruza, asumimos Plan=0 y Hecha=0
        df_m['Plan'] = df_m['Plan'].fillna(0)
        df_m['Hecha'] = df_m['Hecha'].fillna(0)
        df_m['Origen'] = np.where(df_m['Plan'] > 0, "Cruce OK", "Solo SAP")

        # Fallback: Si no hay cruce, usamos la cantidad necesaria original de SAP como teórico
        # Si hay cruce, usamos la regla de tres simple (Receta Dinámica)
        
        df_m['Coef'] = np.where(df_m['Plan'] > 0, df_m['Nec'] / df_m['Plan'], 0)
        
        # EL CALCULO DINAMICO:
        df_m['Teorico_Calc'] = np.where(
            df_m['Origen'] == "Cruce OK",
            df_m['Coef'] * df_m['Hecha'], # Si cruzó, ajustamos a lo real
            df_m['Nec'] # Si no cruzó, mantenemos el estándar
        )

        df_m['Max_Permitido'] = df_m['Teorico_Calc'] * (1 + merma)
        df_m['Diff'] = df_m['Tom'] - df_m['Max_Permitido']
        
        # Estados
        conds = [
            (df_m['Tom'] > df_m['Max_Permitido']),
            (df_m['Tom'] < df_m['Teorico_Calc'] * 0.95)
        ]
        df_m['Estado'] = np.select(conds, ['EXCEDENTE', 'FALTA CARGAR'], default='OK')
        
        # Filtro
        df_m['% Desvio'] = np.where(df_m['Teorico_Calc'] > 0, (df_m['Diff'] / df_m['Teorico_Calc'])*100, 0)
        df_final_m = df_m[(df_m['Estado'] != 'OK') & (abs(df_m['% Desvio']) >= tolerancia)].copy()

        # ------------------------------------
        # CÁLCULO TIEMPOS
        # ------------------------------------
        t_real = df_real.groupby('KEY')['V_Real'].sum().reset_index()
        t_sap = df_sap_t.groupby('KEY')['V_Sap'].sum().reset_index()
        
        df_t = pd.merge(t_sap, t_real, on='KEY', how='outer').fillna(0)
        df_t['Diff'] = df_t['V_Real'] - df_t['V_Sap']
        
        df_t['Accion'] = np.select(
            [df_t['Diff'] > 0.05, df_t['Diff'] < -0.05],
            ['SUMAR (Falta)', 'RESTAR (Sobra)'], default='OK'
        )
        df_final_t = df_t[df_t['Accion'] != 'OK'].sort_values('Diff', ascending=False)

        # ------------------------------------
        # RESULTADOS
        # ------------------------------------
        st.divider()
        tab1, tab2 = st.tabs(["📦 Materiales", "⏱️ Tiempos"])
        
        with tab1:
            st.write(f"**Registros encontrados:** {len(df_final_m)}")
            
            # Verificación visual para ti:
            if st.checkbox("Ver detalle de cálculo (Debug)"):
                st.write(df_final_m[['KEY', 'Nec', 'Plan', 'Hecha', 'Coef', 'Teorico_Calc']].head())
            
            def color_m(val):
                if val == 'EXCEDENTE': return 'background-color: #ffcdd2; color: black'
                if val == 'FALTA CARGAR': return 'background-color: #ffeeb0; color: black'
                return ''
            
            # Elegimos columnas finales
            cols_show = ['KEY', col_mat_desc, 'Origen', 'Hecha', 'Teorico_Calc', 'Tom', 'Estado', 'Diff']
            st.dataframe(df_final_m[cols_show].style.applymap(color_m, subset=['Estado']), use_container_width=True)
            
            # Descarga
            b = io.BytesIO()
            with pd.ExcelWriter(b) as w: df_final_m.to_excel(w, index=False)
            st.download_button("Descargar Excel Materiales", b.getvalue(), "Materiales.xlsx")

        with tab2:
            st.write(f"**Diferencias encontradas:** {len(df_final_t)}")
            
            def color_t(val):
                if val > 0: return 'background-color: #ffeeb0; color: black'
                if val < 0: return 'background-color: #ffcdd2; color: black'
                return ''
            
            st.dataframe(df_final_t.style.applymap(color_t, subset=['Diff']), use_container_width=True)
            
            b2 = io.BytesIO()
            with pd.ExcelWriter(b2) as w: df_final_t.to_excel(w, index=False)
            st.download_button("Descargar Excel Tiempos", b2.getvalue(), "Tiempos.xlsx")

else:
    st.info("Sube los archivos y espera a que aparezcan los selectores de columnas.")
