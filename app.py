import streamlit as st
import pandas as pd
import io
import numpy as np

st.set_page_config(page_title="Dashboard Robustez Total", layout="wide", page_icon="🛡️")
st.title("🛡️ Dashboard de Control: Modo Diagnóstico")
st.markdown("Este modo asegura que **siempre** veas datos. Si falta la producción, usa el estándar de SAP.")

# --- FUNCIONES DE LIMPIEZA ---
def clean_key(val):
    """Limpia la llave para asegurar cruces (quita ceros izq, espacios, puntos)"""
    val = str(val).split('.')[0].strip()
    return val

def clean_num(val):
    if isinstance(val, (int, float)): return val
    if isinstance(val, str):
        val = val.upper().strip().replace('KG','').replace('CJ','').replace('HRA','').strip()
        val = val.replace('.', '').replace(',', '.')
        try: return float(val)
        except: return 0.0
    return 0.0

def load_excel_smart(file, keywords):
    if not file: return None
    try:
        df = pd.read_excel(file, header=None)
        # Buscar header en primeras 20 filas
        for i in range(min(20, len(df))):
            row_str = " ".join(df.iloc[i].astype(str).str.lower())
            if any(k in row_str for k in keywords):
                df.columns = df.iloc[i]
                df = df.iloc[i+1:].reset_index(drop=True)
                df.columns = df.columns.astype(str).str.strip().str.replace('\n', ' ')
                return df
        return df # Si falla, devuelve tal cual
    except: return None

def find_col(df, options):
    for col in df.columns:
        if any(opt in col.lower() for opt in options): return col
    return None

# --- SIDEBAR ---
st.sidebar.header("Configuración")
merma = st.sidebar.number_input("Merma (%)", 0.0, 20.0, 3.0) / 100
# Pongo el default en 0.0 para que NO oculte nada por defecto
tolerancia = st.sidebar.slider("Filtro Tolerancia (%)", 0.0, 50.0, 0.0, help="Déjalo en 0 para ver todos los desvíos")

f_mat = st.sidebar.file_uploader("1. Materiales", type=["xlsx"])
f_prod = st.sidebar.file_uploader("2. Producción", type=["xlsx"])
f_real = st.sidebar.file_uploader("3. Tiempos Real", type=["xlsx"])
f_sap = st.sidebar.file_uploader("4. Tiempos SAP", type=["xlsx"])

