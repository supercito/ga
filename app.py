import streamlit as st
import pandas as pd
import io
import numpy as np

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard Diagnóstico", layout="wide", page_icon="🔧")
st.title("🔧 Dashboard con Diagnóstico de Errores")
st.markdown("Si no ves datos, abre la sección **'🕵️ Ver Datos Cargados'** abajo para ver qué está fallando.")

# --- FUNCIONES DE LIMPIEZA ---
def limpiar_texto(df):
    """Limpia espacios en nombres de columnas y valores string"""
    df.columns = df.columns.astype(str).str.strip()
    # Intentar limpiar filas vacias al inicio si el header falló
    return df

def encontrar_fila_encabezado(df, keywords):
    # Buscamos en las primeras 20 filas
    for i in range(min(20, len(df))):
        fila = df.iloc[i].astype(str).str.lower().tolist()
        texto = " ".join(fila)
        if any(k in texto for k in keywords):
            df.columns = df.iloc[i] # Asignar header
            df = df.iloc[i+1:].reset_index(drop=True) # Datos
            return df, i
    return df, 0

def cargar_excel(file, keywords, name):
    if not file: return None
    try:
        df = pd.read_excel(file, header=None)
        df, fila = encontrar_fila_encabezado(df, keywords)
        df = limpiar_texto(df)
        return df, fila
    except Exception as e:
        st.error(f"Error cargando {name}: {e}")
        return None, 0

def clean_num(val):
    if isinstance(val, (int, float)): return val
    if isinstance(val, str):
        val = val.strip().replace('KG','').replace('CJ','').replace('.','').replace(',','.')
        try: return float(val)
        except: return 0.0
    return 0.0

# --- SIDEBAR ---
st.sidebar.header("Configuración")
merma = st.sidebar.number_input("Merma %", 0.0, 20.0, 3.0) / 100
filtro = st.sidebar.slider("Filtro Visual %", 0.0, 50.0, 0.0, 0.5) # DEFAULT EN 0 PARA VER TODO

st.sidebar.info("Carga los archivos:")
f_mat = st.sidebar.file_uploader("1. Materiales", type=["xlsx"])
f_prod = st.sidebar.file_uploader("2. Producción", type=["xlsx"])
f_real = st.sidebar.file_uploader("3. Tiempos Real", type=["xlsx"])
f_sap = st.sidebar.file_uploader("4. Tiempos SAP", type=["xlsx"])

