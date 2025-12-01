import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control Producción & SAP", layout="wide", page_icon="🏭")
st.title("🏭 Dashboard de Control: Producción, Tiempos y Materiales")
st.markdown("""
**Instrucciones:**
1. Carga los 4 archivos.
2. Mapea las columnas en los selectores.
3. Presiona **"CALCULAR RESULTADOS"**.
""")

# --- FUNCIONES DE LIMPIEZA ---
def cargar_excel_simple(file):
    if not file: return None
    try:
        df_temp = pd.read_excel(file, header=None, nrows=10)
        max_cols = 0
        header_row = 0
        for i in range(len(df_temp)):
            non_na = df_temp.iloc[i].count()
            if non_na > max_cols:
                max_cols = non_na
                header_row = i
        df = pd.read_excel(file, header=header_row)
        df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
        return df
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")
        return None

def clean_key(val):
    return str(val).split('.')[0].strip()

def clean_num(val):
    if isinstance(val, (int, float)): return val
    if isinstance(val, str):
        val = val.upper().strip()
        for unidad in ['KG', 'CJ', 'HRA', 'HR', 'UN', 'M', 'L']:
            val = val.replace(unidad, '')
        val = val.strip().replace('.', '').replace(',', '.')
        try: return float(val)
        except: return 0.0
    return 0.0

def index_col(df, keywords):
    cols_lower = [str(c).lower() for c in df.columns]
    for i, col in enumerate(cols_lower):
        if any(k in col for k in keywords): return i
    return 0

# --- SIDEBAR ---
st.sidebar.header("1. Configuración")
merma = st.sidebar.number_input("Merma (%)", 0.0, 20.0, 3.0, 0.1) / 100
tolerancia = st.sidebar.slider("Filtro Tolerancia (%)", 0.0, 50.0, 0.0)

