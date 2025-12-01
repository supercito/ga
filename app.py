import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control Avanzado SAP", layout="wide", page_icon="🎛️")
st.title("🎛️ Dashboard de Control Avanzado")
st.markdown("Carga archivos -> Mapea columnas -> **Filtra dinámicamente**.")

# --- FUNCIONES ---
def cargar_excel_simple(file):
    if not file: return None
    try:
        df_temp = pd.read_excel(file, header=None, nrows=10)
        max_cols = 0
        header_row = 0
        for i in range(len(df_temp)):
            if df_temp.iloc[i].count() > max_cols:
                max_cols = df_temp.iloc[i].count()
                header_row = i
        df = pd.read_excel(file, header=header_row)
        df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
        return df
    except: return None

def clean_key(val): return str(val).split('.')[0].strip()

def clean_num(val):
    if isinstance(val, (int, float)): return val
    if isinstance(val, str):
        val = val.upper().strip()
        for u in ['KG', 'CJ', 'HRA', 'HR', 'UN', 'M', 'L', '%']: val = val.replace(u, '')
        val = val.strip().replace('.', '').replace(',', '.')
        try: return float(val)
        except: return 0.0
    return 0.0

def index_col(df, keywords):
    cols = [str(c).lower() for c in df.columns]
    for i, col in enumerate(cols):
        if any(k in col for k in keywords): return i
    return 0