# --- LÓGICA ---
if f_mat and f_prod and f_real and f_sap:
    
    # 1. CARGA
    df_mat, r1 = cargar_excel(f_mat, ['necesaria', 'texto breve', 'material'], "Materiales")
    df_prod, r2 = cargar_excel(f_prod, ['cantidad buena', 'cantidad orden'], "Producción")
    df_real, r3 = cargar_excel(f_real, ['tiempo de máquina', 'sector'], "Tiempos Real")
    df_sap, r4 = cargar_excel(f_sap, ['activ.1', 'recursos'], "Tiempos SAP")

    # 2. SECCIÓN DE DIAGNÓSTICO (EXPANDER)
    with st.expander("🕵️ Ver Datos Cargados (Debug) - CLIC AQUÍ SI NO VES DATOS", expanded=False):
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.write(f"**Materiales:** Filas: {len(df_mat)}. Header detectado en fila: {r1}")
            st.write("Columnas:", list(df_mat.columns))
            st.dataframe(df_mat.head(3), use_container_width=True)
            
        with col_d2:
            st.write(f"**Producción:** Filas: {len(df_prod)}. Header detectado en fila: {r2}")
            st.write("Columnas:", list(df_prod.columns))
            st.dataframe(df_prod.head(3), use_container_width=True)

    # 3. IDENTIFICAR Y LIMPIAR ORDEN
    def get_col_orden(df):
        for c in df.columns:
            if 'orden' in c.lower(): return c
        return None

    c_ord_mat = get_col_orden(df_mat)
    c_ord_prod = get_col_orden(df_prod)

    if not c_ord_mat or not c_ord_prod:
        st.error(f"❌ Error Crítico: No encontré la columna 'Orden'. (Mat: {c_ord_mat}, Prod: {c_ord_prod})")
        st.stop()

    # Convertir a String PURO para asegurar cruce
    df_mat['KEY'] = df_mat[c_ord_mat].astype(str).str.split('.').str[0].str.strip()
    df_prod['KEY'] = df_prod[c_ord_prod].astype(str).str.split('.').str[0].str.strip()

    # Debug de Keys
    with st.expander("🔑 Verificación de Cruce de Llaves (Orden)"):
        st.write("Ejemplo Llaves Materiales:", df_mat['KEY'].unique()[:5])
        st.write("Ejemplo Llaves Producción:", df_prod['KEY'].unique()[:5])
        
        # Verificar coincidencia
        coincidencias = len(set(df_mat['KEY']).intersection(set(df_prod['KEY'])))
        st.info(f"Se encontraron **{coincidencias}** órdenes que coinciden entre ambos archivos.")
        if coincidencias == 0:
            st.error("⚠️ NO HAY COINCIDENCIAS. Revisa si un archivo tiene ceros a la izquierda y el otro no.")
            st.stop()

    # 4. LIMPIEZA NUMÉRICA
    # Buscar columnas dinámicamente
    def find_col(df, keys):
        for c in df.columns:
            if any(k in c.lower() for k in keys): return c
        return None

    # Materiales
    c_necesaria = find_col(df_mat, ['necesaria'])
    c_tomada = find_col(df_mat, ['tomada', 'real'])
    
    # Producción
    c_plan = find_col(df_prod, ['cantidad orden', 'plan'])
    c_hecha = find_col(df_prod, ['buena', 'real', 'producida'])

    if not (c_necesaria and c_tomada and c_plan and c_hecha):
        st.error("Faltan columnas numéricas clave (Necesaria, Tomada, Plan o Real). Revisa el Debug.")
        st.stop()

    df_mat['Nec'] = df_mat[c_necesaria].apply(clean_num)
    df_mat['Tom'] = df_mat[c_tomada].apply(clean_num)
    df_prod['Plan'] = df_prod[c_plan].apply(clean_num)
    df_prod['Hecha'] = df_prod[c_hecha].apply(clean_num)

    # 5. CÁLCULOS
    # Agrupar producción
    prod_grouped = df_prod.groupby('KEY')[['Plan', 'Hecha']].sum().reset_index()

    # Merge
    df_final = pd.merge(df_mat, prod_grouped, on='KEY', how='inner') # Inner para ver solo lo que cruza

    if len(df_final) == 0:
        st.warning("El cruce generó 0 filas. Revisa el Expander de Llaves.")
        st.stop()

    # Recalculo Dinámico
    # Evitar división por cero
    df_final['Coef'] = np.where(df_final['Plan'] > 0, df_final['Nec'] / df_final['Plan'], 0)
    df_final['Teorico_Real'] = df_final['Coef'] * df_final['Hecha']
    df_final['Max_Permitido'] = df_final['Teorico_Real'] * (1 + merma)
    
    # Desvíos
    df_final['Diferencia'] = df_final['Tom'] - df_final['Max_Permitido']
    
    # ESTADOS
    conds = [
        (df_final['Tom'] > df_final['Max_Permitido']),
        (df_final['Tom'] < df_final['Teorico_Real'] * 0.95) # Tolerancia hacia abajo
    ]
    vals = ['EXCEDENTE', 'FALTA CARGAR']
    df_final['Estado'] = np.select(conds, vals, default='OK')

    # 6. MOSTRAR TABLA
    st.subheader(f"Resultados ({len(df_final)} registros procesados)")
    
    # Filtro visual
    df_view = df_final[df_final['Estado'] != 'OK'].copy()
    
    # Si el filtro borra todo, avisar
    if len(df_view) == 0:
        st.success("✅ ¡Todo está perfecto! No hay desvíos según la configuración actual.")
        st.write("Prueba bajando el filtro de tolerancia a 0 en el menú lateral para ver todos los datos.")
    else:
        # Definir columnas para mostrar
        c_mat_txt = find_col(df_final, ['texto', 'descrip'])
        cols = ['KEY', c_mat_txt, 'Hecha', 'Nec', 'Teorico_Real', 'Tom', 'Estado', 'Diferencia']
        cols = [c for c in cols if c] # Eliminar Nones
        
        def color_row(row):
            if row['Estado'] == 'EXCEDENTE': return ['background-color: #ffcccc'] * len(row)
            if row['Estado'] == 'FALTA CARGAR': return ['background-color: #ffeeb0'] * len(row)
            return [''] * len(row)

        st.dataframe(df_view[cols].style.apply(color_row, axis=1), use_container_width=True)

else:
    st.info("Sube los 4 archivos para empezar.")
