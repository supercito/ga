import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control Producción Final", layout="wide", page_icon="🏭")
st.title("🏭 Dashboard de Control de Producción")
st.markdown("Si ves ceros donde no debería, revisa la pestaña **'🕵️ Diagnóstico'** al final.")

# --- FUNCIONES ROBUSTAS ---
def cargar_excel_simple(file):
    if not file: return None
    try:
        # Detectar encabezado automáticamente
        df_temp = pd.read_excel(file, header=None, nrows=15)
        max_cols = 0
        header_row = 0
        for i in range(len(df_temp)):
            non_na = df_temp.iloc[i].count()
            if non_na > max_cols:
                max_cols = non_na
                header_row = i
        
        # Cargar dataframe real
        df = pd.read_excel(file, header=header_row)
        # Convertir columnas a string y limpiar espacios del nombre
        df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
        return df
    except: return None

def clean_key(val):
    """
    Limpieza agresiva de la Orden para asegurar el cruce.
    Ej: '000202467.0 ' -> '202467'
    """
    val = str(val).strip()     # Quitar espacios
    val = val.split('.')[0]    # Quitar decimales (.0)
    val = val.lstrip('0')      # Quitar ceros a la izquierda (Clave para SAP)
    return val

def clean_num(val):
    """Convierte texto 1.000,00 o 1,000.00 a float"""
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.upper().strip()
        # Eliminar unidades de medida
        for u in ['KG', 'CJ', 'HRA', 'HR', 'UN', 'M', 'L', '%', ' ']: 
            val = val.replace(u, '')
        
        # Detectar formato: 
        # Si tiene punto y coma, asumimos formato europeo 1.000,00
        if '.' in val and ',' in val:
            val = val.replace('.', '').replace(',', '.')
        # Si solo tiene coma y son decimales (ej 50,5) -> 50.5
        elif ',' in val and '.' not in val:
            val = val.replace(',', '.')
        # Si solo tiene puntos (ej 1.000) asumimos miles -> 1000
        elif val.count('.') == 1 and len(val.split('.')[1]) == 3:
             val = val.replace('.', '')
             
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

st.sidebar.divider()
merma = st.sidebar.number_input("Merma (%)", 0.0, 20.0, 3.0, 0.1) / 100