st.sidebar.divider()
f_mat = st.sidebar.file_uploader("Materiales (SAP)", type=["xlsx"])
f_prod = st.sidebar.file_uploader("Producción (Excel)", type=["xlsx"])
f_real = st.sidebar.file_uploader("Tiempos Reales", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("Tiempos SAP", type=["xlsx"])

# --- LÓGICA PRINCIPAL ---
if f_mat and f_prod and f_real and f_sap_t:
    
    # 1. CARGA
    df_mat = cargar_excel_simple(f_mat)
    df_prod = cargar_excel_simple(f_prod)
    df_real = cargar_excel_simple(f_real)
    df_sap_t = cargar_excel_simple(f_sap_t)

    st.divider()
    st.subheader("🛠️ Selección de Columnas")
    
    # 2. SELECTORES
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.info("📦 Materiales")
        col_mat_orden = st.selectbox("Orden:", df_mat.columns, index=index_col(df_mat, ['orden']), key='mo')
        col_mat_nec = st.selectbox("Cant. Necesaria:", df_mat.columns, index=index_col(df_mat, ['necesaria']), key='mn')
        col_mat_real = st.selectbox("Cant. Tomada:", df_mat.columns, index=index_col(df_mat, ['tomada', 'real']), key='mr')
        col_mat_desc = st.selectbox("Descripción:", df_mat.columns, index=index_col(df_mat, ['texto', 'desc', 'material']), key='md')

    with c2:
        st.info("🏭 Producción")
        col_prod_orden = st.selectbox("Orden:", df_prod.columns, index=index_col(df_prod, ['orden']), key='po')
        col_prod_hecha = st.selectbox("Cajas Reales:", df_prod.columns, index=index_col(df_prod, ['buena', 'real', 'confirmada']), key='ph')
        col_prod_plan = st.selectbox("Cajas Plan:", df_prod.columns, index=index_col(df_prod, ['orden', 'plan', 'cantidad']), key='pp')

    with c3:
        st.info("⏱️ Tiempos Reales")
        col_real_orden = st.selectbox("Orden:", df_real.columns, index=index_col(df_real, ['orden']), key='ro')
        col_real_time = st.selectbox("Tiempo (Máquina):", df_real.columns, index=index_col(df_real, ['tiempo', 'maquina']), key='rt')

    with c4:
        st.info("⏱️ Tiempos SAP")
        col_sap_orden = st.selectbox("Orden:", df_sap_t.columns, index=index_col(df_sap_t, ['orden']), key='so')
        col_sap_time = st.selectbox("Tiempo (Notif):", df_sap_t.columns, index=index_col(df_sap_t, ['activ', 'notif']), key='st')

    st.divider()

    # 3. BOTÓN CÁLCULO
    if st.button("🚀 CALCULAR RESULTADOS", type="primary"):
        st.session_state['calculado'] = True

        # --- LIMPIEZA LLAVES ---
        df_mat['KEY'] = df_mat[col_mat_orden].apply(clean_key)
        df_prod['KEY'] = df_prod[col_prod_orden].apply(clean_key)
        df_real['KEY'] = df_real[col_real_orden].apply(clean_key)
        df_sap_t['KEY'] = df_sap_t[col_sap_orden].apply(clean_key)

        # --- LIMPIEZA VALORES (Nombres Únicos para evitar choques) ---
        df_mat['_Sys_Nec'] = df_mat[col_mat_nec].apply(clean_num)
        df_mat['_Sys_Tom'] = df_mat[col_mat_real].apply(clean_num)
        
        df_prod['_Sys_Hecha'] = df_prod[col_prod_hecha].apply(clean_num)
        df_prod['_Sys_Plan'] = df_prod[col_prod_plan].apply(clean_num)
        
        df_real['_Sys_Real'] = df_real[col_real_time].apply(clean_num)
        df_sap_t['_Sys_Sap'] = df_sap_t[col_sap_time].apply(clean_num)

        # ==========================================
        # CÁLCULO MATERIALES
        # ==========================================
        # Agrupamos producción con nombres internos para no chocar con columnas de Mat
        prod_grouped = df_prod.groupby('KEY')[['_Sys_Plan', '_Sys_Hecha']].sum().reset_index()
        
        # Merge
        df_m = pd.merge(df_mat, prod_grouped, on='KEY', how='left')
        
        # Lógica Fallback
        df_m['_Sys_Plan'] = df_m['_Sys_Plan'].fillna(0)
        df_m['_Sys_Hecha'] = df_m['_Sys_Hecha'].fillna(0)
        df_m['Origen'] = np.where(df_m['_Sys_Plan'] > 0, "Prod OK", "Solo SAP")

        # Cálculo Coeficiente
        df_m['Coef'] = np.where(df_m['_Sys_Plan'] > 0, df_m['_Sys_Nec'] / df_m['_Sys_Plan'], 0)
        
        # Teórico Recalculado
        df_m['Teorico_Calc'] = np.where(
            df_m['Origen'] == "Prod OK",
            df_m['Coef'] * df_m['_Sys_Hecha'], 
            df_m['_Sys_Nec']
        )

        df_m['Max_Permitido'] = df_m['Teorico_Calc'] * (1 + merma)
        df_m['Diff'] = df_m['_Sys_Tom'] - df_m['Max_Permitido']
        
        # Estados
        conds = [
            (df_m['_Sys_Tom'] > df_m['Max_Permitido']),
            (df_m['_Sys_Tom'] < df_m['Teorico_Calc'] * 0.95)
        ]
        df_m['Estado'] = np.select(conds, ['EXCEDENTE', 'FALTA CARGAR'], default='OK')
        
        # Filtro
        df_m['% Desvio'] = np.where(df_m['Teorico_Calc'] > 0, (df_m['Diff'] / df_m['Teorico_Calc'])*100, 0)
        st.session_state['df_final_m'] = df_m[(df_m['Estado'] != 'OK') & (abs(df_m['% Desvio']) >= tolerancia)].copy()

        # ==========================================
        # CÁLCULO TIEMPOS
        # ==========================================
        t_real = df_real.groupby('KEY')['_Sys_Real'].sum().reset_index()
        t_sap = df_sap_t.groupby('KEY')['_Sys_Sap'].sum().reset_index()
        
        df_t = pd.merge(t_sap, t_real, on='KEY', how='outer').fillna(0)
        df_t['Diff'] = df_t['_Sys_Real'] - df_t['_Sys_Sap']
        
        df_t['Accion'] = np.select(
            [df_t['Diff'] > 0.05, df_t['Diff'] < -0.05],
            ['SUMAR (Falta)', 'RESTAR (Sobra)'], default='OK'
        )
        st.session_state['df_final_t'] = df_t[df_t['Accion'] != 'OK'].sort_values('Diff', ascending=False)

    # 4. RESULTADOS
    if st.session_state.get('calculado', False):
        st.subheader("📊 Resultados")
        df_m_res = st.session_state['df_final_m']
        df_t_res = st.session_state['df_final_t']
        
        tab1, tab2 = st.tabs(["📦 Materiales", "⏱️ Tiempos"])
        
        with tab1:
            col_kpi1, col_kpi2 = st.columns(2)
            col_kpi1.metric("Registros con Desvío", len(df_m_res))
            col_kpi2.metric("Total Excedente (U)", f"{df_m_res[df_m_res['Diff']>0]['Diff'].sum():,.2f}")

            def color_m(val):
                if val == 'EXCEDENTE': return 'background-color: #ffcdd2; color: black'
                if val == 'FALTA CARGAR': return 'background-color: #ffeeb0; color: black'
                return ''
            
            # Usamos los nombres internos para mostrar datos
            cols_show = ['KEY', col_mat_desc, 'Origen', '_Sys_Hecha', 'Teorico_Calc', '_Sys_Tom', 'Estado', 'Diff', '% Desvio']
            
            st.dataframe(
                df_m_res[cols_show].style
                .applymap(color_m, subset=['Estado'])
                .format({
                    '_Sys_Hecha': '{:,.0f}',
                    'Teorico_Calc': '{:,.2f}',
                    '_Sys_Tom': '{:,.2f}',
                    'Diff': '{:+,.2f}',
                    '% Desvio': '{:.1f}%'
                }),
                use_container_width=True,
                height=500
            )
            
            b = io.BytesIO()
            with pd.ExcelWriter(b) as w: df_m_res.to_excel(w, index=False)
            st.download_button("📥 Excel Materiales", b.getvalue(), "Materiales.xlsx")

        with tab2:
            st.metric("Órdenes con Diferencia", len(df_t_res))
            
            def color_t(val):
                if val > 0: return 'background-color: #ffeeb0; color: black'
                if val < 0: return 'background-color: #ffcdd2; color: black'
                return ''
            
            st.dataframe(
                df_t_res.style
                .applymap(color_t, subset=['Diff'])
                .format({
                    '_Sys_Sap': '{:,.2f}',
                    '_Sys_Real': '{:,.2f}',
                    'Diff': '{:+,.2f}'
                }),
                use_container_width=True
            )
            
            b2 = io.BytesIO()
            with pd.ExcelWriter(b2) as w: df_t_res.to_excel(w, index=False)
            st.download_button("📥 Excel Tiempos", b2.getvalue(), "Tiempos.xlsx")

else:
    st.info("👈 Sube los 4 archivos en el menú lateral.")
