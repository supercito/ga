import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control Producción & SAP", layout="wide", page_icon="🏭")
st.title("🏭 Dashboard de Control: Producción, Tiempos y Materiales")
st.markdown("""
**Instrucciones:**
1. Carga los 4 archivos en el menú lateral.
2. Selecciona qué columna corresponde a cada dato en los menús desplegables.
3. Presiona **"CALCULAR RESULTADOS"**.
""")

# --- FUNCIONES DE LIMPIEZA ---
def cargar_excel_simple(file):
    """Carga el Excel intentando detectar el encabezado automáticamente"""
    if not file: return None
    try:
        # Leemos primeras 10 lineas
        df_temp = pd.read_excel(file, header=None, nrows=10)
        max_cols = 0
        header_row = 0
        for i in range(len(df_temp)):
            non_na = df_temp.iloc[i].count()
            if non_na > max_cols:
                max_cols = non_na
                header_row = i
        
        # Cargar con ese header
        df = pd.read_excel(file, header=header_row)
        # Limpiar nombres de columnas
        df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
        return df
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return None

def clean_key(val):
    """Limpia la Orden para asegurar el cruce (quita .0 y espacios)"""
    return str(val).split('.')[0].strip()

def clean_num(val):
    """Limpia números con formato europeo o con unidades de texto"""
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

def index_col(df, keywords):
    """Ayuda a pre-seleccionar la columna correcta en el menú"""
    cols_lower = [str(c).lower() for c in df.columns]
    for i, col in enumerate(cols_lower):
        if any(k in col for k in keywords): return i
    return 0

# --- BARRA LATERAL (SIDEBAR) ---
st.sidebar.header("1. Configuración")
merma = st.sidebar.number_input("Merma Permitida (%)", 0.0, 20.0, 3.0, 0.1) / 100
tolerancia = st.sidebar.slider("Filtro Tolerancia (%)", 0.0, 50.0, 0.0, help="0 = Ver todos los desvíos")