# --- SIDEBAR: CARGA ---
st.sidebar.header("1. Carga de Archivos")
f_mat = st.sidebar.file_uploader("Materiales", type=["xlsx"])
f_prod = st.sidebar.file_uploader("Producción", type=["xlsx"])
f_real = st.sidebar.file_uploader("Tiempos Reales", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("Tiempos SAP", type=["xlsx"])

st.sidebar.divider()
st.sidebar.header("2. Configuración Global")
merma = st.sidebar.number_input("Merma Permitida (%)", 0.0, 20.0, 3.0, 0.1) / 100

# --- LÓGICA PRINCIPAL ---
if f_mat and f_prod and f_real and f_sap_t:
    
    # CARGA
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
        col_m_desc = st.selectbox("Material/Desc", df_mat.columns, index=index_col(df_mat, ['texto', 'desc', 'material']), key='md')

    with c2:
        st.info("🏭 Producción")
        col_p_ord = st.selectbox("Orden", df_prod.columns, index=index_col(df_prod, ['orden']), key='po')
        col_p_hech = st.selectbox("Cajas Reales", df_prod.columns, index=index_col(df_prod, ['buena', 'real']), key='ph')
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

    # BOTÓN PROCESAR
    if st.button("🔄 PROCESAR DATOS", type="primary"):
        # Limpieza Keys
        df_mat['KEY'] = df_mat[col_m_ord].apply(clean_key)
        df_prod['KEY'] = df_prod[col_p_ord].apply(clean_key)
        df_real['KEY'] = df_real[col_r_ord].apply(clean_key)
        df_sap_t['KEY'] = df_sap_t[col_s_ord].apply(clean_key)

        # Limpieza Valores
        df_mat['_Sys_Nec'] = df_mat[col_m_nec].apply(clean_num)
        df_mat['_Sys_Tom'] = df_mat[col_m_tom].apply(clean_num)
        df_prod['_Sys_Hecha'] = df_prod[col_p_hech].apply(clean_num)
        df_prod['_Sys_Plan'] = df_prod[col_p_plan].apply(clean_num)
        df_real['_Sys_Real'] = df_real[col_r_val].apply(clean_num)
        df_sap_t['_Sys_Sap'] = df_sap_t[col_s_val].apply(clean_num)

        # --- CÁLCULO MATERIALES ---
        prod_g = df_prod.groupby('KEY')[['_Sys_Plan', '_Sys_Hecha']].sum().reset_index()
        df_m = pd.merge(df_mat, prod_g, on='KEY', how='left')
        
        df_m['_Sys_Plan'] = df_m['_Sys_Plan'].fillna(0)
        df_m['_Sys_Hecha'] = df_m['_Sys_Hecha'].fillna(0)
        
        # Lógica Dinámica
        df_m['Coef'] = np.where(df_m['_Sys_Plan'] > 0, df_m['_Sys_Nec'] / df_m['_Sys_Plan'], 0)
        df_m['Teorico'] = np.where(df_m['_Sys_Plan'] > 0, df_m['Coef'] * df_m['_Sys_Hecha'], df_m['_Sys_Nec'])
        
        df_m['Max_Perm'] = df_m['Teorico'] * (1 + merma)
        df_m['Diff_Kg'] = df_m['_Sys_Tom'] - df_m['Max_Perm']
        
        # Porcentaje de Desvío REAL
        df_m['Pct_Desvio'] = np.where(df_m['Teorico'] > 0, (df_m['Diff_Kg'] / df_m['Teorico'])*100, 0)
        
        # Estados
        conds = [(df_m['_Sys_Tom'] > df_m['Max_Perm']), (df_m['_Sys_Tom'] < df_m['Teorico'] * 0.95)]
        df_m['Estado'] = np.select(conds, ['EXCEDENTE', 'FALTA CARGAR'], default='OK')

        # Guardar en session state
        st.session_state['data_mat'] = df_m
        st.session_state['col_desc_name'] = col_m_desc

        # --- CÁLCULO TIEMPOS ---
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

        st.divider()
        st.header("🔍 Filtros y Resultados")
        
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            st.markdown("##### 1. Filtro de Materiales")
            # Lista de materiales limpia (convertir a str para evitar errores)
            lista_raw = df_m[col_desc].dropna().unique()
            lista_materiales = sorted([str(x) for x in lista_raw])
            excluir = st.multiselect("Ignorar materiales:", lista_materiales)
            
            if excluir:
                df_m = df_m[~df_m[col_desc].astype(str).isin(excluir)]

        with col_f2:
            st.markdown("##### 2. Rango de Desvío (%)")
            if not df_m.empty:
                min_val = float(df_m['Pct_Desvio'].min())
                max_val = float(df_m['Pct_Desvio'].max())
                
                # Evitar error si min y max son iguales
                if min_val == max_val:
                    min_val -= 1.0
                    max_val += 1.0

                rango = st.slider(
                    "Filtrar por %:",
                    min_value=min_val,
                    max_value=max_val,
                    value=(min_val, max_val),
                    step=0.1
                )
                df_m = df_m[(df_m['Pct_Desvio'] >= rango[0]) & (df_m['Pct_Desvio'] <= rango[1])]

        df_final_m = df_m[df_m['Estado'] != 'OK'].copy()
        
        # Renombrar Materiales
        rename_map = {
            'KEY': 'Orden',
            col_desc: 'Material / Descripción',
            '_Sys_Hecha': 'Cajas Producidas',
            'Teorico': 'Consumo Teórico (Kg)',
            '_Sys_Tom': 'Consumo Real (Kg)',
            'Diff_Kg': 'Diferencia (Kg)',
            'Pct_Desvio': '% Desvío',
            'Estado': 'Estado'
        }
        cols_finales = list(rename_map.keys())
        df_show_m = df_final_m[cols_finales].rename(columns=rename_map)

        tab1, tab2 = st.tabs(["📦 Análisis Materiales", "⏱️ Análisis Tiempos"])
        
        with tab1:
            st.markdown(f"**Registros mostrados:** {len(df_show_m)}")
            
            def style_m(val):
                if val == 'EXCEDENTE': return 'background-color: #ffcccc; color: black'
                if val == 'FALTA CARGAR': return 'background-color: #fff4cc; color: black'
                return ''

            st.dataframe(
                df_show_m.style
                .applymap(style_m, subset=['Estado'])
                .format({
                    'Cajas Producidas': '{:,.0f}',
                    'Consumo Teórico (Kg)': '{:,.2f}',
                    'Consumo Real (Kg)': '{:,.2f}',
                    'Diferencia (Kg)': '{:+,.2f}',
                    '% Desvío': '{:.2f}%'
                }),
                use_container_width=True,
                height=600
            )
            
            b = io.BytesIO()
            with pd.ExcelWriter(b) as w: df_show_m.to_excel(w, index=False)
            st.download_button("📥 Excel Materiales", b.getvalue(), "Reporte_Materiales.xlsx")

        with tab2:
            ver_todo = st.checkbox("Ver coincidencias exactas (Diferencia 0)", value=False)
            
            df_final_t = df_t.copy()
            if not ver_todo:
                df_final_t = df_final_t[abs(df_final_t['Diff_Hr']) > 0.01]
            
            rename_t = {
                'KEY': 'Orden',
                '_Sys_Sap': 'Horas SAP',
                '_Sys_Real': 'Horas Reales',
                'Diff_Hr': 'Diferencia (Hs)'
            }
            df_show_t = df_final_t[list(rename_t.keys())].rename(columns=rename_t)
            
            def style_t(val):
                if val > 0: return 'background-color: #fff4cc; color: black' # Falta
                if val < 0: return 'background-color: #ffcccc; color: black' # Sobra
                return ''

            # CORRECCIÓN AQUÍ: Usamos un diccionario para aplicar formato SOLO a las columnas numéricas
            st.dataframe(
                df_show_t.style
                .applymap(style_t, subset=['Diferencia (Hs)'])
                .format({
                    'Horas SAP': '{:,.2f}',
                    'Horas Reales': '{:,.2f}',
                    'Diferencia (Hs)': '{:+,.2f}'
                }),
                use_container_width=True
            )
            
            b2 = io.BytesIO()
            with pd.ExcelWriter(b2) as w: df_show_t.to_excel(w, index=False)
            st.download_button("📥 Excel Tiempos", b2.getvalue(), "Reporte_Tiempos.xlsx")

else:
    st.info("Carga los archivos para comenzar.")
