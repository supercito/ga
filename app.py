import streamlit as st
import pandas as pd
import io
import numpy as np
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control Producción Final", layout="wide", page_icon="🏭")
st.title("🏭 Dashboard de Control de Producción")
st.markdown("Análisis de desviaciones con indicación exacta de corrección en SAP.")

# --- FUNCIONES DE CARGA Y LIMPIEZA ---
def cargar_excel_simple(file):
    if not file: return None
    try:
        # Detectar automáticamente dónde empieza el encabezado
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
    """Limpieza profunda de la Orden (quita ceros a la izquierda y caracteres extra)"""
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

# --- BARRA LATERAL ---
st.sidebar.header("1. Carga de Archivos")
f_mat = st.sidebar.file_uploader("Materiales (SAP)", type=["xlsx"])
f_prod = st.sidebar.file_uploader("Producción (Excel)", type=["xlsx"])
f_real = st.sidebar.file_uploader("Tiempos Reales", type=["xlsx"])
f_sap_t = st.sidebar.file_uploader("Tiempos SAP", type=["xlsx"])

# --- LÓGICA PRINCIPAL ---
if f_mat and f_prod and f_real and f_sap_t:
    
    # 1. Cargar Archivos
    df_mat = cargar_excel_simple(f_mat)
    df_prod = cargar_excel_simple(f_prod)
    df_real = cargar_excel_simple(f_real)
    df_sap_t = cargar_excel_simple(f_sap_t)

    st.divider()
    st.subheader("🛠️ Mapeo de Columnas")
    st.info("Selecciona la columna correspondiente en cada archivo:")
    
    c1, c2, c3, c4 = st.columns(4)
    
    # -------------------------------------------------------------------------
    # NOTA PARA EL USUARIO:
    # Si quieres cambiar el título que aparece encima del menú (ej: "Orden"),
    # cambia el texto dentro de st.selectbox("TITULO NUEVO", ...)
    # -------------------------------------------------------------------------
    
    with c1:
        st.markdown("**📦 Materiales**")
        col_m_ord = st.selectbox("Columna Orden", df_mat.columns, index=index_col(df_mat, ['orden']), key='mo')
        col_m_nec = st.selectbox("Cant. Necesaria", df_mat.columns, index=index_col(df_mat, ['necesaria']), key='mn')
        col_m_tom = st.selectbox("Cant. Real/Tomada", df_mat.columns, index=index_col(df_mat, ['tomada', 'real']), key='mt')
        col_m_desc = st.selectbox("Desc. Material", df_mat.columns, index=index_col(df_mat, ['texto', 'desc', 'material']), key='md')
        col_m_merma = st.selectbox("Merma/Rechazo %", df_mat.columns, index=index_col(df_mat, ['rech', 'niv', 'merma', '%']), key='m_merm')

    with c2:
        st.markdown("**🏭 Producción**")
        col_p_ord = st.selectbox("Columna Orden", df_prod.columns, index=index_col(df_prod, ['orden']), key='po')
        col_p_hech = st.selectbox("Cajas Reales", df_prod.columns, index=index_col(df_prod, ['buena', 'real', 'confirmada']), key='ph')
        col_p_plan = st.selectbox("Cajas Plan", df_prod.columns, index=index_col(df_prod, ['orden', 'plan']), key='pp')

    with c3:
        st.markdown("**⏱️ Tiempos Real**")
        col_r_ord = st.selectbox("Columna Orden", df_real.columns, index=index_col(df_real, ['orden']), key='ro')
        col_r_val = st.selectbox("Tiempo Máquina", df_real.columns, index=index_col(df_real, ['tiempo', 'maquina']), key='rv')

    with c4:
        st.markdown("**⏱️ Tiempos SAP**")
        col_s_ord = st.selectbox("Columna Orden", df_sap_t.columns, index=index_col(df_sap_t, ['orden']), key='so')
        col_s_val = st.selectbox("Tiempo Notificado", df_sap_t.columns, index=index_col(df_sap_t, ['activ', 'notif']), key='sv')

    st.divider()

    # --- BOTÓN DE PROCESAMIENTO ---
    if st.button("🚀 CALCULAR DESVÍOS", type="primary"):
        
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

        # 3. Agrupar Producción y Tiempos
        prod_g = df_prod.groupby('KEY')[['_Sys_Plan', '_Sys_Hecha']].sum().reset_index()
        t_r = df_real.groupby('KEY')['_Sys_Real'].sum().reset_index()
        t_s = df_sap_t.groupby('KEY')['_Sys_Sap'].sum().reset_index()

        # -------------------------------------------------------
        # CÁLCULO DE MATERIALES
        # -------------------------------------------------------
        df_m = pd.merge(df_mat, prod_g, on='KEY', how='left')
        df_m['_Sys_Plan'] = df_m['_Sys_Plan'].fillna(0)
        df_m['_Sys_Hecha'] = df_m['_Sys_Hecha'].fillna(0)

        # Coeficiente (Material por Caja)
        df_m['Coef'] = np.where(df_m['_Sys_Plan'] > 0, df_m['_Sys_Nec'] / df_m['_Sys_Plan'], 0)
        
        # Consumo Teórico Dinámico (Ajustado a Cajas Reales)
        df_m['Teorico'] = np.where(df_m['_Sys_Plan'] > 0, df_m['Coef'] * df_m['_Sys_Hecha'], df_m['_Sys_Nec'])
        
        # Máximo Permitido (Teórico + Merma del archivo)
        # Asumimos que la merma viene como entero (ej: 3 para 3%). Dividimos por 100.
        df_m['Max_Perm'] = df_m['Teorico'] * (1 + (df_m['_Sys_Merma'] / 100))
        
        # Diferencias
        df_m['Diff_Kg'] = df_m['_Sys_Tom'] - df_m['Max_Perm']
        df_m['Pct_Desvio'] = np.where(df_m['Teorico'] > 0, (df_m['Diff_Kg'] / df_m['Teorico'])*100, 0)
        
        # --- DETERMINACIÓN DE ACCIÓN EXACTA PARA SAP ---
        # Si Tomada > Max_Perm -> EXCEDENTE -> Hay que justificar o anular si fue error
        # Si Tomada < Teorico -> FALTA -> Hay que cargar
        
        condiciones = [
            (df_m['_Sys_Tom'] > df_m['Max_Perm']), # Se pasó
            (df_m['_Sys_Tom'] < df_m['Teorico'] * 0.99) # Falta (usamos 0.99 para evitar ruido decimal)
        ]
        estados = ['EXCEDENTE', 'FALTA CARGAR']
        df_m['Estado'] = np.select(condiciones, estados, default='OK')

        # Cálculo de cantidad a informar
        # Si FALTA: Lo que debí usar (Teorico) - Lo que usé
        # Si SOBRA: Lo que usé - Lo permitido (Max Perm)
        df_m['Cant_Ajuste'] = np.select(
            [df_m['Estado'] == 'FALTA CARGAR', df_m['Estado'] == 'EXCEDENTE'],
            [df_m['Teorico'] - df_m['_Sys_Tom'], df_m['_Sys_Tom'] - df_m['Max_Perm']],
            default=0
        )
        
        # Texto de Acción
        df_m['Accion_SAP'] = np.select(
            [df_m['Estado'] == 'FALTA CARGAR', df_m['Estado'] == 'EXCEDENTE'],
            ['CARGAR', 'ANULAR / JUSTIF.'],
            default='-'
        )

        # -------------------------------------------------------
        # CÁLCULO DE TIEMPOS
        # -------------------------------------------------------
        df_t = pd.merge(t_s, t_r, on='KEY', how='outer').fillna(0)
        df_t['Diff_Hr'] = df_t['_Sys_Real'] - df_t['_Sys_Sap']
        
        df_t['Accion_Hr'] = np.select(
            [df_t['Diff_Hr'] > 0.05, df_t['Diff_Hr'] < -0.05],
            ['CARGAR HORAS', 'ANULAR HORAS'],
            default='OK'
        )

        # GUARDAR RESULTADOS
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
            st.header("🔍 Resultados y Filtros")

            # --- FILTROS ---
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                # 1. Filtro Materiales
                lista_raw = df_m[col_desc].dropna().unique()
                lista_materiales = sorted([str(x) for x in lista_raw])
                excluir = st.multiselect("Ignorar estos materiales:", lista_materiales)
                if excluir: df_m = df_m[~df_m[col_desc].astype(str).isin(excluir)]

            with col_f2:
                # 2. Filtro Rango %
                min_v, max_v = df_m['Pct_Desvio'].min(), df_m['Pct_Desvio'].max()
                if min_v == max_v: min_v -= 1; max_v += 1
                min_v, max_v = float(min_v), float(max_v)
                rango = st.slider("Filtrar por % Desvío:", min_v, max_v, (min_v, max_v))
                df_m = df_m[(df_m['Pct_Desvio'] >= rango[0]) & (df_m['Pct_Desvio'] <= rango[1])]

            # Solo mostramos lo que NO es OK
            df_show_m = df_m[df_m['Estado'] != 'OK'].copy()

            # Renombrar Columnas (Aquí se definen los títulos finales)
            cols_map = {
                'KEY': 'Orden', 
                col_desc: 'Material', 
                '_Sys_Hecha': 'Cajas Prod.', 
                'Teorico': 'Cons. Teórico', 
                '_Sys_Tom': 'Cons. SAP', 
                'Accion_SAP': 'Acción SAP',
                'Cant_Ajuste': 'Cant. Ajuste',
                'Pct_Desvio': '% Desvío'
            }
            
            # Seleccionar y Renombrar
            cols_finales = [c for c in cols_map.keys() if c in df_show_m.columns]
            df_final = df_show_m[cols_finales].rename(columns=cols_map)

            # ORDENAR: Primero por Material, luego por Orden
            if 'Material' in df_final.columns:
                df_final = df_final.sort_values(by=['Material', 'Orden'], ascending=[True, True])

            tab1, tab2 = st.tabs(["📦 Materiales a Corregir", "⏱️ Tiempos a Corregir"])
            
            with tab1:
                st.write(f"**{len(df_final)} registros encontrados.**")
                
                # Función de color condicional
                def style_m(val):
                    if val == 'CARGAR': return 'background-color: #fff4cc; color: black; font-weight: bold' # Amarillo
                    if val == 'ANULAR / JUSTIF.': return 'background-color: #ffcccc; color: black; font-weight: bold' # Rojo
                    return ''
                
                st.dataframe(
                    df_final.style.applymap(style_m, subset=['Acción SAP'])
                    .format({
                        'Cajas Prod.': '{:,.0f}', 
                        'Cons. Teórico': '{:,.2f}', 
                        'Cons. SAP': '{:,.2f}', 
                        'Cant. Ajuste': '{:,.2f}',
                        '% Desvío': '{:.2f}%'
                    }), use_container_width=True, height=600
                )
                
                b = io.BytesIO()
                with pd.ExcelWriter(b) as w: df_final.to_excel(w, index=False)
                st.download_button("📥 Descargar Reporte Materiales", b.getvalue(), "Ajuste_Materiales.xlsx")

            with tab2:
                # Filtrar Tiempos OK
                df_show_t = df_t[df_t['Accion_Hr'] != 'OK'].copy()
                
                cols_t = {
                    'KEY':'Orden', 
                    '_Sys_Sap':'Horas SAP', 
                    '_Sys_Real':'Horas Reales', 
                    'Diff_Hr':'Diferencia',
                    'Accion_Hr': 'Acción'
                }
                df_show_t = df_show_t.rename(columns=cols_t)
                
                def style_t(val):
                    if 'CARGAR' in val: return 'background-color: #fff4cc; color: black'
                    if 'ANULAR' in val: return 'background-color: #ffcccc; color: black'
                    return ''
                
                st.dataframe(
                    df_show_t[list(cols_t.values())].style.applymap(style_t, subset=['Acción'])
                    .format({'Horas SAP':'{:,.2f}', 'Horas Reales':'{:,.2f}', 'Diferencia':'{:+,.2f}'}),
                    use_container_width=True
                )
                
                b2 = io.BytesIO()
                with pd.ExcelWriter(b2) as w: df_show_t.to_excel(w, index=False)
                st.download_button("📥 Descargar Reporte Tiempos", b2.getvalue(), "Ajuste_Tiempos.xlsx")

else:
    st.info("Por favor, carga los 4 archivos para comenzar.")