st.sidebar.divider()
st.sidebar.header("2. Carga de Archivos")
f_mat = st.sidebar.file_uploader("Materiales (SAP)", type=["xlsx"])
f_prod = st.sidebar.file_uploader("Producción (Excel)", type=["xlsx"])
f_real = st.sidebar.file_uploader("Tiempos Reales (Piso)", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("Tiempos SAP", type=["xlsx"])

# --- LÓGICA PRINCIPAL ---
if f_mat and f_prod and f_real and f_sap_t:
    
    # 1. CARGA DE DATOS
    df_mat = cargar_excel_simple(f_mat)
    df_prod = cargar_excel_simple(f_prod)
    df_real = cargar_excel_simple(f_real)
    df_sap_t = cargar_excel_simple(f_sap_t)

    st.divider()
    st.subheader("🛠️ Selección de Columnas (Mapeo)")
    
    # 2. SELECTORES DE COLUMNAS
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.info("📦 Materiales")
        col_mat_orden = st.selectbox("Orden:", df_mat.columns, index=index_col(df_mat, ['orden']), key='mo')
        col_mat_nec = st.selectbox("Cant. Necesaria:", df_mat.columns, index=index_col(df_mat, ['necesaria']), key='mn')
        col_mat_real = st.selectbox("Cant. Tomada:", df_mat.columns, index=index_col(df_mat, ['tomada', 'real', 'actual']), key='mr')
        col_mat_desc = st.selectbox("Descripción:", df_mat.columns, index=index_col(df_mat, ['texto', 'desc', 'material']), key='md')

    with c2:
        st.info("🏭 Producción")
        col_prod_orden = st.selectbox("Orden:", df_prod.columns, index=index_col(df_prod, ['orden']), key='po')
        col_prod_hecha = st.selectbox("Cajas Reales (Hechas):", df_prod.columns, index=index_col(df_prod, ['buena', 'real', 'confirmada']), key='ph')
        col_prod_plan = st.selectbox("Cajas Plan (Orden):", df_prod.columns, index=index_col(df_prod, ['orden', 'plan', 'cantidad']), key='pp')

    with c3:
        st.info("⏱️ Tiempos Reales")
        col_real_orden = st.selectbox("Orden:", df_real.columns, index=index_col(df_real, ['orden']), key='ro')
        col_real_time = st.selectbox("Tiempo (Máquina):", df_real.columns, index=index_col(df_real, ['tiempo', 'maquina']), key='rt')

    with c4:
        st.info("⏱️ Tiempos SAP")
        col_sap_orden = st.selectbox("Orden:", df_sap_t.columns, index=index_col(df_sap_t, ['orden']), key='so')
        col_sap_time = st.selectbox("Tiempo (Notif):", df_sap_t.columns, index=index_col(df_sap_t, ['activ', 'notif']), key='st')

    st.divider()

    # 3. BOTÓN DE CÁLCULO
    if st.button("🚀 CALCULAR RESULTADOS", type="primary"):
        st.session_state['calculado'] = True

        # --- LIMPIEZA DE LLAVES ---
        df_mat['KEY'] = df_mat[col_mat_orden].apply(clean_key)
        df_prod['KEY'] = df_prod[col_prod_orden].apply(clean_key)
        df_real['KEY'] = df_real[col_real_orden].apply(clean_key)
        df_sap_t['KEY'] = df_sap_t[col_sap_orden].apply(clean_key)

        # --- LIMPIEZA DE VALORES ---
        df_mat['Nec'] = df_mat[col_mat_nec].apply(clean_num)
        df_mat['Tom'] = df_mat[col_mat_real].apply(clean_num)
        
        df_prod['Hecha'] = df_prod[col_prod_hecha].apply(clean_num)
        df_prod['Plan'] = df_prod[col_prod_plan].apply(clean_num)
        
        df_real['V_Real'] = df_real[col_real_time].apply(clean_num)
        df_sap_t['V_Sap'] = df_sap_t[col_sap_time].apply(clean_num)

        # ==========================================
        # CÁLCULO MATERIALES (DINÁMICO)
        # ==========================================
        prod_grouped = df_prod.groupby('KEY')[['Plan', 'Hecha']].sum().reset_index()
        df_m = pd.merge(df_mat, prod_grouped, on='KEY', how='left')
        
        # Fallback de seguridad
        df_m['Plan'] = df_m['Plan'].fillna(0)
        df_m['Hecha'] = df_m['Hecha'].fillna(0)
        df_m['Origen'] = np.where(df_m['Plan'] > 0, "Prod OK", "Solo SAP")

        # Coeficiente Técnico (Cuánto material por caja según plan)
        df_m['Coef'] = np.where(df_m['Plan'] > 0, df_m['Nec'] / df_m['Plan'], 0)
        
        # Teórico Recalculado
        df_m['Teorico_Calc'] = np.where(
            df_m['Origen'] == "Prod OK",
            df_m['Coef'] * df_m['Hecha'], # Ajuste dinámico
            df_m['Nec']                   # Si no hay prod, usamos el plan original
        )

        df_m['Max_Permitido'] = df_m['Teorico_Calc'] * (1 + merma)
        df_m['Diff'] = df_m['Tom'] - df_m['Max_Permitido']
        
        # Estados
        conds = [
            (df_m['Tom'] > df_m['Max_Permitido']),
            (df_m['Tom'] < df_m['Teorico_Calc'] * 0.95)
        ]
        df_m['Estado'] = np.select(conds, ['EXCEDENTE', 'FALTA CARGAR'], default='OK')
        
        # Filtro Porcentaje
        df_m['% Desvio'] = np.where(df_m['Teorico_Calc'] > 0, (df_m['Diff'] / df_m['Teorico_Calc'])*100, 0)
        
        # Guardar resultado filtrado
        st.session_state['df_final_m'] = df_m[(df_m['Estado'] != 'OK') & (abs(df_m['% Desvio']) >= tolerancia)].copy()

        # ==========================================
        # CÁLCULO TIEMPOS (HORAS)
        # ==========================================
        t_real = df_real.groupby('KEY')['V_Real'].sum().reset_index()
        t_sap = df_sap_t.groupby('KEY')['V_Sap'].sum().reset_index()
        
        df_t = pd.merge(t_sap, t_real, on='KEY', how='outer').fillna(0)
        df_t['Diff'] = df_t['V_Real'] - df_t['V_Sap']
        
        df_t['Accion'] = np.select(
            [df_t['Diff'] > 0.05, df_t['Diff'] < -0.05],
            ['SUMAR (Falta)', 'RESTAR (Sobra)'], default='OK'
        )
        st.session_state['df_final_t'] = df_t[df_t['Accion'] != 'OK'].sort_values('Diff', ascending=False)


    # 4. MOSTRAR RESULTADOS
    if st.session_state.get('calculado', False):
        
        st.subheader("📊 Resultados del Análisis")
        df_m_res = st.session_state['df_final_m']
        df_t_res = st.session_state['df_final_t']
        
        tab1, tab2 = st.tabs(["📦 Materiales", "⏱️ Tiempos"])
        
        # --- TAB MATERIALES ---
        with tab1:
            col_kpi1, col_kpi2 = st.columns(2)
            col_kpi1.metric("Registros con Desvío", len(df_m_res))
            col_kpi2.metric("Total Excedente (U)", f"{df_m_res[df_m_res['Diff']>0]['Diff'].sum():,.2f}")

            # Función de color
            def color_m(val):
                if val == 'EXCEDENTE': return 'background-color: #ffcdd2; color: black' # Rojo claro
                if val == 'FALTA CARGAR': return 'background-color: #ffeeb0; color: black' # Amarillo claro
                return ''
            
            # Columnas finales
            cols_show = ['KEY', col_mat_desc, 'Origen', 'Hecha', 'Teorico_Calc', 'Tom', 'Estado', 'Diff', '% Desvio']
            
            st.dataframe(
                df_m_res[cols_show].style
                .applymap(color_m, subset=['Estado'])
                .format({
                    'Hecha': '{:,.0f}',          # Ej: 1,500
                    'Teorico_Calc': '{:,.2f}',   # Ej: 1,500.50
                    'Tom': '{:,.2f}',            # Ej: 1,600.00
                    'Diff': '{:+,.2f}',          # Ej: +99.50
                    '% Desvio': '{:.1f}%'        # Ej: 5.2%
                }),
                use_container_width=True,
                height=500
            )
            
            # Botón Excel Materiales
            b = io.BytesIO()
            with pd.ExcelWriter(b) as w: df_m_res.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel Materiales", b.getvalue(), "Materiales.xlsx")

        # --- TAB TIEMPOS ---
        with tab2:
            st.metric("Órdenes con Diferencia", len(df_t_res))
            
            def color_t(val):
                if val > 0: return 'background-color: #ffeeb0; color: black' # Falta (Amarillo)
                if val < 0: return 'background-color: #ffcdd2; color: black' # Sobra (Rojo)
                return ''
            
            st.dataframe(
                df_t_res.style
                .applymap(color_t, subset=['Diff'])
                .format({
                    'V_Sap': '{:,.2f}',
                    'V_Real': '{:,.2f}',
                    'Diff': '{:+,.2f}'
                }),
                use_container_width=True
            )
            
            # Botón Excel Tiempos
            b2 = io.BytesIO()
            with pd.ExcelWriter(b2) as w: df_t_res.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel Tiempos", b2.getvalue(), "Tiempos.xlsx")

else:
    st.info("👈 Sube los 4 archivos en el menú lateral para comenzar.")
