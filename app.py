import streamlit as st
import pandas as pd
import io
import numpy as np
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control Producción Final", layout="wide", page_icon="🏭")

# --- ESTILOS CSS (PARA LOGO FIJO Y MEJORAS VISUALES) ---
st.markdown(
    """
    <style>
        /* Hace que la imagen del sidebar se quede fija arriba */
        [data-testid="stSidebar"] [data-testid="stImage"] {
            position: sticky;
            top: 0;
            z-index: 999;
            background-color: #f0f2f6;
            padding-top: 20px;
            padding-bottom: 10px;
        }
        /* Ajuste para que el contenido no quede tapado por el logo */
        [data-testid="stSidebar"] .block-container {
            padding-top: 2rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🏭 Control de Producción")

# --- FUNCIONES DE LIMPIEZA ---
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
    val = str(val).strip()
    if '.' in val: val = val.split('.')[0]
    digits = re.findall(r'\d+', val)
    if digits:
        return str(int("".join(digits)))
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

# --- SIDEBAR (CON LOGO) ---
try:
    # El CSS arriba se encarga de dejarlo fijo
    st.sidebar.image("logo.png", width=200) 
except:
    pass # Si no hay logo, no muestra error, solo sigue

st.sidebar.header("1. Carga de Archivos")

f_mat = st.sidebar.file_uploader("Materiales (SAP)", type=["xlsx"])
f_prod = st.sidebar.file_uploader("Producción (SAP)", type=["xlsx"])
f_real = st.sidebar.file_uploader("Tiempos Reales (P&P)", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("Tiempos SAP", type=["xlsx"])

# --- LÓGICA PRINCIPAL ---
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
        col_m_nec = st.selectbox("Cant. Necesaria", df_mat.columns, index=index_col(df_mat, ['necesaria']), key='mn')
        col_m_tom = st.selectbox("Cant. Real/Tomada", df_mat.columns, index=index_col(df_mat, ['tomada', 'real']), key='mt')
        col_m_desc = st.selectbox("Descripción", df_mat.columns, index=index_col(df_mat, ['texto', 'breve']), key='md')
        col_m_merma = st.selectbox("Merma/Rechazo %", df_mat.columns, index=index_col(df_mat, ['rech', 'niv', 'merma', '%']), key='m_merm')

    with c2:
        st.info("🏭 Producción")
        col_p_ord = st.selectbox("Orden", df_prod.columns, index=index_col(df_prod, ['orden']), key='po')
        col_p_hech = st.selectbox("Cantidad buena confirmada", df_prod.columns, index=index_col(df_prod, ['cantidad buena']), key='ph')
        col_p_plan = st.selectbox("Cantidad orden/plan", df_prod.columns, index=index_col(df_prod, ['cantidad orden']), key='pp')

    with c3:
        st.info("⏱️ Tiempos Real")
        col_r_ord = st.selectbox("Orden", df_real.columns, index=index_col(df_real, ['orden']), key='ro')
        col_r_val = st.selectbox("Tiempo", df_real.columns, index=index_col(df_real, ['tiempo', 'maquina']), key='rv')

    with c4:
        st.info("⏱️ Tiempos SAP")
        col_s_ord = st.selectbox("Orden", df_sap_t.columns, index=index_col(df_sap_t, ['orden']), key='so')
        col_s_val = st.selectbox("Tiempo", df_sap_t.columns, index=index_col(df_sap_t, ['activ', 'notif']), key='sv')

    st.divider()

    if st.button("🚀 CALCULAR DATOS", type="primary"):
        
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

        # 3. Cruce con Producción
        prod_g = df_prod.groupby('KEY')[['_Sys_Plan', '_Sys_Hecha']].sum().reset_index()
        df_m = pd.merge(df_mat, prod_g, on='KEY', how='left')
        df_m['_Sys_Plan'] = df_m['_Sys_Plan'].fillna(0)
        df_m['_Sys_Hecha'] = df_m['_Sys_Hecha'].fillna(0)

        # ----------------------------------------
        # CÁLCULOS MATERIALES
        # ----------------------------------------
        
        # 1. Teórico Dinámico (ajustado a cajas reales)
        df_m['Coef'] = np.where(df_m['_Sys_Plan'] > 0, df_m['_Sys_Nec'] / df_m['_Sys_Plan'], 0)
        df_m['Teorico'] = np.where(df_m['_Sys_Plan'] > 0, df_m['Coef'] * df_m['_Sys_Hecha'], df_m['_Sys_Nec'])
        
        # 2. Merma Permitida (Kilos)
        df_m['Cant_Merma_Kg'] = df_m['Teorico'] * (df_m['_Sys_Merma'] / 100)
        
        # 3. Límite Máximo Permitido
        df_m['Max_Perm'] = df_m['Teorico'] + df_m['Cant_Merma_Kg']
        
        # 4. Diferencias y Estado
        df_m['Diff_Kg'] = df_m['_Sys_Tom'] - df_m['Max_Perm']
        df_m['Pct_Desvio'] = np.where(df_m['Teorico'] > 0, (df_m['Diff_Kg'] / df_m['Teorico'])*100, 0)
        
        conds = [(df_m['_Sys_Tom'] > df_m['Max_Perm']), (df_m['_Sys_Tom'] < df_m['Teorico'] * 0.95)]
        df_m['Estado'] = np.select(conds, ['EXCEDENTE', 'FALTA CARGAR'], default='OK')

        # 5. Cantidad a Ajustar
        df_m['Cant_Ajuste'] = np.select(
            [df_m['Estado'] == 'FALTA CARGAR', df_m['Estado'] == 'EXCEDENTE'],
            [df_m['Teorico'] - df_m['_Sys_Tom'], df_m['_Sys_Tom'] - df_m['Max_Perm']],
            default=0
        )

        # ----------------------------------------
        # CÁLCULOS TIEMPOS
        # ----------------------------------------
        t_r = df_real.groupby('KEY')['_Sys_Real'].sum().reset_index()
        t_s = df_sap_t.groupby('KEY')['_Sys_Sap'].sum().reset_index()
        df_t = pd.merge(t_s, t_r, on='KEY', how='outer').fillna(0)
        df_t['Diff_Hr'] = df_t['_Sys_Real'] - df_t['_Sys_Sap']

        # Guardar en memoria
        st.session_state['data_mat'] = df_m.copy()
        st.session_state['data_time'] = df_t.copy()
        st.session_state['col_desc_name'] = col_m_desc
        st.session_state['processed'] = True

    # --- VISUALIZACIÓN ---
    if st.session_state.get('processed', False):
        df_m = st.session_state.get('data_mat', pd.DataFrame())
        df_t = st.session_state.get('data_time', pd.DataFrame())
        col_desc = st.session_state.get('col_desc_name', 'Material')

        if df_m.empty:
            st.warning("No hay datos.")
        else:
            st.divider()
            st.header("🔍 Resultados")
            
            # FILTROS
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.markdown("##### 1. Filtro Materiales")
                lista_raw = df_m[col_desc].dropna().unique()
                lista_materiales = sorted([str(x) for x in lista_raw])
                excluir = st.multiselect("Ignorar materiales:", lista_materiales)
                if excluir: df_m = df_m[~df_m[col_desc].astype(str).isin(excluir)]

            with col_f2:
                st.markdown("##### 2. Filtros de Desvío (%)")
                # Obtenemos los extremos reales de los datos
                # min_global siempre <= 0, max_global siempre >= 0 para seguridad de sliders
                min_global = min(0.0, float(df_m['Pct_Desvio'].min()))
                max_global = max(0.0, float(df_m['Pct_Desvio'].max()))
                
                # Dividimos en 2 columnas para los sliders
                col_neg, col_pos = st.columns(2)
                
                with col_neg:
                    # Slider Negativo: Desde el mínimo real hasta 0
                    neg_cutoff = st.slider(
                        "Límite Negativo (Falta):",
                        min_value=min_global,
                        max_value=0.0,
                        value=0.0, # Default: muestra todo
                        step=0.1,
                        help="Muestra valores MENORES a este número (más negativos)"
                    )
                
                with col_pos:
                    # Slider Positivo: Desde 0 hasta el máximo real
                    pos_cutoff = st.slider(
                        "Límite Positivo (Exceso):",
                        min_value=0.0,
                        max_value=max_global,
                        value=0.0, # Default: muestra todo
                        step=0.1,
                        help="Muestra valores MAYORES a este número"
                    )
                
                # LÓGICA DE FILTRADO (OR)
                # Queremos ver lo que sea PEOR que el negativo O PEOR que el positivo.
                # Es decir, excluimos el centro cercano a cero.
                df_m = df_m[
                    (df_m['Pct_Desvio'] <= neg_cutoff) | 
                    (df_m['Pct_Desvio'] >= pos_cutoff)
                ]

            # Solo mostrar errores (que no sean OK)
            # Aunque el slider en 0 ya muestra todo, limpiamos los "OK" técnicos si hubiere
            df_show_m = df_m[df_m['Estado'] != 'OK'].copy()

            # --- MAPEO DE COLUMNAS DEFINITIVO ---
            cols_map = {
                'KEY': 'Orden', 
                col_desc: 'Material', 
                '_Sys_Hecha': 'Cajas Prod.', 
                '_Sys_Merma': 'Merma %',             
                'Cant_Merma_Kg': 'Cant. Merma',      
                'Teorico': 'Cons. Teórico', 
                '_Sys_Tom': 'Cons. Real', 
                'Cant_Ajuste': 'Cant. a Ajustar',    
                'Estado': 'Estado'
            }
            
            cols_finales = [c for c in cols_map.keys() if c in df_show_m.columns]
            df_final = df_show_m[cols_finales].rename(columns=cols_map)

            if 'Material' in df_final.columns:
                df_final = df_final.sort_values(by=['Material', 'Orden'], ascending=[True, True])

            tab1, tab2 = st.tabs(["📦 Análisis Materiales", "⏱️ Análisis Tiempos"])
            
            with tab1:
                st.write(f"**{len(df_final)} registros encontrados.**")
                
                def style_m(val):
                    if val == 'EXCEDENTE': return 'background-color: #ffcccc; color: black' # Rojo
                    if val == 'FALTA CARGAR': return 'background-color: #fff4cc; color: black' # Amarillo
                    return ''
                
                st.dataframe(
                    df_final.style.applymap(style_m, subset=['Estado'])
                    .format({
                        'Cajas Prod.': '{:,.0f}', 
                        'Merma %': '{:.1f}%',
                        'Cant. Merma': '{:,.2f}',
                        'Cons. Teórico': '{:,.2f}', 
                        'Cons. Real': '{:,.2f}', 
                        'Cant. a Ajustar': '{:,.2f}'
                    }), use_container_width=True, height=600
                )
                
                b = io.BytesIO()
                with pd.ExcelWriter(b) as w: df_final.to_excel(w, index=False)
                st.download_button("📥 Descargar Tabla Materiales", b.getvalue(), "Materiales.xlsx")

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
                
                b2 = io.BytesIO()
                with pd.ExcelWriter(b2) as w: df_show_t.to_excel(w, index=False)
                st.download_button("📥 Descargar Tabla Tiempos", b2.getvalue(), "Tiempos.xlsx")

else:
    st.info("Carga los archivos para comenzar.")