# --- LÓGICA ---
if f_mat and f_prod and f_real and f_sap_t:
    
    df_mat = cargar_excel_simple(f_mat)
    df_prod = cargar_excel_simple(f_prod)
    df_real = cargar_excel_simple(f_real)
    df_sap_t = cargar_excel_simple(f_sap_t)

    st.subheader("🛠️ Mapeo de Columnas")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.info("📦 Materiales")
        col_m_ord = st.selectbox("Orden", df_mat.columns, index=index_col(df_mat, ['orden']), key='mo')
        col_m_nec = st.selectbox("Necesaria", df_mat.columns, index=index_col(df_mat, ['necesaria']), key='mn')
        col_m_tom = st.selectbox("Real/Tomada", df_mat.columns, index=index_col(df_mat, ['tomada', 'real']), key='mt')
        col_m_desc = st.selectbox("Descripción", df_mat.columns, index=index_col(df_mat, ['texto', 'desc', 'material']), key='md')

    with c2:
        st.info("🏭 Producción")
        col_p_ord = st.selectbox("Orden", df_prod.columns, index=index_col(df_prod, ['orden']), key='po')
        # ¡IMPORTANTE! Asegúrate de elegir la columna de "Confirmada" o "Real"
        col_p_hech = st.selectbox("Cajas Reales (Hechas)", df_prod.columns, index=index_col(df_prod, ['buena', 'real', 'confirmada']), key='ph')
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
        # 1. Limpieza de LLAVES (Crucial para que cruce el 202467)
        df_mat['KEY'] = df_mat[col_m_ord].apply(clean_key)
        df_prod['KEY'] = df_prod[col_p_ord].apply(clean_key)
        df_real['KEY'] = df_real[col_r_ord].apply(clean_key)
        df_sap_t['KEY'] = df_sap_t[col_s_ord].apply(clean_key)

        # 2. Limpieza de VALORES
        df_mat['_Sys_Nec'] = df_mat[col_m_nec].apply(clean_num)
        df_mat['_Sys_Tom'] = df_mat[col_m_tom].apply(clean_num)
        df_prod['_Sys_Hecha'] = df_prod[col_p_hech].apply(clean_num) # Aquí lee las 4928 cajas
        df_prod['_Sys_Plan'] = df_prod[col_p_plan].apply(clean_num)
        df_real['_Sys_Real'] = df_real[col_r_val].apply(clean_num)
        df_sap_t['_Sys_Sap'] = df_sap_t[col_s_val].apply(clean_num)

        # 3. Agrupar Producción (Para tener 1 sola fila por orden)
        prod_g = df_prod.groupby('KEY')[['_Sys_Plan', '_Sys_Hecha']].sum().reset_index()

        # 4. Cruce (Merge)
        df_m = pd.merge(df_mat, prod_g, on='KEY', how='left')
        
        # Diagnóstico interno: Marcar origen
        df_m['_Origen'] = np.where(df_m['_Sys_Plan'].notna(), 'Cruce OK', 'No Cruzó')
        
        # Llenar ceros
        df_m['_Sys_Plan'] = df_m['_Sys_Plan'].fillna(0)
        df_m['_Sys_Hecha'] = df_m['_Sys_Hecha'].fillna(0)
        
        # 5. Cálculos
        df_m['Coef'] = np.where(df_m['_Sys_Plan'] > 0, df_m['_Sys_Nec'] / df_m['_Sys_Plan'], 0)
        df_m['Teorico'] = np.where(df_m['_Sys_Plan'] > 0, df_m['Coef'] * df_m['_Sys_Hecha'], df_m['_Sys_Nec'])
        df_m['Max_Perm'] = df_m['Teorico'] * (1 + merma)
        df_m['Diff_Kg'] = df_m['_Sys_Tom'] - df_m['Max_Perm']
        df_m['Pct_Desvio'] = np.where(df_m['Teorico'] > 0, (df_m['Diff_Kg'] / df_m['Teorico'])*100, 0)
        
        conds = [(df_m['_Sys_Tom'] > df_m['Max_Perm']), (df_m['_Sys_Tom'] < df_m['Teorico'] * 0.95)]
        df_m['Estado'] = np.select(conds, ['EXCEDENTE', 'FALTA CARGAR'], default='OK')

        # Guardar en session
        st.session_state['data_mat'] = df_m
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
            rango = st.slider("Rango Desvío %:", min_v, max_v, (min_v, max_v))
            df_m = df_m[(df_m['Pct_Desvio'] >= rango[0]) & (df_m['Pct_Desvio'] <= rango[1])]

        df_show_m = df_m[df_m['Estado'] != 'OK'].copy()

        # Renombrar
        cols_map = {
            'KEY': 'Orden', col_desc: 'Material', 
            '_Sys_Hecha': 'Cajas Producidas', 'Teorico': 'Consumo Teórico', 
            '_Sys_Tom': 'Consumo Real', 'Diff_Kg': 'Diferencia (Kg)', 
            'Pct_Desvio': '% Desvío', 'Estado': 'Estado', '_Origen': 'Info Cruce'
        }
        df_final = df_show_m[list(cols_map.keys())].rename(columns=cols_map)

        tab1, tab2, tab3 = st.tabs(["📦 Materiales", "⏱️ Tiempos", "🕵️ Diagnóstico de Cruce"])
        
        with tab1:
            st.markdown(f"**Registros:** {len(df_final)}")
            def style_m(val):
                if val == 'EXCEDENTE': return 'background-color: #ffcccc; color: black'
                if val == 'FALTA CARGAR': return 'background-color: #fff4cc; color: black'
                return ''
            
            st.dataframe(
                df_final.style.applymap(style_m, subset=['Estado'])
                .format({
                    'Cajas Producidas': '{:,.0f}', 'Consumo Teórico': '{:,.2f}',
                    'Consumo Real': '{:,.2f}', 'Diferencia (Kg)': '{:+,.2f}',
                    '% Desvío': '{:.2f}%'
                }), use_container_width=True, height=500
            )
            b = io.BytesIO()
            with pd.ExcelWriter(b) as w: df_final.to_excel(w, index=False)
            st.download_button("📥 Excel Materiales", b.getvalue(), "Reporte_Mat.xlsx")

        with tab2:
            ver_ok = st.checkbox("Ver diferencias 0")
            if not ver_ok: df_t = df_t[abs(df_t['Diff_Hr']) > 0.05]
            
            cols_t = {'KEY':'Orden', '_Sys_Sap':'Horas SAP', '_Sys_Real':'Horas Reales', 'Diff_Hr':'Diferencia'}
            df_show_t = df_t[list(cols_t.keys())].rename(columns=cols_t)
            
            def style_t(val):
                if val > 0: return 'background-color: #fff4cc; color: black'
                if val < 0: return 'background-color: #ffcccc; color: black'
                return ''
            
            st.dataframe(
                df_show_t.style.applymap(style_t, subset=['Diferencia'])
                .format({'Horas SAP':'{:,.2f}', 'Horas Reales':'{:,.2f}', 'Diferencia':'{:+,.2f}'}),
                use_container_width=True
            )

        with tab3:
            st.write("### 🕵️ ¿Por qué veo ceros?")
            st.write("Verifica aquí si la Orden 202467 aparece en ambos lados con el mismo formato.")
            
            check_order = st.text_input("Buscar Orden Específica (ej: 202467):")
            
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                st.write("**En Archivo Producción:**")
                st.dataframe(df_prod[['KEY', col_p_hech, '_Sys_Hecha']].head())
                if check_order:
                    st.write(f"Buscando '{check_order}' en Producción:")
                    st.dataframe(df_prod[df_prod['KEY'].str.contains(check_order)])
            
            with c_d2:
                st.write("**En Archivo Materiales:**")
                st.dataframe(df_mat[['KEY']].drop_duplicates().head())
                if check_order:
                    st.write(f"Buscando '{check_order}' en Materiales:")
                    st.dataframe(df_mat[df_mat['KEY'].str.contains(check_order)][['KEY', col_m_nec]].head())

else:
    st.info("Carga archivos para empezar.")
