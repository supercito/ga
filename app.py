import streamlit as st
import pandas as pd
import io
import numpy as np
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control Producción Final", layout="wide", page_icon="🏭")
st.title("🏭 Dashboard de Control: Merma Dinámica")
st.markdown("Ahora la merma se lee directamente del archivo de materiales.")

# --- FUNCIONES ROBUSTAS ---
def cargar_excel_simple(file):
    if not file: return None
    try:
        df_temp = pd.read_excel(file, header=None, nrows=15)
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
    except: return None

def clean_key(val):
    """LIMPIEZA NUCLEAR DE LLAVES"""
    val = str(val).strip()
    if '.' in val: val = val.split('.')[0]
    digits = re.findall(r'\d+', val)
    if digits:
        num_limpio = "".join(digits)
        return str(int(num_limpio))
    return val.upper()

def clean_num(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.upper().strip()
        for u in ['KG', 'CJ', 'HRA', 'HR', 'UN', 'M', 'L', '%', ' ']: 
            val = val.replace(u, '')
        if '.' in val and ',' in val: val = val.replace('.', '').replace(',', '.')
        elif ',' in val: val = val.replace(',', '.')
        try: return float(val)
        except: return 0.0
    return 0.0

def index_col(df, keywords):
    cols = [str(c).lower() for c in df.columns]
    for i, col in enumerate(cols):
        if any(k in col for k in keywords): return i
    return 0

# --- SIDEBAR ---
st.sidebar.header("1. Carga de Archivos")
f_mat = st.sidebar.file_uploader("Materiales", type=["xlsx"])
f_prod = st.sidebar.file_uploader("Producción", type=["xlsx"])
f_real = st.sidebar.file_uploader("Tiempos Reales", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("Tiempos SAP", type=["xlsx"])

# --- LÓGICA ---
if f_mat and f_prod and f_real and f_sap_t:
    
    df_mat = cargar_excel_simple(f_mat)
    df_prod = cargar_excel_simple(f_prod)
    df_real = cargar_excel_simple(f_real)
    df_sap_t = cargar_excel_simple(f_sap_t)

    st.divider()
    st.subheader("🛠️ Mapeo de Columnas")
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.info("📦 Materiales")
        col_m_ord = st.selectbox("Orden", df_mat.columns, index=index_col(df_mat, ['orden']), key='mo')
        col_m_nec = st.selectbox("Necesaria", df_mat.columns, index=index_col(df_mat, ['necesaria']), key='mn')
        col_m_tom = st.selectbox("Real/Tomada", df_mat.columns, index=index_col(df_mat, ['tomada', 'real']), key='mt')
        col_m_desc = st.selectbox("Descripción", df_mat.columns, index=index_col(df_mat, ['texto', 'desc', 'material']), key='md')
        col_m_merma = st.selectbox("Merma/Rechazo %", df_mat.columns, index=index_col(df_mat, ['rech', 'niv', 'merma', '%']), key='m_merm')

    with c2:
        st.info("🏭 Producción")
        col_p_ord = st.selectbox("Orden", df_prod.columns, index=index_col(df_prod, ['orden']), key='po')
        col_p_hech = st.selectbox("Cajas Reales", df_prod.columns, index=index_col(df_prod, ['buena', 'real', 'confirmada']), key='ph')
        col_p_plan = st.selectbox("Cajas Plan", df_prod.columns, index=index_col(df_prod, ['orden', 'plan']), key='pp')

    with c3:
        st.info("⏱️ Tiempos Real")
        col_r_ord = st.selectbox("Orden", df_real.columns, index=index_col(df_real, ['orden']), key='ro')
        col_r_val = st.selectbox("Tiempo", df_real.columns, index=index_col(df_real, ['tiempo', 'maquina']), key='rv')

    with c4:
        st.info("⏱️ Tiempos SAP")
        col_s_ord = st.selectbox("Orden", df_sap_t.columns, index=index_col(df_sap_t, ['orden']), key='so')
        col_s_val = st.selectbox("Tiempo", df_sap_t.columns, index=index_col(df_sap_t, ['activ', 'notif']), key='sv')

    st.divider()

    if st.button("🔄 PROCESAR INFORMACIÓN", type="primary"):
        # 1. Limpieza de LLAVES
        df_mat['KEY'] = df_mat[col_m_ord].apply(clean_key)
        df_prod['KEY'] = df_prod[col_p_ord].apply(clean_key)
        df_real['KEY'] = df_real[col_r_ord].apply(clean_key)
        df_sap_t['KEY'] = df_sap_t[col_s_ord].apply(clean_key)

        # 2. Limpieza de VALORES
        df_mat['_Sys_Nec'] = df_mat[col_m_nec].apply(clean_num)
        df_mat['_Sys_Tom'] = df_mat[col_m_tom].apply(clean_num)
        df_mat['_Sys_Merma'] = df_mat[col_m_merma].apply(clean_num)
        
        df_prod['_Sys_Hecha'] = df_prod[col_p_hech].apply(clean_num)
        df_prod['_Sys_Plan'] = df_prod[col_p_plan].apply(clean_num)
        df_real['_Sys_Real'] = df_real[col_r_val].apply(clean_num)
        df_sap_t['_Sys_Sap'] = df_sap_t[col_s_val].apply(clean_num)

        # 3. Agrupar Producción
        prod_g = df_prod.groupby('KEY')[['_Sys_Plan', '_Sys_Hecha']].sum().reset_index()

        # 4. Cruce
        df_m = pd.merge(df_mat, prod_g, on='KEY', how='left')
        df_m['_Sys_Plan'] = df_m['_Sys_Plan'].fillna(0)
        df_m['_Sys_Hecha'] = df_m['_Sys_Hecha'].fillna(0)

        # 5. Cálculos
        df_m['Coef'] = np.where(df_m['_Sys_Plan'] > 0, df_m['_Sys_Nec'] / df_m['_Sys_Plan'], 0)
        df_m['Teorico'] = np.where(df_m['_Sys_Plan'] > 0, df_m['Coef'] * df_m['_Sys_Hecha'], df_m['_Sys_Nec'])
        
        # Merma Dinámica (Asumiendo que viene como 3 para 3%, dividimos por 100)
        df_m['Max_Perm'] = df_m['Teorico'] * (1 + (df_m['_Sys_Merma'] / 100))
        
        df_m['Diff_Kg'] = df_m['_Sys_Tom'] - df_m['Max_Perm']
        df_m['Pct_Desvio'] = np.where(df_m['Teorico'] > 0, (df_m['Diff_Kg'] / df_m['Teorico'])*100, 0)
        
        conds = [(df_m['_Sys_Tom'] > df_m['Max_Perm']), (df_m['_Sys_Tom'] < df_m['Teorico'] * 0.95)]
        df_m['Estado'] = np.select(conds, ['EXCEDENTE', 'FALTA CARGAR'], default='OK')

        # GUARDAR EN SESSION STATE (Incluyendo las tablas para debug)
        st.session_state['data_mat'] = df_m
        st.session_state['debug_mat'] = df_mat # Guardamos la tabla con columnas limpias
        st.session_state['debug_prod'] = df_prod # Guardamos la tabla con columnas limpias
        
        st.session_state['col_desc_name'] = col_m_desc
        
        # Tiempos
        t_r = df_real.groupby('KEY')['_Sys_Real'].sum().reset_index()
        t_s = df_sap_t.groupby('KEY')['_Sys_Sap'].sum().reset_index()
        df_t = pd.merge(t_s, t_r, on='KEY', how='outer').fillna(0)
        df_t['Diff_Hr'] = df_t['_Sys_Real'] - df_t['_Sys_Sap']
        st.session_state['data_time'] = df_t
        st.session_state['processed'] = True

    # --- VISUALIZACIÓN ---
    if st.session_state.get('processed', False):
        df_m = st.session_state['data_mat']
        df_t = st.session_state['data_time']
        
        # Recuperamos las tablas de debug desde la memoria para evitar el KeyError
        debug_prod = st.session_state.get('debug_prod', pd.DataFrame())
        debug_mat = st.session_state.get('debug_mat', pd.DataFrame())
        
        col_desc = st.session_state['col_desc_name']

        # FILTROS
        st.divider()
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            lista_raw = df_m[col_desc].dropna().unique()
            lista_materiales = sorted([str(x) for x in lista_raw])
            excluir = st.multiselect("Ignorar materiales:", lista_materiales)
            if excluir: df_m = df_m[~df_m[col_desc].astype(str).isin(excluir)]

        with col_f2:
            min_v, max_v = df_m['Pct_Desvio'].min(), df_m['Pct_Desvio'].max()
            if min_v == max_v: min_v -= 1; max_v += 1
            rango = st.slider("Rango Desvío %:", float(min_v), float(max_v), (float(min_v), float(max_v)))
            df_m = df_m[(df_m['Pct_Desvio'] >= rango[0]) & (df_m['Pct_Desvio'] <= rango[1])]

        df_show_m = df_m[df_m['Estado'] != 'OK'].copy()

        cols_map = {
            'KEY': 'Orden', col_desc: 'Material', 
            '_Sys_Hecha': 'Cajas Prod.', '_Sys_Merma': 'Merma Std %',
            'Teorico': 'Cons. Teórico', 
            '_Sys_Tom': 'Cons. Real', 'Diff_Kg': 'Diferencia (Kg)', 
            'Pct_Desvio': '% Desvío', 'Estado': 'Estado'
        }
        
        cols_finales = [c for c in cols_map.keys() if c in df_show_m.columns]
        df_final = df_show_m[cols_finales].rename(columns=cols_map)

        tab1, tab2, tab3 = st.tabs(["📦 Materiales", "⏱️ Tiempos", "🕵️ Diagnóstico"])
        
        with tab1:
            st.markdown(f"**Registros:** {len(df_final)}")
            def style_m(val):
                if val == 'EXCEDENTE': return 'background-color: #ffcccc; color: black'
                if val == 'FALTA CARGAR': return 'background-color: #fff4cc; color: black'
                return ''
            
            st.dataframe(
                df_final.style.applymap(style_m, subset=['Estado'])
                .format({
                    'Cajas Prod.': '{:,.0f}', 'Cons. Teórico': '{:,.2f}', 'Merma Std %': '{:,.1f}',
                    'Cons. Real': '{:,.2f}', 'Diferencia (Kg)': '{:+,.2f}',
                    '% Desvío': '{:.2f}%'
                }), use_container_width=True, height=600
            )
            b = io.BytesIO()
            with pd.ExcelWriter(b) as w: df_final.to_excel(w, index=False)
            st.download_button("📥 Excel Materiales", b.getvalue(), "Reporte_Mat.xlsx")

        with tab2:
            df_show_t = df_t[abs(df_t['Diff_Hr']) > 0.05].copy()
            cols_t = {'KEY':'Orden', '_Sys_Sap':'Horas SAP', '_Sys_Real':'Horas Reales', 'Diff_Hr':'Diferencia'}
            df_show_t = df_show_t.rename(columns=cols_t)
            
            def style_t(val):
                return 'background-color: #fff4cc; color: black' if val > 0 else 'background-color: #ffcccc; color: black'
            
            st.dataframe(
                df_show_t[list(cols_t.values())].style.applymap(style_t, subset=['Diferencia'])
                .format({'Horas SAP':'{:,.2f}', 'Horas Reales':'{:,.2f}', 'Diferencia':'{:+,.2f}'}),
                use_container_width=True
            )

        with tab3:
            st.write("### 🕵️ Diagnóstico de Cruce de Datos")
            check_order = st.text_input("Buscar Orden (ej: 202467):")
            
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                st.write("**Archivo Producción (Limpio):**")
                # Aquí usamos la tabla recuperada de memoria
                if check_order:
                    st.dataframe(debug_prod[debug_prod['KEY'].str.contains(check_order)][['KEY', '_Sys_Hecha']])
                else:
                    st.dataframe(debug_prod[['KEY', '_Sys_Hecha']].head())

            with c_d2:
                st.write("**Archivo Materiales (Limpio):**")
                if check_order:
                    st.dataframe(debug_mat[debug_mat['KEY'].str.contains(check_order)][['KEY', '_Sys_Nec']])
                else:
                    st.dataframe(debug_mat[['KEY', '_Sys_Nec']].head())

else:
    st.info("Carga archivos para empezar.")