# --- LÓGICA PRINCIPAL ---
if f_mat and f_prod and f_real and f_sap:
    
    # CARGA
    df_mat = load_excel_smart(f_mat, ['necesaria', 'material'])
    df_prod = load_excel_smart(f_prod, ['cantidad buena', 'orden'])
    df_real = load_excel_smart(f_real, ['tiempo', 'sector'])
    df_sap = load_excel_smart(f_sap, ['activ.1', 'notificada'])

    # LLAVES
    c_k_mat = find_col(df_mat, ['orden'])
    c_k_prod = find_col(df_prod, ['orden'])
    c_k_real = find_col(df_real, ['orden'])
    c_k_sap = find_col(df_sap, ['orden'])

    if not (c_k_mat and c_k_prod and c_k_real and c_k_sap):
        st.error("Error: No se encontró columna 'Orden' en alguno de los archivos.")
        st.stop()

    df_mat['KEY'] = df_mat[c_k_mat].apply(clean_key)
    df_prod['KEY'] = df_prod[c_k_prod].apply(clean_key)
    df_real['KEY'] = df_real[c_k_real].apply(clean_key)
    df_sap['KEY'] = df_sap[c_k_sap].apply(clean_key)

    # ----------------------------------------------------
    # 📦 ANÁLISIS MATERIALES (CON FALLBACK)
    # ----------------------------------------------------
    c_nec = find_col(df_mat, ['necesaria'])
    c_tom = find_col(df_mat, ['tomada', 'real'])
    c_plan = find_col(df_prod, ['cantidad orden', 'plan'])
    c_hecha = find_col(df_prod, ['buena', 'real', 'producida'])

    df_mat['Nec'] = df_mat[c_nec].apply(clean_num)
    df_mat['Tom'] = df_mat[c_tom].apply(clean_num)
    df_prod['Plan'] = df_prod[c_plan].apply(clean_num)
    df_prod['Hecha'] = df_prod[c_hecha].apply(clean_num)

    # Agrupar producción
    prod_master = df_prod.groupby('KEY')[['Plan', 'Hecha']].sum().reset_index()

    # CRUCE LEFT (Mantener todos los materiales sí o sí)
    df_m = pd.merge(df_mat, prod_master, on='KEY', how='left')

    # --- LÓGICA DE RECETA DINÁMICA CON SEGURIDAD ---
    # Paso 1: Determinar si tenemos datos de producción válidos
    df_m['Tiene_Prod'] = df_m['Plan'].notna() & (df_m['Plan'] > 0)
    
    # Rellenar nulos para que no falle la matemática
    df_m['Plan'].fillna(0, inplace=True)
    df_m['Hecha'].fillna(0, inplace=True)

    # Paso 2: Calcular
    # Coeficiente Técnico
    df_m['Coef'] = np.where(df_m['Plan'] > 0, df_m['Nec'] / df_m['Plan'], 0)
    
    # Teorico Ajustado (Si hay prod, usamos Coef * Hecha. Si no, usamos Nec original)
    df_m['Teorico_Final'] = np.where(
        df_m['Tiene_Prod'], 
        df_m['Coef'] * df_m['Hecha'], 
        df_m['Nec'] # Fallback a SAP estándar
    )

    # Etiqueta de Origen para que sepas qué pasó
    df_m['Origen_Datos'] = np.where(
        df_m['Tiene_Prod'],
        "Ajustado x Producción",
        "⚠️ Sin Cruce (SAP Orig)"
    )

    # Paso 3: Calcular Desvío y Estado
    df_m['Max_Permitido'] = df_m['Teorico_Final'] * (1 + merma)
    df_m['Diff'] = df_m['Tom'] - df_m['Max_Permitido']

    # Filtro %
    df_m['% Desvio'] = np.where(df_m['Teorico_Final'] > 0, (df_m['Diff'] / df_m['Teorico_Final'])*100, 0)

    # Estados
    conds = [
        (df_m['Tom'] > df_m['Max_Permitido']),
        (df_m['Tom'] < df_m['Teorico_Final'] * 0.95)
    ]
    df_m['Estado'] = np.select(conds, ['EXCEDENTE', 'FALTA CARGAR'], default='OK')

    # FILTRO FINAL
    df_view_mat = df_m[
        (df_m['Estado'] != 'OK') & 
        (abs(df_m['% Desvio']) >= tolerancia)
    ].copy()

    # ----------------------------------------------------
    # ⏱️ ANÁLISIS TIEMPOS
    # ----------------------------------------------------
    c_t_real = find_col(df_real, ['tiempo de máquina', 'machine'])
    c_t_sap = find_col(df_sap, ['activ.1', 'notificada'])
    
    if c_t_real and c_t_sap:
        df_real['V_Real'] = df_real[c_t_real].apply(clean_num)
        df_sap['V_Sap'] = df_sap[c_t_sap].apply(clean_num)
        
        gr = df_real.groupby('KEY')['V_Real'].sum().reset_index()
        gs = df_sap.groupby('KEY')['V_Sap'].sum().reset_index()
        
        df_t = pd.merge(gs, gr, on='KEY', how='outer').fillna(0)
        df_t['Diff'] = df_t['V_Real'] - df_t['V_Sap']
        df_t['Accion'] = np.select(
            [df_t['Diff'] > 0.05, df_t['Diff'] < -0.05],
            ['SUMAR', 'RESTAR'], default='OK'
        )
        df_view_t = df_t[df_t['Accion'] != 'OK'].sort_values('Diff', ascending=False)
    else:
        df_view_t = pd.DataFrame()

    # ----------------------------------------------------
    # VISUALIZACIÓN
    # ----------------------------------------------------
    tab1, tab2 = st.tabs(["📦 MATERIALES", "⏱️ TIEMPOS"])

    with tab1:
        c1, c2 = st.columns(2)
        c1.metric("Desvíos Detectados", len(df_view_mat))
        
        # Muestra rápida de por qué no cruzaba
        sin_cruce = len(df_m[df_m['Origen_Datos'].str.contains("Sin Cruce")])
        if sin_cruce > 0:
            st.warning(f"⚠️ Atención: {sin_cruce} materiales no encontraron su orden en el archivo de Producción (se usó el estándar SAP).")

        # Columnas a mostrar
        cols = ['KEY', 'Origen_Datos', 'Hecha', 'Teorico_Final', 'Tom', 'Estado', 'Diff', '% Desvio']
        # Agregar descripción si existe
        c_desc = find_col(df_mat, ['texto', 'descrip'])
        if c_desc: cols.insert(1, c_desc)

        def color_mat(val):
            if val == 'EXCEDENTE': return 'background-color: #ffcdd2; color: black'
            if val == 'FALTA CARGAR': return 'background-color: #ffeeb0; color: black'
            return ''

        st.dataframe(
            df_view_mat[cols].style.applymap(color_mat, subset=['Estado'])
            .format({'Hecha':'{:,.0f}', 'Teorico_Final':'{:.2f}', 'Tom':'{:.2f}', 'Diff':'{:.2f}', '% Desvio':'{:.1f}%'}),
            use_container_width=True
        )

    with tab2:
        if not df_view_t.empty:
            st.dataframe(
                df_view_t.style.format({'V_Sap':'{:.2f}', 'V_Real':'{:.2f}', 'Diff':'{:.2f}'}),
                use_container_width=True
            )
        else:
            st.info("No hay desvíos de tiempos.")

else:
    st.info("Sube los 4 archivos.")
